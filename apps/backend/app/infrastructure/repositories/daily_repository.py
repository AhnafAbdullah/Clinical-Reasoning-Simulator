"""SQLAlchemy implementation of the Daily Challenge attempt store."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db import models as m


class SqlAlchemyDailyRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_session_for_date(self, user_id: uuid.UUID, on: date) -> uuid.UUID | None:
        stmt = select(m.DailyAttempt.session_id).where(
            m.DailyAttempt.user_id == user_id, m.DailyAttempt.challenge_date == on
        )
        return self._s.scalars(stmt).first()

    def record(
        self,
        *,
        user_id: uuid.UUID,
        challenge_date: date,
        case_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        self._s.add(
            m.DailyAttempt(
                user_id=user_id,
                challenge_date=challenge_date,
                case_id=case_id,
                session_id=session_id,
            )
        )
        self._s.flush()

    def attempt_dates(self, user_id: uuid.UUID) -> list[date]:
        stmt = (
            select(m.DailyAttempt.challenge_date)
            .where(m.DailyAttempt.user_id == user_id)
            .order_by(m.DailyAttempt.challenge_date.desc())
        )
        return list(self._s.scalars(stmt))
