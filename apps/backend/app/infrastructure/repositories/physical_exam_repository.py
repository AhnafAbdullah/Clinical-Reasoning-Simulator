"""SQLAlchemy implementation of PhysicalExamRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db import models as m


class SqlAlchemyPhysicalExamRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, *, session_id: uuid.UUID, system: str) -> uuid.UUID:
        row = m.PhysicalExamRequest(session_id=session_id, system=system)
        self._s.add(row)
        self._s.flush()
        return row.id

    def list_for_session(self, session_id: uuid.UUID) -> list[str]:
        stmt = (
            select(m.PhysicalExamRequest.system)
            .where(m.PhysicalExamRequest.session_id == session_id)
            .order_by(m.PhysicalExamRequest.requested_at.asc())
        )
        return list(self._s.scalars(stmt))
