"""Deterministic rubric aggregation (Vol 4C §6). Pure, offline — this is exactly
what the Phase 0C grading spike measures against labelled transcripts."""

from __future__ import annotations

import json

from app.core.config import get_settings
from app.modules.evaluation.scoring import (
    ItemDetection,
    aggregate,
    score_diagnosis,
    score_differential,
    score_efficiency,
)
from app.modules.investigations.use_cases import normalize_name


def _dka_case() -> dict:
    path = get_settings().case_schema_dir / "examples" / "dka_advanced.case.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _ordered(case_json: dict, names: list[str], outcome: str = "INFORMATIVE") -> list[dict]:
    return [{"normalized": normalize_name(n), "name": n, "outcome": outcome} for n in names]


def _all_true(case_json: dict) -> dict[str, ItemDetection]:
    det = {}
    rubric = case_json["rubric"]
    for section in ("history", "communication", "treatment"):
        for item in rubric[section]["items"]:
            det[item["id"]] = ItemDetection(item["id"], True, "evidence")
    return det


def test_perfect_beats_poor(sample_case) -> None:
    perfect = aggregate(
        sample_case,
        free_text_detections=_all_true(sample_case),
        examined_systems=["vitals", "cardiovascular"],
        ordered=_ordered(sample_case, ["ECG", "Troponin I", "Chest X-Ray"]),
        student_differentials=["Unstable angina", "Aortic dissection", "Pericarditis", "GORD"],
        student_diagnosis="Acute inferior STEMI",
    )
    poor = aggregate(
        sample_case,
        free_text_detections={},
        examined_systems=[],
        ordered=_ordered(sample_case, ["Thyroid Function Tests"], outcome="LOW_YIELD"),
        student_differentials=["Indigestion"],
        student_diagnosis="Indigestion",
    )
    assert perfect.overall_score >= 90
    assert poor.overall_score <= 10
    assert perfect.overall_score > poor.overall_score


def test_tier_separation_on_dka() -> None:
    case = _dka_case()
    strong = aggregate(
        case,
        free_text_detections=_all_true(case),
        examined_systems=["vitals", "extremities", "general"],
        ordered=_ordered(
            case,
            [
                "Capillary Blood Ketones",
                "Venous Blood Gas",
                "Random Blood Glucose",
                "Urea & Electrolytes",
            ],
        ),
        student_differentials=["Hyperosmolar hyperglycaemic state", "Sepsis", "Gastroenteritis"],
        student_diagnosis="Diabetic ketoacidosis",
    )
    average = aggregate(
        case,
        free_text_detections={
            "hpi_insulin_omission": ItemDetection("hpi_insulin_omission", True),
            "hpi_osmotic_symptoms": ItemDetection("hpi_osmotic_symptoms", True),
            "tx_fluids": ItemDetection("tx_fluids", True),
            "tx_insulin": ItemDetection("tx_insulin", True),
        },
        examined_systems=["vitals"],
        ordered=_ordered(case, ["Random Blood Glucose", "Capillary Blood Ketones"]),
        student_differentials=["Gastroenteritis"],
        student_diagnosis="Diabetic ketoacidosis",
    )
    poor = aggregate(
        case,
        free_text_detections={},
        examined_systems=[],
        ordered=_ordered(case, ["Serum Amylase", "Thyroid Function Tests"], outcome="LOW_YIELD"),
        student_differentials=["Gastroenteritis"],
        student_diagnosis="Gastroenteritis",
    )
    assert strong.overall_score > average.overall_score > poor.overall_score


def test_diagnosis_scoring_tiers(sample_case) -> None:
    section = sample_case["rubric"]["diagnosis"]
    assert score_diagnosis(section, "STEMI").score == 100
    assert score_diagnosis(section, "Pericarditis").score == 40  # plausible differential
    assert score_diagnosis(section, "Common cold").score == 0


def test_differential_recall(sample_case) -> None:
    section = sample_case["rubric"]["diagnosis"]
    full = score_differential(
        section, ["Unstable angina", "Aortic dissection", "Pericarditis", "GORD"]
    )
    half = score_differential(section, ["Unstable angina", "Aortic dissection"])
    assert full == 100
    assert 40 <= half <= 60


def test_efficiency_penalises_waste() -> None:
    assert score_efficiency([{"outcome": "INFORMATIVE"}, {"outcome": "INFORMATIVE"}]) == 100
    assert score_efficiency([{"outcome": "INFORMATIVE"}, {"outcome": "LOW_YIELD"}]) == 50
    assert score_efficiency([]) == 100


def test_physical_exam_detected_from_systems(sample_case) -> None:
    # Examining vitals satisfies the "checked vital signs" item deterministically.
    result = aggregate(
        sample_case,
        free_text_detections={},
        examined_systems=["vitals"],
        ordered=[],
        student_differentials=[],
        student_diagnosis="",
    )
    assert result.section_scores["physical_exam"] == 100
