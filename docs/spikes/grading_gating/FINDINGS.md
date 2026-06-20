# Phase 0C — Grading & Gating Spike: Findings

**Status:** GO · **Date:** 2026-06-20 · **Refs:** Impl Plan Phase 0C, Vol 4C §6, Vol 4B §9

> **Update (post-spike fix):** the first run scored free-text detection at 76.2%.
> Investigation traced this to a transcript role-labelling bug — conversation
> turns were passed to the Examiner as `user`/`assistant` while the prompt asked
> it to "assess the student turns", so only the (correctly-labelled) management
> turn was seen and history items were never credited. After labelling turns
> `student`/`patient` (`build_examiner_transcript`) and shipping the examiner
> **v2** prompt (intent-based matching + author cues as hints), detection rose to
> **100% (42/42)** on the labelled set with clean tier separation. Numbers below
> are the corrected run.

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
| Tier separation (ACS) | strong 100 > average 73 > poor 0 | strong>avg>poor | ✅ |
| Tier separation (DKA) | strong 100 > average 64 > poor 8 | strong>avg>poor | ✅ |
| Score variance (3 identical runs) | [100, 100, 100], spread 0, σ=0.0 | within tolerance | ✅ |
| Free-text detection vs human key | 100% (42/42) | ≥80% history | ✅ |
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
**GO.** The architecture is sound: deterministic, reproducible, traceable
aggregation; clean tier separation with strong students in the top band; free-
text detection at 100% on the labelled set; and a patient boundary that holds
under attack.

Carry forward (not blockers):
1. Expand the labelled set toward ~10 transcripts/case, including trickier
   paraphrases, to keep detection honest as cases grow. Regression-gate with
   these transcripts whenever the examiner prompt changes.
2. Re-measure if the production model changes from the free-tier gpt-oss family.

The deterministic aggregator built here is the **production** code
(`app/modules/evaluation/scoring.py`), unit-tested in
`tests/test_evaluation_scoring.py`; this spike exercises it against live model
output. Nothing here is throwaway except the labelled transcripts and runner.
