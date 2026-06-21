"""HTTP integration tests for the Phase 3 endpoints (auth, cases, sessions,
conversation, physical exam, investigations) — enveloped responses, ownership,
and the three-outcome investigation model."""

from __future__ import annotations

# ── Auth ─────────────────────────────────────────────────────────────────────────


def test_register_login_me_flow(client) -> None:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password1234", "display_name": "Ann"},
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["success"] is True
    access = body["data"]["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "a@example.com"
    assert me.json()["data"]["role"] == "Student"


def test_duplicate_registration_is_rejected(client) -> None:
    payload = {"email": "dup@example.com", "password": "password1234"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["success"] is False
    assert second.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_and_refresh_rotation(client) -> None:
    client.post(
        "/api/v1/auth/register", json={"email": "b@example.com", "password": "password1234"}
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "b@example.com", "password": "password1234"}
    )
    assert login.status_code == 200
    refresh_token = login.json()["data"]["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    # The presented refresh token is now spent (rotation).
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


def test_protected_endpoint_requires_token(client) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/sessions").status_code == 401


def test_bad_credentials_rejected(client) -> None:
    client.post(
        "/api/v1/auth/register", json={"email": "c@example.com", "password": "password1234"}
    )
    bad = client.post(
        "/api/v1/auth/login", json={"email": "c@example.com", "password": "wrongpassword"}
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHORIZED"


# ── Cases ──────────────────────────────────────────────────────────────────────


def test_cases_list_and_detail_metadata_only(client, auth_headers, published_case_id) -> None:
    listing = client.get("/api/v1/cases", headers=auth_headers)
    assert listing.status_code == 200
    items = listing.json()["data"]
    assert any(c["id"] == str(published_case_id) for c in items)
    # Never expose the clinical JSON.
    assert all("json_content" not in c and "diagnosis" not in c for c in items)

    detail = client.get(f"/api/v1/cases/{published_case_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["difficulty"] == "Basic"


# ── Sessions ───────────────────────────────────────────────────────────────────


def _start_session(client, auth_headers, case_id) -> str:
    resp = client.post("/api/v1/sessions", json={"case_id": str(case_id)}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "ACTIVE"
    assert data["opening_message_id"]
    # Free the opening generation slot so a follow-up turn is not blocked
    # (the background greeting task is asserted separately in the service tests).
    client.buffer._active.clear()  # type: ignore[attr-defined]
    return data["session_id"]


def test_create_get_and_list_session(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)

    got = client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["data"]["current_stage"] == "GREETING"

    listing = client.get("/api/v1/sessions", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["meta"]["total_items"] == 1


def test_delete_session(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)
    resp = client.delete(f"/api/v1/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True
    # It is gone.
    assert client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/sessions", headers=auth_headers).json()["meta"]["total_items"] == 0


def test_cannot_delete_another_users_session(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)
    other = client.post(
        "/api/v1/auth/register",
        json={"email": "thief@example.com", "password": "password1234"},
    ).json()["data"]["access_token"]
    resp = client.delete(
        f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {other}"}
    )
    assert resp.status_code == 404


def test_session_not_found_for_other_user(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)
    # A different user must not see it.
    other = client.post(
        "/api/v1/auth/register",
        json={"email": "intruder@example.com", "password": "password1234"},
    ).json()["data"]["access_token"]
    resp = client.get(
        f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {other}"}
    )
    assert resp.status_code == 404


# ── Conversation ─────────────────────────────────────────────────────────────────


def test_send_message_accepts_and_records(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)
    resp = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "How long have you had the pain?"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    assert resp.json()["data"]["message_id"]

    messages = client.get(f"/api/v1/sessions/{session_id}/messages", headers=auth_headers).json()[
        "data"
    ]
    assert any(m["role"] == "student" for m in messages)


# ── Physical examination ─────────────────────────────────────────────────────────


def test_physical_exam_returns_case_findings(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)
    resp = client.post(
        f"/api/v1/sessions/{session_id}/physical-exam",
        json={"system": "cardiovascular"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["system"] == "cardiovascular"
    assert "heart_sounds" in data["findings"]


def test_physical_exam_unknown_system_404(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)
    resp = client.post(
        f"/api/v1/sessions/{session_id}/physical-exam",
        json={"system": "telepathy"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Investigations ───────────────────────────────────────────────────────────────


def test_investigation_catalog_search(client, auth_headers) -> None:
    resp = client.get("/api/v1/investigations?search=ecg", headers=auth_headers)
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["data"]]
    assert "ECG" in names


def test_investigation_three_outcomes(client, auth_headers, published_case_id) -> None:
    session_id = _start_session(client, auth_headers, published_case_id)

    def order(name: str) -> dict:
        return client.post(
            f"/api/v1/sessions/{session_id}/investigations",
            json={"investigation": name},
            headers=auth_headers,
        ).json()["data"]

    assert order("ECG")["status"] == "AVAILABLE"
    assert order("Thyroid Function Tests")["status"] == "LOW_YIELD"
    assert order("MRI Spine")["status"] == "NOT_AVAILABLE"

    history = client.get(
        f"/api/v1/sessions/{session_id}/investigations", headers=auth_headers
    ).json()["data"]
    assert len(history) == 3
