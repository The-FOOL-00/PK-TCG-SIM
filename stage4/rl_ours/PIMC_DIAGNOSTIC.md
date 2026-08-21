# PIMC pathology diagnostic — 2026-07-25

**Instrumentation only.** No decision behaviour was changed, no A/B was run,
nothing was submitted. The patched `_search_decide`
(`stage4/rl_ours/pimc_diagnostic.py`) is a line-faithful copy of the shipped
one with recording added: identical arithmetic, identical RNG call order,
identical return value — decisions are unchanged by construction.

Corpus: **7,398 searched MAIN decisions over 80 self-play games**, Garchomp
mirror (`metaC_garchomp_nasuo.csv`), `PTCG_SEARCH=1 ROLLOUT=v1
PILOT=garchomp DYN_DECK_TABLES=1`, all gate component flags OFF
(EVAL_FIX / PROMOTE_RULE / LETHAL_PROBE = 0 — i.e. the base shell).
Raw capture: `scratchpad/s3/pimc_raw.json` (3.5 MB).

Background: Long, Sturtevant, Buro & Furtak (AAAI 2010) — strategy fusion,
non-locality, and the three parameters (leaf correlation, bias,
disambiguation) that predict when PIMC is adequate. Cowling, Powley &
Whitehouse (IEEE TCIAIG 2012) — ISMCTS.

---

## PRE-REGISTERED DECISION RULE (fixed before the results section)

Using **DELIVERABLE 1, contested decisions only, median agreement rate**:

| band | response |
|---|---|
| **≥ 80% agreement** | strategy fusion is minor. PIMC is near-appropriate for this game. **DO NOT rebuild the search core.** |
| **≤ 50% agreement** | strategy fusion is severe. **ISMCTS rewrite is justified; proceed to a scoped design doc.** |
| **50–80%** | **INCONCLUSIVE** on this measure alone. Break the tie with DELIVERABLE 2: if belief-set entropy is still high through the game-deciding turn range, treat as **severe**; if it collapses early, treat as **minor**. |

Contested := (≥ 3 legal actions) AND (aggregated top-1 minus top-2 value
margin < 10% of the eval range). `_rollout` returns [0,1], so the eval range
is 1.0 and the margin threshold is 0.10. Forced/near-forced decisions are
reported separately and are never pooled into the headline number.

### Metric definition amendment — fixed BEFORE the measurement run

A 2-game smoke exposed a measurement artifact that would have inverted the
verdict for a spurious reason, so the metric was pinned down before the
80-game run (not after seeing its results):

In **65% of determinizations, every candidate returns an identical rollout
value**. A world in which all candidates tie has *not chosen anything* — the
"argmax" I would record for it is my own index tie-break, an artifact of the
instrumentation rather than a property of the world. Since the task defines
the metric as *"which action would that world alone have chosen"*, tied
determinizations cast no vote and are excluded from the agreement
denominator.

Both variants are reported at every level:
- **naive agreement** — ties broken by index (artifact-inclusive; would read
  spuriously high and is *not* the decision metric);
- **signal-bearing agreement** — computed over determinizations with a
  *strict* (untied) argmax. **This is the primary metric the rule is applied
  to.**

---

## DELIVERABLE 1 — Strategy fusion incidence

### Headline

| slice | n decisions | naive agreement (median) | frac of dets with a strict argmax (median / mean) | frac of dets where ALL candidates tie (mean) | **signal-bearing agreement (median / mean)** |
|---|---|---|---|---|---|
| ALL | 7,398 | 0.938 | 0.062 / 0.132 | 0.650 | **0.667 / 0.722** |
| **CONTESTED** | **5,925 (80.1%)** | 0.938 | **0.000 / 0.093** | 0.673 | **0.667 / 0.703** |
| FORCED/near | 1,473 (19.9%) | 0.875 | 0.250 / 0.287 | 0.558 | 0.750 / 0.764 |

**Contested-decision median signal-bearing agreement = 0.667 (66.7%).**

Note how far the naive number (0.938) diverges from the signal-bearing one
(0.667): the 0.938 is almost entirely the index tie-break voting with itself.
Reporting the pooled naive figure alone would have landed us in the "≥ 80% →
do not rebuild" band on an artifact.

### Distribution of signal-bearing agreement, contested decisions (n = 2,698 with ≥1 strict det)

| agreement band | n | share | |
|---|---|---|---|
| [0.00, 0.25] | 17 | 0.6% | |
| [0.25, 0.50] | 1,130 | **41.9%** | ████████████████ |
| [0.50, 0.75] | 477 | 17.7% | ███████ |
| [0.75, 1.00) | 19 | 0.7% | |
| 1.00 (unanimous) | 1,055 | **39.1%** | ███████████████ |

Bimodal: either the discriminating worlds agree completely (39.1%) or they
split badly (42.5% at ≤ 0.50). Mean distinct actions voted for across strict
determinizations: **2.01** (max 4 of 4 candidates).

### Agreement vs turn (contested only, signal-bearing)

| turns | n | median agreement |
|---|---|---|
| 0–3 | 264 | 1.000 |
| 4–7 | 399 | 0.750 |
| 8–11 | 440 | 0.600 |
| **12–15** | **435** | **0.500** |
| **16–19** | **397** | **0.600** |
| **20–23** | **310** | **0.571** |
| 24–27 | 209 | 0.667 |
| 28–31 | 157 | 0.750 |
| 32–35 | 57 | 0.667 |

Agreement is perfect at setup, **collapses to 0.50–0.60 exactly across turns
12–23**, then partially recovers late (survivorship — decided games are over).
The trough coincides with the game-deciding window identified in D2.

### ⚠️ Second pathology found, larger than the one we came to measure

The instrumentation surfaced a finding the brief did not ask for and which
dominates the numbers above:

- **46.8% of all searched decisions (3,461 / 7,398) had ZERO discriminating
  determinizations** — in none of the ~16 sampled worlds did any of the top-4
  candidates separate. Those decisions fall through to the index tie-break,
  which is v1's own ordering. **For roughly half of searched decisions the
  search returns exactly what the v1 heuristic would have returned, at full
  compute cost.**
- In contested decisions the median fraction of determinizations producing a
  strict argmax is **0.000** (mean 0.093).
- Mechanism (verified): `value_weights.npz` is present and loaded, so leaf
  values are continuous; but `SEARCH_CAP=0 → cap=400` engine steps means most
  rollouts reach a **terminal** state, returning exactly 0 or 1. When a
  sampled world is already decided regardless of which of our four candidates
  we play, all four score identically. Mean within-determinization spread is
  0.46 on a 0–2 scale, concentrated in the minority of worlds that do
  discriminate.

This is *signal poverty*, a distinct failure from strategy fusion, and it
directly explains the last four null results: **S3's BC-as-rollout landing at
exactly 50.0%, and the three killed gates (EVAL_FIX 45.9, PROMOTE_RULE 43.4,
LETHAL_PROBE 45.1).** A component that changes what the search *computes*
cannot change decisions the search does not actually *decide*. Scoping
consequence in the verdict section.

---

## DELIVERABLE 2 — Disambiguation factor

Opponent-hand belief measured per decision over the determinizations actually
sampled: `handCount`, cards the tracker knows by identity, and the Shannon
entropy / perplexity of the card-id distribution across sampled opponent hands.

| turn | n | opp handCt | known | known % | entropy (bits) | perplexity |
|---|---|---|---|---|---|---|
| 0 | 288 | 5.85 | 0.00 | 0.0% | 6.19 | 74.7 |
| 2 | 807 | 4.55 | 0.62 | 13.7% | 5.28 | 45.8 |
| 4 | 657 | 4.19 | 0.99 | 23.5% | 4.70 | 34.3 |
| 6 | 569 | 4.54 | 0.92 | 20.2% | 4.68 | 39.2 |
| 8 | 597 | 4.60 | 0.95 | 20.7% | 4.63 | 38.2 |
| 10 | 506 | 4.99 | 0.98 | 19.6% | 4.86 | 41.6 |
| **12** | 553 | 5.29 | 1.06 | 20.0% | **4.92** | **42.3** |
| **14** | 497 | 5.22 | 1.06 | 20.3% | **4.81** | **40.5** |
| **16** | 501 | 5.35 | 1.08 | 20.2% | **4.99** | **41.9** |
| **18** | 437 | 5.45 | 1.32 | 24.3% | **4.86** | **39.5** |
| **20** | 460 | 5.65 | 1.40 | 24.8% | **4.78** | **38.5** |
| **22** | 327 | 5.47 | 1.14 | 20.9% | **5.05** | **40.8** |
| **24** | 297 | 5.75 | 1.01 | 17.5% | **5.25** | **45.5** |
| 26 | 201 | 5.47 | 1.16 | 21.2% | 5.07 | 42.3 |
| 30 | 178 | 5.85 | 1.12 | 19.1% | 5.26 | 48.0 |
| 34 | 89 | 5.89 | 0.85 | 14.5% | 5.40 | 48.2 |
| 40 | 29 | 5.59 | 0.52 | 9.3% | 5.31 | 41.9 |

**Game-deciding turn range.** 607 prize-take events across the 80 games:
turn **q1 = 12, median = 18, q3 = 24**. The IQR — **turns 12–24** — is the
window containing the majority of game-deciding decisions. Median game length
is 24 turns.

**Verdict on disambiguation: hidden information does NOT resolve.** Entropy
falls only from 6.19 bits at setup to a floor of ~4.63 by turn 8, then
*rises again* and sits at **4.78–5.25 bits (perplexity 38–48) straight
through the deciding window of turns 12–24**. We never identify more than
~25% of the opponent's hand, and through the deciding turns we know ~1 card
of ~5.5. The belief set is as wide at turn 24 as at turn 6 — draws replace
identified cards as fast as we identify them.

This is the low-disambiguation regime in which Long et al. predict PIMC
performs worst.

---

## DELIVERABLE 3 — Seat bias

Gate B's 114/86 was recorded as "not directional evidence." Measured properly
over the full available corpus:

**Method.** For each gate, challenger plays seat 0 in half the games and seat 1
in the other half, so seat-0 wins = (challenger wins as seat 0) + (games as
seat 1 − challenger wins as seat 1).

| corpus | n | seat-0 wins | seat-0 rate |
|---|---|---|---|
| gateA_evalfix | 400 | 215 | 53.8% |
| gateA_evalfix_retry | 400 | 205 | 51.2% |
| gateB_lethal | 400 | 213 | 53.2% |
| gateB_lethal_retry | 400 | 228 | 57.0% |
| gateD_promote | 400 | 213 | 53.2% |
| gs1_retry | 400 | 205 | 51.2% |
| gs1_retry2 | 400 | 199 | 49.8% |
| gs1_s1_junlee_rollout | 400 | 216 | 54.0% |
| 3 sanity runs | 72 | 38 | 52.8% |
| **POOLED** | **3,272** | **1,732** | **52.93%** |

**Seat-0 win rate = 52.93%, Wilson 95% CI [51.22%, 54.64%] — CI excludes
50%, so the bias is real, ~3 points.** Confound note: gate arms differ by one
component flag, but every component measured null, so the estimate is
approximately unbiased. The confound-free check — this diagnostic's 80
identical-agent mirror games — reads seat-0 57.5% [46.6%, 67.7%], consistent
in direction, not individually significant at n=80.

Interpretation: bias is one of Long et al.'s three PIMC parameters, and ~3
points of it is real but modest. It is **not** large enough to explain
Gate B's 114/86 on its own (that reading sits in the upper tail of this
distribution). Practical consequence: seat alternation in our gates is
necessary and is already being done; no gate conclusion changes.

---

## DELIVERABLE 4 — Time budget audit

Wall clock consumed per player per match, measured by wrapping the agent
call (governor untouched, per instruction). 160 player-matches (80 games × 2).

| statistic | seconds | % of the 600 s bank |
|---|---|---|
| min | 2.8 | 0.5% |
| q1 | 22.2 | 3.7% |
| **median** | **32.2** | **5.4%** |
| q3 | 41.0 | 6.8% |
| p95 | 49.0 | 8.2% |
| max | 59.0 | 9.8% |

| band | player-matches | share | |
|---|---|---|---|
| 0–5% | 72 | 45.0% | ██████████████████ |
| 5–10% | 88 | 55.0% | ██████████████████████ |
| 10–20% | 0 | 0.0% | |
| >20% | 0 | 0.0% | |
| **>100% (timeout)** | **0** | **0.0%** | |

**We use ~5% of the legal budget; the worst observed match used 9.8%. At p95,
91.8 points of the bank go unused.** Zero timeout risk observed in this
corpus (median game 24 turns, max 49).

Reported as measurement only — the governor is not changed here. It exists
because timeout is an instant loss and we have a crash history, and the
ship-vs-gate coupling is documented in `writeup_notes.md` §6h. But the
headroom is roughly **10×**, and any rewrite scoping should treat compute as
abundant rather than scarce.

---

## VERDICT

**Applying the pre-registered rule, mechanically:**

1. D1, contested decisions, median signal-bearing agreement = **0.667** →
   falls in the **50–80% INCONCLUSIVE** band.
2. Rule directs the tie-break to D2: *"if belief-set entropy is still high
   through the game-deciding turn range, treat as severe; if it collapses
   early, treat as minor."*
3. D2: entropy is **4.78–5.25 bits (perplexity 38–48) throughout the
   game-deciding window of turns 12–24**, having fallen only from 6.19 at
   setup — and it *rises* after turn 8 rather than collapsing. Opponent-hand
   identification never exceeds ~25%.

→ **Entropy is still high through the game-deciding turn range.**

# → VERDICT: SEVERE. An ISMCTS rewrite is justified; proceed to a scoped design doc.

Supporting (not decisive, consistent): agreement bottoms out at 0.50–0.60
precisely across turns 12–23, the same window D2 flags as both
maximally-uncertain and game-deciding; and 42.5% of discriminating contested
decisions have worlds splitting at ≤ 50% agreement with a mean of 2.0
distinct actions voted for.

## Mandatory scoping input for that design doc

A rewrite scoped to strategy fusion *alone* would not deliver, and the design
doc must open with this rather than discover it later:

1. **Signal poverty is the larger effect.** 46.8% of searched decisions have
   *no* discriminating determinization at all; in contested decisions the
   median is 0. ISMCTS changes how information sets are aggregated — it does
   **not** by itself create discrimination between actions that a
   terminal-valued rollout scores identically. Sharing statistics across an
   information set will help only where some world separates the candidates.
2. **The fix for #1 is in the value/rollout signal, not the tree topology**:
   rollouts reaching terminal at `cap=400` return 0/1, so already-decided
   worlds flatten all candidates. Candidate levers — bounded-depth rollouts
   scored by the (already loaded) value net rather than played to terminal,
   more rollouts per candidate, or finer leaf evaluation. Note the tension
   with Sanjay's §6i D2 finding that deeper rollouts are a losing trade at
   fixed budget — but D4 shows our budget is **not** fixed in practice: we
   are using ~5% of it.
3. **This diagnostic retro-explains the last four null results.** S3's
   BC-as-rollout at exactly 50.0% and the three killed gates (45.9 / 43.4 /
   45.1) are all consistent with components that alter values which are then
   ties anyway. That is a stronger explanation than "components don't
   transfer from Sanjay's deck geometry", and it is testable: the same
   components re-gated on a search core that actually discriminates should
   read differently.
4. **Compute is abundant** (D4: ~10× headroom), so the rewrite is not
   budget-constrained — but the governor stays as-is until a rewrite is
   actually scoped and gated.

**No rewrite work has been started. Report ends here.**

---

### Artifacts

| file | contents |
|---|---|
| `stage4/rl_ours/pimc_diagnostic.py` | instrumented run harness (behaviour-identical patch) |
| `stage4/rl_ours/pimc_analyze.py` | analysis → the tables above |
| `scratchpad/s3/pimc_raw.json` | 7,398-decision raw capture, 80 games |
