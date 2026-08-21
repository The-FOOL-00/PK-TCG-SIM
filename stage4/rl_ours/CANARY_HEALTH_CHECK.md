# Canary health check — `ptcg-search-gradedleaf-c16`

Run 2026-07-26 after Kaggle auth was restored. **Diagnostic only — nothing
rebuilt, resubmitted, or changed.** Under the n ≥ 40 rule, **no band from
CANARY_SUBMISSION_LOG.md §3 is applied.**

Evidence: **28 agent logs** (every completed episode) + **28 replays** for
submission **54991680**, pulled via
`/api/v1/competitions/episodes/{id}/agents/{idx}/logs` and the replay CDN.

---

## 0. ⚠️ FIRST — the canary was displaced, and the slot you were reading was not ours

Full submission history (`/api/v1/competitions/submissions/list/`) resolves the
confusion:

| submitted (UTC) | id | file | score | status |
|---|---|---|---|---|
| 07-26 **07:52** | 54995194 | `submission_grimmsnariex_v1.tar.gz` | 401.1 | **ACTIVE** (Sanjay) |
| 07-26 **04:58** | 54991880 | `submission_trevenant_v21.tar.gz` | 725.9 | **ACTIVE** (Sanjay) |
| 07-26 **04:45** | **54991680** | **`canary_cap16.tar.gz`** | **439.1** | **DISPLACED — our canary** |
| 07-26 01:56 | 54988933 | `submission_trevenant_v20.tar.gz` | 726.8 | inactive |
| 07-25 17:02 | 54980729 | `submission_trevenant_v17.tar.gz` | 750.5 | inactive |
| 07-22 00:55 | 54890463 | `submission_trevenant_v11.tar.gz` | 778.5 | inactive |

**Our canary went up at 04:45 and was displaced 13 minutes later** by
`trevenant_v21` (04:58), then again by `grimmsnariex_v1` (07:52). It ran **28
episodes** and stopped.

Two consequences:

1. **The canary can never complete its read.** It froze at n = 28, below the
   n ≥ 40 threshold. Per §5 of the submission log, **any band applied to 439.1
   is INVALID.** Getting a valid read requires re-uploading and protecting the
   slot.
2. **v7 (μ 881) is gone, and it was not our doing.** Sanjay's own uploads
   displaced it — his current best active is 725.9, and his newest
   (`grimmsnariex_v1`) is at **401.1**. The team's two slots are now both his,
   at 725.9 and 401.1.

I initially pulled logs for the two *active* submissions and found
`SELFCHECK PASS`, `AGENT_DIR=…`, and an `observer.py` UserWarning — none of
which exist anywhere in our bundle (0 matches for `SELFCHECK`/`AGENT_DIR`; no
`observer.py` file). That signature mismatch is what exposed the displacement.
**Everything below is from the real canary, 54991680.**

---

## 1. Does `value_weights.npz` load at runtime? — **HYPOTHESIS REFUTED**

**The weights load. The graded leaf is working as designed.**

Across all 28 episode logs the canary emitted **zero stderr output** — no
`WARNING: value_weights.npz not found`, no `failed loading value_weights.npz`,
no `learned value disabled`, no `heuristic tiers` fallback message.

**Why absence is meaningful here rather than ambiguous:** stderr capture
demonstrably works on this platform — Sanjay's agents in the same competition,
same day, produced captured stderr (`[ptcg] SELFCHECK PASS…`). Our agent prints
nothing when healthy and prints a loud one-time warning when the weights path
fails. Silence is therefore positive evidence, not missing data.

This corroborates the pre-submission V1 check, which loaded the weights under
simulated Kaggle conditions (no `__file__`, repo stripped from `sys.path`) and
fired the graded path 274,431 times.

There was also **no silent except-and-continue**: the `numpy`-missing branch in
`_lv_load` would have forced the pure-Python reader and produced a ~10×
slowdown. Measured latency (below) rules that out.

## 2. Exceptions / FALLBACK invocations — **NONE**

Zero across all 28 episodes: no `FALLBACK`, no `Traceback`, no
`sampling failed`, no `engine search failed`, no `cg engine unavailable`.
Matches local self-play exactly (0 across 4,153 calls). Nothing
environment-specific surfaced.

## 3. Timeouts / near-timeouts — **NONE. Large margin.**

| metric | local validation | **ladder (28 eps)** |
|---|---|---|
| per-decision p50 | 197 ms | **351 ms** |
| per-decision p90 | 331 ms | 516 ms |
| per-decision max | 453 ms | **755 ms** |
| worst player-match | 13.7 s (2.3% of bank) | **31.3 s (5.2% of bank)** |
| median player-match | — | 12.6 s (2.1%) |

Kaggle's CPU is ≈**1.8× slower** than local — an ordinary environment
difference, entirely accounted for, and nowhere near the 600 s bank. **94.8%
of the bank unused in the worst observed match.** Timeout is not a factor.

## 4. Is the search discriminating, or returning tie-breaks?

**Not directly measurable from ladder logs**, and I won't infer more than the
data supports. Our `[gov]` telemetry (`searches=`, `avg_dets=`, `max_ema=`,
`sticky=`) is emitted by an `atexit` handler, and **no `[gov]` line appears in
any of the 28 logs** — the platform terminates the agent process without
running `atexit`. Leaf values are not logged either.

What the timing *does* support: 351 ms p50 on a ~1.8× slower CPU is consistent
with the full 16 determinizations running (local was 197 ms at `avg_dets`
16.00). A collapsed search would be far faster, not slower. So the search is
running at depth — but whether its leaves are discriminating on ladder-realistic
opponents is **unresolved**, and that is precisely the Amendment 2 question the
canary was meant to answer.

## 5. Environment-specific differences

| observation | assessment |
|---|---|
| CPU ~1.8× slower than local | expected, harmless |
| `atexit` handlers not run → `[gov]` telemetry lost | **actionable**: our only in-flight search diagnostic is invisible on ladder. Future bundles should flush governor state per-game (e.g. on new-game detection) rather than only at exit |
| No `observer.py` schema warning for us | that warning belongs to Sanjay's stack, not ours |

---

## What the canary actually shows: it is healthy, and losing

**Record: 9W–19L over 28 episodes** (27 public + 1 validation).

End reasons:

| outcome | reason | count |
|---|---|---|
| losses | prizes | 12 |
| losses | **no-active (board wipe)** | **7** |
| wins | prizes | 7 |
| wins | deckout | 2 |

**37% of losses are board-wipes, and they are catastrophically early:**

| episode | turns | reason |
|---|---|---|
| 88197145 | **2** | no-active |
| 88192784 | **2** | no-active |
| 88194959 | 6 | no-active |
| 88191686 | 8 | no-active |
| 88189043 | 10 | no-active |
| 88194415 | 12 | no-active |

Losing at turn 2 with no Pokémon in play means we established an active and
**never developed a bench** before it was knocked out.

**This is not a mulligan problem.** Mulligans across the 28 games: **ours 7,
opponents 18.** We are drawing Basics at better than twice the opponents' rate
and still benching out — so the failure is in what the agent *does* with them.

This is the same failure family Sanjay documented (§6l `_develop_before_end`,
§6m Poffin passes) and it is a **strategy** defect, not a deployment defect.

---

## Verdict

| # | check | result |
|---|---|---|
| 1 | `value_weights.npz` loads | ✅ **loads — primary hypothesis REFUTED** |
| 2 | exceptions / FALLBACK | ✅ none |
| 3 | timeouts | ✅ none; worst match 5.2% of bank |
| 4 | search discriminating? | ⚠️ **unresolved** — `[gov]` telemetry lost to `atexit` |
| 5 | environment differences | ✅ only a ~1.8× slower CPU; plus the `atexit` gap |
| — | deployment health | ✅ **clean** |
| — | **strength** | ❌ 9W–19L; 7 early board-wipes |
| — | **read validity** | ⛔ **n = 28 < 40 and frozen — 439.1 is INVALID as a band input** |

**The graded leaf shipped correctly and ran correctly.** The bundle did exactly
what the pre-submission verification predicted. The deployment hypothesis is
dead, and the honest reading is that this is a strength problem — but one we
are **not** entitled to score yet, because the submission was displaced before
reaching the pre-registered threshold.

Nothing rebuilt, resubmitted, or changed, as instructed.

### Artifacts

| path | contents |
|---|---|
| `scratchpad/s3/canary_real/` | 28 agent logs, submission 54991680 |
| `scratchpad/s3/canary_replays/` | 28 replays |
| `scratchpad/s3/eps_54991680.json` | episode index |
