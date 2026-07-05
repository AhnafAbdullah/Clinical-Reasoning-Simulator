"""FastAPI dependencies: DB session, repositories, authenticated principal, and
the AI subsystem singletons. Tests override these via ``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import container
from app.core.config import Settings, get_settings
from app.core.db import session_scope
from app.core.security import decode_access_token
from app.domain.entities import User
from app.domain.errors import InvalidCredentialsError, PermissionDeniedError, TokenError
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.core.rate_limit import RateLimiter
from app.modules.ai.aios import AIOS
from app.modules.ai.stream_manager import StreamManager

# auto_error=False so a missing header surfaces as our TokenError (401 envelope),
# not Starlette's default 403.
_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    with session_scope() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


def client_ip(request: Request) -> str:
    """Best-effort client address for rate limiting. Behind nginx the first
    X-Forwarded-For hop is the real client; the header is spoofable when the
    API is exposed directly, so treat this as a throttle key, never as auth."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


ClientIp = Annotated[str, Depends(client_ip)]


def get_current_user(
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise TokenError("Missing bearer token.")
    claims = decode_access_token(credentials.credentials)
    user = SqlAlchemyUserRepository(db).get(claims.user_id)
    if user is None or not user.is_active:
        raise InvalidCredentialsError("User no longer exists or is inactive.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_user_detached(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Authenticate with a short-lived DB session of our own instead of the
    request-scoped ``get_db`` one. Streaming endpoints must use this: a yield-dep
    session is only released after the response body finishes, so with ``get_db``
    every open SSE connection would pin a pooled DB connection for its lifetime."""
    if credentials is None:
        raise TokenError("Missing bearer token.")
    claims = decode_access_token(credentials.credentials)
    with session_scope() as db:
        user = SqlAlchemyUserRepository(db).get(claims.user_id)
    if user is None or not user.is_active:
        raise InvalidCredentialsError("User no longer exists or is inactive.")
    return user


CurrentUserDetached = Annotated[User, Depends(get_current_user_detached)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise PermissionDeniedError("Administrator role required.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


# ── AI subsystem (overridable in tests) ─────────────────────────────────────────


def get_aios() -> AIOS:
    return container.get_aios()


def get_stream_manager() -> StreamManager:
    return container.get_stream_manager()


def get_rate_limiter() -> RateLimiter:
    return container.get_rate_limiter()


AIOSDep = Annotated[AIOS, Depends(get_aios)]
StreamManagerDep = Annotated[StreamManager, Depends(get_stream_manager)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
