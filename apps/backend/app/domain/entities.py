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
    InvestigationOutcome,
    MessageRole,
    SessionStatus,
    UserRole,
)
from app.domain.errors import CasePublishError, InvalidStateTransition, SessionCompletedError
from app.domain.hashing import content_hash


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


@dataclass(frozen=True)
class ConversationRecord:
    """A persisted conversation turn (read model for transcript assembly)."""

    id: uuid.UUID
    role: MessageRole
    message: str
    timestamp: datetime


@dataclass(frozen=True)
class InvestigationRecord:
    """A persisted investigation order with its case-derived outcome."""

    id: uuid.UUID
    investigation_name: str
    normalized_name: str
    indicated: bool | None
    outcome: InvestigationOutcome
    ordered_at: datetime


@dataclass
class User:
    """An application user. Authentication material lives here; the role governs
    authorization (Vol 5 §5/§8)."""

    email: str
    id: uuid.UUID = field(default_factory=_new_id)
    password_hash: str | None = None
    google_id: str | None = None
    role: UserRole = UserRole.STUDENT
    display_name: str | None = None
    profile_picture: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    last_login: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


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

    # ── State machine (Vol 4D §4-5) ─────────────────────────────────────────────
    # Two parts: an *open working phase* (history / exam / investigations may be
    # interleaved and revisited freely) and *sequential commitment points*
    # (differential -> final diagnosis -> management, strictly ordered and
    # irreversible). The working phase closes when the final diagnosis is
    # submitted. A completed session is read-only.

    # Stages whose actions may be performed while the working phase is open.
    _WORKING_OPEN = (
        ClinicalStage.GREETING,
        ClinicalStage.HISTORY,
        ClinicalStage.PHYSICAL_EXAM,
        ClinicalStage.INVESTIGATIONS,
        ClinicalStage.DIFFERENTIAL,
        ClinicalStage.FINAL_DIAGNOSIS,
    )

    @property
    def is_working_phase_open(self) -> bool:
        """True while history/exam/investigations may still be performed."""
        return self.status == SessionStatus.ACTIVE and self.current_stage in self._WORKING_OPEN

    def ensure_working_action(self, action: str) -> None:
        """Guard for conversation / physical exam / investigation ordering."""
        if self.status != SessionStatus.ACTIVE:
            raise SessionCompletedError(
                f"Cannot {action}: session is {self.status.value}, not ACTIVE."
            )
        if not self.is_working_phase_open:
            raise InvalidStateTransition(
                f"Cannot {action}: the working phase closed at final-diagnosis submission."
            )

    def reach_stage(self, stage: ClinicalStage) -> None:
        """Monotonically advance ``current_stage`` during the working phase.

        Performing an action never moves the stage *backward* (revisiting history
        while at INVESTIGATIONS keeps the stage at INVESTIGATIONS), so progress is
        a high-water mark, not the last thing the student did."""
        order = list(ClinicalStage)
        if order.index(stage) > order.index(self.current_stage):
            self.current_stage = stage

    def submit_differential(self) -> None:
        """First commitment point: lock the ranked differential, advance to the
        final-diagnosis stage. Cannot be repeated or skipped ahead to."""
        if self.status != SessionStatus.ACTIVE:
            raise SessionCompletedError("Session is not ACTIVE.")
        order = list(ClinicalStage)
        if order.index(self.current_stage) >= order.index(ClinicalStage.FINAL_DIAGNOSIS):
            raise InvalidStateTransition("Differential has already been submitted.")
        self.current_stage = ClinicalStage.FINAL_DIAGNOSIS

    def submit_diagnosis(self) -> None:
        """Second commitment point: requires a submitted differential. Locks the
        diagnosis, advances to management, and closes the working phase."""
        if self.status != SessionStatus.ACTIVE:
            raise SessionCompletedError("Session is not ACTIVE.")
        if self.current_stage != ClinicalStage.FINAL_DIAGNOSIS:
            raise InvalidStateTransition(
                "A ranked differential must be submitted before the final diagnosis."
            )
        self.current_stage = ClinicalStage.MANAGEMENT

    def submit_management(self) -> None:
        """Third commitment point: requires a submitted diagnosis. Moves the
        session into EVALUATING (the evaluation runs asynchronously)."""
        if self.status != SessionStatus.ACTIVE:
            raise SessionCompletedError("Session is not ACTIVE.")
        if self.current_stage != ClinicalStage.MANAGEMENT:
            raise InvalidStateTransition(
                "A final diagnosis must be submitted before the management plan."
            )
        self.status = SessionStatus.EVALUATING

    def complete(self) -> None:
        """Evaluation written: EVALUATING -> COMPLETED (Vol 4D §12)."""
        if self.status != SessionStatus.EVALUATING:
            raise InvalidStateTransition("Only an EVALUATING session can be completed.")
        self.status = SessionStatus.COMPLETED
        self.completed_at = _utcnow()
