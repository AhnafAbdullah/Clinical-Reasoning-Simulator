"""Case browsing endpoints (Vol 5 §10). Read-only for students; metadata only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbDep
from app.api.envelope import ok, page_meta
from app.domain.errors import NotFoundError
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.modules.cases.schemas import CaseSummary

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("")
def list_cases(
    db: DbDep,
    _: CurrentUser,
    difficulty: str | None = None,
    specialty: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    # Case libraries are small (MVP); fetch published then filter/paginate in memory.
    cases = SqlAlchemyCaseRepository(db).list_published(difficulty=difficulty, limit=1000)
    if specialty:
        cases = [c for c in cases if c.specialty.lower() == specialty.lower()]
    if search:
        q = search.lower()
        cases = [c for c in cases if q in c.title.lower()]
    total = len(cases)
    start = (page - 1) * page_size
    window = cases[start : start + page_size]
    data = [CaseSummary.from_entity(c).model_dump(mode="json") for c in window]
    return ok(data, meta=page_meta(page=page, page_size=page_size, total_items=total))


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, db: DbDep, _: CurrentUser) -> dict[str, Any]:
    case = SqlAlchemyCaseRepository(db).get(case_id)
    if case is None or not case.is_published:
        raise NotFoundError("Case not found.")
    return ok(CaseSummary.from_entity(case).model_dump(mode="json"))
