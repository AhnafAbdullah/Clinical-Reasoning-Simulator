"""OpenRouter provider adapter — the single MVP ``LLMProvider`` (Vol 4A §15, ADR-0002).

OpenRouter exposes an OpenAI-compatible Chat Completions API and already routes
across the major vendors behind one endpoint, so we implement the provider port
exactly once. The API key lives server-side only (Vol 4A §24).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings, get_settings
from app.domain.ai import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    StreamChunk,
)
from app.domain.errors import ProviderError

# Rough fallback pricing (USD per 1M tokens) used only when a model is known.
# OpenRouter is the source of truth at runtime; this is a best-effort estimate
# for the metrics layer and is intentionally conservative/configurable.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # model: (prompt_usd_per_mtok, completion_usd_per_mtok)
    "openai/gpt-4o": (2.5, 10.0),
    "openai/gpt-4o-mini": (0.15, 0.6),
}


def _to_payload(request: LLMRequest, *, stream: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": request.model,
        "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
        "temperature": request.temperature,
        "stream": stream,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    return payload


def _usage_from(data: dict) -> LLMUsage:
    usage = data.get("usage") or {}
    return LLMUsage(
        prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage.get("completion_tokens", 0) or 0),
    )


class OpenRouterProvider:
    """Implements ``app.domain.ai.LLMProvider``."""

    name = "openrouter"

    def __init__(
        self, settings: Settings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _http(self) -> httpx.AsyncClient:
        """One shared client for the provider's lifetime: connection + TLS reuse
        across turns instead of a fresh handshake per LLM call."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        if not self._settings.openrouter_api_key:
            raise ProviderError("CRS_OPENROUTER_API_KEY is not configured.")
        return {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "HTTP-Referer": self._settings.openrouter_app_url,
            "X-Title": self._settings.openrouter_app_title,
            "Content-Type": "application/json",
        }

    @property
    def _url(self) -> str:
        return f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            resp = await self._http().post(
                self._url, headers=self._headers(), json=_to_payload(request, stream=False)
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenRouter request failed: {exc}") from exc

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Malformed OpenRouter response: {exc}") from exc

        return LLMResponse(
            text=text,
            model=data.get("model", request.model),
            usage=_usage_from(data),
            finish_reason=finish_reason,
            raw=data,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        try:
            async with self._http().stream(
                "POST",
                self._url,
                headers=self._headers(),
                json=_to_payload(request, stream=True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    chunk = self._parse_sse_line(line)
                    if chunk is not None:
                        yield chunk
                        if chunk.done:
                            return
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenRouter stream failed: {exc}") from exc

    @staticmethod
    def _parse_sse_line(line: str) -> StreamChunk | None:
        line = line.strip()
        if not line or not line.startswith("data:"):
            return None
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return StreamChunk(done=True)
        try:
            payload = json.loads(data)
            choice = payload["choices"][0]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None
        delta = (choice.get("delta") or {}).get("content") or ""
        finish_reason = choice.get("finish_reason")
        usage = _usage_from(payload) if payload.get("usage") else None
        return StreamChunk(
            delta=delta,
            done=bool(finish_reason),
            usage=usage,
            finish_reason=finish_reason,
        )

    async def health_check(self) -> bool:
        if not self._settings.openrouter_api_key:
            return False
        try:
            resp = await self._http().get(
                f"{self._settings.openrouter_base_url.rstrip('/')}/models",
                headers=self._headers(),
                timeout=10.0,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def estimate_cost(self, request: LLMRequest, usage: LLMUsage) -> float:
        prices = _PRICE_PER_MTOK.get(request.model)
        if prices is None:
            return 0.0
        prompt_price, completion_price = prices
        return round(
            (usage.prompt_tokens / 1_000_000) * prompt_price
            + (usage.completion_tokens / 1_000_000) * completion_price,
            6,
        )


def get_provider() -> OpenRouterProvider:
    return OpenRouterProvider()


# Re-export for callers building requests.
__all__ = ["OpenRouterProvider", "get_provider", "ChatMessage"]
