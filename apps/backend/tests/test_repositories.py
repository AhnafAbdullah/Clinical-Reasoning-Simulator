import uuid

import pytest

from app.domain.entities import ClinicalSession
from app.domain.enums import CaseStatus, Difficulty
from app.domain.errors import CaseImmutableError
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.modules.cases.use_cases import create_draft_case, publish_case


def _publish_sample(session, sample_case):
    repo = SqlAlchemyCaseRepository(session)
    meta = sample_case["metadata"]
    draft = create_draft_case(
        repo,
        title=meta["title"],
        difficulty=Difficulty(meta["difficulty"]),
        specialty=meta["specialty"],
        json_content=sample_case,
    )
    return repo, publish_case(repo, draft.id, reviewed_by="Dr X", reviewer_credentials="MBBS")


def test_publish_and_list(session, sample_case):
    repo, published = _publish_sample(session, sample_case)
    assert published.status == CaseStatus.PUBLISHED
    assert published.content_hash
    listed = repo.list_published()
    assert [c.id for c in listed] == [published.id]
    assert repo.list_published(difficulty="Basic")
    assert repo.list_published(difficulty="Advanced") == []


def test_published_case_is_immutable(session, sample_case):
    repo, published = _publish_sample(session, sample_case)
    case = repo.get(published.id)
    case.title = "tampered"
    with pytest.raises(CaseImmutableError):
        repo.update(case)


def test_published_case_can_be_archived(session, sample_case):
    repo, published = _publish_sample(session, sample_case)
    case = repo.get(published.id)
    case.archive()
    updated = repo.update(case)
    assert updated.status == CaseStatus.ARCHIVED


def test_session_repository_roundtrip(session, sample_case):
    repo, published = _publish_sample(session, sample_case)
    case = repo.get(published.id)
    srepo = SqlAlchemySessionRepository(session)
    clinical = ClinicalSession.start(uuid.uuid4(), case)
    srepo.add(clinical)
    fetched = srepo.get(clinical.id)
    assert fetched is not None
    assert fetched.case_content_hash == published.content_hash
