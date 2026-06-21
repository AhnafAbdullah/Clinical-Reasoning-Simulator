"""Session endpoints (Vol 5 §11/§14). Workflow-oriented, enveloped responses."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status

from app.api.deps import (
    AIOSDep,
    CurrentUser,
    DbDep,
    RateLimiterDep,
    SettingsDep,
    StreamManagerDep,
)
from app.api.envelope import ok, page_meta
from app.domain.enums import ClinicalStage
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.physical_exam_repository import (
    SqlAlchemyPhysicalExamRepository,
)
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.modules.conversation.service import ConversationService
from app.modules.sessions import use_cases as uc
from app.modules.sessions.schemas import (
    PhysicalExamRequest,
    SessionCreatedResponse,
    SessionCreateRequest,
    SessionDetail,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreateRequest,
    db: DbDep,
    user: CurrentUser,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    aios: AIOSDep,
    stream: StreamManagerDep,
) -> dict[str, Any]:
    await limiter.check(
        "sessions", str(user.id), limit=settings.rate_limit_sessions_per_hour, window_seconds=3600
    )
    session, case_json = uc.start_session(
        SqlAlchemyCaseRepository(db),
        SqlAlchemySessionRepository(db),
        user_id=user.id,
        case_id=body.case_id,
    )

    # Kick off the opening patient statement on the streaming machinery (Vol 4D §6).
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
        SessionCreatedResponse(
            session_id=session.id,
            status=session.status.value,
            opening_message_id=opening_message_id,
        ).model_dump(mode="json")
    )


@router.get("")
def list_sessions(
    db: DbDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    repo = SqlAlchemySessionRepository(db)
    offset = (page - 1) * page_size
    sessions = repo.list_for_user(user.id, limit=page_size, offset=offset)
    total = repo.count_for_user(user.id)
    data = [SessionDetail.from_entity(s).model_dump(mode="json") for s in sessions]
    return ok(data, meta=page_meta(page=page, page_size=page_size, total_items=total))


@router.get("/{session_id}")
def get_session(session_id: uuid.UUID, db: DbDep, user: CurrentUser) -> dict[str, Any]:
    session = uc.load_owned_session(
        SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id
    )
    return ok(SessionDetail.from_entity(session).model_dump(mode="json"))


@router.delete("/{session_id}")
def delete_session(session_id: uuid.UUID, db: DbDep, user: CurrentUser) -> dict[str, Any]:
    uc.delete_session(SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id)
    return ok({"deleted": True})


@router.post("/{session_id}/physical-exam")
def physical_exam(
    session_id: uuid.UUID, body: PhysicalExamRequest, db: DbDep, user: CurrentUser
) -> dict[str, Any]:
    sessions = SqlAlchemySessionRepository(db)
    session = uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    session.ensure_working_action("perform a physical examination")
    findings = uc.physical_exam_findings(
        uc.case_json_for_session(SqlAlchemyCaseRepository(db), session), body.system
    )
    SqlAlchemyPhysicalExamRepository(db).add(session_id=session.id, system=findings["system"])
    session.reach_stage(ClinicalStage.PHYSICAL_EXAM)
    sessions.update(session)
    return ok(findings)
