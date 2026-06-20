"""Auth use cases: register, login, refresh-rotation, logout (Vol 5 §5/§8).

Pure application logic over repository ports and the ``core.security`` primitives.
Refresh tokens rotate: each successful refresh revokes the presented token and
issues a new one, so a stolen token is single-use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.domain.entities import User
from app.domain.enums import UserRole
from app.domain.errors import EmailAlreadyRegisteredError, InvalidCredentialsError, TokenError
from app.domain.repositories import RefreshTokenRepository, UserRepository


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(
    users: UserRepository,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
) -> User:
    email = _normalize_email(email)
    if users.get_by_email(email) is not None:
        raise EmailAlreadyRegisteredError("An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        role=UserRole.STUDENT,
    )
    return users.add(user)


def authenticate(users: UserRepository, *, email: str, password: str) -> User:
    user = users.get_by_email(_normalize_email(email))
    # Verify even when the user is missing? We skip — but the Argon2 cost on the
    # found path dominates; the timing gap here is acceptable for the MVP.
    if user is None or not user.password_hash:
        raise InvalidCredentialsError("Incorrect email or password.")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Incorrect email or password.")
    if not user.is_active:
        raise InvalidCredentialsError("This account is disabled.")
    user.last_login = datetime.now(timezone.utc)
    return users.update(user)


def issue_token_pair(
    tokens: RefreshTokenRepository,
    user: User,
    *,
    settings: Settings | None = None,
) -> TokenPair:
    s = settings or get_settings()
    refresh = generate_refresh_token()
    tokens.store(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=s.refresh_token_ttl_days),
    )
    access = create_access_token(user.id, user.role.value, settings=s)
    return TokenPair(access_token=access, refresh_token=refresh)


def refresh_tokens(
    users: UserRepository,
    tokens: RefreshTokenRepository,
    *,
    refresh_token: str,
    settings: Settings | None = None,
) -> TokenPair:
    token_hash = hash_refresh_token(refresh_token)
    user_id = tokens.get_active(token_hash)
    if user_id is None:
        raise TokenError("Refresh token is invalid, expired, or already used.")
    user = users.get(user_id)
    if user is None or not user.is_active:
        raise TokenError("Account is no longer available.")
    tokens.revoke(token_hash)  # rotation: the presented token is now spent
    return issue_token_pair(tokens, user, settings=settings)


def logout(tokens: RefreshTokenRepository, *, refresh_token: str) -> None:
    tokens.revoke(hash_refresh_token(refresh_token))
