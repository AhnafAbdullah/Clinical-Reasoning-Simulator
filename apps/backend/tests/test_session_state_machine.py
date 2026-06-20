"""Session state-machine rules (Vol 4D §4-5): open working phase, then strictly
ordered commitment points."""

from __future__ import annotations

import uuid

import pytest

from app.domain.entities import ClinicalSession
from app.domain.enums import ClinicalStage, Difficulty, SessionStatus
from app.domain.errors import InvalidStateTransition, SessionCompletedError


def _session() -> ClinicalSession:
    return ClinicalSession(
        user_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        case_version=1,
        case_content_hash="x" * 64,
        difficulty=Difficulty.BASIC,
        status=SessionStatus.ACTIVE,
        current_stage=ClinicalStage.GREETING,
    )


def test_reach_stage_is_monotonic() -> None:
    s = _session()
    s.reach_stage(ClinicalStage.INVESTIGATIONS)
    assert s.current_stage == ClinicalStage.INVESTIGATIONS
    # Revisiting history must not move the high-water mark backward.
    s.reach_stage(ClinicalStage.HISTORY)
    assert s.current_stage == ClinicalStage.INVESTIGATIONS


def test_working_actions_allowed_through_investigations() -> None:
    s = _session()
    s.reach_stage(ClinicalStage.INVESTIGATIONS)
    s.ensure_working_action("order an investigation")  # no raise


def test_commitment_order_enforced() -> None:
    s = _session()
    # Cannot submit diagnosis before differential.
    with pytest.raises(InvalidStateTransition):
        s.submit_diagnosis()
    s.submit_differential()
    assert s.current_stage == ClinicalStage.FINAL_DIAGNOSIS
    # Differential is one-shot.
    with pytest.raises(InvalidStateTransition):
        s.submit_differential()
    s.submit_diagnosis()
    assert s.current_stage == ClinicalStage.MANAGEMENT


def test_working_phase_closes_after_final_diagnosis() -> None:
    s = _session()
    s.submit_differential()
    s.submit_diagnosis()  # stage -> MANAGEMENT, working phase closed
    with pytest.raises(InvalidStateTransition):
        s.ensure_working_action("send a message")


def test_management_then_evaluating_then_completed() -> None:
    s = _session()
    s.submit_differential()
    s.submit_diagnosis()
    s.submit_management()
    assert s.status == SessionStatus.EVALUATING
    s.complete()
    assert s.status == SessionStatus.COMPLETED
    assert s.completed_at is not None


def test_actions_blocked_once_not_active() -> None:
    s = _session()
    s.status = SessionStatus.COMPLETED
    with pytest.raises(SessionCompletedError):
        s.ensure_working_action("send a message")
