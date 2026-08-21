# PHASE 1 — conditional rule mining

**Evidence base only. Nothing designed, built or submitted.** v1-alone
throughout; governor, `cap=16`, `END_VETO`, `EVAL_FIX`, `PROMOTE_RULE`,
`LETHAL_PROBE`, the candidate arms and R1/R2/R3 all stay off.

## Method

Prior mining (PILOT_KNOWLEDGE.md) reported **unconditional** rates. This records
the full state context of every MAIN decision and partitions on it, producing
`state -> action-distribution` cells.

**Deck-matched comparison.** "Them" is every **top-10 Grimmsnarl side** across
`replays_top10_jul21/`, `jul22/` and `jul26/` (504 sides, **19,323 MAIN
decisions**). "Us" is our **D1 Grimmsnarl** self-play arm (200 sides, **6,692
decisions**). Same 60 cards, different pilot — so any divergence is piloting,
not deck.

Every feature is computed from the seat's own observation, so all of it is
available to the agent at decision time: turn bucket, prizes remaining both
sides, whether we can KO the opponent's active now, whether our active is KOable
by the opponent's best printed attack, bench counts, energy attached vs cheapest
attack cost, hand size, and whether the turn's supporter has resolved.

Cells are ranked by **leverage = cell frequency x total-variation distance**
between their action distribution and ours. Only cells with **n >= 30 on both
sides** are reported; 41 qualified.

---

## THE HEADLINE — we spend the turn the moment we can attack

The top cell is not a priority problem. It is a **sequencing** problem, and it
is the largest divergence in the dataset.

**ATTACK ends the turn. Every other action is free.** Measured over own turns
that contained an attack:

| | top-10 Grimmsnarl | **ours** |
|---|---|---|
| own turns measured | 3025 | 1525 |
| turns containing an attack | 62.9% | 49.5% |
| turns using an ability | **80.2%** | 61.8% |
| **actions taken before the attack** | **mean 5.87, median 6** | **mean 2.97, median 2** |
| **attacked as the FIRST action of the turn** | **2.0%** (39/1903) | **43.0%** (325/755) |
| what preceded the attack | PLAY 44% ABILITY 29% EVOLVE 14% ATTACH 10% | PLAY 50% ABILITY 17% EVOLVE 16% ATTACH 13% |

**Top-10 attack first in 2% of their attacking turns. We do it in 43%.** They
average ~6 free actions before swinging; we average ~3.

The mechanism is `WEIGHT_LETHAL = 100000`: the instant a KO is available the
attack outranks everything, the agent takes it, and the turn ends with cards
unplayed and abilities unused. In the `can_KO` cell our action distribution is
**100% ATTACK** against their 22%.

The 11x difference in cell size (5057 decisions vs 451) is itself the finding:
**they linger in can-KO states extracting value; we exit immediately.**

---

## RANKED DIVERGENCE CELLS — top 20 by leverage

*"per own-side" = expected occurrences of the cell per side (their 38.3
decisions/side, our 33.5).*

| # | condition | n(them) | n(us) | TVD | per own-side | **their top actions** | **our top actions** |
|---|---|---|---|---|---|---|---|
| 1 | `can_KO` | 5057 | 451 | **0.784** | 10.0 | PLAY 35% ABILITY 25% ATTACK 22% | ATTACK 100% |
| 2 | `supporter_pending` | 12022 | 4199 | **0.223** | 23.8 | PLAY 44% ABILITY 26% EVOLVE 11% | PLAY 52% ATTACH 15% EVOLVE 13% |
| 3 | `attacker_powered` | 11029 | 2483 | **0.187** | 21.9 | PLAY 36% ABILITY 25% ATTACK 17% | PLAY 41% ATTACK 30% ABILITY 12% |
| 4 | `supporter_done` | 7301 | 2493 | **0.270** | 14.5 | PLAY 38% ABILITY 18% ATTACK 17% | ABILITY 34% PLAY 29% RETREAT 13% |
| 5 | `bench>=3` | 15385 | 4802 | **0.114** | 30.5 | PLAY 36% ABILITY 26% EVOLVE 12% | PLAY 40% ABILITY 19% ATTACK 14% |
| 6 | `atk_legal & supporter_pending` | 6170 | 1390 | **0.276** | 12.2 | PLAY 39% ABILITY 31% ATTACK 10% | PLAY 45% ATTACK 32% EVOLVE 11% |
| 7 | `turn=T7+ & powered` | 7255 | 1660 | **0.225** | 14.4 | PLAY 34% ABILITY 31% ATTACK 16% | PLAY 37% ATTACK 35% ABILITY 12% |
| 8 | `hand>=6` | 8994 | 3572 | **0.176** | 17.8 | PLAY 48% ABILITY 21% EVOLVE 12% | PLAY 43% ATTACH 15% EVOLVE 14% |
| 9 | `turn=T7+` | 9573 | 3683 | **0.156** | 19.0 | PLAY 35% ABILITY 31% ATTACK 12% | PLAY 42% ABILITY 18% ATTACK 16% |
| 10 | `can_KO & race=BEHIND` | 1850 | 114 | **0.804** | 3.7 | PLAY 40% ABILITY 23% ATTACK 20% | ATTACK 100% |
| 11 | `safe_active` | 14036 | 3912 | **0.095** | 27.8 | PLAY 44% ABILITY 19% ATTACK 11% | PLAY 44% ABILITY 14% ATTACK 13% |
| 12 | `can_KO & race=AHEAD` | 1675 | 210 | **0.786** | 3.3 | ABILITY 33% PLAY 28% ATTACK 21% | ATTACK 100% |
| 13 | `can_KO & race=EVEN` | 1532 | 127 | **0.758** | 3.0 | PLAY 36% ATTACK 24% ABILITY 20% | ATTACK 100% |
| 14 | `atk_legal & supporter_done` | 4555 | 729 | **0.207** | 9.0 | PLAY 33% ATTACK 28% ABILITY 19% | ATTACK 42% ABILITY 25% PLAY 24% |
| 15 | `race=AHEAD` | 3839 | 1237 | **0.231** | 7.6 | ABILITY 34% PLAY 29% ATTACK 15% | PLAY 39% ATTACK 26% ABILITY 14% |
| 16 | `our_active_KOable` | 5287 | 2780 | **0.155** | 10.5 | PLAY 36% ABILITY 33% EVOLVE 12% | PLAY 43% ABILITY 19% EVOLVE 14% |
| 17 | `no_KO_available` | 5668 | 1668 | **0.142** | 11.2 | PLAY 39% ABILITY 26% ATTACK 14% | PLAY 48% ATTACK 18% ABILITY 15% |
| 18 | `attacker_not_powered` | 8294 | 4209 | **0.095** | 16.4 | PLAY 49% ABILITY 20% ATTACH 13% | PLAY 45% ABILITY 19% ATTACH 14% |
| 19 | `KOable & attacker_powered` | 2965 | 1063 | **0.266** | 5.9 | ABILITY 37% PLAY 30% ATTACK 11% | PLAY 42% ATTACK 23% ABILITY 14% |
| 20 | `race=EVEN` | 8374 | 3281 | **0.093** | 16.6 | PLAY 47% ABILITY 17% ATTACH 12% | PLAY 46% ABILITY 14% ATTACH 13% |

---

## The five cells that matter most, in full

### can_KO
| action | PLAY | ATTACH | EVOLVE | ABILITY | RETREAT | ATTACK | END |
|---|---|---|---|---|---|---|---|
| **top-10** | 34.6% | 8.4% | 9.2% | 25.4% | 0.8% | 21.6% | 0.0% |
| **us** | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| delta | -34.6 | -8.4 | -9.2 | -25.4 | -0.8 | +78.4 | -0.0 |

### atk_legal & supporter_pending
| action | PLAY | ATTACH | EVOLVE | ABILITY | RETREAT | ATTACK | END |
|---|---|---|---|---|---|---|---|
| **top-10** | 39.5% | 7.9% | 10.2% | 30.6% | 1.5% | 10.4% | 0.0% |
| **us** | 44.5% | 8.1% | 10.8% | 4.5% | 0.0% | 32.1% | 0.0% |
| delta | +5.1 | +0.3 | +0.6 | -26.1 | -1.5 | +21.7 | -0.0 |

### supporter_done
| action | PLAY | ATTACH | EVOLVE | ABILITY | RETREAT | ATTACK | END |
|---|---|---|---|---|---|---|---|
| **top-10** | 38.0% | 10.5% | 11.1% | 17.8% | 2.5% | 17.3% | 2.8% |
| **us** | 29.3% | 3.0% | 7.9% | 34.1% | 13.2% | 12.4% | 0.0% |
| delta | -8.7 | -7.4 | -3.2 | +16.3 | +10.7 | -4.9 | -2.8 |

### turn=T7+ & powered
| action | PLAY | ATTACH | EVOLVE | ABILITY | RETREAT | ATTACK | END |
|---|---|---|---|---|---|---|---|
| **top-10** | 34.4% | 7.6% | 8.5% | 30.9% | 1.9% | 16.4% | 0.3% |
| **us** | 37.1% | 5.5% | 9.9% | 12.2% | 0.5% | 34.8% | 0.0% |
| delta | +2.7 | -2.1 | +1.4 | -18.7 | -1.4 | +18.3 | -0.3 |

### safe_active
| action | PLAY | ATTACH | EVOLVE | ABILITY | RETREAT | ATTACK | END |
|---|---|---|---|---|---|---|---|
| **top-10** | 44.0% | 10.7% | 10.8% | 19.4% | 1.6% | 11.2% | 2.4% |
| **us** | 43.6% | 11.2% | 9.0% | 14.5% | 8.6% | 13.1% | 0.0% |
| delta | -0.4 | +0.5 | -1.7 | -4.9 | +7.1 | +1.9 | -2.4 |

---

## What the evidence supports

Four patterns recur across independent cells, each with large n:

**1. Attack last, not first.** `can_KO` (n=5057/451, TVD 0.784), plus the
turn-sequence measurement above. **The single largest effect in the data.**

**2. Abilities are systematically under-used, and most so when an attack is
available.** `atk_legal & supporter_pending`: they ABILITY 30.6% vs our 4.5%
(-26.1). `turn=T7+ & powered`: 30.9% vs 12.2%. `supporter_pending`: 26.2% vs
5.9%. Abilities are free — they do not end the turn — which is why top-10 fire
them before committing.

*Note: R1 in PILOT_KNOWLEDGE.md raised ability priority in the static ladder and
failed. The conditional finding is different in shape: the issue is not that
abilities rank too low globally, it is that they are skipped **specifically when
an attack is on the menu**, because attack wins and ends the turn.*

**3. We retreat when we are safe.** `safe_active` (n=14036/3912): retreat 8.6%
vs their 1.6%. `supporter_done`: 13.2% vs 2.5%. Retreat costs energy and tempo
and we spend it in states where nothing threatens us.

**4. The prize race does not change our behaviour, and it changes theirs.**
`can_KO & race=BEHIND` vs `can_KO & race=AHEAD`: their ABILITY share moves
23.4% -> 33.0% and PLAY 39.7% -> 27.6%. Ours is 100% ATTACK in both. We have no
race-conditional behaviour at all, which is exactly what "two state-conditional
rules in the whole policy" predicts.

## Scope limits, stated plainly

- **The `can_KO` cell is partly definitional.** Our 100%-ATTACK share is forced
  by `WEIGHT_LETHAL`, so the TVD of 0.784 overstates how much *free* choice
  differs. The turn-sequence measurement is the honest version of that finding,
  and it is independent of the cell definition.
- **KO-ability uses printed damage**, ignoring abilities, tools and weakness, so
  `can_ko` and `ko_able` are proxies. They are computable at decision time,
  which is what a shipped rule needs.
- **Their sides span three harvest dates** (07-21, 07-22, 07-26) and a shifting
  field; ours is a self-play mirror. The deck is matched, the opposition is not.
- **Self-play overstates ladder by ~2x** (0.4574 vs 0.2370 measured). Nothing
  here is a strength claim; it is a behavioural difference.

## Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/conditional_mine.py` | state extractor + cell partitioning |
| `stage4/rl_ours/conditional_probe.py` | turn-sequence measurement |
| `scratchpad/s3/conditional_cells.json` | all 41 qualifying cells |

**STOP — Phase 1 gate. Awaiting approval before Phase 2 design.**
