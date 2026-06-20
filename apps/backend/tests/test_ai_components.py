"""Model Router, Validator, and Retry Manager unit tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.domain.ai import ModelProfile, RenderedPrompt
from app.domain.errors import GenerationExhaustedError, ProviderError
from app.modules.ai.model_router import ModelRouter
from app.modules.ai.retry import RetryManager
from app.modules.ai.validator import ResponseValidator


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


# ── Model Router ────────────────────────────────────────────────────────────────


def test_router_resolves_profiles() -> None:
    router = ModelRouter(_settings(model_latency="a/fast", model_reasoning="b/smart"))
    assert router.select(ModelProfile.LATENCY) == "a/fast"
    assert router.select("reasoning") == "b/smart"


def test_router_fallbacks_are_ordered_and_unique() -> None:
    router = ModelRouter(_settings(model_default="d", model_latency="d", model_reasoning="r"))
    fb = router.fallbacks("latency")
    assert fb[0] == "d"
    assert "r" in fb
    assert len(fb) == len(set(fb))


# ── Validator ───────────────────────────────────────────────────────────────────

_TEXT = RenderedPrompt("patient", 1, [], output_type="plain_text", max_words=120)
_JSON = RenderedPrompt("examiner", 1, [], output_type="json", output_schema="x")


def test_validator_rejects_empty() -> None:
    assert ResponseValidator().validate("   ", _TEXT).ok is False


def test_validator_rejects_forbidden_content() -> None:
    res = ResponseValidator().validate(
        "You clearly have a STEMI.", _TEXT, forbidden_values=("STEMI",)
    )
    assert res.ok is False
    assert "forbidden" in res.reason


def test_validator_rejects_leak_pattern() -> None:
    assert ResponseValidator().validate("As an AI language model, I...", _TEXT).ok is False


def test_validator_accepts_clean_text() -> None:
    assert ResponseValidator().validate("The pain began two hours ago.", _TEXT).ok is True


def test_validator_parses_json_contract() -> None:
    res = ResponseValidator().validate('```json\n{"items": []}\n```', _JSON)
    assert res.ok is True
    assert res.parsed == {"items": []}


def test_validator_rejects_bad_json() -> None:
    assert ResponseValidator().validate("not json", _JSON).ok is False


# ── Retry Manager ───────────────────────────────────────────────────────────────


async def test_retry_succeeds_after_transient_failures() -> None:
    rm = RetryManager(_settings(llm_max_retries=3, llm_backoff_base_seconds=0.0))
    attempts: list[str] = []

    async def attempt(model: str) -> str:
        attempts.append(model)
        if len(attempts) < 2:
            raise ProviderError("boom")
        return "ok"

    result, retry_count = await rm.run(["m1", "m2"], attempt)
    assert result == "ok"
    assert retry_count == 1
    # Escalated to the alternate model on the retry.
    assert attempts == ["m1", "m2"]


async def test_retry_exhausts_and_raises() -> None:
    rm = RetryManager(_settings(llm_max_retries=2, llm_backoff_base_seconds=0.0))

    async def always_fail(model: str) -> str:
        raise ProviderError("down")

    with pytest.raises(GenerationExhaustedError):
        await rm.run(["m1"], always_fail)
