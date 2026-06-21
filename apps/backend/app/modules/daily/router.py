"""Daily Challenge endpoints — the immersive front door.

GET  /api/v1/daily        -> today's challenge meta + the player's streak/state
POST /api/v1/daily/start  -> begin (or resume) today's one attempt; streams the
                             opening patient statement like a normal session
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter

from app.api.deps import AIOSDep, CurrentUser, DbDep, StreamManagerDep
from app.api.envelope import ok
from app.domain.errors import NotFoundError
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.daily_repository import SqlAlchemyDailyRepository
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.modules.conversation.service import ConversationService
from app.modules.daily import use_cases as uc
from app.modules.sessions import use_cases as session_uc

router = APIRouter(prefix="/api/v1/daily", tags=["daily"])


def _today() -> date:
    return date.today()


@router.get("")
def daily_status(db: DbDep, user: CurrentUser) -> dict[str, Any]:
    today = _today()
    cases = SqlAlchemyCaseRepository(db).list_published(limit=1000)
    if not cases:
        raise NotFoundError("No cases are available yet.")
    todays = uc.case_of_the_day(cases, today)
    daily = SqlAlchemyDailyRepository(db)
    session_id = daily.get_session_for_date(user.id, today)
    streak = uc.compute_streak(daily.attempt_dates(user.id), today)
    return ok(
        {
            "date": today.isoformat(),
            # Title is withheld to preserve the "who walks in?" surprise.
            "difficulty": todays.difficulty.value,
            "specialty": todays.specialty,
            "estimated_duration": todays.estimated_duration,
            "attempted": session_id is not None,
            "session_id": str(session_id) if session_id else None,
            "streak": streak,
        }
    )


@router.post("/start")
async def daily_start(
    db: DbDep, user: CurrentUser, aios: AIOSDep, stream: StreamManagerDep
) -> dict[str, Any]:
    today = _today()
    daily = SqlAlchemyDailyRepository(db)

    existing = daily.get_session_for_date(user.id, today)
    if existing is not None:
        # One attempt per day — resume the same session (no new opening turn).
        session = session_uc.load_owned_session(
            SqlAlchemySessionRepository(db), session_id=existing, user_id=user.id
        )
        return ok(
            {
                "session_id": str(session.id),
                "status": session.status.value,
                "opening_message_id": None,
                "resumed": True,
                "streak": uc.compute_streak(daily.attempt_dates(user.id), today),
            }
        )

    cases = SqlAlchemyCaseRepository(db).list_published(limit=1000)
    todays = uc.case_of_the_day(cases, today)
    session, case_json = session_uc.start_session(
        SqlAlchemyCaseRepository(db),
        SqlAlchemySessionRepository(db),
        user_id=user.id,
        case_id=todays.id,
    )
    daily.record(user_id=user.id, challenge_date=today, case_id=todays.id, session_id=session.id)

    opening_message_id = str(uuid.uuid4())
    service = ConversationService(aios, stream)
    if await service.begin_turn(session.id, opening_message_id):
        service.schedule_patient_turn(
            session=session,
            case_json=case_json,
            history=[],
            current_message=None,
            message_id=opening_message_id,
            user_id=user.id,
        )

    return ok(
        {
            "session_id": str(session.id),
            "status": session.status.value,
            "opening_message_id": opening_message_id,
            "resumed": False,
            "streak": uc.compute_streak(daily.attempt_dates(user.id), today),
        }
    )
