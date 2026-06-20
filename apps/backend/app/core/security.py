"""Security primitives: Argon2 password hashing and JWT issue/verify (Vol 5 §5).

Kept free of FastAPI/HTTP concerns so it can be unit-tested in isolation. The
auth module composes these into register/login/refresh flows.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings, get_settings
from app.domain.errors import TokenError

_ph = PasswordHasher()

ACCESS = "access"
REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:  # malformed hash, etc. — never raise from a verify
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


# ── Refresh tokens ──────────────────────────────────────────────────────────────
# The opaque refresh secret is returned to the client; only its SHA-256 is stored,
# so a database leak does not yield usable tokens. Rotation is handled in the auth
# use cases (each use mints a new one and revokes the old).


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── JWT access tokens ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    role: str
    token_type: str


def create_access_token(user_id: uuid.UUID, role: str, *, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": ACCESS,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.access_token_ttl_minutes)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str, *, settings: Settings | None = None) -> TokenClaims:
    s = settings or get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Access token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("Access token is invalid.") from exc
    if payload.get("type") != ACCESS:
        raise TokenError("Expected an access token.")
    try:
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            role=str(payload["role"]),
            token_type=ACCESS,
        )
    except (KeyError, ValueError) as exc:
        raise TokenError("Access token is missing required claims.") from exc
