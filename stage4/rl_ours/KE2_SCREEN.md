# KE2 — Kangaskhan-native free-draw-ability-before-ATTACH rule, screen

**Nothing submitted.** Written before any arm below is run.

## Why this exists

KE1 targeted the `can_KO` cell (n=746, TVD=0.720) but fired only 1.4x per
game — too narrow to move the needle at n=400. KE2 targets a much larger
surface: the `supporter_pending` cell — 54.1% of all MAIN decisions,
n_them=1693, TVD=0.226. The specific gap:

| action | top-10 | us | gap |
|---|---|---|---|
| ATTACH | 5.5% | **20.0%** | **us +14.5pt** |
| ABILITY | **31.2%** | 13.8% | **us −17.4pt** |
| PLAY | 48.6% | 54.6% | +6pt |

We spend on ATTACH-as-filler before extracting free draws; top-10 draws
first and attaches after. Same mechanism-class as KE1 (free-draw ability
first before a resource-committing action), different trigger (chose
ATTACH, not chose terminal). Should fire much more often because ATTACH is
a per-turn action that qualifies whenever the supporter is still pending.

## What KE2 does, mechanically

`_ke2_veto` in `main.py`. Fires only when:
1. Chosen action is `OT_ATTACH`.
2. `supporterPlayed` is False for this turn.
3. Our active or bench includes a Pokemon with a free-draw ability
   (reuses `_has_free_draw_ability` — same "once during your turn" +
   "active spot" + "draw N cards" − "discard" filter as KE1).
4. The engine offers an `OT_ABILITY` on the menu targeting that Pokemon.

When all four hold: swap the chosen index to the Ability. Same
strict-dominance argument as KE1 — taking a free draw before an attach
does not prevent the attach; both are non-terminal, and the MAIN menu
re-presents afterward, so KE2 only adds information to the subsequent
attach decision.

**Unit-tested before any self-play, 6/6 pass**: fires when all conditions
hold, abstains cleanly when supporter is already played / chosen type is
PLAY not ATTACH / no free-draw Pokemon on board / flag is off / KE1 is off
(independence).

## Arms — self-play mirror, `--deck metaX_kangaskhan_top10.csv`, 400 games each

| arm | config |
|---|---|
| K0 (baseline, already on disk) | v1-alone, no rules |
| KE1 (already on disk) | + KE1_FREE_DRAW |
| **KE2** | + KE2_ABIL_BEFORE_ATTACH |
| **KE12** | + KE1 + KE2 combined |

## PRE-REGISTERED BANDS — fixed before running

**Primary: prize velocity, KE2 vs K0.** Same +0.02 pass line as KE1 (both
are strictly-dominated rules, so any positive above noise is meaningful).

| band | condition | reading |
|---|---|---|
| **PASS** | KE2 − K0 ≥ +0.02 | mined rule transfers; screen KE12 for stack effect and continue |
| **AMBIGUOUS** | 0 ≤ delta < +0.02 | extend to 600g before deciding, same rule as prior tests |
| **FAIL** | KE2 − K0 < 0 | ATTACH-before-Ability was correct on this deck (self-play mirror equalizes both sides); note the constraint, do not ship |

**Secondary check on KE12:** does layering KE1 on top of KE2 produce a
larger gain than KE2 alone? Only meaningful if KE2 itself is at least
non-negative — if KE2 fails, KE12 is not evaluated for a ship decision
(KE1 alone was already tested and failed to clear noise).

**Guards, not verdict inputs:** own-turns not higher than K0's 7.75;
attack-when-legal not down more than 3pt from K0's 36.7%. `ke2_veto`
fire count reported to confirm mechanism engages (expected: substantially
higher than KE1's 1.4/game, since trigger is broader).

**Bands are not revised after seeing results.**
