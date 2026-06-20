"""OpenRouter adapter: payload mapping, SSE parsing, cost, and config guards.

Live calls require CRS_OPENROUTER_API_KEY and are skipped otherwise.
"""

from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.domain.ai import ChatMessage, ChatRole, LLMProvider, LLMRequest, LLMUsage
from app.domain.errors import ProviderError
from app.infrastructure.ai.openrouter import OpenRouterProvider, _to_payload


def test_satisfies_provider_port() -> None:
    assert isinstance(OpenRouterProvider(), LLMProvider)


def test_payload_maps_messages_and_params() -> None:
    request = LLMRequest(
        model="x/y",
        messages=[ChatMessage(ChatRole.SYSTEM, "sys"), ChatMessage(ChatRole.USER, "hi")],
        temperature=0.3,
        max_tokens=64,
    )
    payload = _to_payload(request, stream=True)
    assert payload["model"] == "x/y"
    assert payload["stream"] is True
    assert payload["max_tokens"] == 64
    assert payload["messages"][0] == {"role": "system", "content": "sys"}


def test_parse_sse_token_and_done() -> None:
    chunk = OpenRouterProvider._parse_sse_line('data: {"choices":[{"delta":{"content":"Hi"}}]}')
    assert chunk is not None and chunk.delta == "Hi" and chunk.done is False
    assert OpenRouterProvider._parse_sse_line("data: [DONE]").done is True
    # Comment/keepalive lines are ignored.
    assert OpenRouterProvider._parse_sse_line(": keepalive") is None


def test_estimate_cost_known_model() -> None:
    provider = OpenRouterProvider()
    cost = provider.estimate_cost(
        LLMRequest(model="openai/gpt-4o-mini", messages=[]),
        LLMUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000),
    )
    assert cost == pytest.approx(0.15 + 0.6)


def test_estimate_cost_unknown_model_is_zero() -> None:
    provider = OpenRouterProvider()
    cost = provider.estimate_cost(LLMRequest(model="unknown/model", messages=[]), LLMUsage(10, 10))
    assert cost == 0.0


async def test_missing_key_raises() -> None:
    provider = OpenRouterProvider(Settings(_env_file=None, openrouter_api_key=""))  # type: ignore[call-arg]
    with pytest.raises(ProviderError):
        await provider.generate(LLMRequest(model="x/y", messages=[]))


async def test_health_check_false_without_key() -> None:
    provider = OpenRouterProvider(Settings(_env_file=None, openrouter_api_key=""))  # type: ignore[call-arg]
    assert await provider.health_check() is False


@pytest.mark.skipif(
    not os.getenv("CRS_OPENROUTER_API_KEY"),
    reason="set CRS_OPENROUTER_API_KEY to run live OpenRouter smoke test",
)
async def test_live_generate_smoke() -> None:
    provider = OpenRouterProvider()
    response = await provider.generate(
        LLMRequest(
            model=Settings().model_latency,  # type: ignore[call-arg]
            messages=[ChatMessage(ChatRole.USER, "Reply with the single word: pong")],
            max_tokens=8,
        )
    )
    assert response.text
