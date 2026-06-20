"""Repository interfaces (ports). Implementations live in infrastructure.

The application layer depends on these Protocols, never on SQLAlchemy.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.entities import (
    ClinicalCase,
    ClinicalSession,
    ConversationRecord,
    InvestigationRecord,
    User,
)
from app.domain.enums import InvestigationOutcome, MessageRole


@runtime_checkable
class UserRepository(Protocol):
    def add(self, user: User) -> User: ...

    def get(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def get_by_google_id(self, google_id: str) -> User | None: ...

    def update(self, user: User) -> User: ...


@runtime_checkable
class RefreshTokenRepository(Protocol):
    def store(self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> None: ...

    def get_active(self, token_hash: str) -> uuid.UUID | None:
        """Return the owning user id for a non-revoked, unexpired token, else None."""
        ...

    def revoke(self, token_hash: str) -> None: ...

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None: ...


@runtime_checkable
class ConversationRepository(Protocol):
    def add(
        self, *, session_id: uuid.UUID, role: MessageRole, message: str, token_count: int | None
    ) -> uuid.UUID: ...

    def list_for_session(self, session_id: uuid.UUID) -> list[ConversationRecord]: ...


@runtime_checkable
class InvestigationRepository(Protocol):
    def add(
        self,
        *,
        session_id: uuid.UUID,
        investigation_name: str,
        normalized_name: str,
        indicated: bool | None,
        outcome: InvestigationOutcome,
    ) -> uuid.UUID: ...

    def find(self, session_id: uuid.UUID, normalized_name: str) -> InvestigationRecord | None: ...

    def list_for_session(self, session_id: uuid.UUID) -> list[InvestigationRecord]: ...


@runtime_checkable
class PhysicalExamRepository(Protocol):
    def add(self, *, session_id: uuid.UUID, system: str) -> uuid.UUID: ...

    def list_for_session(self, session_id: uuid.UUID) -> list[str]: ...


@runtime_checkable
class SubmissionRepository(Protocol):
    """Differential / diagnosis / management commitments (write-once, locked)."""

    def save_differential(self, session_id: uuid.UUID, differentials: list[str]) -> uuid.UUID: ...

    def save_diagnosis(self, session_id: uuid.UUID, answer: str) -> uuid.UUID: ...

    def save_treatment(self, session_id: uuid.UUID, plan: str) -> uuid.UUID: ...

    def get_differential(self, session_id: uuid.UUID) -> list[str] | None: ...

    def get_diagnosis(self, session_id: uuid.UUID) -> str | None: ...

    def get_treatment(self, session_id: uuid.UUID) -> str | None: ...


@runtime_checkable
class EvaluationRepository(Protocol):
    def exists(self, session_id: uuid.UUID) -> bool: ...

    def save(
        self,
        *,
        session_id: uuid.UUID,
        overall: int,
        section_scores: dict[str, int],
        differential: int,
        efficiency: int,
        rubric_version: int | None,
        feedback: dict,
    ) -> None: ...

    def get(self, session_id: uuid.UUID) -> dict | None: ...


@runtime_checkable
class CaseRepository(Protocol):
    def add(self, case: ClinicalCase) -> ClinicalCase: ...

    def get(self, case_id: uuid.UUID) -> ClinicalCase | None: ...

    def update(self, case: ClinicalCase) -> ClinicalCase: ...

    def list_published(
        self, *, difficulty: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ClinicalCase]: ...


@runtime_checkable
class SessionRepository(Protocol):
    def add(self, session: ClinicalSession) -> ClinicalSession: ...

    def get(self, session_id: uuid.UUID) -> ClinicalSession | None: ...

    def update(self, session: ClinicalSession) -> ClinicalSession: ...

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[ClinicalSession]: ...

    def count_for_user(self, user_id: uuid.UUID) -> int: ...
