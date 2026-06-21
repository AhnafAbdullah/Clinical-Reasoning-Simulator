"""Live 3-tier playthrough against a running backend (real patient + examiner).

For a given case it runs three genuine end-to-end sessions over the HTTP API —
perfect, partial, wrong — and prints the consultant overall scores. Inputs are
derived from the case's own rubric. Deliberately frugal with model calls (one
packed history turn for perfect/partial, none for wrong) to respect the free
tier.

Usage:  python docs/spikes/grading_gating/live_playthrough.py <base_url> <case_substr> [tiers]
Example: python docs/spikes/grading_gating/live_playthrough.py http://localhost:8020 "chest pain"
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[3] / "apps" / "backend"
EXAMPLES = BACKEND.parent.parent / "packages" / "case-schema" / "examples"


def _case_by_substr(substr: str) -> dict:
    for p in sorted(EXAMPLES.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        if substr.lower() in c["metadata"]["title"].lower() or substr.lower() in p.stem:
            return c
    raise SystemExit(f"No case matching {substr!r}")


def _history_cues(case: dict, fraction: float) -> str:
    items = case["rubric"]["history"]["items"]
    take = items[: max(1, int(len(items) * fraction))]
    cues = []
    for it in take:
        cues.extend(it.get("detection_cues", [])[:3])
    return "I would like to ask you about: " + ", ".join(cues) + "."


def _exam_systems(case: dict) -> list[str]:
    return list((case.get("physical_exam") or {}).keys())


def _expected(case: dict) -> list[str]:
    return case["rubric"]["investigations"].get("expected", [])


def _mgmt_text(case: dict, fraction: float) -> str:
    items = case["rubric"]["treatment"]["items"]
    take = items[: max(1, int(len(items) * fraction))]
    cues = []
    for it in take:
        cues.extend(it.get("detection_cues", [])[:2])
    return "My management plan: " + ", ".join(cues) + "."


class Client:
    def __init__(self, base: str, token: str) -> None:
        self.c = httpx.Client(base_url=base, timeout=90)
        self.h = {"Authorization": f"Bearer {token}"}

    def post(self, path, body):
        r = self.c.post(path, json=body, headers=self.h)
        return (r.json() or {}).get("data", {})

    def get(self, path):
        r = self.c.get(path, headers=self.h)
        return (r.json() or {}).get("data", {})


def _wait_greeting(cl: Client, sid: str, timeout: float = 40) -> None:
    """Wait until the opening patient turn is persisted (frees the gen slot)."""
    end = time.time() + timeout
    while time.time() < end:
        msgs = cl.get(f"/api/v1/sessions/{sid}/messages") or []
        if any(m["role"] == "patient" for m in msgs):
            return
        time.sleep(2)


def run_tier(base: str, token: str, case: dict, case_id: str, tier: str) -> int | str:
    cl = Client(base, token)
    sid = cl.post("/api/v1/sessions", {"case_id": case_id})["session_id"]

    if tier in ("perfect", "partial"):
        _wait_greeting(cl, sid)
        frac = 1.0 if tier == "perfect" else 0.5
        cl.post(f"/api/v1/sessions/{sid}/messages", {"message": _history_cues(case, frac)})
        for system in _exam_systems(case) if tier == "perfect" else ["vitals"]:
            cl.post(f"/api/v1/sessions/{sid}/physical-exam", {"system": system})
        tests = _expected(case)
        for t in tests if tier == "perfect" else tests[: max(1, len(tests) // 2)]:
            cl.post(f"/api/v1/sessions/{sid}/investigations", {"investigation": t})

    rub = case["rubric"]["diagnosis"]
    diffs = rub.get("acceptable_differentials", [])
    if tier == "perfect":
        cl.post(f"/api/v1/sessions/{sid}/differentials", {"differentials": diffs or ["a", "b"]})
        cl.post(f"/api/v1/sessions/{sid}/diagnosis", {"diagnosis": (rub.get("accepted") or ["?"])[0]})
        cl.post(f"/api/v1/sessions/{sid}/management", {"plan": _mgmt_text(case, 1.0)})
    elif tier == "partial":
        cl.post(f"/api/v1/sessions/{sid}/differentials", {"differentials": diffs[:1] or ["a"]})
        cl.post(f"/api/v1/sessions/{sid}/diagnosis", {"diagnosis": diffs[0] if diffs else "uncertain"})
        cl.post(f"/api/v1/sessions/{sid}/management", {"plan": _mgmt_text(case, 0.5)})
    else:  # wrong
        cl.post(f"/api/v1/sessions/{sid}/differentials", {"differentials": ["Something unrelated"]})
        cl.post(f"/api/v1/sessions/{sid}/diagnosis", {"diagnosis": "Common cold"})
        cl.post(f"/api/v1/sessions/{sid}/management", {"plan": "Rest and fluids at home."})

    end = time.time() + 90
    while time.time() < end:
        data = cl.get(f"/api/v1/sessions/{sid}/evaluation") or {}
        if "overall_score" in data:
            return data["overall_score"]
        time.sleep(3)
    return "TIMEOUT"


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8020"
    substr = sys.argv[2] if len(sys.argv) > 2 else "chest pain"
    tiers = sys.argv[3].split(",") if len(sys.argv) > 3 else ["perfect", "partial", "wrong"]

    case = _case_by_substr(substr)
    case_id = None
    reg = httpx.post(
        f"{base}/api/v1/auth/register",
        json={"email": f"live{int(time.time())}@example.com", "password": "password1234"},
        timeout=30,
    )
    token = reg.json()["data"]["access_token"]
    cases = httpx.get(f"{base}/api/v1/cases", headers={"Authorization": f"Bearer {token}"}, timeout=30).json()["data"]
    for c in cases:
        if c["title"] == case["metadata"]["title"]:
            case_id = c["id"]
    if not case_id:
        raise SystemExit("case not found via API (is it seeded?)")

    print(f"\nLIVE 3-tier: {case['metadata']['title']}  [{case['metadata']['difficulty']}]")
    for tier in tiers:
        score = run_tier(base, token, case, case_id, tier)
        print(f"  {tier:8} -> overall {score}")


if __name__ == "__main__":
    main()
