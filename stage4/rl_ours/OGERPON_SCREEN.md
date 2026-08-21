# Ogerpon screen — the one deck that survives closure

**Written 2026-08-02, BEFORE any arm was run. Nothing submitted.**

## Why this and not the opponent model

The Part-5 plan in [PATH_AUG02.md](PATH_AUG02.md) was "harden the search shell,
opponent model first." [DECK_SWITCH.md](DECK_SWITCH.md)'s 2×2 addendum kills it:

| | Garchomp | Grimmsnarl | |
|---|---|---|---|
| **v1-alone** | 0.2628 | 0.4574 | deck effect **+0.1946** |
| **search** (`cap=0`) | 0.2430 | 0.4288 | deck effect +0.1858 |
| **search effect** | **−0.0198** [−0.0538, +0.0144] | **−0.0286** [−0.0666, +0.0096] | |

Search is non-positive on **both** decks against a matched control, worsens turn
of first prize on both (11.2→12.9, 9.2→10.3), and costs ~500 ms/decision plus
the governor's entire failure surface. An opponent model would have to pay down
that deficit *before* delivering anything. That is the same "fix the diagnosed
defect and the gap closes" bet that has now failed seven times.

The same table says where value actually lives: **the deck effect is ~10× the
policy effect and the opposite sign.** One deck change produced +0.1946 on the
first attempt under pre-registration; nine policy interventions produced nothing
that cleared a band.

## Why Ogerpon specifically

FINAL_PATH_JUL21 Part 2 closed *counter-deck* selection — picking a deck to beat
the field — and it stays closed. This is not that. This is the closure axis:
which deck does **our** pilot execute best. Reopening condition is a within-team
measurement, which is exactly what this screen is.

From the seven-archetype closure table (writeup §2) and the Jul-31 census
(`roster_diff_jul31.md`):

| deck | our closure | archetype W% vs field | attacker shape |
|---|---|---|---|
| **Teal Mask Ogerpon ex** | **80.9%** ᵃ | **64.7%** (n=34) | Basic, no evolution |
| Marnie's Grimmsnarl ex (shipped) | 79.9% | 55.8% (n=172) | Stage-2 + Rare Candy |
| Mega Kangaskhan / Raging Bolt | 45.0% | 71.4% (n=35) | fails closure |
| Dragapult ex / Munkidori | 46.3% ᵃ | 76.5% (n=17) | fails closure |

Ogerpon is the **only** archetype in the census with a higher field win rate than
Grimmsnarl that does *not* fail closure. It is a Basic-only attacker — the deck
shape our fixed priority order handles best, the same mechanism that put
Grimmsnarl at 79.9%. keidroid holds seat 10 with it at μ1132.5.

**The catch this screen exists to resolve:** ᵃ Ogerpon's 80.9% was measured on the
*second harness*. Absolute values are not comparable to Grimmsnarl's 79.9%. A
same-harness head-to-head has never been run. Everything above is a reason to
measure, not a reason to switch.

## Arms — 300 games each, `horizon_test.py`, both seats same agent

| arm | policy | deck |
|---|---|---|
| `ZG_V1` | v1-alone | Grimmsnarl (control) |
| `ZO_V1` | v1-alone | **Ogerpon** |
| `ZG_SHIP` | E1+E2+T1+T2 (current ship) | Grimmsnarl |
| `ZO_SHIP` | E1+E2 only | **Ogerpon** |

`ZO_SHIP` cannot carry T1/T2 — both are Grimmsnarl-specific (T2 targets Shadow
Bullet's splash, a Grimmsnarl attack; T1 is Boss's Orders and is generic but was
tuned on Grimmsnarl decisions). E1/E2 are generic sequencing. **A switch
therefore forfeits T1/T2 and must beat the shipped build anyway** — that is the
honest bar and `ZG_SHIP` vs `ZO_SHIP` is the row that decides it.

## PRE-REGISTERED BANDS — fixed before any arm runs

Primary: **prize velocity** (prizes ÷ own turns), the DECK_SWITCH.md unit.
Envelopes for closure: Grimmsnarl **0.5725**, Ogerpon **0.5845**.

**Decision row: `ZO_SHIP` vs `ZG_SHIP`** (ship-vs-ship, T1/T2 forfeited).

| band | condition | action |
|---|---|---|
| **PASS** | `ZO_SHIP` velocity ≥ `ZG_SHIP` × 1.10, and bootstrap 95% CI on the difference excludes 0 | escalate: 300-game head-to-head A/B + a canary. Ships only on CI-low > 50% **and** into slot 2 only |
| **MARGINAL** | `ZO_SHIP` ≥ `ZG_SHIP` but CI spans 0 | record, do not act. Not worth a slot at 14 days out |
| **FAIL** | `ZO_SHIP` < `ZG_SHIP` | Ogerpon closed. Grimmsnarl rides |

Secondary, reported either way, **not** action-triggering:

- `ZO_V1` vs `ZG_V1` closure on a **single harness** — settles whether 80.9% vs
  79.9% survives a matched instrument at all. This is the number the writeup's
  footnote ᵃ is hedging, and it is worth having regardless of the ship decision.
- Attack share / own turn and attack-when-legal per arm.

**Kill:** if `ZO_V1` closure lands below `ZG_V1` closure, the Ogerpon hypothesis
is dead on its own terms and the `ZO_SHIP` row is not read for a ship decision.

## ⚠️ Instrument warning — added before reading any arm, after inspecting the list

Both lists validate (60 cards, no unknown ids, only Basic Energy over 4 copies).
But the Ogerpon list is not the deck shape closure was validated on:

| | Ogerpon | Grimmsnarl (shipped) |
|---|---|---|
| basic energy | **17× {G}** | 10× {D} |
| attacker | 4× Teal Mask Ogerpon ex (Basic) | 3× Marnie's Grimmsnarl ex (Stage-2) |
| engine | 4× Tera Orb, 4× Bug Catching Set | 4× Buddy-Buddy Poffin, 3× Rare Candy |
| **disruption** | **4× Crushing Hammer, 4× Judge** | none |

**Prize velocity measures our own prize rate. Crushing Hammer and Judge win by
lowering the *opponent's* prize rate — which our own velocity cannot see.** In a
mirror both seats disrupt each other equally, so the effect partly cancels and
partly suppresses both sides' velocity at once.

This means closure may **misprice this archetype in either direction**, and the
80.9% second-harness figure inherits the same problem. It is the same shape as
lie #2 in the writeup's catalogue — a mirror blind to an effect both sides share.

**Consequence for this screen, fixed now:** a PASS on velocity alone is **not**
sufficient for Ogerpon specifically. PASS additionally requires that
`ZO_SHIP`'s advantage not be explainable as suppressed opponent velocity — check
`own turns / side` across arms. If Ogerpon's velocity edge comes with *fewer own
turns per side* (games ending sooner) rather than more prizes per turn, treat it
as MARGINAL regardless of the CI. A real closure edge should show up as prizes
per turn, not as shorter games.

## RESULT — 2026-08-02, 300 games / 600 sides per arm. **FAIL. Ogerpon closed.**

| | `ZG_V1` Grimm | `ZO_V1` Ogerpon | `ZG_SHIP` Grimm | `ZO_SHIP` Ogerpon |
|---|---|---|---|---|
| **prize velocity** | 0.4725 | 0.4723 | **0.4860** | **0.4699** |
| own turns / side | 7.18 | **5.77** | 7.13 | **5.65** |
| attack share / turn | 47.4% | 36.1% | 45.2% | 35.7% |
| **attack-when-legal** | **88.9%** | **56.2%** | **89.1%** | **54.8%** |
| turn of first prize | 8.6 | 8.4 | 8.8 | 8.3 |

**Decision row `ZO_SHIP` vs `ZG_SHIP`: −0.0161, CI [−0.0416, +0.0094] → FAIL**
(pre-registered: FAIL if `ZO_SHIP` < `ZG_SHIP`). Ogerpon does not ship.

**Closure on a single harness, which is what this screen existed to get:**

| deck | v1-alone | shipped | envelope |
|---|---|---|---|
| Grimmsnarl | 0.4725 / 0.5725 = **82.5%** | 0.4860 / 0.5725 = **84.9%** | 0.5725 |
| Ogerpon | 0.4723 / 0.5845 = **80.8%** | 0.4699 / 0.5845 = **80.4%** | 0.5845 |

Ogerpon's second-harness 80.9% **replicates almost exactly** (80.8% v1-alone) —
the harness was fine. What does not survive is the *ranking*: on one instrument
Grimmsnarl is **82.5%**, not 79.9%, so it leads Ogerpon rather than trailing it.
The writeup's footnote ᵃ was right to refuse the cross-harness comparison, and
**§2 of the writeup should be corrected** — Ogerpon is not our highest-closure
deck; Grimmsnarl is.

### The instrument warning fired exactly as written

The pre-registered guard was: *"if Ogerpon's edge comes with fewer own turns
rather than more prizes per turn, treat it as MARGINAL regardless of the CI."*
Ogerpon runs **5.65 own turns/side against Grimmsnarl's 7.13** — its games end
~20% sooner. It did not need the guard in the end (it lost outright), but the
mechanism is visible and it is worse than mispricing:

**attack-when-legal collapses from 89.1% to 54.8%.** Our pilot has a legal
attack and declines it nearly half the time on Ogerpon, against ~1-in-9 on
Grimmsnarl. That is a piloting failure, not a deck property — and it is the same
54.4% we measured on Garchomp in the DECK_SWITCH 2×2. **Grimmsnarl is the
outlier our pilot happens to execute; two of the three other decks we have
measured this way sit near 55%.**

## Limits, stated before the numbers exist

1. **Mirror self-play.** Measures behaviour and velocity, not ladder strength;
   our writeup §8 records it overstating ladder strength ~2×. Nothing ships off
   this screen alone — PASS escalates to A/B and canary, it does not ship.
2. **A switch costs a slot** and 14 days is not enough to re-mine an
   Ogerpon-native T1/T2 equivalent. The realistic ceiling here is
   "Grimmsnarl-class closure on a deck with a ~9-point better field matchup,"
   not a second +0.19.
3. **This does not outrank restoring v7** ([PATH_AUG02.md](PATH_AUG02.md) Part 2,
   +~178 μ for one upload). It is the best *development* path; it is not the
   best *action*.
