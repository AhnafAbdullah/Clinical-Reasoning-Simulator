"""HTTP tests for the commitment endpoints: ordered, irreversible commitment
points and the evaluation lifecycle (Vol 5 §16-18)."""

from __future__ import annotations


def _start_session(client, auth_headers, case_id) -> str:
    resp = client.post("/api/v1/sessions", json={"case_id": str(case_id)}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    client.buffer._active.clear()  # type: ignore[attr-defined]  # free the opening slot
    return resp.json()["data"]["session_id"]


def test_full_commitment_flow_to_evaluating(client, auth_headers, published_case_id) -> None:
    sid = _start_session(client, auth_headers, published_case_id)

    diff = client.post(
        f"/api/v1/sessions/{sid}/differentials",
        json={"differentials": ["Acute coronary syndrome", "Pericarditis"]},
        headers=auth_headers,
    )
    assert diff.status_code == 200
    assert diff.json()["data"]["current_stage"] == "FINAL_DIAGNOSIS"

    dx = client.post(
        f"/api/v1/sessions/{sid}/diagnosis",
        json={"diagnosis": "STEMI"},
        headers=auth_headers,
    )
    assert dx.status_code == 200
    assert dx.json()["data"]["current_stage"] == "MANAGEMENT"

    mgmt = client.post(
        f"/api/v1/sessions/{sid}/management",
        json={"plan": "Aspirin and primary PCI."},
        headers=auth_headers,
    )
    assert mgmt.status_code == 202
    assert mgmt.json()["data"]["status"] == "EVALUATING"

    # Evaluation is decoupled; the fake provider cannot produce examiner JSON, so
    # it stays PENDING (the completed path is covered in test_evaluation_service).
    ev = client.get(f"/api/v1/sessions/{sid}/evaluation", headers=auth_headers)
    assert ev.status_code == 200
    assert ev.json()["data"]["status"] == "PENDING"


def test_commitment_order_is_enforced(client, auth_headers, published_case_id) -> None:
    sid = _start_session(client, auth_headers, published_case_id)
    # Diagnosis before a differential is rejected.
    resp = client.post(
        f"/api/v1/sessions/{sid}/diagnosis",
        json={"diagnosis": "STEMI"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_management_closes_working_phase(client, auth_headers, published_case_id) -> None:
    sid = _start_session(client, auth_headers, published_case_id)
    client.post(
        f"/api/v1/sessions/{sid}/differentials",
        json={"differentials": ["ACS"]},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/sessions/{sid}/diagnosis", json={"diagnosis": "STEMI"}, headers=auth_headers
    )
    # After the final diagnosis the working phase is closed: no more messages.
    msg = client.post(
        f"/api/v1/sessions/{sid}/messages",
        json={"message": "One more question?"},
        headers=auth_headers,
    )
    assert msg.status_code == 409
