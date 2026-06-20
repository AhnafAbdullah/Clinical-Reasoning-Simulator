"""Deterministic rubric aggregation (Vol 4C §6, Vol 3 §18).

The Examiner agent only maps evidence to free-text rubric items; ALL arithmetic
lives here, in software, against the fixed case rubric. Structured actions
(exams performed, investigations ordered, diagnosis, differential) are matched
deterministically. Because the maths is deterministic, scores are reproducible
and every deduction is traceable to a specific rubric item.

Pure functions only — no I/O, no model calls — so this is exhaustively unit-
testable and is exactly what the Phase 0C grading spike measures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.investigations.use_cases import normalize_name

# The six weighted rubric sections that make up the overall score (Vol 3 §18).
SECTION_KEYS = (
    "history",
    "physical_exam",
    "investigations",
    "diagnosis",
    "treatment",
    "communication",
)


@dataclass(frozen=True)
class ItemDetection:
    """A free-text rubric item judgement from the Examiner agent."""

    id: str
    satisfied: bool
    evidence: str = ""


@dataclass(frozen=True)
class SectionScore:
    name: str
    score: int  # 0-100
    awarded: float
    possible: float
    satisfied: list[str] = field(default_factory=list)
    missed: list[dict[str, str]] = field(default_factory=list)  # {id, description}


@dataclass(frozen=True)
class EvaluationResult:
    overall_score: int
    section_scores: dict[str, int]
    differential_score: int
    efficiency_score: int
    feedback: dict[str, Any]


def _pct(awarded: float, possible: float) -> int:
    return round(100 * awarded / possible) if possible > 0 else 100


def _matches(a: str, b: str) -> bool:
    """Lenient name match: equal, or one normalised name contains the other."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


# ── Free-text sections (history / communication / treatment) ─────────────────────


def score_item_section(section: dict, detections: dict[str, ItemDetection]) -> SectionScore:
    items = section.get("items", []) or []
    awarded = 0.0
    possible = 0.0
    satisfied: list[str] = []
    missed: list[dict[str, str]] = []
    for item in items:
        weight = float(item.get("weight", 1))
        possible += weight
        det = detections.get(item["id"])
        if det is not None and det.satisfied:
            awarded += weight
            satisfied.append(item["id"])
        else:
            missed.append({"id": item["id"], "description": item.get("description", "")})
    return SectionScore("", _pct(awarded, possible), awarded, possible, satisfied, missed)


# ── Physical examination (deterministic from performed systems) ──────────────────


def score_physical_exam(
    section: dict, examined_systems: list[str], exam_findings: dict[str, Any]
) -> SectionScore:
    """An item is satisfied if any examined system's name or its case findings
    contain one of the item's detection cues (Vol 4C §6 — structured action)."""
    haystacks = []
    for system in examined_systems:
        text = system + " " + str(exam_findings.get(system, ""))
        haystacks.append(normalize_name(text))
    blob = " ".join(haystacks)

    items = section.get("items", []) or []
    awarded = 0.0
    possible = 0.0
    satisfied: list[str] = []
    missed: list[dict[str, str]] = []
    for item in items:
        weight = float(item.get("weight", 1))
        possible += weight
        cues = item.get("detection_cues", []) or []
        hit = any(normalize_name(c) and normalize_name(c) in blob for c in cues)
        if hit:
            awarded += weight
            satisfied.append(item["id"])
        else:
            missed.append({"id": item["id"], "description": item.get("description", "")})
    return SectionScore("", _pct(awarded, possible), awarded, possible, satisfied, missed)


# ── Investigations: coverage of expected; efficiency from waste ──────────────────


def score_investigations(section: dict, ordered_names: list[str]) -> SectionScore:
    expected = section.get("expected", []) or []
    matched = [e for e in expected if any(_matches(e, o) for o in ordered_names)]
    awarded = float(len(matched))
    possible = float(len(expected))
    missed = [
        {"id": e, "description": f"Expected investigation: {e}"}
        for e in expected
        if e not in matched
    ]
    return SectionScore("", _pct(awarded, possible), awarded, possible, matched, missed)


def score_efficiency(ordered: list[dict[str, Any]]) -> int:
    """Proportion of ordered tests that were informative. Ordering low-yield or
    unavailable tests is wasteful (Vol 3 §22). No orders -> no waste -> 100."""
    if not ordered:
        return 100
    informative = sum(1 for o in ordered if o.get("outcome") == "INFORMATIVE")
    return _pct(float(informative), float(len(ordered)))


# ── Diagnosis & differential (deterministic) ─────────────────────────────────────


def score_diagnosis(section: dict, student_diagnosis: str) -> SectionScore:
    accepted = section.get("accepted", []) or []
    acceptable = section.get("acceptable_differentials", []) or []
    if any(_matches(a, student_diagnosis) for a in accepted):
        return SectionScore("diagnosis", 100, 1.0, 1.0, ["correct"], [])
    if any(_matches(a, student_diagnosis) for a in acceptable):
        # A reasonable differential, but not the leading diagnosis.
        return SectionScore(
            "diagnosis",
            40,
            0.4,
            1.0,
            [],
            [
                {
                    "id": "diagnosis",
                    "description": "Named a plausible differential rather than the leading diagnosis.",
                }
            ],
        )
    return SectionScore(
        "diagnosis",
        0,
        0.0,
        1.0,
        [],
        [{"id": "diagnosis", "description": "Diagnosis not recognised."}],
    )


def score_differential(section: dict, student_differentials: list[str]) -> int:
    acceptable = section.get("acceptable_differentials", []) or []
    if not acceptable:
        return 100
    matched = sum(1 for a in acceptable if any(_matches(a, s) for s in student_differentials))
    return _pct(float(matched), float(len(acceptable)))


# ── Aggregation + consultant report ──────────────────────────────────────────────


def _item_descriptions(case_json: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    rubric = case_json.get("rubric", {})
    for key in ("history", "physical_exam", "treatment", "communication"):
        for item in rubric.get(key, {}).get("items", []) or []:
            out[item["id"]] = item.get("description", "")
    return out


def _build_report(
    case_json: dict,
    sections: dict[str, SectionScore],
    overall: int,
    differential: int,
    efficiency: int,
) -> dict[str, Any]:
    descs = _item_descriptions(case_json)
    strengths: list[str] = []
    weaknesses: list[str] = []
    for section in sections.values():
        strengths.extend(descs[i] for i in section.satisfied if i in descs and descs[i])
        weaknesses.extend(m["description"] for m in section.missed if m["description"])
    tp = case_json.get("teaching_points", {})
    return {
        "overall_score": overall,
        "differential_score": differential,
        "efficiency_score": efficiency,
        "sections": {
            name: {"score": s.score, "satisfied": s.satisfied, "missed": s.missed}
            for name, s in sections.items()
        },
        "strengths": strengths[:8],
        "weaknesses": weaknesses[:8],
        "teaching_points": (tp.get("pearls", []) or []) + (tp.get("pitfalls", []) or []),
        "learning_objectives": tp.get("learning_objectives", []) or [],
    }


def aggregate(
    case_json: dict,
    *,
    free_text_detections: dict[str, ItemDetection],
    examined_systems: list[str],
    ordered: list[dict[str, Any]],
    student_differentials: list[str],
    student_diagnosis: str,
) -> EvaluationResult:
    """Combine the Examiner's free-text judgements with deterministic structured
    scoring into the full evaluation (Vol 4D §12)."""
    rubric = case_json["rubric"]
    findings = case_json.get("physical_exam", {}) or {}
    ordered_names = [o.get("normalized") or o.get("name", "") for o in ordered]

    sections: dict[str, SectionScore] = {
        "history": score_item_section(rubric["history"], free_text_detections),
        "communication": score_item_section(rubric["communication"], free_text_detections),
        "treatment": score_item_section(rubric["treatment"], free_text_detections),
        "physical_exam": score_physical_exam(rubric["physical_exam"], examined_systems, findings),
        "investigations": score_investigations(rubric["investigations"], ordered_names),
        "diagnosis": score_diagnosis(rubric["diagnosis"], student_diagnosis),
    }

    total_w = 0.0
    acc = 0.0
    for key in SECTION_KEYS:
        weight = float(rubric[key].get("weight", 0))
        total_w += weight
        acc += weight * sections[key].score
    overall = round(acc / total_w) if total_w > 0 else 0

    differential = score_differential(rubric["diagnosis"], student_differentials)
    efficiency = score_efficiency(ordered)
    feedback = _build_report(case_json, sections, overall, differential, efficiency)

    return EvaluationResult(
        overall_score=overall,
        section_scores={k: sections[k].score for k in SECTION_KEYS},
        differential_score=differential,
        efficiency_score=efficiency,
        feedback=feedback,
    )
