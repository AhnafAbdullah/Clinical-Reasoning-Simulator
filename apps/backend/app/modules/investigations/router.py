"""Investigation endpoints (Vol 5 §15): the catalog plus per-session ordering."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbDep, RateLimiterDep, SettingsDep
from app.api.envelope import ok, page_meta
from app.domain.enums import ClinicalStage
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationRepository,
)
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.modules.investigations import use_cases as uc
from app.modules.investigations.catalog import search_catalog
from app.modules.investigations.schemas import InvestigationOrderRequest
from app.modules.sessions import use_cases as session_uc

# The browsable catalog is case-independent.
catalog_router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])
# Ordering and history are scoped to a session.
session_router = APIRouter(prefix="/api/v1/sessions", tags=["investigations"])


@catalog_router.get("")
def list_catalog(
    _: CurrentUser,
    search: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    entries = search_catalog(query=search, category=category)
    total = len(entries)
    start = (page - 1) * page_size
    window = entries[start : start + page_size]
    data = [{"name": e.name, "category": e.category} for e in window]
    return ok(data, meta=page_meta(page=page, page_size=page_size, total_items=total))


@session_router.post("/{session_id}/investigations")
async def order_investigation(
    session_id: uuid.UUID,
    body: InvestigationOrderRequest,
    db: DbDep,
    user: CurrentUser,
    limiter: RateLimiterDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    await limiter.check(
        "investigations",
        str(user.id),
        limit=settings.rate_limit_investigations_per_minute,
        window_seconds=60,
    )
    sessions = SqlAlchemySessionRepository(db)
    session = session_uc.load_owned_session(sessions, session_id=session_id, user_id=user.id)
    session.ensure_working_action("order an investigation")
    case_json = session_uc.case_json_for_session(SqlAlchemyCaseRepository(db), session)

    result = uc.order_investigation(
        SqlAlchemyInvestigationRepository(db),
        session=session,
        case_json=case_json,
        raw_name=body.investigation,
    )
    session.reach_stage(ClinicalStage.INVESTIGATIONS)
    sessions.update(session)
    return ok(
        {
            "status": result.status,
            "outcome": result.outcome.value,
            "indicated": result.indicated,
            "duplicate": result.duplicate,
            "result": result.result,
        }
    )


@session_router.get("/{session_id}/investigations")
def list_session_investigations(
    session_id: uuid.UUID, db: DbDep, user: CurrentUser
) -> dict[str, Any]:
    session_uc.load_owned_session(
        SqlAlchemySessionRepository(db), session_id=session_id, user_id=user.id
    )
    return ok(uc.list_orders(SqlAlchemyInvestigationRepository(db), session_id))
