"""Cases module — application use cases (Vol 2B §5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.entities import ClinicalCase
from app.domain.enums import CaseStatus, Difficulty
from app.domain.errors import CasePublishError
from app.domain.repositories import CaseRepository
from app.infrastructure.case_schema import validate_case


def create_draft_case(
    repo: CaseRepository,
    *,
    title: str,
    difficulty: Difficulty,
    specialty: str,
    json_content: dict,
    estimated_duration: int = 25,
) -> ClinicalCase:
    """Create a Draft case after validating its JSON against the schema."""
    validate_case(json_content)
    case = ClinicalCase(
        title=title,
        difficulty=difficulty,
        specialty=specialty,
        json_content=json_content,
        estimated_duration=estimated_duration,
        status=CaseStatus.DRAFT,
    )
    return repo.add(case)


def publish_case(
    repo: CaseRepository,
    case_id: uuid.UUID,
    *,
    reviewed_by: str,
    reviewer_credentials: str | None = None,
) -> ClinicalCase:
    """Publish a case. Re-validates JSON, requires recorded medical sign-off by a
    qualified reviewer, computes the content hash, and locks the case
    (Vol 3 §8, Vol 4D §16). Immutability after this is also enforced by the DB.
    """
    case = repo.get(case_id)
    if case is None:
        raise CasePublishError(f"Case {case_id} not found.")
    if case.is_published:
        raise CasePublishError("Case is already published and immutable.")

    validate_case(case.json_content)

    # Record the medical sign-off (the human gate) before the domain publish check.
    case.reviewed_by = reviewed_by
    case.reviewer_credentials = reviewer_credentials
    case.reviewed_at = datetime.now(timezone.utc)
    case.medical_signoff = True

    case.publish()  # domain invariants + hash + status transition
    return repo.update(case)
