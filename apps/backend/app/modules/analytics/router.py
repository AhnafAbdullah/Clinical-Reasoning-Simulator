"""Analytics endpoint (Vol 5 §19): a student's own performance summary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep
from app.api.envelope import ok
from app.infrastructure.repositories.analytics_repository import SqlAlchemyAnalyticsRepository

router = APIRouter(prefix="/api/v1/users/me", tags=["analytics"])


@router.get("/analytics")
def my_analytics(db: DbDep, user: CurrentUser) -> dict[str, Any]:
    return ok(SqlAlchemyAnalyticsRepository(db).summary(user.id))
