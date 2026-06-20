"""AIOS end-to-end: the full pipeline with a fake provider."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.domain.errors import GenerationExhaustedError
from app.modules.ai.aios import AIOS
from app.modules.ai.audit import CapturingAuditSink


def _settings() -> Settings:
    # No backoff sleeps in tests.
    return Settings(_env_file=None, llm_backoff_base_seconds=0.0)  # type: ignore[call-arg]


def _patient_run(provider, sink, **kw):
    aios = AIOS(provider, settings=_settings(), audit_sink=sink)
    return aios.run(
        "patient",
        {"current_stage": "HISTORY"},
        current_user_message="When did the pain start?",
        session_id="s1",
        user_id="u1",
        message_id="m1",
        **kw,
    )


async def test_run_produces_validated_result_and_audit(fake_provider_cls, sample_case) -> None:
    sink = CapturingAuditSink()
    provider = fake_provider_cls(text="It started about two hours ago while watching TV.")
    result = await _patient_run(provider, sink, case=sample_case)

    assert "two hours" in result.text
    # Every interaction is audited with reproducibility provenance (Vol 4A §20).
    assert len(sink.interactions) == 1
    interaction = result.interaction
    assert interaction.agent == "patient"
    assert interaction.prompt_id == "patient"
    assert interaction.prompt_version == 1
    assert interaction.provider == "fake"
    assert interaction.model  # a concrete model was routed
    assert interaction.validation_status == "ok"
    assert interaction.retry_count == 0
    assert interaction.prompt_tokens > 0


async def test_run_retries_transient_failure(fake_provider_cls, sample_case) -> None:
    sink = CapturingAuditSink()
    provider = fake_provider_cls(text="The pain is central.", fail_times=1)
    result = await _patient_run(provider, sink, case=sample_case)
    assert result.interaction.retry_count == 1
    assert result.text == "The pain is central."


async def test_run_rejects_leaked_diagnosis(fake_provider_cls, sample_case) -> None:
    sink = CapturingAuditSink()
    provider = fake_provider_cls(text="You are clearly having a STEMI, a heart attack.")
    with pytest.raises(GenerationExhaustedError):
        await _patient_run(provider, sink, case=sample_case)
    # The failed call is still audited.
    assert sink.interactions
    assert sink.interactions[-1].validation_status == "failed"


def test_prepare_renders_without_leaking(fake_provider_cls, sample_case) -> None:
    aios = AIOS(fake_provider_cls(), settings=_settings(), audit_sink=CapturingAuditSink())
    rendered, leak_terms = aios.prepare(
        "patient",
        {"current_stage": "HISTORY"},
        case=sample_case,
        current_user_message="Does it radiate anywhere?",
    )
    whole = "\n".join(m.content for m in rendered.messages).lower()
    assert "stemi" not in whole
    assert any("STEMI" in t for t in leak_terms)
    # Last message is the student's current turn.
    assert rendered.messages[-1].content == "Does it radiate anywhere?"


async def test_unknown_agent_raises(fake_provider_cls) -> None:
    aios = AIOS(fake_provider_cls(), settings=_settings())
    with pytest.raises(KeyError):
        await aios.run("nonexistent", {})
