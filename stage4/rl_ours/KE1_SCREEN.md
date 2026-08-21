# KE1 — Kangaskhan-native free-draw-ability rule, screen

**Nothing submitted.** Written before any arm below is run.

## Why this exists (in contrast to K1)

K1 (KANGASKHAN_E1.md) tested whether Grimmsnarl's E1 sequencing rule
transferred wholesale to Kangaskhan/Raging Bolt. It didn't — same failure
shape as ARCHALUDON_TEST, driven by Raging Bolt's Burst Roar being a hybrid
attack+refresh effect that E1 misfires on. **That was a port test. This is
not.** KE1 is a fresh rule built directly from `kangaskhan_mine.py`'s own
Phase-1 output for this deck:

- The `can_KO` cell (n=404 top-10 pilots / n=342 us, TVD=0.720 — largest
  TVD in the mining table by 3x) showed top-10 taking **ABILITY 24.0%** of
  decisions when a lethal was on the menu, versus **0.0%** for us.
- The specific ability, verified against `card_data.json`: Mega Kangaskhan
  ex (id 756)'s *Run Errand* — "Once during your turn, if this Pokémon is
  in the Active Spot, you may use this Ability. Draw 2 cards." Free
  (no cost), doesn't end the turn.

## What KE1 does, mechanically

`_ke1_veto` in `main.py`. Fires **only** when:
1. Chosen action is a terminal type (ATTACK / RETREAT / END).
2. Our active carries a skill matching the pattern *"once during your turn"
   + "active spot" + "draw N cards"* (N in 1-5) with **no "discard"** in
   the same skill text — the last exclusion is deliberate, to avoid the
   Cinderace/Burst-Roar hybrid-effect shape that broke E1 on Archaludon and
   K1 here.
3. The engine still offers an `OT_ABILITY` option on the current menu
   (authoritative signal that the once-per-turn use is still legal — no
   manual firing tracker needed).

When those all hold, swap the chosen index to the Ability. Otherwise
`_ke1_veto` returns `result` unchanged. `_validate_result` and the fallback
chain downstream are unaffected.

**Unit-tested before any self-play:** ability detection correctly matches
Run Errand (756), rejects Munkidori's Adrena-Brain, Fezandipiti's Flip the
Script, Meowth's Last-Ditch Catch, and Raging Bolt (no ability). Veto
correctly abstains when flag is off, when chosen type is non-terminal, and
when the active is a card without the free-draw ability.

## Arms — self-play mirror, `--deck metaX_kangaskhan_top10.csv`

Comparators from KANGASKHAN_E1.md (400g runs already on disk):

| arm | config | velocity | own turns |
|---|---|---|---|
| K0 (baseline) | v1-alone, no rules | 0.2991 | 7.75 |
| K1 (E1 ported) | + SEQ_E1 | 0.2850 | 7.89 |

New arm:

| arm | config |
|---|---|
| **KE1** | v1-alone + KE1_FREE_DRAW |

## PRE-REGISTERED BANDS — fixed before running

**Primary: prize velocity, KE1 vs K0 (both at 400 games / 800 sides).**

| band | condition | reading |
|---|---|---|
| **PASS** | KE1 − K0 ≥ +0.02 | mined rule transfers cleanly; ship-verify and continue Kangaskhan native build |
| **AMBIGUOUS** | 0 ≤ delta < +0.02 | non-negative but small; extend before deciding, same rule as every prior test |
| **FAIL** | KE1 − K0 < 0 | even a strictly-dominated free-draw veto doesn't help self-play — most likely the self-play mirror can't test this rule properly (opponent also gets the free draws, cancelling any tempo edge); note the constraint, do not ship, move on |

**Guards, not verdict inputs:** own-turns not higher than K0's 7.75;
attack-when-legal not down more than 3pts from K0's 36.7%. `ke1_veto` fire
count reported to confirm mechanism engages (expected: nonzero, but small
per game — Run Errand is once-per-turn and requires being in the active
spot).

**Threshold lower than E1's +0.03 because this is a strictly-dominated
rule** (taking a free ability before a terminal action is not a tradeoff,
it's a free option), so any positive delta above noise is meaningful.

**Bands are not revised after seeing results.**

---

## RESULTS

| n | K0 baseline | KE1 | delta | 95% CI | own-turns guard | atk-when-legal |
|---|---|---|---|---|---|---|
| **400g (800 sides each)** | 0.2991 | 0.2920 | **−0.0071** | **[−0.0306, +0.0167]** | 7.76 vs 7.75 (equal) | 36.6% vs 36.9% |

`ke1_veto` firing rate: **1.4 per game** (562 total fires in the last-game
cumulative STATS, divided by 400 games).

## VERDICT

**FAIL under the pre-registered band** (delta < 0), but the effect surface
is too small for this to be a meaningful signal either way.

### Root cause is different from K1's — this one is scope, not misfire

K1 failed because E1 misfired on Raging Bolt's dual-purpose Burst Roar
(hundreds of unintended vetoes per game). **KE1's per-turn fire rate is
1.4/game** — Mega Kangaskhan needs to be in the active spot with an unused
Run Errand AND v1 must have chosen a terminal action AND the engine must
still be offering the Ability on that specific menu. In a self-play mirror
where opponents also have the same free draws, and where the deck cycles
attackers via Meowth ex bounces / Ogerpon promotions, the pattern qualifies
only ~1 time per game.

**Delta is inside noise (95% CI spans zero, ±0.024)**; the point estimate
being slightly negative is inter-run RNG at 1.4 fires/game, not a real
signal. This screen cannot distinguish "KE1 is a strictly-dominated no-op"
from "KE1 is a small positive effect" at n=400 — the confidence bound is
wider than any effect a rule this rarely-firing could produce.

### What this closes and what it doesn't

**Closes:** any hope that a single small sequencing rule mined from the
`can_KO` cell is enough on its own to move Kangaskhan's velocity
measurably. Even the cleanest, correctly-carved-out rule (excludes the
Cinderace/Burst-Roar hybrid shape by design, unit-verified) is too narrow
in fire rate.

**Does not close:** the broader mining finding. The `can_KO` cell showed a
0.72 TVD across n=746 decisions — top-10 is doing something structurally
different in that state, and KE1 captured only one specific piece of it
(the Run Errand Ability). Other pieces from the same cell that this rule
does *not* touch: **PLAY 33.0%** (top-10 keep playing setup cards even with
lethal on the menu — likely powering up secondary attackers via Ogerpon's
Teal Dance, or benching Meowth ex for the Last-Ditch Catch draw). Those
would need their own scoped rules, mined and screened separately.

**Time-cost reality check for the user:** building the full complement of
mined rules for Kangaskhan — one per relevant cell, each individually
unit-tested and pre-registered like KE1 — is exactly the multi-week arc
that produced Grimmsnarl's E1+E2+T1+T2. The single-rule effect at n=400 is
in the noise floor; the *set* of rules is what would move the needle. This
is not a quick add-on; it is the same scale of investment the Grimmsnarl
build required, on a deck we're starting from scratch on.

