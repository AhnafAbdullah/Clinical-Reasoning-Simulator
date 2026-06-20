"""Conversation endpoints (Vol 5 §12-13).

POST messages returns 202 + a correlation id immediately; the patient turn is
generated in the background and delivered over the SSE stream keyed by that id,
which is resumable via the Last-Event-ID header.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AIOSDep,
    CurrentUser,
    DbDep,
    RateLimiterDep,
    SettingsDep,
    StreamManagerDep,
)
from app.api.envelope import ok
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
    sessions = SqlAlchemySessionRepository(db)
    session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    session.ensure_working_action("send a message")
    case_json = session_uc.case_json_for_session(SqlAlchemyCaseRepository(db), session)

    conv = SqlAlchemyConversationRepository(db)
    prior = records_to_chat(conv.list_for_session(session.id))  # before adding the new turn
    conv.add(
        session_id=session.id, role=MessageRole.STUDENT, message=body.message, token_count=None
    )
    if session.current_stage == ClinicalStage.GREETING:
        session.reach_stage(ClinicalStage.HISTORY)
        sessions.update(session)

    message_id = str(uuid.uuid4())
    service = ConversationService(aios, stream)
    if not await service.begin_turn(session.id, message_id):
        # One active generation per session (Vol 4A §16 / Vol 5 §13).
        from app.domain.errors import InvalidStateTransition

        raise InvalidStateTransition("A patient response is already being generated.")

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
    db: DbDep,
    user: CurrentUser,
    stream: StreamManagerDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    session_uc.load_owned_session(
        SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id
    )
    after_seq = -1
    if last_event_id and last_event_id.isdigit():
        after_seq = int(last_event_id)
    return StreamingResponse(
        stream.sse(message_id, after_seq),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
