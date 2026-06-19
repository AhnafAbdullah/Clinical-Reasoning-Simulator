"""Domain entities. Pure Python: no FastAPI, no SQLAlchemy, no I/O.

These carry the business invariants. Infrastructure maps them to/from ORM rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.enums import (
    CaseStatus,
    ClinicalStage,
    Difficulty,
    SessionStatus,
)
from app.domain.errors import CasePublishError
from app.domain.hashing import content_hash


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


@dataclass
class ClinicalCase:
    """A clinical case. Published cases are immutable (enforced here, in the
    publish use case, and by a database trigger — Vol 3 §8)."""

    title: str
    difficulty: Difficulty
    specialty: str
    json_content: dict
    id: uuid.UUID = field(default_factory=_new_id)
    status: CaseStatus = CaseStatus.DRAFT
    estimated_duration: int = 25
    version: int = 1
    content_hash: str | None = None
    reviewed_by: str | None = None
    reviewer_credentials: str | None = None
    reviewed_at: datetime | None = None
    medical_signoff: bool = False
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    published_at: datetime | None = None

    @property
    def is_published(self) -> bool:
        return self.status == CaseStatus.PUBLISHED

    def compute_hash(self) -> str:
        return content_hash(self.json_content)

    def publish(self) -> None:
        """Transition Validated -> Published. Requires recorded medical sign-off
        by a qualified reviewer (Vol 3 §8, Vol 4D §16). Mutates in place.

        Schema validation of ``json_content`` happens in the publish use case
        (infrastructure), before this is called.
        """
        if self.status not in (CaseStatus.DRAFT, CaseStatus.VALIDATED):
            raise CasePublishError(f"Cannot publish a case in status {self.status.value}.")
        if not self.medical_signoff:
            raise CasePublishError("medical_signoff is required before publication.")
        if not self.reviewed_by:
            raise CasePublishError("reviewed_by is required before publication.")
        self.content_hash = self.compute_hash()
        self.status = CaseStatus.PUBLISHED
        self.published_at = _utcnow()
        self.updated_at = _utcnow()

    def archive(self) -> None:
        if self.status != CaseStatus.PUBLISHED:
            raise CasePublishError("Only published cases can be archived.")
        self.status = CaseStatus.ARCHIVED
        self.updated_at = _utcnow()


@dataclass
class ClinicalSession:
    """One attempt at a case. Binds to the exact case bytes it ran against."""

    user_id: uuid.UUID
    case_id: uuid.UUID
    case_version: int
    case_content_hash: str
    difficulty: Difficulty
    id: uuid.UUID = field(default_factory=_new_id)
    status: SessionStatus = SessionStatus.CREATED
    current_stage: ClinicalStage = ClinicalStage.GREETING
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None

    @classmethod
    def start(cls, user_id: uuid.UUID, case: ClinicalCase) -> "ClinicalSession":
        """Create an ACTIVE session for a published case, snapshotting its
        version, content hash, and difficulty (Vol 3 §20)."""
        if not case.is_published:
            raise CasePublishError("Sessions can only be started on published cases.")
        if case.content_hash is None:
            raise CasePublishError("Published case is missing its content hash.")
        return cls(
            user_id=user_id,
            case_id=case.id,
            case_version=case.version,
            case_content_hash=case.content_hash,
            difficulty=case.difficulty,
            status=SessionStatus.ACTIVE,
            current_stage=ClinicalStage.GREETING,
        )
