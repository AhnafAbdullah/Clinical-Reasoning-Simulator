"""Evaluation workflow (Vol 4D §12, Vol 4C §6).

The Examiner agent runs a single free-text extraction pass (history /
communication / treatment items → satisfied + evidence). Everything else is
deterministic. ``scoring.aggregate`` then turns the per-item judgements into the
section/overall/differential/efficiency scores and the consultant report.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.domain.ai import ChatMessage
from app.modules.ai.aios import AIOS
from app.modules.evaluation.scoring import EvaluationResult, ItemDetection, aggregate

EXAMINER_AGENT = "examiner"

# Rubric sections whose items are judged from free text by the Examiner.
_FREE_TEXT_SECTIONS = ("history", "communication", "treatment")


def collect_free_text_items(case_json: dict) -> list[dict[str, str]]:
    rubric = case_json.get("rubric", {})
    items: list[dict[str, str]] = []
    for section in _FREE_TEXT_SECTIONS:
        for item in rubric.get(section, {}).get("items", []) or []:
            items.append({"id": item["id"], "description": item.get("description", "")})
    return items


def build_examiner_transcript(
    conversation: list[ChatMessage], *, management_plan: str | None
) -> list[dict[str, str]]:
    """The Examiner sees the consultation plus the student's written management
    plan (so treatment items are detectable from one transcript)."""
    turns = [{"role": m.role.value, "content": m.content} for m in conversation]
    if management_plan:
        turns.append({"role": "student", "content": f"Management plan: {management_plan}"})
    return turns


def _parse_detections(text: str) -> dict[str, ItemDetection]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    data = json.loads(cleaned)
    detections: dict[str, ItemDetection] = {}
    for raw in data.get("items", []) or []:
        item_id = raw.get("id")
        if not item_id:
            continue
        detections[item_id] = ItemDetection(
            id=item_id,
            satisfied=bool(raw.get("satisfied")),
            evidence=str(raw.get("evidence") or ""),
        )
    return detections


async def run_examiner_detection(
    aios: AIOS,
    *,
    case_json: dict,
    rubric_items: list[dict[str, str]],
    transcript: list[dict[str, str]],
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, ItemDetection]:
    if not rubric_items:
        return {}
    result = await aios.run(
        EXAMINER_AGENT,
        {"rubric_items": rubric_items, "transcript": transcript},
        case=case_json,
        session_id=session_id,
        user_id=user_id,
    )
    return _parse_detections(result.text)


async def evaluate_session(
    aios: AIOS,
    *,
    case_json: dict,
    conversation: list[ChatMessage],
    examined_systems: list[str],
    ordered: list[dict[str, Any]],
    student_differentials: list[str],
    student_diagnosis: str,
    management_plan: str | None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EvaluationResult:
    rubric_items = collect_free_text_items(case_json)
    transcript = build_examiner_transcript(conversation, management_plan=management_plan)
    detections = await run_examiner_detection(
        aios,
        case_json=case_json,
        rubric_items=rubric_items,
        transcript=transcript,
        session_id=session_id,
        user_id=user_id,
    )
    return aggregate(
        case_json,
        free_text_detections=detections,
        examined_systems=examined_systems,
        ordered=ordered,
        student_differentials=student_differentials,
        student_diagnosis=student_diagnosis,
    )
