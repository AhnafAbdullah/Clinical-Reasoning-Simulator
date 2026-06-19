"""Repository interfaces (ports). Implementations live in infrastructure.

The application layer depends on these Protocols, never on SQLAlchemy.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.domain.entities import ClinicalCase, ClinicalSession


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
