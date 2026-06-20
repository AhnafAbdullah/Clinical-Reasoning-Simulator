"""Pydantic models for conversation endpoints (Vol 5 §12)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.domain.entities import ConversationRecord


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class MessageAccepted(BaseModel):
    message_id: str
    status: str = "GENERATING"


class MessageItem(BaseModel):
    id: uuid.UUID
    role: str
    message: str
    timestamp: str

    @classmethod
    def from_record(cls, r: ConversationRecord) -> "MessageItem":
        return cls(id=r.id, role=r.role.value, message=r.message, timestamp=r.timestamp.isoformat())
