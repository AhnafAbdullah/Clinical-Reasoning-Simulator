"""SQLAlchemy ORM models — the full Volume 3 schema (corrected edition).

These are persistence models. Domain entities (app.domain.entities) are mapped
to/from a subset of them by the repositories.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    CaseStatus,
    ClinicalStage,
    Difficulty,
    InvestigationOutcome,
    MessageRole,
    SessionStatus,
    UserRole,
)
from app.infrastructure.db.base import Base, JSONType
from sqlalchemy import Uuid


def _enum(py_enum: type) -> SAEnum:
    """VARCHAR-backed enum storing the enum *value* (portable across PG/SQLite)."""
    return SAEnum(
        py_enum,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


_TS = DateTime(timezone=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole), nullable=False, default=UserRole.STUDENT
    )
    display_name: Mapped[str | None] = mapped_column(String(255))
    profile_picture: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_login: Mapped[datetime | None] = mapped_column(_TS)
    deleted_at: Mapped[datetime | None] = mapped_column(_TS)  # soft delete (Vol 3 §4)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(_TS, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(_TS)


class ClinicalCase(Base):
    __tablename__ = "clinical_cases"

    id: Mapped[uuid.UUID] = _pk()
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(_enum(Difficulty), nullable=False, index=True)
    specialty: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[CaseStatus] = mapped_column(
        _enum(CaseStatus), nullable=False, default=CaseStatus.DRAFT, index=True
    )
    estimated_duration: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    json_content: Mapped[dict] = mapped_column(JSONType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Immutability + governance (Vol 3 §8)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewer_credentials: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(_TS)
    medical_signoff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(_TS)


class ClinicalSession(Base):
    __tablename__ = "clinical_sessions"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_cases.id"), nullable=False, index=True
    )
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    case_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        _enum(SessionStatus), nullable=False, default=SessionStatus.CREATED
    )
    current_stage: Mapped[ClinicalStage] = mapped_column(
        _enum(ClinicalStage), nullable=False, default=ClinicalStage.GREETING
    )
    difficulty: Mapped[Difficulty] = mapped_column(_enum(Difficulty), nullable=False)
    started_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(_TS)

    conversation: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(_enum(MessageRole), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)

    session: Mapped[ClinicalSession] = relationship(back_populates="conversation")


class PhysicalExamRequest(Base):
    """Records that a student examined a body system (findings come from the case
    JSON, not from this row). Persisted so the examiner can later credit the
    physical-exam rubric (Vol 4D §8)."""

    __tablename__ = "physical_exam_requests"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    system: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)


class InvestigationOrder(Base):
    __tablename__ = "investigation_orders"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    indicated: Mapped[bool | None] = mapped_column(Boolean)
    outcome: Mapped[InvestigationOutcome] = mapped_column(
        _enum(InvestigationOutcome), nullable=False
    )
    ordered_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)


class DifferentialSubmission(Base):
    __tablename__ = "differential_submissions"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    differentials: Mapped[list] = mapped_column(JSONType, nullable=False)  # ranked list
    submitted_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)


class DiagnosisSubmission(Base):
    __tablename__ = "diagnosis_submissions"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_answer: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)


class TreatmentSubmission(Base):
    __tablename__ = "treatment_submissions"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_plan: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # write-once per session (Vol 3 §25)
        index=True,
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    history_score: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_score: Mapped[int] = mapped_column(Integer, nullable=False)
    investigation_score: Mapped[int] = mapped_column(Integer, nullable=False)
    differential_score: Mapped[int] = mapped_column(Integer, nullable=False)
    diagnosis_score: Mapped[int] = mapped_column(Integer, nullable=False)
    treatment_score: Mapped[int] = mapped_column(Integer, nullable=False)
    communication_score: Mapped[int] = mapped_column(Integer, nullable=False)
    efficiency_score: Mapped[int] = mapped_column(Integer, nullable=False)
    rubric_version: Mapped[int | None] = mapped_column(Integer)
    feedback_json: Mapped[dict] = mapped_column(JSONType, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONType)
    timestamp: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
