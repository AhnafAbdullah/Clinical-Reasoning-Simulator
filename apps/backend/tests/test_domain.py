import uuid

import pytest

from app.domain.entities import ClinicalCase, ClinicalSession
from app.domain.enums import CaseStatus, ClinicalStage, Difficulty, SessionStatus
from app.domain.errors import CasePublishError


def _draft() -> ClinicalCase:
    return ClinicalCase(
        title="t",
        difficulty=Difficulty.BASIC,
        specialty="Internal Medicine",
        json_content={"k": "v"},
    )


def test_publish_requires_signoff():
    case = _draft()
    case.reviewed_by = "Dr X"
    with pytest.raises(CasePublishError):
        case.publish()


def test_publish_requires_reviewer():
    case = _draft()
    case.medical_signoff = True
    with pytest.raises(CasePublishError):
        case.publish()


def test_publish_sets_hash_and_status():
    case = _draft()
    case.medical_signoff = True
    case.reviewed_by = "Dr X"
    case.publish()
    assert case.status == CaseStatus.PUBLISHED
    assert case.content_hash == case.compute_hash()
    assert case.published_at is not None


def test_cannot_publish_twice():
    case = _draft()
    case.medical_signoff = True
    case.reviewed_by = "Dr X"
    case.publish()
    with pytest.raises(CasePublishError):
        case.publish()


def test_session_start_requires_published():
    case = _draft()
    with pytest.raises(CasePublishError):
        ClinicalSession.start(uuid.uuid4(), case)


def test_session_start_snapshots_case():
    case = _draft()
    case.medical_signoff = True
    case.reviewed_by = "Dr X"
    case.publish()
    s = ClinicalSession.start(uuid.uuid4(), case)
    assert s.status == SessionStatus.ACTIVE
    assert s.current_stage == ClinicalStage.GREETING
    assert s.case_content_hash == case.content_hash
    assert s.case_version == case.version
    assert s.difficulty == case.difficulty
