"""Read-only analytics aggregation over completed sessions + evaluations (Vol 3 §26).

Pure SQL aggregation; no model calls. Returns plain dicts the analytics use case
shapes into the API response.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db import models as m


class SqlAlchemyAnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def summary(self, user_id: uuid.UUID) -> dict:
        ev = m.Evaluation
        cs = m.ClinicalSession

        base = (
            select(ev.overall_score, cs.difficulty, ev.generated_at)
            .join(cs, ev.session_id == cs.id)
            .where(cs.user_id == user_id)
            .order_by(ev.generated_at.asc())
        )
        rows = self._s.execute(base).all()

        completed = len(rows)
        average = round(sum(r.overall_score for r in rows) / completed) if completed else 0

        by_difficulty: dict[str, dict[str, int]] = {}
        for r in rows:
            key = r.difficulty.value if hasattr(r.difficulty, "value") else str(r.difficulty)
            bucket = by_difficulty.setdefault(key, {"count": 0, "total": 0})
            bucket["count"] += 1
            bucket["total"] += r.overall_score
        by_difficulty_out = {
            k: {"count": v["count"], "average_score": round(v["total"] / v["count"])}
            for k, v in by_difficulty.items()
        }

        trend = [{"date": r.generated_at.isoformat(), "score": r.overall_score} for r in rows[-20:]]

        # Investigation usage: how many orders, and how efficient (informative share).
        total_orders = (
            self._s.scalar(
                select(func.count())
                .select_from(m.InvestigationOrder)
                .join(cs, m.InvestigationOrder.session_id == cs.id)
                .where(cs.user_id == user_id)
            )
            or 0
        )
        informative = (
            self._s.scalar(
                select(func.count())
                .select_from(m.InvestigationOrder)
                .join(cs, m.InvestigationOrder.session_id == cs.id)
                .where(
                    cs.user_id == user_id,
                    m.InvestigationOrder.outcome == "INFORMATIVE",
                )
            )
            or 0
        )

        return {
            "cases_completed": completed,
            "average_score": average,
            "by_difficulty": by_difficulty_out,
            "score_trend": trend,
            "investigation_usage": {
                "total_ordered": int(total_orders),
                "informative": int(informative),
                "informative_pct": round(100 * informative / total_orders) if total_orders else 0,
            },
        }
