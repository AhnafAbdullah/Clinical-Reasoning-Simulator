"""Conversation service: drives a patient turn through the AIOS and the buffered,
resumable stream (Vol 4D §7/§13, Vol 4A §16).

Design: *decide, then stream*. The full patient reply is generated, validated,
retried and audited by the AIOS first; only then is the settled text delivered
token-by-token through the Stream Manager. This keeps validation off the token
path and makes the stream trivially resumable.

To stay race-free, the background generation task is handed everything it needs
(history + current message) as plain values — it never re-reads the conversation
the request just wrote. It opens its own DB session purely to persist the patient
reply before the stream's completion event.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence

from app.core.db import session_scope
from app.domain.ai import ChatMessage, ChatRole
from app.domain.entities import ClinicalSession, ConversationRecord
from app.domain.enums import MessageRole
from app.modules.ai.aios import AIOS
from app.modules.ai.stream_manager import StreamManager
from app.infrastructure.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)

logger = logging.getLogger(__name__)

PATIENT_AGENT = "patient"

# Keep strong references to in-flight background generations so they are not
# garbage-collected mid-run (asyncio holds only weak refs to tasks).
_background_tasks: set[asyncio.Task] = set()


def records_to_chat(records: Sequence[ConversationRecord]) -> list[ChatMessage]:
    """Map persisted turns to provider chat messages (student=user, patient=assistant)."""
    out: list[ChatMessage] = []
    for r in records:
        role = ChatRole.USER if r.role == MessageRole.STUDENT else ChatRole.ASSISTANT
        out.append(ChatMessage(role=role, content=r.message))
    return out


class ConversationService:
    def __init__(self, aios: AIOS, stream_manager: StreamManager) -> None:
        self.aios = aios
        self.stream = stream_manager

    async def begin_turn(self, session_id: uuid.UUID, message_id: str) -> bool:
        """Reserve the single active-generation slot for the session."""
        return await self.stream.begin(str(session_id), message_id)

    def schedule_patient_turn(
        self,
        *,
        session: ClinicalSession,
        case_json: dict,
        history: list[ChatMessage],
        current_message: str | None,
        message_id: str,
        user_id: uuid.UUID,
    ) -> None:
        """Fire-and-forget the generation; the client attaches via the SSE stream."""
        task = asyncio.create_task(
            self._generate(
                session=session,
                case_json=case_json,
                history=history,
                current_message=current_message,
                message_id=message_id,
                user_id=user_id,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def _generate(
        self,
        *,
        session: ClinicalSession,
        case_json: dict,
        history: list[ChatMessage],
        current_message: str | None,
        message_id: str,
        user_id: uuid.UUID,
    ) -> None:
        try:
            result = await self.aios.run(
                PATIENT_AGENT,
                {"current_stage": session.current_stage.value},
                case=case_json,
                history=history,
                current_user_message=current_message,
                session_id=str(session.id),
                user_id=str(user_id),
                message_id=message_id,
            )
            # Persist before the completion event so a reconnect always finds the
            # turn already saved (Vol 4D §7). Fresh session: the request's is gone.
            with session_scope() as db:
                SqlAlchemyConversationRepository(db).add(
                    session_id=session.id,
                    role=MessageRole.PATIENT,
                    message=result.text,
                    token_count=result.interaction.completion_tokens,
                )
            await self.stream.stream_text(message_id, result.text)
        except Exception as exc:  # generation/validation/persistence failure
            logger.exception("Patient turn failed for message %s", message_id)
            await self.stream.fail(message_id, str(exc))
