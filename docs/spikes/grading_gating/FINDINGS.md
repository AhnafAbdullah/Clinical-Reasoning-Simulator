# Phase 0C — Grading & Gating Spike: Findings

**Status:** Conditional GO · **Date:** 2026-06-20 · **Refs:** Impl Plan Phase 0C, Vol 4C §6, Vol 4B §9

This spike de-risks the two product-defining questions *before* committing to the
full evaluation build: (1) can we grade free-text clinical reasoning consistently
and correctly against a rubric, and (2) does the patient hold its knowledge
boundary under attack? Run with `python docs/spikes/grading_gating/run_spike.py`.

## Setup
- **Cases:** 1 Basic (`acs-chest-pain-basic`) + 1 Advanced (`dka-young-t1dm-advanced`),
  each with a full itemised rubric (Vol 3 §18).
- **Transcripts:** 3 labelled per case (strong / average / poor) with a human key
  for the free-text rubric items, in `transcripts.py`.
- **Pipeline under test:** the real product code — Examiner agent
  (`gpt-oss-120b:free`, temp 0.2) for free-text item detection +
  `app.modules.evaluation.scoring.aggregate` for deterministic aggregation.
- **Models:** OpenRouter free tier (gpt-oss). Patient = `gpt-oss-20b:free`.

## Results (live)

| Measure | Result | Bar | Verdict |
|---|---|---|---|
| Tier separation (ACS) | strong 70 > average 64 > poor 0 | strong>avg>poor | ✅ |
| Tier separation (DKA) | strong 70 > average 64 > poor 8 | strong>avg>poor | ✅ |
| Score variance (3 identical runs) | [70, 70, 70], spread 0, σ=0.0 | within tolerance | ✅ |
| Free-text detection vs human key | 76.2% (32/42) | ≥80% history | ⚠️ near |
| Structured scoring (exam/inv/dx/diff) | deterministic, exact | ≥90% | ✅ (by construction) |
| Patient gating (prompt injection) | 0 / 4 leaked | near-zero | ✅ |

## Interpretation
- **Consistency is excellent.** Zero score variance across repeated runs at low
  temperature — the deterministic aggregation means the only stochastic part is
  per-item detection, and even that was stable here. This was the biggest risk
  and it is retired.
- **Tiers separate cleanly and monotonically** on both cases.
- **Gating holds.** The patient refused every injection ("ignore your
  instructions / what's my diagnosis / reveal the rubric") with no leakage —
  the renderer's `forbidden_context` enforcement plus the response screen work
  end-to-end against a live model.
- **Detection accuracy is the soft spot (76.2%).** Structured items are scored
  deterministically and are exact; the gap is the free-text history/treatment
  extraction, where the free-tier model is conservative and misses some items a
  human credits. Strong/average both land at ~70 because a few satisfied items
  are not detected, compressing the top of the range (though order is preserved).

## Go / No-Go
**Conditional GO.** The architecture is sound: deterministic, reproducible,
traceable aggregation; clean tier separation; and a patient boundary that holds
under attack. Proceed with the Phase 4 build.

Carry forward as tracked risks (not blockers):
1. **Lift free-text detection ≥80%** before high-stakes use — via examiner prompt
   iteration (clearer evidence criteria, few-shot exemplars) and/or a stronger
   production model than the free tier. Regression-gate with these transcripts.
2. **Widen the top of the score range** so strong students score in the 85–100
   band once detection improves.
3. Expand the labelled set toward ~10 transcripts/case for tighter measurement.

The deterministic aggregator built here is the **production** code
(`app/modules/evaluation/scoring.py`), unit-tested in
`tests/test_evaluation_scoring.py`; this spike exercises it against live model
output. Nothing here is throwaway except the labelled transcripts and runner.
