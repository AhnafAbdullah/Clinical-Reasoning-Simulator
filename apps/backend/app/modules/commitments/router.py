"""Commitment + evaluation endpoints (Vol 5 §16-18, Vol 4D §10-12).

The three commitment points are strictly ordered and irreversible — the domain
state machine enforces the order; each is validated, persisted and locked. No
grading happens at submission. Submitting the management plan moves the session
to EVALUATING and queues the (decoupled) evaluation worker.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import AIOSDep, CurrentUser, DbDep
from app.api.envelope import ok
from app.domain.enums import SessionStatus
from app.domain.errors import NotFoundError
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.infrastructure.repositories.submission_repository import (
    SqlAlchemyEvaluationRepository,
    SqlAlchemySubmissionRepository,
)
from app.modules.commitments.schemas import (
    DiagnosisRequest,
    DifferentialRequest,
    ManagementRequest,
)
from app.modules.evaluation.service import EvaluationService
from app.modules.sessions import use_cases as session_uc

router = APIRouter(prefix="/api/v1/sessions", tags=["commitments"])


@router.post("/{session_id}/differentials")
def submit_differentials(
    session_id: uuid.UUID, body: DifferentialRequest, db: DbDep, user: CurrentUser
) -> dict[str, Any]:
    sessions = SqlAlchemySessionRepository(db)
    session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    session.submit_differential()  # validates ordering; raises on misuse
    SqlAlchemySubmissionRepository(db).save_differential(session.id, body.differentials)
    sessions.update(session)
    return ok({"current_stage": session.current_stage.value})


@router.post("/{session_id}/diagnosis")
def submit_diagnosis(
    session_id: uuid.UUID, body: DiagnosisRequest, db: DbDep, user: CurrentUser
) -> dict[str, Any]:
    sessions = SqlAlchemySessionRepository(db)
    session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    session.submit_diagnosis()
    SqlAlchemySubmissionRepository(db).save_diagnosis(session.id, body.diagnosis)
    sessions.update(session)
    return ok({"current_stage": session.current_stage.value})


@router.post("/{session_id}/management", status_code=status.HTTP_202_ACCEPTED)
def submit_management(
    session_id: uuid.UUID,
    body: ManagementRequest,
    db: DbDep,
    user: CurrentUser,
    aios: AIOSDep,
    background: BackgroundTasks,
) -> dict[str, Any]:
    sessions = SqlAlchemySessionRepository(db)
    session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    session.submit_management()  # ACTIVE -> EVALUATING
    SqlAlchemySubmissionRepository(db).save_treatment(session.id, body.plan)
    sessions.update(session)
    # Commit now so the background worker (which Starlette may start before this
    # request's yield-dependency commits) reads the fully-persisted EVALUATING
    # session and the management plan.
    db.commit()
    background.add_task(EvaluationService(aios).run, session.id)
    return ok({"status": session.status.value})


@router.get("/{session_id}/evaluation")
def get_evaluation(session_id: uuid.UUID, db: DbDep, user: CurrentUser) -> dict[str, Any]:
    sessions = SqlAlchemySessionRepository(db)
    session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    evaluation = SqlAlchemyEvaluationRepository(db).get(session_id)
    if evaluation is not None:
        return ok(evaluation)
    if session.status == SessionStatus.EVALUATING:
        return ok({"status": "PENDING"})
    raise NotFoundError("No evaluation is available for this session.")
