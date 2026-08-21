# VN health check — `ptcg-search-endveto-narrow-vw` (sha `094207968a66`)

Run 2026-07-26 ~16:40 UTC after auth was restored. **Diagnostic only —
nothing rebuilt, resubmitted, or changed.** Under the n ≥ 40 rule this is a
health check, not a strength read; no band is applied.

Evidence: **25 agent logs** (every completed episode) for submission
**55003807**, pulled via `/api/v1/competitions/episodes/{id}/agents/{idx}/logs`.
Reference: `scratchpad/s3/horizon_VN/` (60 self-play games, 120 sides).

---

# PRIMARY HYPOTHESIS — STICKY LATCH: **REFUTED**

**`sticky=True` appears in 0 of 30 `[gov]`/`[gov-snap]` lines across all 25
episodes. The governor never latched. `avg_dets` held at a median of 16.00.**

Per the pre-registered reading in the previous revision of this file:

> **`sticky=False` throughout and `avg_dets` ≈ 16** → the latch hypothesis is
> refuted; the search ran at full depth and 509.2 is a strength result, not a
> degradation artefact.

μ509.2's proximity to v1-alone's historical μ≈512 is **coincidence, not
mechanism.** The agent was searching at full depth in every logged game.

The `[gov-snap]` instrumentation added in the last session is what made this
answerable — 30 telemetry lines where the previous canary produced zero.

---

## 1. Sticky latch rate

| | value |
|---|---|
| `[gov]`/`[gov-snap]` lines captured | **30** across 25 episodes |
| **`sticky=True`** | **0 / 30** |
| `max_cons_skip` | 0 everywhere |
| `warmN` | 10 (warm-start behaving as designed) |
| `hystM` | 0 (hysteresis never needed to fire) |

No latch, at any turn, in any episode. Nothing to report on "at what
turn/decision it latched" because it never did.

## 2. Time spent per game vs the 600 s bank

| source | p50 | p90 | max |
|---|---|---|---|
| `[gov]` `spent=` field | 44.6 s | — | 98.8 s |
| summed log `duration` (per episode) | **50.4 s** | 80.8 s | **106.6 s** |
| **as % of 600 s bank** | **8.4%** | 13.5% | **17.8%** |

**Max 17.8% of the bank — 82% unused.** Comfortably inside, and *below* the
44.6% projection from scaling self-play by 1.8×. The projection was
conservative: ladder games are shorter than self-play games (§4), so total
per-game cost is lower even though each decision is slower.

Longest single decision: **3.15 s**, marginally over `GOV_CAP_S = 3.0` — the
budget is checked *between* determinizations, so a single determinization can
overshoot. Harmless at this magnitude, and expected by design.

## 3. `avg_dets` — holding, not degrading

| | value |
|---|---|
| median | **16.00** of 16 |
| max | 16.00 |
| min | **15.40** |
| `max_ema` observed | 0.182 (cap is 0.20 — never hit) |

**No budget-pressure degradation.** The single 15.40 reading is one episode
briefly trimming determinizations, which is the controller working as intended,
not failing.

## 4. Decisions per game — ladder games are *shorter*

| | ladder (per side) | self-play VN (per side) |
|---|---|---|
| decisions p50 | **39** | 73 |
| decisions max | **62** | 117 |

**Ladder games take roughly half the decisions of self-play games.** That is
the expected signature of losing faster against a stronger field — fewer turns
before the game ends — and it is why total per-game time came in under
projection despite slower per-decision compute.

*(Correction carried forward: the "VN self-play ~160–210 decisions" figure in
the task brief came from a `[gov]` trace counting **both seats in one
process**. Per side it is 73 median / 117 max, which is the correct comparison
basis and what is used above.)*

## 5. Ladder vs self-play — side by side

| metric | self-play VN | **ladder VN** | reading |
|---|---|---|---|
| sticky latched | 0 / 60 games | **0 / 25 episodes** | ✅ same |
| `avg_dets` | 15.98–15.99 | **15.40–16.00 (median 16.00)** | ✅ same |
| decisions / side | p50 73, max 117 | **p50 39, max 62** | ladder games ~half as long |
| wall-clock / side | p50 53.9 s, max 148.8 s | **p50 50.4 s, max 106.6 s** | ✅ ladder *cheaper* per game |
| % of bank | p50 9.0%, max 24.8% | **p50 8.4%, max 17.8%** | ✅ well inside |

**The ladder environment did not stress the governor the way the 1.8×
projection suggested it might.** Both the latch risk and the compute risk
flagged in END_VETO.md §4.4 are, on this evidence, not materialising.

## 6. Is the END veto firing? — **not directly measurable, as predicted**

The veto increments `STATS["end_veto"]`, but `_gov_emit` does not print
`STATS`, so **no veto counter appears in ladder logs.** This was flagged in the
previous revision and is confirmed here.

It cannot be inferred from these logs either — inferring it needs the
END-with-development-available rate, which requires **replays** (option lists +
chosen actions), not agent logs. Those were not pulled for this check.

**Actionable, not done here:** adding `end_veto=%d` to the `[gov]` line is a
one-line instrumentation change that would make this directly observable in
every future bundle. Recommend it for the next build.

## 7. `value_weights.npz` — **loaded, no warning**

**No `value_weights.npz not found` line appears in any of the 25 episode
logs.** Since the same bundle emits that warning loudly when the file is
missing (observed in the pre-rebuild verification), its absence confirms the
weights loaded on the real platform.

Value-net evaluation *count* is not logged, so the "~0.5% of rollouts" figure
cannot be confirmed from ladder logs — only that the model is present and
loading. The clean-env verification measured 707 evaluations over 20 games,
which is the supporting evidence.

## 8. Exceptions, FALLBACK, timeouts

| check | result |
|---|---|
| `FALLBACK` invocations | **0** |
| `Traceback` / uncaught exceptions | **0** |
| `SELFCHECK FAIL` | **0** |
| `cg engine unavailable` / `sampling failed` / `engine search failed` | **0** |
| timeouts | **0** (max 17.8% of bank) |

### One non-error signal worth naming: 614 `SLOW decision` lines

```python
if ms > 1000.0:
    print("[agent %s] SLOW decision turn=%s took %.0f ms" % (AGENT_VERSION, turn, ms), ...)
```

| | value |
|---|---|
| total lines | **614** across 25 episodes |
| per episode | min 4, median 26, max 44 |
| durations | p50 1699 ms, p90 2438 ms, **max 3151 ms** |

This is a **pre-existing 1-second telemetry threshold**, not an error and not
new to this build — it fires because V-NARROW's per-decision cost sits around
1.7 s, above a threshold set when decisions were much faster. Concentrated in
early turns (91× at turn 3, 69× at turn 5, 67× at turn 1), where the bank is
full and the governor grants the largest budget.

**No action required for correctness**, but it makes ladder logs noisy — ~25
lines per episode of expected behaviour — which works against the log-hygiene
argument used to justify shipping `value_weights.npz`. Worth raising the
threshold to ~3000 ms in a future bundle so a genuinely slow decision still
stands out.

## 9. Submission status — **ACTIVE**

| | id | file | score | uploaded |
|---|---|---|---|---|
| **VN** | **55003807** | `endveto_narrow_vw.tar.gz` | **509.2** | 14:34 UTC |
| other slot | 54995194 | `submission_grimmsnariex_v1.tar.gz` | 391.9 | 07:52 UTC |

**Game count on VN: 26 episodes, 11W–15L (42%).** (25 have logs; one
completed after the log pull.)

### ⚠️ Slot cost — unchanged from the previous check and still live

| time | slots |
|---|---|
| 04:58 / 07:52 | `trevenant_v21` (**700.9**) + `grimmsnariex_v1` (391.9) |
| **now** | **VN (509.2)** + `grimmsnariex_v1` (391.9) |

Uploading VN displaced `trevenant_v21`, which sits at **700.9** in the
submission history. Team score moved 700.9 → 509.2 purely through slot
occupancy. Restoring it costs an upload, which would displace one of the two
current entries. **Your call — not a health finding, and not something I act
on.**

---

## Summary

| # | item | result |
|---|---|---|
| 1 | sticky latch | ✅ **0 / 30 — never latched. PRIMARY HYPOTHESIS REFUTED** |
| 2 | spent vs bank | ✅ p50 8.4%, max **17.8%** — 82% unused |
| 3 | `avg_dets` | ✅ median **16.00**, min 15.40 — no degradation |
| 4 | decisions/game | ladder p50 **39** vs self-play 73 — games ~half as long |
| 5 | vs self-play | ✅ consistent; ladder *cheaper* than the 1.8× projection |
| 6 | END-veto firing | ⚠️ **not loggable** — needs a one-line `[gov]` addition |
| 7 | `value_weights.npz` | ✅ loaded, no warning |
| 8 | exceptions / FALLBACK / timeouts | ✅ **0 / 0 / 0**; 614 benign `SLOW decision` lines |
| 9 | submission active | ✅ active, 509.2, 26 episodes, 11W–15L |

**Deployment is clean and the governor is healthy.** The agent searched at full
depth in every logged game and used at most 18% of the time bank. μ509.2 is
therefore a **strength reading, not a degradation artefact** — and at n=26 it
remains below the n ≥ 40 threshold, so no band applies to it yet.

Two follow-ups, neither done here: add `end_veto` to the `[gov]` line, and
raise the `SLOW decision` threshold to ~3000 ms.

### Artifacts

| path | contents |
|---|---|
| `scratchpad/s3/vn_logs/` | 25 agent logs, submission 55003807 |
| `scratchpad/s3/eps_55003807.json` | episode index |
