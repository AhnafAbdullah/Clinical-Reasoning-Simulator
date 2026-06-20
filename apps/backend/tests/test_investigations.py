"""Three-outcome investigation ordering against the immutable case (Vol 4D §9)."""

from __future__ import annotations

import uuid

from app.domain.entities import ClinicalSession
from app.domain.enums import Difficulty, InvestigationOutcome, SessionStatus
from app.infrastructure.db.base import Base  # noqa: F401  (ensures models import)
from app.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationRepository,
)
from app.modules.investigations.use_cases import normalize_name, order_investigation


def _session() -> ClinicalSession:
    return ClinicalSession(
        user_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        case_version=1,
        case_content_hash="x" * 64,
        difficulty=Difficulty.BASIC,
        status=SessionStatus.ACTIVE,
    )


def test_normalize_name() -> None:
    assert normalize_name("  Chest  X-Ray ") == "chest x ray"
    assert normalize_name("ECG") == "ecg"


def test_indicated_test_is_informative(session, sample_case) -> None:
    repo = SqlAlchemyInvestigationRepository(session)
    s = _session()
    res = order_investigation(repo, session=s, case_json=sample_case, raw_name="ECG")
    assert res.outcome == InvestigationOutcome.INFORMATIVE
    assert res.status == "AVAILABLE"
    assert "ST elevation" in res.result["result"]
    assert res.duplicate is False


def test_non_indicated_test_is_low_yield(session, sample_case) -> None:
    repo = SqlAlchemyInvestigationRepository(session)
    s = _session()
    res = order_investigation(
        repo, session=s, case_json=sample_case, raw_name="Thyroid Function Tests"
    )
    assert res.outcome == InvestigationOutcome.LOW_YIELD
    assert res.indicated is False


def test_unknown_test_is_not_available(session, sample_case) -> None:
    repo = SqlAlchemyInvestigationRepository(session)
    s = _session()
    res = order_investigation(repo, session=s, case_json=sample_case, raw_name="MRI Spine")
    assert res.outcome == InvestigationOutcome.NOT_AVAILABLE
    assert res.status == "NOT_AVAILABLE"


def test_reorder_is_idempotent(session, sample_case) -> None:
    repo = SqlAlchemyInvestigationRepository(session)
    s = _session()
    first = order_investigation(repo, session=s, case_json=sample_case, raw_name="ECG")
    second = order_investigation(repo, session=s, case_json=sample_case, raw_name="  ecg ")
    assert first.duplicate is False
    assert second.duplicate is True
    assert len(repo.list_for_session(s.id)) == 1
