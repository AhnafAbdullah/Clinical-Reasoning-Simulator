"""Daily Challenge: deterministic case-of-the-day, streaks, one-attempt-per-day."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from app.domain.entities import ClinicalCase
from app.domain.enums import Difficulty
from app.modules.daily.use_cases import case_of_the_day, compute_streak


def _case(cid: str) -> ClinicalCase:
    return ClinicalCase(
        id=uuid.UUID(cid),
        title=f"Case {cid[:4]}",
        difficulty=Difficulty.BASIC,
        specialty="Internal Medicine",
        json_content={},
    )


def test_case_of_the_day_is_deterministic_per_date() -> None:
    cases = [_case(f"{i:032x}") for i in range(5)]
    day = date(2026, 6, 21)
    assert case_of_the_day(cases, day).id == case_of_the_day(cases, day).id
    # Different day can (usually) differ, but the same day is always identical.
    assert case_of_the_day(cases, day).id == case_of_the_day(list(reversed(cases)), day).id


def test_case_of_the_day_covers_the_pool() -> None:
    cases = [_case(f"{i:032x}") for i in range(5)]
    picked = {case_of_the_day(cases, date(2026, 1, 1) + timedelta(days=d)).id for d in range(60)}
    assert len(picked) == 5  # every case surfaces across two months


def test_compute_streak() -> None:
    today = date(2026, 6, 21)
    assert compute_streak([], today) == 0
    assert compute_streak([today], today) == 1
    assert compute_streak([today, today - timedelta(days=1), today - timedelta(days=2)], today) == 3
    # A gap breaks it.
    assert compute_streak([today, today - timedelta(days=2)], today) == 1
    # Yesterday-only still counts as an active streak (today not played yet).
    assert compute_streak([today - timedelta(days=1)], today) == 1
    # Two days ago with nothing since is broken.
    assert compute_streak([today - timedelta(days=2)], today) == 0


# ── HTTP ─────────────────────────────────────────────────────────────────────────


def test_daily_status_then_start_then_resume(client, auth_headers, published_case_id) -> None:
    status = client.get("/api/v1/daily", headers=auth_headers).json()["data"]
    assert status["attempted"] is False
    assert status["streak"] == 0
    assert status["difficulty"]  # meta present
    assert "title" not in status  # surprise preserved

    started = client.post("/api/v1/daily/start", headers=auth_headers)
    assert started.status_code == 200
    d = started.json()["data"]
    assert d["resumed"] is False
    assert d["opening_message_id"]
    assert d["streak"] == 1
    sid = d["session_id"]
    client.buffer._active.clear()  # type: ignore[attr-defined]  # free the opening slot

    after = client.get("/api/v1/daily", headers=auth_headers).json()["data"]
    assert after["attempted"] is True
    assert after["session_id"] == sid

    # Second start the same day resumes the same session — one attempt per day.
    again = client.post("/api/v1/daily/start", headers=auth_headers).json()["data"]
    assert again["resumed"] is True
    assert again["session_id"] == sid
