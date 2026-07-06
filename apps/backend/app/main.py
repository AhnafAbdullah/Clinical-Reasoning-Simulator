"""FastAPI application entrypoint (foundation: health/readiness only for now)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.errors import register_exception_handlers
from app.api.skeleton import router as skeleton_router
from app.core import container
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging
from app.modules.analytics.router import router as analytics_router
from app.modules.auth.router import router as auth_router
from app.modules.cases.router import router as cases_router
from app.modules.commitments.router import router as commitments_router
from app.modules.conversation.router import router as conversation_router
from app.modules.daily.router import router as daily_router
from app.modules.debrief.router import router as debrief_router
from app.modules.investigations.router import (
    catalog_router as investigations_catalog_router,
    session_router as investigations_session_router,
)
from app.modules.sessions.router import router as sessions_router

configure_logging()


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    # Release shared network resources (Redis pool, provider HTTP client).
    await container.shutdown()
    engine.dispose()


app = FastAPI(title="Clinical Reasoning Simulator API", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(sessions_router)
app.include_router(conversation_router)
app.include_router(commitments_router)
app.include_router(debrief_router)
app.include_router(investigations_catalog_router)
app.include_router(investigations_session_router)
app.include_router(analytics_router)
app.include_router(daily_router)
app.include_router(skeleton_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (Vol 5 §20)."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    """Readiness probe: database, Redis, and the AI provider (Vol 5 §20)."""
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised in integration
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        await container.get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised in integration
        checks["redis"] = f"error: {exc.__class__.__name__}"

    if settings.openrouter_api_key:
        try:
            checks["ai_provider"] = (
                "ok" if await container.get_provider().health_check() else "error"
            )
        except Exception as exc:  # pragma: no cover
            checks["ai_provider"] = f"error: {exc.__class__.__name__}"
    else:
        checks["ai_provider"] = "unconfigured"

    ready = all(v in ("ok", "unconfigured") for v in checks.values())
    return {"ready": ready, "checks": checks}
