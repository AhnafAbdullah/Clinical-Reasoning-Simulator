"""SQLAlchemy implementation of ConversationRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import ConversationRecord
from app.domain.enums import MessageRole
from app.infrastructure.db import models as m


def _to_domain(row: m.ConversationMessage) -> ConversationRecord:
    return ConversationRecord(
        id=row.id, role=row.role, message=row.message, timestamp=row.timestamp
    )


class SqlAlchemyConversationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(
        self,
        *,
        session_id: uuid.UUID,
        role: MessageRole,
        message: str,
        token_count: int | None,
    ) -> uuid.UUID:
        row = m.ConversationMessage(
            session_id=session_id, role=role, message=message, token_count=token_count
        )
        self._s.add(row)
        self._s.flush()
        return row.id

    def list_for_session(self, session_id: uuid.UUID) -> list[ConversationRecord]:
        stmt = (
            select(m.ConversationMessage)
            .where(m.ConversationMessage.session_id == session_id)
            .order_by(m.ConversationMessage.timestamp.asc(), m.ConversationMessage.id.asc())
        )
        return [_to_domain(r) for r in self._s.scalars(stmt)]
