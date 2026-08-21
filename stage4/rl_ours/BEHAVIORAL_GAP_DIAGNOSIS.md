# Behavioural gap diagnosis — canary `ptcg-search-gradedleaf-c16`

Diagnosis 2026-07-26. **Nothing built, nothing submitted.** Proposals only.

Evidence: 28 ladder replays (`scratchpad/s3/canary_replays/`), 28 agent logs
(`scratchpad/s3/canary_real/`), **1,107 MAIN decisions across 261 own turns**,
`profile_top10_jul26.json`. Deployment already verified clean
([CANARY_HEALTH_CHECK.md](CANARY_HEALTH_CHECK.md)).

---

## PRIORITY 4 — SCORECARD (this is the standing table)

Ours computed with **the same script** used for the field
(`behavioral_profile_jul21.py`), so units are identical (per-TURN, §6m rule).

| metric | field (top-10, 07-26) | **ours** | gap |
|---|---|---|---|
| **attack share / own turn** | **0.47 – 0.64** | **0.18** | **−0.29 to −0.46** ❌ |
| first attack turn | 4.1 – 5.6 | **7.91** | **+2.3 turns late** ❌ |
| first evolution turn | 3.6 – 4.2 | **5.81** | **+1.6 turns late** ❌ |
| hand size T3 | 5.4 – 7.8 | 5.81 | in range ✅ |
| hand size T5 | 4.6 – 8.2 | 5.67 | in range ✅ |
| hand size T7 | 4.7 – 10.3 | 5.38 | low-normal ⚠️ |
| extra draws / turn | 2.1 – 2.6 | **1.32** | **−0.8** ❌ |
| deliberation (median) | 38 – 633 ms | 155 ms | in class ✅ |
| win rate (harvest) | 44 – 84% | **34%** | ❌ |

### Two corrections to the brief's premises

1. **Attack share is 0.18, not 0.32.** Measured in field units. The gap is
   roughly twice as large as assumed.
2. **First attack is T7.91, not T5.5 — it is NOT in range.** It is 2.3 turns
   later than the slowest top-10 team. The earlier T5.5 figure was carried
   forward from an unverified summary line; this measurement supersedes it.

Hand size is the only healthy column. We are not card-starved — we are
*tempo*-starved.

---

## PRIORITY 1 — TIE-BREAK DIRECTION

### The premise needs correcting: ties do **not** use engine option order

```python
order  = sorted(range(len(options)), key=lambda i: (-scores[i], i))   # main.py:2505
cands  = order[:SEARCH_TOPK]                                          # main.py:2506
best   = max(cands, key=lambda i: (totals[i] / n, -cands.index(i)))   # main.py:2554
```

On a tie in `totals`, `max` selects the largest `-cands.index(i)` → the
**smallest index within `cands`** → `cands[0]`. Since `order` is sorted by
*descending v1 score*, `cands[0]` is **v1's highest-scored option**.

**So a tied search returns v1's top pick. Engine option ordering is irrelevant
to the tie-break** — it only breaks ties *between equal v1 scores* (the `, i`
term). The hypothesised passive-index bias does not exist as posed, and I
found no evidence for it.

### But the real bias is worse, and it is in the v1 ladder itself

Because ~47% of decisions are ties (PIMC_DIAGNOSTIC.md), the v1 weight ladder
decides roughly half our moves:

| action | v1 score |
|---|---|
| lethal attack | 100000 |
| bench-urgent (≤1 Pokémon in play) | 3500 |
| **attach energy** | **3000** |
| **evolve** | **2800** |
| **play item** | **2400** |
| bench | 2300 |
| supporter / tool / ability / stadium | 2030 – 2150 |
| **non-lethal ATTACK** | **1000 + min(dmg,1900)×0.5 → ~1050–1130 in practice** |
| retreat | −500 |
| END | −1000000 |

**A non-lethal attack can never outrank any setup action.** The code comment
says so explicitly ("always below setup"). This is deliberate turn-structure
design — the MAIN menu re-presents after each setup action, so the intent is
"do all setup, then attack".

**The intent does not survive contact with the ladder.** Measured: of 261 own
turns, 97 ended in ATTACK and 164 ended in END (97 + 164 = 261 exactly — every
turn terminates in one or the other). We do not run out of setup and then
attack; **we run out of setup and then pass.**

### Measured tie resolution: passive, and far above base rate

| chosen action | count | share of decisions | offered | take-rate |
|---|---|---|---|---|
| PLAY | 393 | 35.5% | 1858 | 21.2% |
| ATTACH | 179 | 16.2% | 1300 | 13.8% |
| **END** | **164** | **14.8%** | 1107 | 14.8% |
| EVOLVE | 145 | 13.1% | 605 | 24.0% |
| **ATTACK** | **97** | **8.8%** | 556 | **17.4%** |
| RETREAT | 71 | 6.4% | 582 | 12.2% |
| ABILITY | 58 | 5.2% | 293 | 19.8% |

Development 70.0% · **ATTACK 8.8%** · passive (END+RETREAT) **21.2%**.

**The decisive number: of the 164 ENDs, 94 (57.3%) had a development option
still available on the menu** — PLAY 79, EVOLVE 17, ABILITY 12, ATTACH 11.
And this splits **32 in wins vs 62 in losses**.

Since v1 scores END at −1,000,000, **v1 would never choose END while any other
option existed.** Every one of those 94 is the *search* actively overriding v1
to pass. That is not a tie-break artefact — it is the search discriminating and
choosing wrong.

**Answer to Priority 1: ties themselves resolve to v1's top pick (development-
first, never END). The passive bias is real but arrives via a different route —
the search overriding v1 to select END 94 times with development still on the
table.** Quantified above; this is a primary cause of both the attack-share
gap and the bench failure.

---

## PRIORITY 2 — BOARD-WIPE MECHANISM

### The four catastrophic losses had **zero** bench-legal decisions

| ep | turns | own turns | bench-legal decisions | Basics in hand (ever) |
|---|---|---|---|---|
| 88192784 | 2 | 1 | **0** | none |
| 88197145 | 2 | 1 | **0** | none |
| 88194959 | 6 | 3 | **0** | none |
| 88191686 | 8 | 4 | **0** | none |

We never held a Basic to bench. So these are **not** decline-to-bench failures
in the direct sense — and the "we draw Basics at 2× their rate" framing does
not apply to these specific games.

### But we held the card that fixes it, and passed instead

**ep 88192784, turn 1, bench 0, holding two Buddy-Buddy Poffin:**

```
decision 1:  [0] PLAY Fighting Gong   [1] ATTACH  <== CHOSEN
             [2] PLAY Buddy-Buddy Poffin   [3] ATTACH
             [4] PLAY Buddy-Buddy Poffin   [5] ATTACH   [6] END
decision 2:  [0] PLAY Fighting Gong
             [1] PLAY Buddy-Buddy Poffin
             [2] PLAY Buddy-Buddy Poffin
             [3] END                 <== CHOSEN
```

**We ended turn 1 with an empty bench holding two copies of a Basic-searcher,
then lost on turn 2 with no Pokémon in play.** ep 88191686 repeats it exactly
(turn 1 END over Poffin; turn 3 ATTACH over Poffin).

Across all 28 games: **18 ENDs occurred with bench < 5 and a playable
Basic-searcher in hand.**

This is Sanjay's §6l `_develop_before_end` case reproduced verbatim on our
stack — he measured it firing in 1 of 20 such decisions; we are at 18.

### Control: is the defect general or wipe-specific? — **GENERAL**

| | wins | losses |
|---|---|---|
| bench-take rate (of bench-legal decisions) | 51/107 = **47.7%** | 83/162 = **51.2%** |
| attack-take rate (of attack-legal decisions) | 67/325 = **20.6%** | 30/175 = **17.1%** |

Bench-taking is **statistically indistinguishable between wins and losses** —
if anything marginally higher in losses. **The development defect is general,
not board-wipe-specific.** Board wipes are where a general slowness becomes
immediately fatal; they are the visible tail, not a separate bug.

*(Caveat on the bench metric: "took" counts choosing any PLAY option, which
includes non-Pokémon cards, so 47.7/51.2% overstates true benching. It is used
only as a wins-vs-losses control, where the bias applies equally to both.)*

### Did cap=16 make this worse than cap=400? — **UNTESTED, and it must be tested**

The mechanism is plausible and specific: benching a Basic pays off when that
Basic absorbs a KO **several turns later**. At `cap=16` engine steps
(≈1–2 turns) that payoff is **outside the evaluation horizon**, while END
resolves immediately. A 16-step horizon can rationally prefer passing.

I cannot settle it from the data in hand. The cap=400 captures I hold
(`pimc_raw.json`, Gate 2 arms A1/A3) recorded agreement and margins, **not
chosen action types**, and they are self-play mirror rather than ladder. Making
the comparison requires re-running instrumented — which is building, excluded
this session.

**Flagging it loudly as the single highest-value unresolved question**: if
cap=16 degraded development, then Gate 1's P1 "improvement" (zero-discrimination
54.5% → 5.7%) bought discrimination at the cost of horizon, and the graded-leaf
direction is actively harmful rather than neutral. The test is cheap (§Proposal 0)
and should precede any further work on this line.

---

## PRIORITY 3 — ATTACK SHARE

Attack share 0.18 vs field 0.47–0.64. Decomposed in Sanjay's §6n units:

| quantity | ours | reference |
|---|---|---|
| own turns | 261 | — |
| turns where ATTACK was legal | 141 = **54.0%** | Sanjay top **77%** / his agent 53% |
| turns containing an attack | 52 = **19.9%** | field 47–64% |
| **attack taken when legal (per turn)** | **36.9%** | Sanjay top **92%** / his agent 86% |

**Both halves are broken, and the second is the novel one.**

- **Availability (54% vs 77%)** — we are not in a position to attack on nearly
  half our turns. Matches Sanjay's agent almost exactly (53%). Downstream of
  late evolution (T5.81 vs 3.6–4.2) and weak draw (1.32 vs 2.1–2.6).
- **Uptake (36.9% vs 86–92%)** — **this is much worse than anything previously
  recorded on either stack.** When attacking is legal we decline it ~63% of the
  time. Sanjay's agent declined 8–14%.

Ranked substitutes on non-attacking turns (the 164 turn-ending ENDs plus
in-turn choices): **PLAY 35.5%, ATTACH 16.2%, END 14.8%, EVOLVE 13.1%,
RETREAT 6.4%, ABILITY 5.2%.**

**Category answer: (d) repeated setup, plus (c) passing.** Not retreat loops
(6.4%, and RETREAT take-rate is the lowest of any action at 12.2%). The v1
ladder guarantees every setup action outranks attacking, and the search then
adds 94 ENDs on top. We keep developing and then pass, rather than converting
development into damage.

---

## PROPOSALS — ranked by (expected effect on the measured gap) / (cost × blast radius)

None of these are built. All measurement is on **ladder**, not mirror A/B —
five consecutive mirror nulls (S3, Gates A/D/B, Gate 2) make mirror the wrong
instrument for this class of change.

### 0. ⭐ Horizon-harm test — `cap=16` vs `cap=400`, instrumented for action types

**Do this before anything else.** Not a fix: a decision-gate on the whole
graded-leaf direction.

- **Mechanism:** re-run the existing instrumentation with chosen-action-type
  recording added, at both caps, and compare END-with-development-available
  rate, bench-take rate, and attack-when-legal.
- **Cost:** ~2 h (instrumentation exists; add action-type capture to
  `pimc_diagnostic.py`). **Blast radius: zero** — diagnostic only.
- **Decides:** whether Gate 1's direction is neutral or actively harmful.

### 1. ⭐ `_develop_before_end` — never END with an unfull bench while holding a Basic-searcher

Highest effect-per-cost of the actual fixes.

- **Mechanism:** at a MAIN return, if bench < `benchMax` and a playable
  Basic-searcher (Buddy-Buddy Poffin, Nest Ball, Hop's Bag …) is on the menu,
  veto END and take it. Directly targets the **18 measured occurrences**, two
  of which lost the game on turn 2.
- **Note Sanjay's trap:** he shipped this rule **silently dead** by comparing
  against `len(me.bench)` (occupied slots) instead of **`benchMax`**. Use
  `benchMax`.
- **Cost:** ~3 h including a replay-driven fire-count check.
  **Blast radius: low** — one veto on the END path; `_validate_result` and the
  fallback chain untouched; strictly dominated action (a free Item converting
  deck Basics into board presence cannot be worse than passing).
- **Ladder measurement:** fire-rate telemetry per game (§4) + no-active loss
  share, currently **7/19 = 37%** of losses.

### 2. ⭐ END-veto when any development option remains

Bigger surface, bigger payoff, more care needed.

- **Mechanism:** the search chose END over an available development action **94
  times (57.3% of all ENDs)**, and v1 scores END at −1e6 so this is always a
  search override. Simplest form: never return END from the search when a
  development option is on the menu **and** the search's margin over that
  option is inside the noise floor (Gate 2 measured excess-over-chance ≈ ±0.02).
  This makes the search *defer to v1* exactly where PIMC_DIAGNOSTIC showed it
  cannot discriminate.
- **Cost:** ~4 h. **Blast radius: medium** — touches every END decision. Needs
  the abstain-style guard (§6j "a confidently wrong term is worse than an
  absent one") so it only fires inside the measured noise band.
- **Ladder measurement:** END-with-development-available rate (baseline 57.3%)
  and attack-share (baseline 0.18).

### 3. Attack-uptake floor when legal

- **Mechanism:** we take a legal attack on only **36.9%** of turns vs 86–92%
  on both reference stacks. Rather than forcing a rate (Sanjay's
  `_ability_before_end` measured **−6.5 pts at n=400** doing exactly that —
  "matching a rate is not matching a policy"), raise `WEIGHT_ATTACK_BASE` so a
  *loaded, non-chip* attack can outrank marginal setup, mirroring the existing
  `WEIGHT_TEMPO_LOADED = 2450` hook which already encodes this idea but is
  Garchomp-pilot-scoped.
- **Cost:** ~2 h. **Blast radius: medium** — changes v1's ordering, which also
  changes the ~47% of decisions resolved by tie-break. That is leverage in both
  directions; it must ship with §4 telemetry.
- **Explicitly not** a forced-attack rule.

### 4. ⭐ Per-game `[gov]` telemetry flush — **include regardless of everything above**

- **Mechanism:** `_gov_flush` is registered via `atexit`, and the platform
  terminates the agent without running `atexit` handlers — **we got zero search
  telemetry from 28 ladder games.** Flush on new-game detection instead
  (`CardTracker.update` already returns a new-game signal and already calls
  `_gov_flush`; the gap is only the final game and process teardown).
- **Cost:** ~1 h. **Blast radius: nil** — instrumentation only, no behaviour
  change, one stderr line per game.
- **Why it matters:** without it we cannot answer "is the search
  discriminating on ladder?" for any future bundle. Every future bundle carries
  it.

### Not proposed

- **Deck change** — closed on piloting-penalty grounds (FINAL_PATH_JUL21.md
  Part 2); nothing here reopens it.
- **Mirror A/B for any of the above** — five consecutive nulls; ladder is the
  instrument.

---

## Summary of findings

| # | finding | status |
|---|---|---|
| 1 | Tie-break returns **v1's top pick**, not engine index order | ✅ premise corrected |
| 2 | v1 ladder puts every setup action above non-lethal attack | ✅ confirmed in code |
| 3 | **94 ENDs (57.3%) with development still available** — search overriding v1 to pass | ✅ measured |
| 4 | **18 ENDs with empty-ish bench + playable Basic-searcher in hand** | ✅ measured |
| 5 | Turn-1 END holding **two Poffin** → turn-2 board-wipe loss | ✅ two verbatim cases |
| 6 | Development defect is **general**, not wipe-specific (wins 47.7% vs losses 51.2%) | ✅ control passed |
| 7 | Attack uptake when legal **36.9%** vs 86–92% on both reference stacks | ✅ measured, novel |
| 8 | Attack share **0.18** (not 0.32); first attack **T7.91** (not T5.5, not in range) | ⚠️ brief corrected |
| 9 | cap=16 horizon harm | ❓ **untested — highest-value open question** |

Stopping here as instructed. Nothing built, nothing submitted.
