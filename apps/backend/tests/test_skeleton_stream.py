"""Phase 0B: prove the POST->message_id->SSE-stream plumbing works."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_message_then_stream_by_correlation_id():
    resp = client.post("/api/v1/_skeleton/messages", json={"message": "hello there"})
    assert resp.status_code == 202
    mid = resp.json()["message_id"]
    assert resp.json()["status"] == "GENERATING"

    with client.stream("GET", f"/api/v1/_skeleton/stream?message_id={mid}") as s:
        body = "".join(chunk for chunk in s.iter_text())
    assert "event: token" in body
    assert "event: complete" in body
    assert mid in body
    # tokens stream word-by-word, so reassemble them to check the echo
    import json as _json

    tokens = [
        _json.loads(line[len("data: ") :])["token"]
        for line in body.splitlines()
        if line.startswith("data: ") and '"token"' in line
    ]
    assert "".join(tokens) == "You said: hello there "


def test_unknown_message_id_streams_error():
    with client.stream("GET", "/api/v1/_skeleton/stream?message_id=nope") as s:
        body = "".join(chunk for chunk in s.iter_text())
    assert "UNKNOWN_MESSAGE_ID" in body
