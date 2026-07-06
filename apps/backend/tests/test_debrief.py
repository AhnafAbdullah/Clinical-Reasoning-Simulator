"""Debrief assembly (unit) and the gated reveal endpoint (HTTP)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.entities import ConversationRecord, InvestigationRecord
from app.domain.enums import InvestigationOutcome, MessageRole
from app.modules.debrief.use_cases import build_debrief


def _record(role: MessageRole, message: str) -> ConversationRecord:
    return ConversationRecord(
        id=uuid.uuid4(), role=role, message=message, timestamp=datetime.now(timezone.utc)
    )


def _order(name: str, outcome: InvestigationOutcome) -> InvestigationRecord:
    return InvestigationRecord(
        id=uuid.uuid4(),
        investigation_name=name,
        normalized_name=name.lower(),
        indicated=None,
        outcome=outcome,
        ordered_at=datetime.now(timezone.utc),
    )


def _evaluation(diagnosis_score: int = 100) -> dict:
    return {
        "overall_score": 82,
        "section_scores": {
            "history": 67,
            "physical_exam": 100,
            "investigations": 67,
            "diagnosis": diagnosis_score,
            "treatment": 50,
            "communication": 100,
        },
        "differential_score": 50,
        "efficiency_score": 67,
        "feedback": {
            "sections": {
                "history": {
                    "satisfied": ["hpi_radiation", "hpi_character"],
                    "missed": [{"id": "risk_smoking", "description": "Elicited smoking history"}],
                },
                "treatment": {
                    "satisfied": ["tx_aspirin"],
                    "missed": [
                        {
                            "id": "tx_reperfusion",
                            "description": "Arranged reperfusion (PCI or thrombolysis)",
                        }
                    ],
                },
            }
        },
        "generated_at": "2026-07-06T00:00:00+00:00",
    }


def test_debrief_reveals_case_and_maps_reasoning(sample_case) -> None:
    radiation_q = _record(MessageRole.STUDENT, "Does the pain radiate to your arm or jaw?")
    transcript = [
        radiation_q,
        _record(MessageRole.PATIENT, "Yes, it goes into my left arm."),
        _record(MessageRole.STUDENT, "How would you describe the pain — crushing? heavy?"),
    ]
    ordered = [
        _order("ECG", InvestigationOutcome.INFORMATIVE),
        _order("Thyroid Function Tests", InvestigationOutcome.LOW_YIELD),
    ]

    out = build_debrief(
        sample_case,
        evaluation=_evaluation(),
        transcript=transcript,
        ordered=ordered,
        differentials=["ACS", "Pericarditis"],
        diagnosis="STEMI",
        plan="Aspirin, urgent PCI",
    )

    # The reveal carries the case's clinical truth.
    assert "STEMI" in out["reveal"]["diagnosis"]
    assert out["reveal"]["explanation"]
    assert "Unstable angina" in out["reveal"]["differentials"]
    assert out["student"]["verdict"] == "correct"

    # History: satisfied items map to the transcript message that earned them.
    asked_ids = {a["id"]: a for a in out["history"]["asked"]}
    assert asked_ids["hpi_radiation"]["message_id"] == str(radiation_q.id)
    assert [m["id"] for m in out["history"]["missed"]] == ["risk_smoking"]

    # That same message is highlighted in the transcript replay.
    highlighted = {t["id"]: t["highlights"] for t in out["transcript"]}
    assert highlighted[str(radiation_q.id)] == ["Asked whether the pain radiates"]

    # Investigations: annotated from the case; expected-but-not-ordered surfaced.
    by_name = {o["name"]: o for o in out["investigations"]["ordered"]}
    assert by_name["ECG"]["indicated"] is True
    assert "STEMI" in (by_name["ECG"]["interpretation"] or "")
    assert by_name["Thyroid Function Tests"]["indicated"] is False
    missed_names = [m["name"] for m in out["investigations"]["missed"]]
    assert "Troponin I" in missed_names and "Chest X-Ray" in missed_names

    # Management: done/missed beside the ideal plan.
    assert out["management"]["done"] == ["Gave aspirin / antiplatelet"]
    assert out["management"]["missed"] == ["Arranged reperfusion (PCI or thrombolysis)"]
    assert any("PCI" in step for step in out["management"]["ideal"]["emergency"])

    # Teaching points travel through.
    assert out["teaching"]["pearls"]
    assert out["teaching"]["pitfalls"]


def test_debrief_verdict_tiers(sample_case) -> None:
    for score, verdict in ((100, "correct"), (40, "close"), (0, "missed")):
        out = build_debrief(
            sample_case,
            evaluation=_evaluation(diagnosis_score=score),
            transcript=[],
            ordered=[],
            differentials=[],
            diagnosis="?",
            plan="",
        )
        assert out["student"]["verdict"] == verdict


# ── HTTP: the reveal is gated on the evaluation existing ─────────────────────────


def _start_session(client, auth_headers, case_id) -> str:
    resp = client.post("/api/v1/sessions", json={"case_id": str(case_id)}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    client.buffer._active.clear()  # type: ignore[attr-defined]  # free the opening slot
    return resp.json()["data"]["session_id"]


def test_debrief_hidden_while_session_active(client, auth_headers, published_case_id) -> None:
    sid = _start_session(client, auth_headers, published_case_id)
    resp = client.get(f"/api/v1/sessions/{sid}/debrief", headers=auth_headers)
    assert resp.status_code == 404  # never leak clinical truth mid-case


def test_debrief_pending_while_evaluating(client, auth_headers, published_case_id) -> None:
    sid = _start_session(client, auth_headers, published_case_id)
    client.post(
        f"/api/v1/sessions/{sid}/differentials",
        json={"differentials": ["ACS"]},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/sessions/{sid}/diagnosis", json={"diagnosis": "STEMI"}, headers=auth_headers
    )
    client.post(
        f"/api/v1/sessions/{sid}/management", json={"plan": "Aspirin, PCI"}, headers=auth_headers
    )
    resp = client.get(f"/api/v1/sessions/{sid}/debrief", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "PENDING"


def test_debrief_full_payload_once_evaluated(
    client, auth_headers, published_case_id, session
) -> None:
    from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
    from app.infrastructure.repositories.submission_repository import (
        SqlAlchemyEvaluationRepository,
    )

    sid = _start_session(client, auth_headers, published_case_id)
    client.post(
        f"/api/v1/sessions/{sid}/messages",
        json={"message": "Does the pain radiate anywhere, like your arm?"},
        headers=auth_headers,
    )
    client.buffer._active.clear()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/sessions/{sid}/investigations",
        json={"investigation": "ECG"},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/sessions/{sid}/differentials",
        json={"differentials": ["ACS", "Pericarditis"]},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/sessions/{sid}/diagnosis", json={"diagnosis": "STEMI"}, headers=auth_headers
    )
    client.post(
        f"/api/v1/sessions/{sid}/management", json={"plan": "Aspirin, PCI"}, headers=auth_headers
    )

    # Simulate the evaluation worker having finished (the HTTP fake provider
    # cannot produce examiner JSON; the worker path is covered in its own tests).
    session_uuid = uuid.UUID(sid)
    eval_dict = _evaluation()
    SqlAlchemyEvaluationRepository(session).save(
        session_id=session_uuid,
        overall=eval_dict["overall_score"],
        section_scores=eval_dict["section_scores"],
        differential=eval_dict["differential_score"],
        efficiency=eval_dict["efficiency_score"],
        rubric_version=1,
        feedback=eval_dict["feedback"],
    )
    srepo = SqlAlchemySessionRepository(session)
    s = srepo.get(session_uuid)
    assert s is not None
    s.complete()
    srepo.update(s)

    resp = client.get(f"/api/v1/sessions/{sid}/debrief", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "STEMI" in data["reveal"]["diagnosis"]
    assert data["student"]["diagnosis"] == "STEMI"
    assert data["student"]["verdict"] == "correct"
    assert data["scores"]["overall"] == 82
    # The radiation question was asked and is mapped to a transcript message.
    asked = {a["id"] for a in data["history"]["asked"]}
    assert "hpi_radiation" in asked
    assert any(t["highlights"] for t in data["transcript"])
    # The ECG order is annotated from the case.
    assert data["investigations"]["ordered"][0]["name"] == "ECG"
    assert data["investigations"]["ordered"][0]["indicated"] is True
