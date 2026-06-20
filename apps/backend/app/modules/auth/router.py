"""Auth endpoints (Vol 5 §8). Responses use the standard envelope."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbDep, RateLimiterDep, SettingsDep
from app.api.envelope import ok
from app.domain.errors import AuthError
from app.infrastructure.repositories.user_repository import (
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from app.modules.auth import use_cases as uc
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _token_payload(pair: uc.TokenPair) -> dict[str, Any]:
    return TokenResponse(
        access_token=pair.access_token, refresh_token=pair.refresh_token
    ).model_dump()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbDep) -> dict[str, Any]:
    users = SqlAlchemyUserRepository(db)
    tokens = SqlAlchemyRefreshTokenRepository(db)
    user = uc.register_user(
        users, email=body.email, password=body.password, display_name=body.display_name
    )
    pair = uc.issue_token_pair(tokens, user)
    return ok(_token_payload(pair))


@router.post("/login")
async def login(
    body: LoginRequest, db: DbDep, limiter: RateLimiterDep, settings: SettingsDep
) -> dict[str, Any]:
    await limiter.check(
        "login",
        body.email.lower(),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    users = SqlAlchemyUserRepository(db)
    tokens = SqlAlchemyRefreshTokenRepository(db)
    user = uc.authenticate(users, email=body.email, password=body.password)
    pair = uc.issue_token_pair(tokens, user)
    return ok(_token_payload(pair))


@router.post("/refresh")
def refresh(body: RefreshRequest, db: DbDep) -> dict[str, Any]:
    users = SqlAlchemyUserRepository(db)
    tokens = SqlAlchemyRefreshTokenRepository(db)
    pair = uc.refresh_tokens(users, tokens, refresh_token=body.refresh_token)
    return ok(_token_payload(pair))


@router.post("/logout")
def logout(body: RefreshRequest, db: DbDep) -> dict[str, Any]:
    uc.logout(SqlAlchemyRefreshTokenRepository(db), refresh_token=body.refresh_token)
    return ok({"revoked": True})


@router.post("/google")
def google(settings: SettingsDep) -> dict[str, Any]:
    # Behind the enable_google_login flag (Vol 2B §31). Wired in a later pass.
    if not settings.enable_google_login:
        raise AuthError("Google login is not enabled.")
    raise AuthError("Google login is not yet implemented.")


@router.get("/me")
def me(user: CurrentUser) -> dict[str, Any]:
    return ok(UserProfile.from_entity(user).model_dump())
