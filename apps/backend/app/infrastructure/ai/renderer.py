"""Prompt Renderer: the only component that turns a template into a finished
prompt (Vol 4A §12, Vol 4B §11).

Pipeline:
    load template -> render Jinja2 body (StrictUndefined, includes) ->
    assert knowledge boundaries (forbidden context absent) -> build messages.

The boundary assertion is the single most important safety property of the
patient prompt: forbidden case content is rejected *before* the model is called,
not by asking the model to behave (Vol 4B §9).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2 import TemplateError as Jinja2TemplateError

from app.domain.ai import ChatMessage, ChatRole, RenderedPrompt
from app.domain.errors import KnowledgeBoundaryError, PromptRenderError

from .registry import PromptRegistry, PromptTemplate, get_registry

# Forbidden string fragments shorter than this are ignored when scanning the
# rendered prompt, to avoid spurious matches on common short words.
_MIN_FORBIDDEN_LEN = 4


class PromptRenderer:
    def __init__(self, registry: PromptRegistry) -> None:
        self.registry = registry
        self.env = Environment(
            loader=FileSystemLoader(str(registry.root)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

    def render(
        self,
        prompt_id: str,
        variables: dict[str, object],
        *,
        version: int | None = None,
        forbidden_values: Iterable[str] = (),
        messages_tail: Sequence[ChatMessage] = (),
    ) -> RenderedPrompt:
        template = self.registry.get(prompt_id, version)
        system_text = self._render_body(template, variables)

        tail = list(messages_tail)
        self._assert_boundaries(template, system_text, tail, forbidden_values)

        messages = [ChatMessage(role=ChatRole.SYSTEM, content=system_text), *tail]
        contract = template.output_contract
        return RenderedPrompt(
            prompt_id=template.id,
            prompt_version=template.version,
            messages=messages,
            output_type=str(contract.get("type", "plain_text")),
            output_schema=contract.get("schema"),
            max_words=contract.get("max_words"),
        )

    def _render_body(self, template: PromptTemplate, variables: dict[str, object]) -> str:
        try:
            jinja_template = self.env.from_string(template.body)
            return jinja_template.render(**variables).strip()
        except Jinja2TemplateError as exc:
            raise PromptRenderError(
                f"Failed to render {template.id} v{template.version}: {exc}"
            ) from exc

    def _assert_boundaries(
        self,
        template: PromptTemplate,
        system_text: str,
        tail: Sequence[ChatMessage],
        forbidden_values: Iterable[str],
    ) -> None:
        haystack = "\n".join([system_text, *(m.content for m in tail)]).lower()
        for value in forbidden_values:
            needle = str(value).strip().lower()
            if len(needle) >= _MIN_FORBIDDEN_LEN and needle in haystack:
                raise KnowledgeBoundaryError(
                    f"Forbidden context leaked into rendered prompt "
                    f"{template.id} v{template.version}."
                )


def get_renderer() -> PromptRenderer:
    return PromptRenderer(get_registry())
