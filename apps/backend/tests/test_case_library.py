"""Regression: every shipped case must (a) validate against the schema and
(b) produce perfect > partial > wrong overall scores under the real aggregator.

Deterministic, no LLM calls — the Examiner only does free-text detection (proven
100% accurate in the Phase 0C spike); here we feed the detections a perfect /
partial / wrong student would generate and assert the scoring separates them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.infrastructure.case_schema import validate_case
from app.modules.evaluation.scoring import ItemDetection, aggregate
from app.modules.investigations.use_cases import normalize_name

EXAMPLES = sorted((get_settings().case_schema_dir / "examples").glob("*.json"))
CASE_IDS = [p.stem for p in EXAMPLES]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _free_text_ids(case: dict) -> list[str]:
    out = []
    for sec in ("history", "communication", "treatment"):
        for item in case["rubric"].get(sec, {}).get("items", []) or []:
            out.append(item["id"])
    return out


def _ordered(names: list[str], outcome: str) -> list[dict]:
    return [{"normalized": normalize_name(n), "name": n, "outcome": outcome} for n in names]


def _perfect(case: dict):
    rub = case["rubric"]
    return aggregate(
        case,
        free_text_detections={i: ItemDetection(i, True) for i in _free_text_ids(case)},
        examined_systems=list((case.get("physical_exam") or {}).keys()),
        ordered=_ordered(rub["investigations"].get("expected", []), "INFORMATIVE"),
        student_differentials=list(rub["diagnosis"].get("acceptable_differentials", [])),
        student_diagnosis=(rub["diagnosis"].get("accepted") or ["?"])[0],
    )


def _partial(case: dict):
    rub = case["rubric"]
    ids = _free_text_ids(case)
    expected = rub["investigations"].get("expected", [])
    diffs = rub["diagnosis"].get("acceptable_differentials", [])
    return aggregate(
        case,
        free_text_detections={i: ItemDetection(i, True) for i in ids[: max(1, len(ids) // 2)]},
        examined_systems=["vitals"],
        ordered=_ordered(expected[: max(1, len(expected) // 2)], "INFORMATIVE"),
        student_differentials=diffs[:1],
        student_diagnosis=diffs[0] if diffs else "uncertain",
    )


def _wrong(case: dict):
    not_indicated = case["rubric"]["investigations"].get("not_indicated", []) or ["X"]
    return aggregate(
        case,
        free_text_detections={},
        examined_systems=[],
        ordered=_ordered(not_indicated, "LOW_YIELD"),
        student_differentials=["Something unrelated"],
        student_diagnosis="Common cold",
    )


def test_library_is_present() -> None:
    assert len(EXAMPLES) >= 12  # 2 original + 10 added


@pytest.mark.parametrize("path", EXAMPLES, ids=CASE_IDS)
def test_case_valid_and_tiers_separate(path: Path) -> None:
    case = _load(path)
    validate_case(case)
    perfect, partial, wrong = _perfect(case), _partial(case), _wrong(case)
    assert perfect.overall_score > partial.overall_score > wrong.overall_score
    assert perfect.overall_score >= 85
    assert wrong.overall_score <= 20
