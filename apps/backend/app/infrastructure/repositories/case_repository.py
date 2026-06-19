"""SQLAlchemy implementation of CaseRepository, mapping ORM rows to domain entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import ClinicalCase
from app.domain.enums import CaseStatus
from app.domain.errors import CaseImmutableError
from app.infrastructure.db import models as m


def _to_domain(row: m.ClinicalCase) -> ClinicalCase:
    return ClinicalCase(
        id=row.id,
        title=row.title,
        difficulty=row.difficulty,
        specialty=row.specialty,
        json_content=row.json_content,
        status=row.status,
        estimated_duration=row.estimated_duration,
        version=row.version,
        content_hash=row.content_hash,
        reviewed_by=row.reviewed_by,
        reviewer_credentials=row.reviewer_credentials,
        reviewed_at=row.reviewed_at,
        medical_signoff=row.medical_signoff,
        created_at=row.created_at,
        updated_at=row.updated_at,
        published_at=row.published_at,
    )


def _apply(row: m.ClinicalCase, case: ClinicalCase) -> None:
    row.title = case.title
    row.difficulty = case.difficulty
    row.specialty = case.specialty
    row.json_content = case.json_content
    row.status = case.status
    row.estimated_duration = case.estimated_duration
    row.version = case.version
    row.content_hash = case.content_hash
    row.reviewed_by = case.reviewed_by
    row.reviewer_credentials = case.reviewer_credentials
    row.reviewed_at = case.reviewed_at
    row.medical_signoff = case.medical_signoff
    row.published_at = case.published_at


class SqlAlchemyCaseRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, case: ClinicalCase) -> ClinicalCase:
        row = m.ClinicalCase(id=case.id)
        _apply(row, case)
        self._s.add(row)
        self._s.flush()
        return _to_domain(row)

    def get(self, case_id: uuid.UUID) -> ClinicalCase | None:
        row = self._s.get(m.ClinicalCase, case_id)
        return _to_domain(row) if row else None

    def update(self, case: ClinicalCase) -> ClinicalCase:
        row = self._s.get(m.ClinicalCase, case.id)
        if row is None:
            raise LookupError(f"Case {case.id} not found")
        # App-level mirror of the DB immutability trigger (Vol 3 §8): once a row is
        # Published, the only permitted change is Published -> Archived with content
        # unchanged. The Validated -> Published transition itself is still allowed
        # because the persisted row is not yet Published at that point.
        if row.status == CaseStatus.PUBLISHED:
            archiving = (
                case.status == CaseStatus.ARCHIVED
                and case.json_content == row.json_content
                and case.content_hash == row.content_hash
                and case.title == row.title
                and case.difficulty == row.difficulty
                and case.version == row.version
            )
            if not archiving:
                raise CaseImmutableError(
                    "Published clinical cases are immutable (only Published->Archived allowed)."
                )
        _apply(row, case)
        self._s.flush()
        return _to_domain(row)

    def list_published(
        self, *, difficulty: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ClinicalCase]:
        stmt = select(m.ClinicalCase).where(m.ClinicalCase.status == CaseStatus.PUBLISHED)
        if difficulty:
            stmt = stmt.where(m.ClinicalCase.difficulty == difficulty)
        stmt = stmt.order_by(m.ClinicalCase.created_at.desc()).limit(limit).offset(offset)
        return [_to_domain(r) for r in self._s.scalars(stmt)]
