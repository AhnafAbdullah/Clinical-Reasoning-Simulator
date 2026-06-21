"""Three-tier grading check across ALL published cases (free / deterministic).

For every case it derives three student performances straight from the case
rubric — perfect, partial, wrong — and runs the real scoring aggregator
(app.modules.evaluation.scoring.aggregate). No LLM calls: the free-text
detections are simulated (a perfect student asks everything; a wrong student
asks nothing), which is exactly the signal the live Examiner produces (already
validated at 100% accuracy in the spike). This is the reproducible proof that
each rubric separates the tiers.

Run:  python docs/spikes/grading_gating/three_tier.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from app.modules.evaluation.scoring import ItemDetection, aggregate  # noqa: E402
from app.modules.investigations.use_cases import normalize_name  # noqa: E402

EXAMPLES = BACKEND.parent.parent / "packages" / "case-schema" / "examples"


def _free_text_ids(case: dict) -> list[str]:
    out = []
    for sec in ("history", "communication", "treatment"):
        for item in case["rubric"].get(sec, {}).get("items", []) or []:
            out.append(item["id"])
    return out


def _ordered(names: list[str], outcome: str) -> list[dict]:
    return [{"normalized": normalize_name(n), "name": n, "outcome": outcome} for n in names]


def _exam_systems(case: dict, *, all_systems: bool) -> list[str]:
    systems = list((case.get("physical_exam") or {}).keys())
    return systems if all_systems else []


def perfect(case: dict):
    ids = _free_text_ids(case)
    rub = case["rubric"]
    return aggregate(
        case,
        free_text_detections={i: ItemDetection(i, True) for i in ids},
        examined_systems=_exam_systems(case, all_systems=True),
        ordered=_ordered(rub["investigations"].get("expected", []), "INFORMATIVE"),
        student_differentials=list(rub["diagnosis"].get("acceptable_differentials", [])),
        student_diagnosis=(rub["diagnosis"].get("accepted") or ["?"])[0],
    )


def partial(case: dict):
    ids = _free_text_ids(case)
    half_ids = ids[: max(1, len(ids) // 2)]
    rub = case["rubric"]
    expected = rub["investigations"].get("expected", [])
    half_tests = expected[: max(1, len(expected) // 2)]
    diffs = rub["diagnosis"].get("acceptable_differentials", [])
    # Names a plausible differential as the final diagnosis (partial credit).
    plausible = diffs[0] if diffs else "uncertain"
    return aggregate(
        case,
        free_text_detections={i: ItemDetection(i, True) for i in half_ids},
        examined_systems=_exam_systems(case, all_systems=False) or ["vitals"],
        ordered=_ordered(half_tests, "INFORMATIVE"),
        student_differentials=diffs[:1],
        student_diagnosis=plausible,
    )


def wrong(case: dict):
    rub = case["rubric"]
    not_indicated = rub["investigations"].get("not_indicated", []) or ["Thyroid Function Tests"]
    return aggregate(
        case,
        free_text_detections={},
        examined_systems=[],
        ordered=_ordered(not_indicated, "LOW_YIELD"),
        student_differentials=["Something unrelated"],
        student_diagnosis="Common cold",
    )


def main() -> None:
    files = sorted(EXAMPLES.glob("*.json"))
    print(f"{'case':45} {'diff':12} {'perfect':>7} {'partial':>7} {'wrong':>5}  ok")
    print("-" * 90)
    all_ok = True
    for path in files:
        case = json.loads(path.read_text(encoding="utf-8"))
        p, pa, w = perfect(case), partial(case), wrong(case)
        ok = p.overall_score > pa.overall_score > w.overall_score
        all_ok = all_ok and ok
        title = case["metadata"]["title"][:44]
        diff = case["metadata"]["difficulty"]
        print(
            f"{title:45} {diff:12} {p.overall_score:>7} {pa.overall_score:>7} "
            f"{w.overall_score:>5}  {'PASS' if ok else 'FAIL'}"
        )
    print("-" * 90)
    print("ALL TIERS SEPARATE CORRECTLY" if all_ok else "SOME CASES FAILED TIER SEPARATION")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
