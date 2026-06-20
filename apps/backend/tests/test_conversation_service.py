"""Conversation service: decide-then-stream patient turn (Vol 4D §7, Vol 4A §16)."""

from __future__ import annotations

import uuid
from contextlib import contextmanager

from app.domain.entities import ClinicalSession
from app.domain.enums import Difficulty, SessionStatus
from app.infrastructure.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from app.modules.ai.aios import AIOS
from app.modules.ai.buffer import InMemoryGenerationBuffer
from app.modules.ai.stream_manager import StreamManager
from app.modules.conversation.service import ConversationService


def _session() -> ClinicalSession:
    return ClinicalSession(
        user_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        case_version=1,
        case_content_hash="x" * 64,
        difficulty=Difficulty.BASIC,
        status=SessionStatus.ACTIVE,
    )


async def test_turn_persists_then_streams(session, sample_case, monkeypatch, fake_provider_cls):
    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr("app.modules.conversation.service.session_scope", _scope)

    buffer = InMemoryGenerationBuffer()
    aios = AIOS(fake_provider_cls("It started about two hours ago while watching TV."))
    service = ConversationService(aios, StreamManager(buffer))

    s = _session()
    message_id = "m-1"
    assert await service.begin_turn(s.id, message_id) is True

    await service._generate(
        session=s,
        case_json=sample_case,
        history=[],
        current_message="When did the pain start?",
        message_id=message_id,
        user_id=s.user_id,
    )

    events = await buffer.snapshot(message_id)
    types = [e.type for e in events]
    assert "token" in types
    assert types[-1] == "complete"  # persistence happened before completion

    records = SqlAlchemyConversationRepository(session).list_for_session(s.id)
    assert any("two hours ago" in r.message for r in records)


async def test_one_active_generation_per_session(sample_case, fake_provider_cls):
    buffer = InMemoryGenerationBuffer()
    service = ConversationService(AIOS(fake_provider_cls("ok")), StreamManager(buffer))
    s = _session()
    assert await service.begin_turn(s.id, "m1") is True
    assert await service.begin_turn(s.id, "m2") is False  # already active


async def test_generation_failure_emits_error_event(session, sample_case, monkeypatch):
    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr("app.modules.conversation.service.session_scope", _scope)

    # A provider that always fails exhausts retries -> the buffer gets an error event.
    from tests.conftest import FakeProvider

    buffer = InMemoryGenerationBuffer()
    aios = AIOS(FakeProvider(fail_times=99))
    service = ConversationService(aios, StreamManager(buffer))

    s = _session()
    await service.begin_turn(s.id, "m-err")
    await service._generate(
        session=s,
        case_json=sample_case,
        history=[],
        current_message="Hello?",
        message_id="m-err",
        user_id=s.user_id,
    )
    events = await buffer.snapshot("m-err")
    assert events[-1].type == "error"
