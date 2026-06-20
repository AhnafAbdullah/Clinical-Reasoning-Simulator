"""SQLAlchemy implementation of InvestigationRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import InvestigationRecord
from app.domain.enums import InvestigationOutcome
from app.infrastructure.db import models as m


def _to_domain(row: m.InvestigationOrder) -> InvestigationRecord:
    return InvestigationRecord(
        id=row.id,
        investigation_name=row.investigation_name,
        normalized_name=row.normalized_name,
        indicated=row.indicated,
        outcome=row.outcome,
        ordered_at=row.ordered_at,
    )


class SqlAlchemyInvestigationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(
        self,
        *,
        session_id: uuid.UUID,
        investigation_name: str,
        normalized_name: str,
        indicated: bool | None,
        outcome: InvestigationOutcome,
    ) -> uuid.UUID:
        row = m.InvestigationOrder(
            session_id=session_id,
            investigation_name=investigation_name,
            normalized_name=normalized_name,
            indicated=indicated,
            outcome=outcome,
        )
        self._s.add(row)
        self._s.flush()
        return row.id

    def find(self, session_id: uuid.UUID, normalized_name: str) -> InvestigationRecord | None:
        stmt = select(m.InvestigationOrder).where(
            m.InvestigationOrder.session_id == session_id,
            m.InvestigationOrder.normalized_name == normalized_name,
        )
        row = self._s.scalars(stmt).first()
        return _to_domain(row) if row else None

    def list_for_session(self, session_id: uuid.UUID) -> list[InvestigationRecord]:
        stmt = (
            select(m.InvestigationOrder)
            .where(m.InvestigationOrder.session_id == session_id)
            .order_by(m.InvestigationOrder.ordered_at.asc())
        )
        return [_to_domain(r) for r in self._s.scalars(stmt)]
