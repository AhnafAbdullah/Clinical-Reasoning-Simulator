"""Analytics aggregation (Vol 3 §26, Vol 5 §19)."""

from __future__ import annotations

import uuid

from app.infrastructure.db import models as m
from app.infrastructure.repositories.analytics_repository import SqlAlchemyAnalyticsRepository


def _session_row(user_id: uuid.UUID, difficulty: str) -> m.ClinicalSession:
    return m.ClinicalSession(
        user_id=user_id,
        case_id=uuid.uuid4(),
        case_version=1,
        case_content_hash="x" * 64,
        status="COMPLETED",
        current_stage="MANAGEMENT",
        difficulty=difficulty,
    )


def _eval_row(session_id: uuid.UUID, overall: int) -> m.Evaluation:
    return m.Evaluation(
        session_id=session_id,
        overall_score=overall,
        history_score=overall,
        exam_score=overall,
        investigation_score=overall,
        differential_score=overall,
        diagnosis_score=overall,
        treatment_score=overall,
        communication_score=overall,
        efficiency_score=overall,
        feedback_json={},
    )


def test_analytics_summary_aggregates(session) -> None:
    user_id = uuid.uuid4()
    for difficulty, score in [("Basic", 80), ("Basic", 60), ("Advanced", 50)]:
        s = _session_row(user_id, difficulty)
        session.add(s)
        session.flush()
        session.add(_eval_row(s.id, score))
        session.add(
            m.InvestigationOrder(
                session_id=s.id,
                investigation_name="ECG",
                normalized_name="ecg",
                indicated=True,
                outcome="INFORMATIVE",
            )
        )
    session.flush()

    summary = SqlAlchemyAnalyticsRepository(session).summary(user_id)
    assert summary["cases_completed"] == 3
    assert summary["average_score"] == round((80 + 60 + 50) / 3)
    assert summary["by_difficulty"]["Basic"]["count"] == 2
    assert summary["by_difficulty"]["Basic"]["average_score"] == 70
    assert summary["investigation_usage"]["total_ordered"] == 3
    assert summary["investigation_usage"]["informative_pct"] == 100
    assert len(summary["score_trend"]) == 3


def test_analytics_empty_for_new_user(session) -> None:
    summary = SqlAlchemyAnalyticsRepository(session).summary(uuid.uuid4())
    assert summary["cases_completed"] == 0
    assert summary["average_score"] == 0


def test_analytics_endpoint(client, auth_headers) -> None:
    resp = client.get("/api/v1/users/me/analytics", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["cases_completed"] == 0
