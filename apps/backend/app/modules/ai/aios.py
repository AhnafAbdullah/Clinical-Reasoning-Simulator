"""AI Operating System — the single entry point for all AI operations (Vol 4A §4-7).

Every AI request follows the same pipeline; no step may be skipped:

    agent select -> context build -> memory inject -> prompt render ->
    model route -> generate (with retry) -> validate -> audit -> result

The application asks for an agent capability and supplies variables; it never
selects prompts or models, never talks to a provider directly, and never sees an
unvalidated response.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from app.core.config import Settings, get_settings
from app.domain.ai import (
    AIInteraction,
    AIResult,
    ChatMessage,
    LLMProvider,
    LLMRequest,
    RenderedPrompt,
)
from app.domain.errors import ResponseValidationError
from app.infrastructure.ai.registry import PromptRegistry, get_registry
from app.infrastructure.ai.renderer import PromptRenderer

from .agents import AgentSpec, get_agent_specs
from .audit import AuditSink, LoggingAuditSink
from .context_builder import ContextBuilder
from .memory import MemoryManager
from .model_router import ModelRouter
from .retry import RetryManager
from .validator import ResponseValidator


class AIOS:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        registry: PromptRegistry | None = None,
        settings: Settings | None = None,
        audit_sink: AuditSink | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider
        self.registry = registry or get_registry()
        self.renderer = PromptRenderer(self.registry)
        self.context_builder = ContextBuilder()
        self.memory = MemoryManager()
        self.router = ModelRouter(self.settings)
        self.validator = ResponseValidator()
        self.retry = RetryManager(self.settings)
        self.audit = audit_sink or LoggingAuditSink()
        self._agents = get_agent_specs(self.settings)

    def agent_spec(self, agent: str) -> AgentSpec:
        try:
            return self._agents[agent]
        except KeyError as exc:
            raise KeyError(f"Unknown agent {agent!r}.") from exc

    def prepare(
        self,
        agent: str,
        variables: dict[str, Any],
        *,
        case: dict[str, Any] | None = None,
        history: Sequence[ChatMessage] = (),
        current_user_message: str | None = None,
        extracted_facts: Sequence[str] = (),
    ) -> tuple[RenderedPrompt, list[str]]:
        """Run the deterministic part of the pipeline (no model call): build
        context + memory and render the prompt with boundaries enforced.

        Returns the rendered prompt and the response leak terms (so the caller
        can screen the eventual response too)."""
        spec = self.agent_spec(agent)
        template = self.registry.get(spec.prompt_id)

        built = self.context_builder.build(case or {}, template, extra=dict(variables))
        bundle = self.memory.build(
            template.memory_layers,
            history=history,
            current_user_message=current_user_message,
            extracted_facts=extracted_facts,
        )
        render_vars = {**built.variables, **bundle.variables}
        rendered = self.renderer.render(
            spec.prompt_id,
            render_vars,
            forbidden_values=built.forbidden_values,
            messages_tail=bundle.messages_tail,
        )
        return rendered, built.leak_terms

    async def run(
        self,
        agent: str,
        variables: dict[str, Any],
        *,
        case: dict[str, Any] | None = None,
        history: Sequence[ChatMessage] = (),
        current_user_message: str | None = None,
        extracted_facts: Sequence[str] = (),
        session_id: str | None = None,
        user_id: str | None = None,
        message_id: str | None = None,
    ) -> AIResult:
        spec = self.agent_spec(agent)
        template = self.registry.get(spec.prompt_id)
        rendered, leak_terms = self.prepare(
            agent,
            variables,
            case=case,
            history=history,
            current_user_message=current_user_message,
            extracted_facts=extracted_facts,
        )

        models = self.router.fallbacks(template.profile)
        leak_terms_t = tuple(leak_terms)
        started = time.perf_counter()
        last_usage = {"prompt": 0, "completion": 0}
        chosen_model = {"name": models[0]}

        async def attempt(model: str) -> str:
            chosen_model["name"] = model
            request = LLMRequest(
                model=model,
                messages=rendered.messages,
                temperature=spec.temperature,
                max_tokens=self.settings.llm_max_tokens,
                metadata={"agent": agent, "session_id": session_id, "message_id": message_id},
            )
            response = await self.provider.generate(request)
            last_usage["prompt"] = response.usage.prompt_tokens
            last_usage["completion"] = response.usage.completion_tokens
            result = self.validator.validate(response.text, rendered, forbidden_values=leak_terms_t)
            if not result.ok:
                raise ResponseValidationError(result.reason)
            return response.text

        try:
            text, retry_count = await self.retry.run(models, attempt)
            validation_status = "ok"
        except Exception:
            self._audit(
                spec,
                rendered,
                chosen_model["name"],
                last_usage,
                started,
                self.settings.llm_max_retries,
                "failed",
                session_id,
                user_id,
                message_id,
            )
            raise

        interaction = self._audit(
            spec,
            rendered,
            chosen_model["name"],
            last_usage,
            started,
            retry_count,
            validation_status,
            session_id,
            user_id,
            message_id,
        )
        return AIResult(text=text, interaction=interaction)

    def _audit(
        self,
        spec: AgentSpec,
        rendered: RenderedPrompt,
        model: str,
        usage: dict[str, int],
        started: float,
        retry_count: int,
        validation_status: str,
        session_id: str | None,
        user_id: str | None,
        message_id: str | None,
    ) -> AIInteraction:
        from app.domain.ai import LLMRequest as _Req
        from app.domain.ai import LLMUsage as _Usage

        usage_obj = _Usage(usage["prompt"], usage["completion"])
        cost = self.provider.estimate_cost(_Req(model=model, messages=rendered.messages), usage_obj)
        interaction = AIInteraction(
            agent=spec.name,
            prompt_id=rendered.prompt_id,
            prompt_version=rendered.prompt_version,
            profile=self.registry.get(spec.prompt_id).profile,
            model=model,
            provider=self.provider.name,
            prompt_tokens=usage["prompt"],
            completion_tokens=usage["completion"],
            latency_ms=int((time.perf_counter() - started) * 1000),
            retry_count=retry_count,
            validation_status=validation_status,
            estimated_cost=cost,
            session_id=session_id,
            user_id=user_id,
            message_id=message_id,
        )
        self.audit.record(interaction)
        return interaction
