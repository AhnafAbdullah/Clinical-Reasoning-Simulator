"""Debrief endpoint: the full case reveal, gated on the evaluation existing.

The case JSON is never exposed while a session is playable (Vol 3 §8); the
debrief may reveal the clinical truth only once the evaluation row is written —
i.e. the commitments are locked and the session is (or is about to be) COMPLETED.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep
from app.api.envelope import ok
from app.domain.enums import SessionStatus
from app.domain.errors import NotFoundError
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from app.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationRepository,
)
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.infrastructure.repositories.submission_repository import (
    SqlAlchemyEvaluationRepository,
    SqlAlchemySubmissionRepository,
)
from app.modules.debrief.use_cases import build_debrief
from app.modules.sessions import use_cases as session_uc

router = APIRouter(prefix="/api/v1/sessions", tags=["debrief"])


@router.get("/{session_id}/debrief")
def get_debrief(session_id: uuid.UUID, db: DbDep, user: CurrentUser) -> dict[str, Any]:
    session = session_uc.load_owned_session(
        SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id
    )
    evaluation = SqlAlchemyEvaluationRepository(db).get(session_id)
    if evaluation is None:
        if session.status == SessionStatus.EVALUATING:
            return ok({"status": "PENDING"})
        # Active/abandoned sessions must never leak the case's clinical truth.
        raise NotFoundError("No debrief is available for this session yet.")

    case_json = session_uc.case_json_for_session(SqlAlchemyCaseRepository(db), session)
    submissions = SqlAlchemySubmissionRepository(db)
    return ok(
        build_debrief(
            case_json,
            evaluation=evaluation,
            transcript=SqlAlchemyConversationRepository(db).list_for_session(session_id),
            ordered=SqlAlchemyInvestigationRepository(db).list_for_session(session_id),
            differentials=submissions.get_differential(session_id) or [],
            diagnosis=submissions.get_diagnosis(session_id) or "",
            plan=submissions.get_treatment(session_id) or "",
        )
    )
