"""Conversation endpoints (Vol 5 §12-13).

POST messages returns 202 + a correlation id immediately; the patient turn is
generated in the background and delivered over the SSE stream keyed by that id,
which is resumable via the Last-Event-ID header.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AIOSDep,
    CurrentUser,
    CurrentUserDetached,
    DbDep,
    RateLimiterDep,
    SettingsDep,
    StreamManagerDep,
)
from app.api.envelope import ok
from app.core.db import session_scope
from app.domain.ai import ChatMessage
from app.domain.entities import ClinicalSession
from app.domain.errors import InvalidStateTransition, NotFoundError
from app.domain.enums import ClinicalStage, MessageRole
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.modules.conversation.schemas import MessageAccepted, MessageItem, MessageRequest
from app.modules.conversation.service import ConversationService, records_to_chat
from app.modules.sessions import use_cases as session_uc

router = APIRouter(prefix="/api/v1/sessions", tags=["conversation"])


@router.post("/{session_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_message(
    session_id: uuid.UUID,
    body: MessageRequest,
    db: DbDep,
    user: CurrentUser,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    aios: AIOSDep,
    stream: StreamManagerDep,
) -> dict[str, Any]:
    await limiter.check(
        "messages", str(user.id), limit=settings.rate_limit_messages_per_minute, window_seconds=60
    )

    # Sync SQLAlchemy work runs in worker threads so it never blocks the event
    # loop (which is also serving every active SSE stream).
    def _load_and_validate() -> tuple[ClinicalSession, dict, list[ChatMessage]]:
        sessions = SqlAlchemySessionRepository(db)
        session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
        session.ensure_working_action("send a message")
        case_json = session_uc.case_json_for_session(SqlAlchemyCaseRepository(db), session)
        conv = SqlAlchemyConversationRepository(db)
        prior = records_to_chat(conv.list_for_session(session.id))  # before adding the new turn
        return session, case_json, prior

    session, case_json, prior = await asyncio.to_thread(_load_and_validate)

    message_id = str(uuid.uuid4())
    service = ConversationService(aios, stream)
    if not await service.begin_turn(session.id, message_id):
        # One active generation per session (Vol 4A §16 / Vol 5 §13). Nothing has
        # been written yet, so the rejected turn leaves no orphan student message.
        raise InvalidStateTransition("A patient response is already being generated.")

    def _record_turn() -> None:
        sessions = SqlAlchemySessionRepository(db)
        conv = SqlAlchemyConversationRepository(db)
        conv.add(
            session_id=session.id, role=MessageRole.STUDENT, message=body.message, token_count=None
        )
        if session.current_stage == ClinicalStage.GREETING:
            session.reach_stage(ClinicalStage.HISTORY)
            sessions.update(session)
        # Commit NOW, before the background generation is scheduled: its own
        # session persists the patient reply, and a reply must never be able to
        # land for a student message that was still uncommitted (and could roll
        # back). The request-scoped teardown commit then finds nothing to do.
        db.commit()

    try:
        await asyncio.to_thread(_record_turn)
    except Exception:
        # Free the reserved generation slot (a terminal event marks it done);
        # otherwise the session would refuse new turns until the buffer TTL.
        await stream.fail(message_id, "Your message could not be saved. Please try again.")
        raise

    service.schedule_patient_turn(
        session=session,
        case_json=case_json,
        history=prior,
        current_message=body.message,
        message_id=message_id,
        user_id=user.id,
    )
    return ok(MessageAccepted(message_id=message_id).model_dump())


@router.get("/{session_id}/messages")
def list_messages(session_id: uuid.UUID, db: DbDep, user: CurrentUser) -> dict[str, Any]:
    session_uc.load_owned_session(
        SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id
    )
    records = SqlAlchemyConversationRepository(db).list_for_session(session_id)
    return ok([MessageItem.from_record(r).model_dump(mode="json") for r in records])


@router.get("/{session_id}/stream")
async def stream_message(
    session_id: uuid.UUID,
    message_id: str,
    user: CurrentUserDetached,
    stream: StreamManagerDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    # Deliberately NOT the request-scoped DbDep: that session is only released
    # after the response body finishes, and an SSE body can live for minutes —
    # each open stream would pin a pooled DB connection. Check ownership with a
    # short-lived session (in a worker thread), then stream with none held.
    def _check_ownership() -> None:
        with session_scope() as db:
            session_uc.load_owned_session(
                SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id
            )

    await asyncio.to_thread(_check_ownership)
    # The generation must belong to the session whose ownership we just proved;
    # message ids are unguessable but authorization must not rely on that.
    if await stream.session_of(message_id) != str(session_id):
        raise NotFoundError("No generation with this id exists for this session.")
    after_seq = -1
    if last_event_id and last_event_id.isdigit():
        after_seq = int(last_event_id)
    return StreamingResponse(
        stream.sse(message_id, after_seq),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
