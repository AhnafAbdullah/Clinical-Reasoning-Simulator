"""Debrief assembly: the post-completion case reveal.

Pure functions over the immutable case JSON, the persisted evaluation and the
session's recorded actions — no I/O, no model calls, exhaustively unit-testable
(same philosophy as ``evaluation.scoring``).

The clinical truth (final diagnosis, rationale, ideal management, which tests
were indicated and why) may only be revealed AFTER the evaluation exists; the
router enforces that gate. This module just assembles the story:

  * the reveal        — diagnosis + explanation + the case's own differential
  * the student's run — their commitments and how the diagnosis verdict landed
  * the reasoning gap — history questions asked vs missed, mapped to the
                        transcript messages that earned them
  * investigations    — every order annotated with the case's clinical
                        significance, plus the expected tests never ordered
  * management        — rubric items done/missed beside the ideal plan
  * teaching points   — straight from the case author
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.domain.entities import ConversationRecord, InvestigationRecord
from app.domain.enums import MessageRole
from app.modules.investigations.use_cases import normalize_name


def _matches(a: str, b: str) -> bool:
    """Lenient name match (same rule as evaluation scoring): equal, or one
    normalised name contains the other."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _norm_text(text: str) -> str:
    """Normalise free text for cue matching: lowercase, punctuation → spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _iter_case_investigations(case_json: dict) -> list[dict]:
    section = case_json.get("investigations", {}) or {}
    items: list[dict] = []
    for group in ("laboratory", "imaging", "bedside"):
        items.extend(section.get(group, []) or [])
    return items


def _find_case_investigation(case_json: dict, name: str) -> dict | None:
    for entry in _iter_case_investigations(case_json):
        if _matches(entry.get("name", ""), name):
            return entry
    return None


def _verdict(diagnosis_score: int) -> str:
    """Map the deterministic diagnosis section score to a reveal verdict."""
    if diagnosis_score >= 100:
        return "correct"
    if diagnosis_score > 0:
        return "close"  # named a plausible differential, not the leading diagnosis
    return "missed"


def _match_message(
    item: dict, student_messages: Sequence[ConversationRecord]
) -> ConversationRecord | None:
    """First student message whose text contains one of the item's detection
    cues — the question that (most likely) earned the rubric item."""
    cues = [c for c in (item.get("detection_cues") or []) if _norm_text(str(c))]
    for record in student_messages:
        blob = _norm_text(record.message)
        if any(_norm_text(str(c)) in blob for c in cues):
            return record
    return None


def _history_review(
    case_json: dict,
    feedback: dict,
    transcript: Sequence[ConversationRecord],
) -> tuple[list[dict], list[dict], dict[str, list[str]]]:
    """History rubric items split into asked/missed, plus per-message highlight
    descriptions keyed by message id (for the transcript replay)."""
    rubric_items = case_json.get("rubric", {}).get("history", {}).get("items", []) or []
    section = (feedback.get("sections") or {}).get("history") or {}
    satisfied_ids = set(section.get("satisfied") or [])
    student_messages = [r for r in transcript if r.role == MessageRole.STUDENT]

    asked: list[dict] = []
    missed: list[dict] = []
    highlights: dict[str, list[str]] = {}
    for item in rubric_items:
        entry = {"id": item["id"], "description": item.get("description", "")}
        if item["id"] in satisfied_ids:
            record = _match_message(item, student_messages)
            asked.append({**entry, "message_id": str(record.id) if record else None})
            if record is not None:
                highlights.setdefault(str(record.id), []).append(entry["description"])
        else:
            missed.append(entry)
    return asked, missed, highlights


def _investigation_review(
    case_json: dict, ordered: Sequence[InvestigationRecord]
) -> tuple[list[dict], list[dict]]:
    """Every order annotated from the case, plus expected tests never ordered."""
    reviewed: list[dict] = []
    for record in ordered:
        entry = _find_case_investigation(case_json, record.investigation_name)
        reviewed.append(
            {
                "name": record.investigation_name,
                "outcome": record.outcome.value,
                "indicated": entry.get("indicated") if entry else False,
                "significance": (entry or {}).get("clinical_significance"),
                "interpretation": (entry or {}).get("interpretation"),
                "result": (entry or {}).get("result"),
            }
        )

    expected = case_json.get("rubric", {}).get("investigations", {}).get("expected", []) or []
    ordered_names = [r.investigation_name for r in ordered]
    missed: list[dict] = []
    for name in expected:
        if not any(_matches(name, o) for o in ordered_names):
            entry = _find_case_investigation(case_json, name)
            missed.append(
                {"name": name, "significance": (entry or {}).get("clinical_significance")}
            )
    return reviewed, missed


def _management_review(case_json: dict, feedback: dict) -> dict[str, Any]:
    """Treatment rubric items done/missed beside the case's ideal plan."""
    rubric_items = case_json.get("rubric", {}).get("treatment", {}).get("items", []) or []
    descriptions = {i["id"]: i.get("description", "") for i in rubric_items}
    section = (feedback.get("sections") or {}).get("treatment") or {}
    done = [descriptions[i] for i in (section.get("satisfied") or []) if i in descriptions]
    missed = [m.get("description", "") for m in (section.get("missed") or [])]
    ideal = case_json.get("management", {}) or {}
    return {
        "done": [d for d in done if d],
        "missed": [m for m in missed if m],
        "ideal": {
            "emergency": ideal.get("emergency_management", []) or [],
            "definitive": ideal.get("definitive_management", []) or [],
            "follow_up": ideal.get("follow_up", []) or [],
            "patient_education": ideal.get("patient_education", []) or [],
        },
    }


def build_debrief(
    case_json: dict,
    *,
    evaluation: dict,
    transcript: Sequence[ConversationRecord],
    ordered: Sequence[InvestigationRecord],
    differentials: list[str],
    diagnosis: str,
    plan: str,
) -> dict[str, Any]:
    """Assemble the full debrief payload for a completed, evaluated session."""
    feedback: dict = evaluation.get("feedback") or {}
    meta = case_json.get("metadata", {}) or {}
    case_dx = case_json.get("diagnosis", {}) or {}
    teaching = case_json.get("teaching_points", {}) or {}

    asked, missed_questions, highlights = _history_review(case_json, feedback, transcript)
    reviewed_orders, missed_orders = _investigation_review(case_json, ordered)
    section_scores: dict = evaluation.get("section_scores") or {}

    return {
        "case": {
            "title": meta.get("title", ""),
            "specialty": meta.get("specialty", ""),
            "difficulty": meta.get("difficulty", ""),
        },
        "reveal": {
            "diagnosis": case_dx.get("final_diagnosis", ""),
            "explanation": case_dx.get("explanation", ""),
            "differentials": case_dx.get("differentials", []) or [],
        },
        "student": {
            "diagnosis": diagnosis,
            "differentials": differentials,
            "plan": plan,
            "verdict": _verdict(int(section_scores.get("diagnosis", 0))),
        },
        "scores": {
            "overall": evaluation.get("overall_score", 0),
            "sections": section_scores,
            "differential": evaluation.get("differential_score", 0),
            "efficiency": evaluation.get("efficiency_score", 0),
        },
        "history": {"asked": asked, "missed": missed_questions},
        "investigations": {"ordered": reviewed_orders, "missed": missed_orders},
        "management": _management_review(case_json, feedback),
        "teaching": {
            "pearls": teaching.get("pearls", []) or [],
            "pitfalls": teaching.get("pitfalls", []) or [],
            "learning_objectives": teaching.get("learning_objectives", []) or [],
            "references": teaching.get("references", []) or [],
        },
        "transcript": [
            {
                "id": str(r.id),
                "role": r.role.value,
                "message": r.message,
                "highlights": highlights.get(str(r.id), []),
            }
            for r in transcript
        ],
        "generated_at": evaluation.get("generated_at"),
    }
