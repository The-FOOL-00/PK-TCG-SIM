# Horizon-harm test + v1-alone baseline

**DIAGNOSTIC ONLY.** No fix built, nothing submitted. Governor decision logic
untouched.

Question: does `cap=16` truncate the rollout below the payoff horizon of
development actions — a benched Basic absorbing a KO several turns out — while
END resolves immediately? If yes, the graded-leaf direction is actively
harmful and the cap must revert.

---

## PRE-REGISTERED READING (fixed before running)

**"Materially better" is defined, before results, as:**
- **≥ 10 point** difference on END-with-development-available, **or**
- **≥ 10 point** difference on attack-when-legal uptake.

| condition | verdict |
|---|---|
| **H1 materially better than H2** | the `cap=16` direction is **HARMFUL** → recommend reverting to `cap=400` |
| **H1 ≈ H2** (neither materially better) | the defect **predates the graded leaf** and lives in the search layer generally |
| **H3 matches or beats the better of H1/H2** on these counters | headline finding: **"search layer is net-negative on END decisions"** — report plainly |

**This is a behavioural test, not a win-rate test.** Mirror A/B has returned
null five times, but those measured win rate. These counters measure the defect
directly and do not cancel between mirrored sides. **Win rate is reported for
completeness and is explicitly NOT a verdict input.**

Baselines to beat, from the 28 ladder games at `cap=16`
([BEHAVIORAL_GAP_DIAGNOSIS.md](BEHAVIORAL_GAP_DIAGNOSIS.md)):

| counter | ladder canary | field (top-10, 07-26) |
|---|---|---|
| END with development available | 57.3% (94/164) | — |
| ENDs w/ bench<max + playable Basic-searcher | 18 over 28 games | — |
| attack taken when legal (per turn) | 36.9% | 86–92% (both reference stacks) |
| attack share per own turn | 0.18 | 0.47–0.64 |
| first attack turn | 7.91 | 4.1–5.6 |
| first evolution turn | 5.81 | 3.6–4.2 |

### Arms

| arm | config | meaning |
|---|---|---|
| **H1** | `SEARCH_CAP=0` (→400 steps), terminal leaf | shipped v2.2.0-class search |
| **H2** | `SEARCH_CAP=16`, graded leaf | current canary config |
| **H3** | `PTCG_SEARCH=0`, v1 heuristic alone | no rollouts at all |

≥ 60 self-play games per arm, Garchomp deck, identical instrumentation.
Field-unit metrics computed with **the same `behavioral_profile_jul21.py`**
used for the top-10 table.

*H3 rationale: three top-10 agents decide in 38–43 ms at μ1120–1183 and are
demonstrably not searching. If v1 alone matches or beats H2 on these counters,
the search layer is subtracting value on this decision class.*

---

## RESULTS

60 self-play games per arm (**120 sides each**, both seats pooled — same agent
on both sides). Field-unit rows from `behavioral_profile_jul21.py`;
decision-level rows from `horizon_counters.py`.

### Decision-level counters — the verdict inputs

| arm | games | ENDs | **END + development available** | END + bench<max & Basic-searcher (per game) | own turns | **attack-when-legal (per turn)** | attack share / turn |
|---|---|---|---|---|---|---|---|
| **H1** cap=400 | 60 | 680 | **46.3%** | 0.50 | 1357 | **50.5%** | 30.7% |
| **H2** cap=16 | 60 | 1129 | **60.8%** | 0.85 | 1822 | **38.1%** | 20.7% |
| **H3** v1 alone | 60 | 554 | **0.0%** | **0.00** | 1360 | **49.7%** | 31.0% |
| *ladder canary (cap=16, 28 eps)* | 28 | 164 | *57.3%* | *0.64* | 261 | *36.9%* | *18%* |

H2's self-play numbers reproduce the ladder canary closely (60.8% vs 57.3%;
38.1% vs 36.9%), confirming the self-play harness measures the same defect
the ladder exhibited.

### Chosen-action distribution (% of MAIN decisions)

| action | H1 | H2 | H3 |
|---|---|---|---|
| PLAY | 35.1% | 33.2% | 34.7% |
| ATTACH | 17.4% | 16.6% | 17.2% |
| EVOLVE | 13.2% | 11.4% | 13.4% |
| ABILITY | 3.6% | 4.5% | 4.2% |
| **ATTACK** | **12.5%** | **10.4%** | **14.0%** |
| RETREAT | 5.5% | 6.6% | 6.7% |
| **END** | **12.7%** | **17.4%** | **9.8%** |

### Full scorecard vs the top-10 envelope

| metric | field (top-10 07-26) | **H1** cap=400 | **H2** cap=16 | **H3** v1 alone |
|---|---|---|---|---|
| attack share / own turn | 0.47 – 0.64 | 0.31 | **0.23** | **0.32** |
| first attack turn | 4.1 – 5.6 | 6.52 | **8.19** | **5.26** ✅ *in range* |
| first evolution turn | 3.6 – 4.2 | 4.67 | **5.36** | 4.82 |
| hand T3 | 5.4 – 7.8 | 5.62 | 6.01 | 5.07 |
| hand T5 | 4.6 – 8.2 | 5.19 | 5.67 | 5.20 |
| hand T7 | 4.7 – 10.3 | 5.29 | 5.59 | 4.98 |
| extra draws / turn | 2.1 – 2.6 | 1.34 | 1.36 | 1.45 |
| median deliberation | 38 – 633 ms | 166 ms | 91 ms | **0.01 ms** |
| wall-clock / player-game | — | 32.6 s (max 71.9) | 14.7 s (max 23.9) | **0.0 s** |

Win rate was 50% in every arm by construction (self-play, both seats identical)
and is **not** a verdict input, as pre-registered.

---

## VERDICT

### 1. `cap=16` is HARMFUL — revert to `cap=400`

Applying the pre-registered materiality rule (≥10 points on either counter):

| counter | H1 cap=400 | H2 cap=16 | H1 advantage | material? |
|---|---|---|---|---|
| END + development available | 46.3% | 60.8% | **14.5 pts** | ✅ **yes** (≥10) |
| attack-when-legal | 50.5% | 38.1% | **12.4 pts** | ✅ **yes** (≥10) |

**Both criteria fire, independently.** H1 is materially better than H2 on both
pre-registered counters. Per the header rule: **the `cap=16` direction is
HARMFUL. Recommend reverting `SEARCH_CAP` to 0 (400-step cap).**

Supporting evidence, consistent in direction: H2 passes with a playable
Basic-searcher in hand **0.85 times per game vs H1's 0.50** (+70%), first
attack is **1.7 turns later** (8.19 vs 6.52), first evolution **0.7 turns
later**, and attack share is **8 points lower**. H2's games also run longer
(1822 own turns vs 1357 over the same 60 games) — the signature of passive
play dragging games out.

The mechanism proposed in BEHAVIORAL_GAP_DIAGNOSIS.md is supported: at 16
engine steps the payoff of a development action (a benched Basic absorbing a
KO several turns out) falls outside the evaluation horizon, while END resolves
immediately inside it.

**This retro-invalidates the Gate 1 direction.** Gate 1's P1 improvement
(zero-discrimination 54.5% → 5.7%) was real, but it bought discrimination at
the cost of horizon. The discrimination was measured on a metric that could not
see this trade-off. Recorded as a methodology lesson: *a metric that improves
while the behaviour it is a proxy for degrades is a bad proxy.*

### 2. ⚠️ HEADLINE — the search layer is net-negative on END decisions

**H3 (v1 alone) ends a turn with development still available 0.0% of the time.
Zero, out of 554 ENDs.**

This is not a small edge — it is categorical. v1 scores END at −1,000,000, so
it is structurally incapable of passing while any other option exists. Adding
search introduces this failure from nothing:

| arm | END + development available |
|---|---|
| **H3 v1 alone** | **0.0%** |
| H1 cap=400 | 46.3% |
| H2 cap=16 | 60.8% |

**Every one of those ENDs is the search overriding v1 to pass.** Likewise, H3
never once passed holding a playable Basic-searcher with bench space (0.00/game
vs H1 0.50 and H2 0.85).

And the search buys nothing back on the other counter:

| arm | attack-when-legal | attack share / turn | first attack |
|---|---|---|---|
| H3 v1 alone | **49.7%** | **0.32** | **5.26** ✅ in field range |
| H1 cap=400 | 50.5% | 0.31 | 6.52 |
| H2 cap=16 | 38.1% | 0.23 | 8.19 |

H3 is **statistically indistinguishable from H1** on attack-when-legal (49.7%
vs 50.5%) and attack share (0.32 vs 0.31), while being **the only arm whose
first-attack turn lands inside the field envelope** (5.26 vs field 4.1–5.6).
It achieves this at **0.01 ms** per decision versus H1's 166 ms — four orders
of magnitude cheaper.

**Per the pre-registered rule, the headline finding fires: on this decision
class the search layer is net-negative.** It contributes a large, purely
destructive END pathology and returns no measurable benefit on attack timing
or uptake.

This is consistent with the external evidence that prompted H3's inclusion:
three top-10 agents decide in 38–43 ms at μ1120–1183 and are demonstrably not
running deep search.

### Scope limits — what this does NOT establish

State plainly, because the finding is strong and easy to over-read:

- **These are behavioural counters, not strength.** Self-play win rate is 50%
  by construction and was excluded as a verdict input by pre-registration. It
  remains possible that some of the search's ENDs are correct in genuinely
  dominated positions — but 46–61% is far too high for that to explain them,
  and H3 proves a 0% alternative exists.
- **Only the END/attack decision class was measured.** The search may add value
  elsewhere (lethal detection, multi-select, promotion). This test says nothing
  about those.
- **H3 is not a ship recommendation.** v1 alone was measured at μ≈512
  historically. Its counters are better; its ladder strength is not established
  by this test and must not be inferred from it.
- **Self-play mirror, single deck.** Both sides identical on Garchomp; the
  field is 7/10 Grimmsnarl.

---

## Instrumentation shipped regardless — per-game `[gov]` flush

Built as instructed. **Emission path only; no decision logic touched.**

- `_gov_emit(tag)` split out of `_gov_flush()` — prints the telemetry line
  **without** resetting counters.
- `_gov_flush()` now calls `_gov_emit("gov")` then resets, as before, at the
  new-game boundary (that call site was already correct).
- **New:** `_gov_note()` emits a `[gov-snap]` line every `GOV_EMIT_EVERY = 40`
  decisions. This is the fix for the real gap — the platform terminates the
  process without running `atexit`, so the *final* game of every episode
  previously produced no telemetry at all, which is why 28 ladder games
  yielded zero.

`GOV_EMIT_EVERY = 0` disables it. No governor decision path reads any of this;
`_gov_budget`, `_gov_det`, warm-start and hysteresis are byte-identical.
Every future bundle carries it.

---

## Recommendation

1. **Revert `SEARCH_CAP` to 0.** Pre-registered rule fired on both counters.
2. **Treat the END pathology as the primary defect**, not a cap tuning problem.
   It exists at both caps (46.3% at cap=400) and is absent without search
   (0.0%). The `_develop_before_end` and END-veto proposals in
   BEHAVIORAL_GAP_DIAGNOSIS.md target exactly this and are now better
   motivated — an END-veto that defers to v1 inside the noise band would, by
   construction, move H1 toward H3's 0%.
3. **Re-examine whether the search earns its cost at all** on this decision
   class. H3 matches H1 on every attack counter, beats it on first-attack turn,
   and costs four orders of magnitude less. That is a strategic question for
   you, not a change I would make.

Nothing built beyond the instrumentation, nothing submitted.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/horizon_test.py` | three-arm self-play runner |
| `stage4/rl_ours/horizon_counters.py` | decision-level counters (chosen-action capture) |
| `scratchpad/s3/horizon_H{1,2,3}/` | 60 games per arm |
| `scratchpad/s3/horizon_counters.json` | raw counters |
