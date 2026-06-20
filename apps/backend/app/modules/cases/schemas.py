"""Pydantic models for case endpoints (Vol 5 §10).

Students only ever see metadata; the clinical JSON is never exposed (Vol 5 §28).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.domain.entities import ClinicalCase


class CaseSummary(BaseModel):
    id: uuid.UUID
    title: str
    difficulty: str
    specialty: str
    estimated_duration: int

    @classmethod
    def from_entity(cls, c: ClinicalCase) -> "CaseSummary":
        return cls(
            id=c.id,
            title=c.title,
            difficulty=c.difficulty.value,
            specialty=c.specialty,
            estimated_duration=c.estimated_duration,
        )
