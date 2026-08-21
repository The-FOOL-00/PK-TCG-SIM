# END-veto — build, four-arm measurement, and ship verification

Built and measured 2026-07-26. **NOT SUBMITTED.** Bundle produced, verified,
stopped for your decision.

Premise ([HORIZON_TEST.md](HORIZON_TEST.md)): search is net-**positive**
overall (v2.2.0 μ697 vs v1-alone μ≈512) but net-**negative** on the END
decision class — v1 alone ends a turn with development still available 0.0% of
554 ENDs, while search introduces 46.3% (cap=400). Keep search, veto its ENDs.

## Step 0 — revert

`SEARCH_CAP` is back to **0** (400-step cap), restoring the v2.2.0 baseline
config. The pre-registered rule in HORIZON_TEST.md fired on both counters, so
this is a revert, not a new variable. Repo default was already `"0"`; the
cap=16 value existed only in the displaced canary bundle.

## Step 1 — two variants, separate flags

`PTCG_END_VETO` = `""` (off, byte-identical) | `"narrow"` | `"broad"`.
Applied in `agent()` **after** `_search_decide` and **before**
`_validate_result` — the validation and fallback chain are untouched.

- **V-NARROW** — veto END only when `len(bench) < benchMax` **and** a playable
  Basic-searcher is on the menu. **The replacement is that searcher**, so the
  substituted action is strictly dominated (a free Item converting deck Basics
  into board presence cannot be worse than passing).
- **V-BROAD** — veto END whenever *any* development option is on the menu;
  replacement is the highest v1-scored development option. **Not dominated.**

`benchMax`, not `len(bench)` — Sanjay shipped this rule silently dead by using
the occupied-slot list, which reads a 1/5 bench as full (§6l). Proven firing
below.

### Unit verification on the exact position that lost us a game

ep 88192784 turn 1, bench 0, holding two Buddy-Buddy Poffin — the real ladder
decision where the canary passed and lost on turn 2:

| END_VETO | v1 scores | chosen |
|---|---|---|
| `""` (off) | `[2400, 2400, 2400, -1000000]` | **END** |
| `"narrow"` | same | **Buddy-Buddy Poffin** ✅ |
| `"broad"` | same | **Fighting Gong** ⚠️ |

Guards, all passing: bench full → narrow abstains; no searcher in hand →
narrow abstains, broad fires; chosen action already non-END → unchanged.

**Note the broad row.** With three PLAY options tied at v1 2400, broad falls
through to index order and takes Fighting Gong over the Poffin. That is the
non-dominance risk made concrete, before any measurement.

---

## Step 2 — four-arm measurement

60 self-play games per arm (**120 sides**), Garchomp, identical instrumentation.
Field-unit rows from `behavioral_profile_jul21.py`; decision-level rows from
`horizon_counters.py`.

| metric | field 07-26 | **H1** baseline | **VN** narrow | **VB** broad | **H3** v1-alone |
|---|---|---|---|---|---|
| **END + development available** | — | 46.3% | **37.3%** | **0.0%** | 0.0% |
| **END + bench<max & searcher (per game)** | — | 0.50 | **0.00** | **0.00** | 0.00 |
| **attack-when-legal (per turn)** | 86–92% | 50.5% | **56.6%** ⭐ | 51.4% | 49.7% |
| **attack share / own turn** (counters) | — | 30.7% | **36.3%** ⭐ | 33.3% | 31.0% |
| attack share / turn (profiler) | 0.47–0.64 | 0.31 | **0.35** ⭐ | 0.34 | 0.32 |
| first attack turn | 4.1–5.6 | 6.52 | 6.70 | **6.39** | 5.26 |
| first evolution turn | 3.6–4.2 | 4.67 | **4.37** ⭐ | 4.53 | 4.82 |
| hand T3 / T5 / T7 | 5.4–7.8 / 4.6–8.2 / 4.7–10.3 | 5.62/5.19/5.29 | 5.32/5.11/5.10 | **5.49/5.53/5.53** | 5.07/5.20/4.98 |
| extra draws / turn | 2.1–2.6 | 1.34 | **1.55** | **1.55** | 1.45 |
| own turns (60 games) | — | 1357 | 1211 | 1388 | 1360 |
| median deliberation | 38–633 ms | 166 | 492 | 444 | 0.01 |
| wall-clock mean / **max** per player-game | — | 33.0 / **71.9 s** | 61.0 / **148.8 s** | 64.2 / **144.8 s** | 0.0 / 0.1 |

Chosen-action distribution (% of MAIN decisions):

| action | H1 | VN | VB | H3 |
|---|---|---|---|---|
| PLAY | 35.1 | 35.8 | 35.1 | 34.7 |
| ATTACH | 17.4 | 17.9 | 17.9 | 17.2 |
| EVOLVE | 13.2 | 14.1 | 13.3 | 13.4 |
| ABILITY | 3.6 | 3.5 | 4.7 | 4.2 |
| ATTACK | 12.5 | **13.0** | 12.4 | 14.0 |
| RETREAT | 5.5 | 5.2 | 5.9 | 6.7 |
| END | 12.7 | **10.5** | 10.8 | 9.8 |

---

## Step 3 — the two questions, answered explicitly

### Q1. Does V-BROAD beat V-NARROW on attack-when-legal and first-attack turn, or only on the END counter itself?

**Only on the END counter, plus a marginal first-attack edge. It loses both
attack-uptake counters.**

| counter | VN | VB | winner |
|---|---|---|---|
| END + development available | 37.3% | **0.0%** | VB — *but by construction; zeroing it is the arm's definition, not evidence* |
| **attack-when-legal** | **56.6%** | 51.4% | **VN by 5.2 pts** |
| **attack share / turn** | **36.3%** | 33.3% | **VN by 3.0 pts** |
| first attack turn | 6.70 | **6.39** | VB by 0.31 turns |
| first evolution turn | **4.37** | 4.53 | VN |

V-BROAD eliminates the END counter completely and converts that into **less**
attacking than the targeted veto. Forcing a development action whenever one
exists churns resources — it plays *a* card rather than *the useful* card, as
the Fighting-Gong-over-Poffin unit case predicted.

### Q2. Does either show a counter moving the WRONG way vs H1?

**Yes — and the pattern is the inverse of what the decision rule anticipated.**

- **V-BROAD: no regression on any counter.** Every metric is equal to or
  better than H1.
- **V-NARROW: three small regressions.** First attack **+0.18 turns later**
  (6.70 vs 6.52), and hand sizes lower at all three checkpoints
  (T3 −0.30, T5 −0.08, T7 −0.19).

So the pre-registered conditional — *"if V-BROAD shows any counter-regression
and V-NARROW does not, recommend V-NARROW"* — **does not fire.** It is the
other way round. I am therefore deciding on merits and saying so, rather than
claiming a rule fired that did not.

---

## RECOMMENDATION: **V-NARROW**

Reasoning, with the counter-argument stated:

1. **It wins the counter that is actually the gap.** Attack-when-legal is
   50.5% at baseline against a field of 86–92%. VN moves it to **56.6%**, the
   largest gain of any arm; VB manages 51.4%. VN also gets attack share
   closest to the field (0.35 vs 0.47–0.64) and first evolution closest
   (4.37 vs 3.6–4.2).
2. **It eliminates the exact mechanism that lost games.** END-with-searcher
   goes 0.50 → **0.00** per game. Two of the canary's 19 losses were turn-2
   board-wipes after passing with Poffin in hand; VN takes the Poffin.
3. **The substituted action is strictly dominated.** VN plays a free Item that
   converts deck Basics into board presence. VB picks by v1 score among all
   development options and we *observed* it choosing Fighting Gong over the
   Poffin on a tie — it can burn a Supporter or misattach energy. With one
   usable ladder slot, a dominated change is worth more than a
   plausible-but-unverified one; that is your stated constraint and I am
   applying it.
4. **VN's regressions are small and plausibly noise** at n=120 sides:
   +0.18 turns on first attack, 0.1–0.3 cards on hand size. Against that, its
   attack-uptake gain is 5.2 points.

**Honest counter-argument for VB, not hidden:** VB is the only arm with no
regression on any counter, and it drives END+development to zero — the
headline pathology — where VN only reaches 37.3%. If the END counter is
believed to be the causal variable rather than a symptom, VB is the better
choice. I weight it lower because VB's END advantage is definitional while its
attack-uptake shortfall is measured, and because VB is not dominated.

**Neither arm is close to the field envelope.** VN's 56.6% attack-when-legal
is still ~30 points short of 86–92%, and first attack (6.70) remains outside
4.1–5.6. This is an incremental fix to a large gap, not a closing of it.

---

## Step 4 — ship verification (V-NARROW only)

**Bundle: `dist/endveto/endveto_narrow.tar.gz`** · 2.01 MiB, 13 members ·
sha256 `6fffebfe631c975b29e24f472af3f5268207457f620dbadb1ea05df85c1bdcc3` ·
`AGENT_VERSION = ptcg-search-endveto-narrow` · deck `metaC_garchomp_nasuo.csv`
· config `belief=comp rollout=v1 cap=0 governor=on END_VETO=narrow`.

### 4.1 Diff vs the cap=0 no-veto baseline — every changed line

| change | lines | nature |
|---|---|---|
| `AGENT_VERSION` string | 1 | label |
| `END_VETO` flag + `BASIC_SEARCHERS` frozenset + comment block | ~19 | **new behaviour (the variant)** |
| `_end_veto()` function | ~45 | **new behaviour (the variant)** |
| `_end_veto` call site in `agent()`, guarded by `if END_VETO:` with its own try/except | 8 | **new behaviour (the variant)** |
| `GOV_EMIT_EVERY = 40` constant | 2 | instrumentation |
| `_gov_flush()` split into `_gov_emit(tag)` + `_gov_flush()` | ~12 | instrumentation |
| `[gov-snap]` emit in `_gov_note` | 5 | instrumentation |

**Two logical changes: the END-veto, and the `[gov-snap]` telemetry you asked
for regardless.** `_validate_result`, the fallback chain, `_gov_budget`,
`_gov_det`, warm-start, hysteresis, eval weights, the promotion rule and the
lethal probe are all untouched.

### 4.2 Self-play, clean environment — **PASS**

Tarball extracted to a bare dir, `main.py` `exec()`'d with **no `__file__`**
and the repo stripped from `sys.path` (Kaggle load conditions).

| check | result |
|---|---|
| games | 20 |
| crashes | **0** |
| uncaught exceptions | **0** |
| `STATS["fallbacks"]` / calls | **0 / 3003** |
| caught-error stderr lines | **1** — the `value_weights.npz` warning (see 4.5) |

Builder's own smoke on the same bundle: `SMOKE-OK 24 games 0 crash 0 fallback`.

### 4.3 Fault injection under the veto — **ALL OK**

`tools/test_search_robustness.py` with `PTCG_END_VETO=narrow`, 4 games /
45 decisions:

| scenario | result |
|---|---|
| no-engine | all answers == v1 ✅ |
| begin-raises | all answers == v1 ✅ (20 stderr lines, expected) |
| sampler-raises | all answers == v1 ✅ |
| budget-zero | sticky latched, all answers == v1 ✅ |
| healthy control | 5/45 answers changed by search, **all legal** ✅ |

### 4.4 Wall-clock — ⚠️ the real cost of this change

| source | local MAX | **×1.8 Kaggle projection** | % of 600 s bank |
|---|---|---|---|
| H1 baseline (60 games) | 71.9 s | 129 s | 21.6% |
| 20-game verification run | 52.8 s | 95 s | 15.8% |
| **VN horizon arm (60 games)** | **148.8 s** | **268 s** | **44.6%** ⚠️ |

Take the 60-game figure as binding — more games, higher max.
**The veto roughly doubles compute** (mean 33.0 → 61.0 s per player-game),
because vetoing END extends turns and every extra MAIN decision costs another
search. Projected worst case is **44.6% of the bank** — safe, but a material
narrowing from the baseline's 21.6%, and the largest single risk this change
carries. Timeout is an instant loss, so this is worth your explicit attention.

### 4.5 `value_weights.npz` packaging at cap=400 — **recommend INCLUDING it; currently EXCLUDED**

The builder's rule is `need_value = cap > 0`, so at cap=0 it is left out.
Measured consequences in the clean-env run: `_lv_model()` returns False, one
`[agent] WARNING: value_weights.npz not found` line, and **0 value-net
evaluations** — those rollouts return a flat 0.5 instead.

**This affects ~0.5% of rollouts** (at cap=400, 99.5% reach terminal —
measured in Gate 1). Small, but:

- **The VN arm we measured had the file** (found in the repo root via
  `_find_file`). Shipping without it means the bundle is not the configuration
  the recommendation rests on.
- Flat 0.5 is precisely the tie-inducing value whose elimination this whole
  line of work is about — small dose, wrong direction.
- It removes a spurious warning that will make future ladder-log triage
  harder, which is exactly how the last two silent failures were found.

Cost is 123 KB in a 2 MiB bundle. **Recommendation: include it.** This needs a
one-line override of the builder's `need_value` rule, which I have **not**
made — it would change the artifact after verification, so it is yours to
approve, and the bundle would need a rebuild and re-verify.

### 4.6 `[gov-snap]` flush in the bundle — **CONFIRMED**

Present (`GOV_EMIT_EVERY = 40`, `_gov_emit`, `[gov-snap]`). Emission only; no
decision path reads it. This is the fix for the `atexit` gap that produced zero
telemetry from 28 ladder games.

---

## Summary

| item | status |
|---|---|
| Step 0 revert to cap=400 | ✅ done |
| V-NARROW / V-BROAD built behind separate flags | ✅ done, unit-verified |
| Four-arm measurement, 60 games each | ✅ done |
| Recommendation | **V-NARROW** (merits; the pre-registered conditional did not fire — reported) |
| Ship verification 4.1–4.4, 4.6 | ✅ pass |
| 4.5 `value_weights.npz` | ⚠️ **recommend include — needs your approval + rebuild** |
| Submitted | ❌ **no** |

Two open items for you: whether to include `value_weights.npz` (rebuild
required), and whether the 44.6%-of-bank projection is acceptable.

### Artifacts

| path | contents |
|---|---|
| `dist/endveto/endveto_narrow.tar.gz` | the V-NARROW bundle |
| `dist/endveto/bundle_vn/` | extracted, for diffing |
| `stage4/rl_ours/endveto_verify.json` | clean-env verification record |
| `scratchpad/s3/horizon_{H1,VN,VB,H3}/` | 60 games per arm |
| `scratchpad/s3/horizon_counters.json` | raw counters |

---

# REBUILD — V-NARROW with `value_weights.npz`, plus the time-budget question

Appended 2026-07-26. **Still not submitted.**

## 1. Governor time budget — my earlier framing was wrong, and this corrects it

### Does `_gov_budget` track the per-match clock, or only per-decision time?

**It tracks the per-match clock.** I previously implied the 44.6% projection
was an unguarded timeout risk. That was wrong.

```python
def _gov_budget(obs):
    """Per-decision time budget in seconds, None = unlimited (governor off)."""
    if not GOVERNOR:
        return None
    remaining = obs.get("remainingOverageTime")
    if not isinstance(remaining, (int, float)):
        remaining = 600.0
    turn = (obs.get("current") or {}).get("turn") or 0
    dpt = (_GOV["n_dec"] / max(1.0, float(turn))) if turn else 4.0
    est = max(8.0, dpt * max(GOV_P90_TURNS - turn, 2.0))
    return max(0.0, min(GOV_CAP_S, 0.5 * float(remaining) / est))
```

The per-decision budget is derived **from** the match clock:
`0.5 × remaining / est`, where `est` projects the decisions left. It is a
proportional controller that **reserves half the remaining bank at every
decision**, so it cannot drain the bank monotonically.

The fact that makes this work — which I had not previously checked — is the
competition configuration:

| replay | `actTimeout` | `runTimeout` |
|---|---|---|
| ladder (canary episode) | **0** | 2000 |
| local self-play | **0** | 3000 |

**`actTimeout: 0` means there is no free per-step allowance — every second of
agent time draws from the 600 s pool.** So `remainingOverageTime` *is* the
match clock, not a separate overage bank. Verified: a ladder game ran
600 → **586.3** (13.7 s, matching that game's measured agent time); local runs
show 600 → 577.

The per-decision and per-match budgets are therefore **not** independent here
— the former is computed from the latter.

### Sticky-latch condition, and would it fire before a 600 s timeout?

```python
budget = _gov_budget(obs)
if budget is not None and budget < GOV_STICKY_S:      # GOV_STICKY_S = 0.2
    _GOV["sticky"] = True
    ... heuristic-only for the rest of the game
```

Latches when `0.5 × remaining / est < 0.2`, i.e. **`remaining < 0.4 × est`**.
With `GOV_P90_TURNS = 20`:

| phase | `est` | latches at |
|---|---|---|
| early (turn ≈ 2, dpt ≈ 10) | `10 × 18 = 180` | **remaining < 72 s** |
| late (turn ≥ 18) | `max(8, 2 × dpt) ≈ 20` | **remaining < 8 s** |

**Yes — it latches with 72 s of reserve early and 8 s late, both before
exhaustion**, degrading to pure v1 rather than failing. That is the mechanism
the fault-injection "budget-zero → sticky latched → all answers == v1"
scenario exercises.

### Empirical governor trace (new `[gov-snap]` instrumentation, 3 VN games)

```
[gov-snap] game=0 decisions=160 spent=91.4s  avg_dets=15.98 sticky=False worst=[(15, 3.0, 1.24, 16)
[gov]      game=0 decisions=210 spent=103.4s avg_dets=15.98 sticky=False
[gov-snap] game=2 decisions=80  spent=34.2s  avg_dets=15.99 sticky=False worst=[(5, 2.34, 1.54, 16)
[gov]      game=2 decisions=112 spent=37.8s  avg_dets=15.99 sticky=False worst=[(5, 2.04, 1.04, 16)
```

The budget field visibly responds to the draining bank (3.0 → 2.34 → 2.04),
`avg_dets` holds at ~15.99, and **`sticky` never latched** even in a
210-decision, 103 s game. It throttles smoothly rather than cliff-edging.

### Wall-clock distribution — full tail

| arm | p50 | p90 | p99 | max | max %bank | **×1.8 max %bank** |
|---|---|---|---|---|---|---|
| H1 baseline | 32.7 s | 56.6 s | 68.6 s | 71.9 s | 12.0% | 21.6% |
| **VN** | **53.9 s** | **111.9 s** | **143.9 s** | **148.8 s** | 24.8% | **44.6%** |
| VB | 56.6 s | 118.2 s | 143.4 s | 144.8 s | 24.1% | 43.4% |

**Tail shape:** VN's p99 (143.9 s) is within 3% of its max (148.8 s). The
distribution is **compressed against a ceiling, not heavy-tailed** — the
signature of an active cap. So the max should **not** grow materially over
hundreds of ladder games; it is bounded by the controller, not by luck.

### Is a cumulative per-match guard needed?

**No — the existing mechanism already is one, and is better than the
threshold-latch design proposed:** proportional throttling degrades gradually,
whereas a 400 s cliff would drop the agent to v1 abruptly mid-game.

**One residual edge case, named not built:** if the harness ever omits
`remainingOverageTime`, the code falls back to a **constant** `remaining =
600.0`, silently disabling the drain response — budget would sit at 3.0
forever. It is present on this ladder (verified in the canary replays), so not
a live risk. Belt-and-braces would be `min(remaining, 600 - elapsed)` from a
per-game accumulator: one variable, no new policy. **Not built.**

**Verdict on the ship-blocking question: NOT blocking.** The 44.6% projection
is a real compute-cost increase worth knowing, but it is governed, bounded,
and degrades to v1 rather than to a timeout.

## 2. Rebuild with `value_weights.npz`

Added `--force-weights` to the builder (`need_value = cap > 0 or
force_weights`). Rationale as stated: the measured VN arm had the file loadable
via `_find_file`, so excluding it shipped an untested configuration.

**`main.py` in the rebuilt bundle differs from the previous build by the
version string alone** — confirming the only artifact change is the added
weights file.

## 3. Re-verification

| item | value |
|---|---|
| **bundle** | `dist/endveto/endveto_narrow_vw.tar.gz` |
| **sha256** | `094207968a666fcaaf2b75ff9ec9a47501a7f9d398a7b123206107af00315f77` |
| size / members | 2.12 MiB / **14** (was 2.01 MiB / 13) |
| `AGENT_VERSION` | `ptcg-search-endveto-narrow-vw` |
| `END_VETO` baked | `"narrow"` ✅ |
| `SEARCH_CAP` baked | `0` ✅ |
| `[gov-snap]` present | ✅ |

| check | before (no weights) | **after** |
|---|---|---|
| `value_weights.npz` in tarball | ❌ False | ✅ **True** |
| `_lv_model()` loads in clean env | ❌ False | ✅ **True** (predict 0.437265, in [0,1]) |
| `value_weights.npz not found` warning | ⚠️ present | ✅ **gone** |
| **value-net evaluations in play** | **0** | ✅ **707** |
| clean-env self-play games | 20 | 20 |
| crashes | 0 | ✅ **0** |
| caught-error stderr lines | 1 (the warning) | ✅ **0** |
| `STATS` fallbacks / calls | 0 / 3003 | ✅ **0 / 2655** |
| fault injection (4 scenarios) | ALL OK | ✅ **ALL OK** (healthy control 12/55 changed, all legal) |
| wall-clock MAX (20-game run) | 52.8 s (8.8%) | **47.8 s (8.0%)** |
| ×1.8 projection (20-game run) | 15.8% | **14.4%** |
| ×1.8 projection (60-game VN arm, binding) | 44.6% | **44.6%** |

The value net now fires **707 times** across 20 games — the ~0.5% of rollouts
reaching the 400-step cap, as predicted — and the stderr warning is gone. The
artifact now matches the configuration V-NARROW was measured on.

## Status

| item | state |
|---|---|
| Governor per-match guard | ✅ exists, verified in code + telemetry — **not ship-blocking** |
| Rebuild with weights | ✅ done |
| Re-verification | ✅ all checks pass, zero warnings |
| Veto logic / eval weights / promotion rule / lethal probe / governor logic | untouched |
| **Submitted** | ❌ **no** |

**Recommended artifact: `dist/endveto/endveto_narrow_vw.tar.gz`**
(sha256 `0942079686…`). Stopping here.
