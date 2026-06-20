"""Pydantic models for session endpoints (Vol 5 §11/§14)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.domain.entities import ClinicalSession


class SessionCreateRequest(BaseModel):
    # difficulty is intentionally absent: it is a property of the case (Vol 5 §11).
    case_id: uuid.UUID


class SessionCreatedResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    # Correlation id for the streamed opening patient statement (Vol 4D §6).
    opening_message_id: str


class SessionDetail(BaseModel):
    session_id: uuid.UUID
    case_id: uuid.UUID
    status: str
    current_stage: str
    difficulty: str
    started_at: str
    completed_at: str | None

    @classmethod
    def from_entity(cls, s: ClinicalSession) -> "SessionDetail":
        return cls(
            session_id=s.id,
            case_id=s.case_id,
            status=s.status.value,
            current_stage=s.current_stage.value,
            difficulty=s.difficulty.value,
            started_at=s.started_at.isoformat(),
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
        )


class PhysicalExamRequest(BaseModel):
    system: str = Field(min_length=1, max_length=64)
