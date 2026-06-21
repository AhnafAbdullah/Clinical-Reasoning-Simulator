"""Daily Challenge logic: a deterministic case-of-the-day and streak maths.

Pure functions — no I/O — so the date-seeded pick and the streak counter are
trivially testable and reproducible.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date, timedelta

from app.domain.entities import ClinicalCase


def case_of_the_day(cases: Sequence[ClinicalCase], on: date) -> ClinicalCase:
    """Pick the same case for everyone on a given day. Stable across restarts:
    cases are ordered by id and indexed by a hash of the ISO date."""
    if not cases:
        raise ValueError("no published cases available")
    ordered = sorted(cases, key=lambda c: str(c.id))
    seed = int(hashlib.sha256(on.isoformat().encode()).hexdigest(), 16)
    return ordered[seed % len(ordered)]


def compute_streak(attempt_dates: Sequence[date], today: date) -> int:
    """Consecutive days played, ending today (or yesterday if today not yet
    played, so an active streak isn't shown as broken before the day is over)."""
    days = set(attempt_dates)
    if today in days:
        cursor = today
    elif (today - timedelta(days=1)) in days:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
