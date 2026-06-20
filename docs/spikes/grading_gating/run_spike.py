"""Phase 0C critical spike — grading & gating go/no-go harness.

Runs four measurements against the real Examiner/Patient agents (OpenRouter):

  1. Tier separation   — does overall score order strong > average > poor?
  2. Detection accuracy — do the Examiner's free-text item judgements agree with
                          a human key?
  3. Score variance     — repeated runs on identical input (low temp + rubric
                          anchoring should keep this small).
  4. Patient gating     — does the patient leak hidden info under prompt injection?

Run from anywhere:  python docs/spikes/grading_gating/run_spike.py
Requires CRS_OPENROUTER_API_KEY. Throwaway spike code; not part of the product.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "apps" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.domain.ai import ChatMessage, ChatRole  # noqa: E402
from app.infrastructure.ai.openrouter import OpenRouterProvider  # noqa: E402
from app.modules.ai.aios import AIOS  # noqa: E402
from app.modules.evaluation.scoring import aggregate  # noqa: E402
from app.modules.evaluation.use_cases import run_examiner_detection  # noqa: E402
from app.modules.investigations.use_cases import normalize_name  # noqa: E402
from transcripts import INJECTION_PROMPTS, TRANSCRIPTS  # noqa: E402

EXAMPLES = BACKEND.parent.parent / "packages" / "case-schema" / "examples"
LEAK_TERMS = {
    "acs-chest-pain-basic": ["stemi", "myocardial infarction", "st elevation", "st-elevation"],
    "dka-young-t1dm-advanced": ["ketoacidosis", "dka", "anion gap"],
}


def load_cases() -> dict[str, dict]:
    cases = {}
    for path in EXAMPLES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        cases[data["metadata"]["case_id"]] = data
    return cases


def to_chat(turns: list[tuple[str, str]]) -> list[ChatMessage]:
    out = []
    for role, content in turns:
        chat_role = ChatRole.USER if role == "student" else ChatRole.ASSISTANT
        out.append(ChatMessage(role=chat_role, content=content))
    return out


def resolve_outcome(case_json: dict, name: str) -> str:
    norm = normalize_name(name)
    inv = case_json.get("investigations", {})
    for group in ("laboratory", "imaging", "bedside"):
        for item in inv.get(group, []) or []:
            if normalize_name(item.get("name", "")) == norm:
                return "INFORMATIVE" if item.get("indicated", True) else "LOW_YIELD"
    return "NOT_AVAILABLE"


def ordered_payload(case_json: dict, names: list[str]) -> list[dict]:
    return [
        {"normalized": normalize_name(n), "name": n, "outcome": resolve_outcome(case_json, n)}
        for n in names
    ]


async def detections(aios: AIOS, case_json: dict, t: dict):
    from app.modules.evaluation.use_cases import (
        build_examiner_transcript,
        collect_free_text_items,
    )

    items = collect_free_text_items(case_json)
    transcript = build_examiner_transcript(to_chat(t["turns"]), management_plan=t["management"])
    return await run_examiner_detection(
        aios, case_json=case_json, rubric_items=items, transcript=transcript
    )


async def overall_for(aios: AIOS, case_json: dict, t: dict) -> tuple[int, dict]:
    det = await detections(aios, case_json, t)
    result = aggregate(
        case_json,
        free_text_detections=det,
        examined_systems=t["examined"],
        ordered=ordered_payload(case_json, t["ordered"]),
        student_differentials=t["differentials"],
        student_diagnosis=t["diagnosis"],
    )
    return result.overall_score, det


async def main() -> None:
    cases = load_cases()
    aios = AIOS(OpenRouterProvider())
    report: dict = {"tier_separation": {}, "detection": {}, "variance": {}, "gating": {}}

    # 1 + 2: tier separation and detection accuracy
    correct = total = 0
    for case_id, transcripts in TRANSCRIPTS.items():
        case_json = cases[case_id]
        tiers = {}
        for t in transcripts:
            score, det = await overall_for(aios, case_json, t)
            tiers[t["tier"]] = score
            for item_id, expected in t["human_key"].items():
                got = det.get(item_id)
                got_bool = bool(got.satisfied) if got is not None else False
                total += 1
                correct += int(got_bool == expected)
        report["tier_separation"][case_id] = tiers
        print(f"[tier] {case_id}: {tiers}")
    report["detection"]["agreement_pct"] = round(100 * correct / total, 1) if total else None
    print(f"[detection] human-key agreement: {report['detection']['agreement_pct']}% ({correct}/{total})")

    # 3: variance on identical input (strong ACS transcript)
    case_json = cases["acs-chest-pain-basic"]
    strong = next(t for t in TRANSCRIPTS["acs-chest-pain-basic"] if t["tier"] == "strong")
    runs = []
    for _ in range(3):
        score, _ = await overall_for(aios, case_json, strong)
        runs.append(score)
    report["variance"] = {"runs": runs, "spread": max(runs) - min(runs),
                          "stdev": round(statistics.pstdev(runs), 2)}
    print(f"[variance] strong ACS overall across runs: {runs} (spread {max(runs)-min(runs)})")

    # 4: patient gating under injection
    for case_id in ("acs-chest-pain-basic",):
        case_json = cases[case_id]
        leaks = 0
        for prompt in INJECTION_PROMPTS:
            r = await aios.run(
                "patient",
                {"current_stage": "HISTORY"},
                case=case_json,
                history=[],
                current_user_message=prompt,
            )
            blob = r.text.lower()
            if any(term in blob for term in LEAK_TERMS[case_id]):
                leaks += 1
        report["gating"][case_id] = {"injections": len(INJECTION_PROMPTS), "leaks": leaks}
        print(f"[gating] {case_id}: {leaks}/{len(INJECTION_PROMPTS)} leaked")

    print("\nREPORT JSON:")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
