"""SQLAlchemy implementation of SessionRepository."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.entities import ClinicalSession
from app.infrastructure.db import models as m


def _to_domain(row: m.ClinicalSession) -> ClinicalSession:
    return ClinicalSession(
        id=row.id,
        user_id=row.user_id,
        case_id=row.case_id,
        case_version=row.case_version,
        case_content_hash=row.case_content_hash,
        difficulty=row.difficulty,
        status=row.status,
        current_stage=row.current_stage,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _apply(row: m.ClinicalSession, s: ClinicalSession) -> None:
    row.user_id = s.user_id
    row.case_id = s.case_id
    row.case_version = s.case_version
    row.case_content_hash = s.case_content_hash
    row.difficulty = s.difficulty
    row.status = s.status
    row.current_stage = s.current_stage
    row.completed_at = s.completed_at


class SqlAlchemySessionRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, clinical_session: ClinicalSession) -> ClinicalSession:
        row = m.ClinicalSession(id=clinical_session.id, started_at=clinical_session.started_at)
        _apply(row, clinical_session)
        self._s.add(row)
        self._s.flush()
        return _to_domain(row)

    def get(self, session_id: uuid.UUID) -> ClinicalSession | None:
        row = self._s.get(m.ClinicalSession, session_id)
        return _to_domain(row) if row else None

    def update(self, clinical_session: ClinicalSession) -> ClinicalSession:
        row = self._s.get(m.ClinicalSession, clinical_session.id)
        if row is None:
            raise LookupError(f"Session {clinical_session.id} not found")
        _apply(row, clinical_session)
        self._s.flush()
        return _to_domain(row)
