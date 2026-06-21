"""Patient presentation (avatar) info + affect heuristic (Phase B)."""

from __future__ import annotations

import pytest

from app.modules.sessions.use_cases import _derive_affect, patient_presentation


@pytest.mark.parametrize(
    "personality,communication,expected",
    [
        ("Stoic, plays down symptoms", "Brief answers", "stoic"),
        ("Anxious, frightened", "Speaks quickly", "anxious"),
        ("In significant distress from pain", "Clutching abdomen", "in_pain"),
        ("Drowsy, irritable", "Slow, confused", "drowsy"),
        ("Breathless", "Pursed-lip breathing, short phrases", "breathless"),
        ("Cooperative and relaxed", "Clear answers", "calm"),
    ],
)
def test_affect_heuristic(personality: str, communication: str, expected: str) -> None:
    assert _derive_affect(personality, communication) == expected


def test_patient_presentation_shape(sample_case) -> None:
    p = patient_presentation(sample_case)
    assert p["name"] == sample_case["patient"]["name"]
    assert p["age"] == sample_case["patient"]["age"]
    assert p["gender"] == "male"
    assert p["affect"] in {"calm", "anxious", "in_pain", "drowsy", "stoic", "breathless"}


def test_patient_presentation_endpoint(client, auth_headers, published_case_id) -> None:
    sid = client.post(
        "/api/v1/sessions", json={"case_id": str(published_case_id)}, headers=auth_headers
    ).json()["data"]["session_id"]
    resp = client.get(f"/api/v1/sessions/{sid}/patient", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["gender"] == "male"
    assert "affect" in data
