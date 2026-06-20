"""Investigation ordering with the three-outcome model (Vol 4D §9, Vol 3 §15/§22).

Ordering resolves entirely against the immutable case JSON — no AI invents
results. Each order is persisted with its normalised name, indicated flag and
outcome so efficiency can be graded later. Re-ordering the same test is
idempotent: the original outcome is returned and no duplicate row is written.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.domain.entities import ClinicalSession
from app.domain.enums import InvestigationOutcome
from app.domain.repositories import InvestigationRepository

_LOW_YIELD_DEFAULT = "Within normal limits / non-contributory."
_NOT_AVAILABLE = "This investigation is not available or indicated for this case."

# Outcome -> API status string (Vol 5 §15).
_STATUS = {
    InvestigationOutcome.INFORMATIVE: "AVAILABLE",
    InvestigationOutcome.LOW_YIELD: "LOW_YIELD",
    InvestigationOutcome.NOT_AVAILABLE: "NOT_AVAILABLE",
}


@dataclass(frozen=True)
class OrderResult:
    status: str
    outcome: InvestigationOutcome
    indicated: bool | None
    result: dict[str, Any]
    duplicate: bool


def normalize_name(name: str) -> str:
    """Case/spacing/punctuation-insensitive key for matching and de-duplication."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _iter_case_investigations(case_json: dict) -> list[dict]:
    section = case_json.get("investigations", {}) or {}
    items: list[dict] = []
    for group in ("laboratory", "imaging", "bedside"):
        for item in section.get(group, []) or []:
            items.append(item)
    return items


def _match(case_json: dict, normalized: str) -> dict | None:
    for item in _iter_case_investigations(case_json):
        if normalize_name(str(item.get("name", ""))) == normalized:
            return item
    return None


def _resolve(case_json: dict, raw_name: str) -> tuple[InvestigationOutcome, bool | None, dict]:
    item = _match(case_json, normalize_name(raw_name))
    if item is None:
        return (
            InvestigationOutcome.NOT_AVAILABLE,
            None,
            {"name": raw_name, "message": _NOT_AVAILABLE},
        )
    indicated = bool(item.get("indicated", True))
    if not indicated:
        return (
            InvestigationOutcome.LOW_YIELD,
            False,
            {
                "name": item.get("name", raw_name),
                "result": item.get("low_yield_response", _LOW_YIELD_DEFAULT),
                "interpretation": "Low yield",
            },
        )
    return (
        InvestigationOutcome.INFORMATIVE,
        True,
        {
            "name": item.get("name", raw_name),
            "result": item.get("result"),
            "interpretation": item.get("interpretation"),
            "clinical_significance": item.get("clinical_significance"),
            "normal_range": item.get("normal_range"),
        },
    )


def order_investigation(
    investigations: InvestigationRepository,
    *,
    session: ClinicalSession,
    case_json: dict,
    raw_name: str,
) -> OrderResult:
    normalized = normalize_name(raw_name)
    outcome, indicated, result = _resolve(case_json, raw_name)

    existing = investigations.find(session.id, normalized)
    if existing is not None:
        # Idempotent re-order: return the original outcome, recomputing the result
        # payload from the (immutable) case so the client still gets findings.
        return OrderResult(
            status=_STATUS[existing.outcome],
            outcome=existing.outcome,
            indicated=existing.indicated,
            result=result,
            duplicate=True,
        )

    investigations.add(
        session_id=session.id,
        investigation_name=raw_name,
        normalized_name=normalized,
        indicated=indicated,
        outcome=outcome,
    )
    return OrderResult(
        status=_STATUS[outcome],
        outcome=outcome,
        indicated=indicated,
        result=result,
        duplicate=False,
    )


def list_orders(
    investigations: InvestigationRepository, session_id: uuid.UUID
) -> list[dict[str, Any]]:
    return [
        {
            "investigation_name": r.investigation_name,
            "normalized_name": r.normalized_name,
            "indicated": r.indicated,
            "outcome": r.outcome.value,
            "status": _STATUS[r.outcome],
            "ordered_at": r.ordered_at.isoformat(),
        }
        for r in investigations.list_for_session(session_id)
    ]
