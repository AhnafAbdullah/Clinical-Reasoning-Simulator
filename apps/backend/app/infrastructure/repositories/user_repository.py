"""SQLAlchemy implementations of UserRepository and RefreshTokenRepository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import User
from app.infrastructure.db import models as m


def _to_domain(row: m.User) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        google_id=row.google_id,
        role=row.role,
        display_name=row.display_name,
        profile_picture=row.profile_picture,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_login=row.last_login,
        deleted_at=row.deleted_at,
    )


def _apply(row: m.User, u: User) -> None:
    row.email = u.email
    row.password_hash = u.password_hash
    row.google_id = u.google_id
    row.role = u.role
    row.display_name = u.display_name
    row.profile_picture = u.profile_picture
    row.is_active = u.is_active
    row.last_login = u.last_login
    row.deleted_at = u.deleted_at


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, user: User) -> User:
        row = m.User(id=user.id)
        _apply(row, user)
        self._s.add(row)
        self._s.flush()
        return _to_domain(row)

    def get(self, user_id: uuid.UUID) -> User | None:
        row = self._s.get(m.User, user_id)
        return _to_domain(row) if row and row.deleted_at is None else None

    def get_by_email(self, email: str) -> User | None:
        stmt = select(m.User).where(m.User.email == email, m.User.deleted_at.is_(None))
        row = self._s.scalars(stmt).first()
        return _to_domain(row) if row else None

    def get_by_google_id(self, google_id: str) -> User | None:
        stmt = select(m.User).where(m.User.google_id == google_id, m.User.deleted_at.is_(None))
        row = self._s.scalars(stmt).first()
        return _to_domain(row) if row else None

    def update(self, user: User) -> User:
        row = self._s.get(m.User, user.id)
        if row is None:
            raise LookupError(f"User {user.id} not found")
        _apply(row, user)
        self._s.flush()
        return _to_domain(row)


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def store(self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> None:
        self._s.add(m.RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
        self._s.flush()

    def get_active(self, token_hash: str) -> uuid.UUID | None:
        stmt = select(m.RefreshToken).where(
            m.RefreshToken.token_hash == token_hash,
            m.RefreshToken.revoked_at.is_(None),
            m.RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        row = self._s.scalars(stmt).first()
        return row.user_id if row else None

    def get_revoked_owner(self, token_hash: str) -> uuid.UUID | None:
        stmt = select(m.RefreshToken).where(
            m.RefreshToken.token_hash == token_hash,
            m.RefreshToken.revoked_at.is_not(None),
        )
        row = self._s.scalars(stmt).first()
        return row.user_id if row else None

    def revoke(self, token_hash: str) -> None:
        stmt = select(m.RefreshToken).where(
            m.RefreshToken.token_hash == token_hash, m.RefreshToken.revoked_at.is_(None)
        )
        for row in self._s.scalars(stmt):
            row.revoked_at = datetime.now(timezone.utc)
        self._s.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = select(m.RefreshToken).where(
            m.RefreshToken.user_id == user_id, m.RefreshToken.revoked_at.is_(None)
        )
        for row in self._s.scalars(stmt):
            row.revoked_at = datetime.now(timezone.utc)
        self._s.flush()
