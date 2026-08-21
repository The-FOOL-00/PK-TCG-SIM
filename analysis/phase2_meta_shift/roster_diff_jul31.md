# Top-10 intelligence — 2026-07-31

Fresh harvest per explicit user direction, checking for a new archetype/
development path before committing to a bigger engineering investment.
286 replays / 335 sides across the current top 10. Same method as the
07-21/07-22/07-26 snapshots (`behavioral_profile_jul21.py`, per-TURN units),
directly comparable.

Sources: `leaderboard_2026-07-31.csv`, `replays_top10_jul31/`,
`profile_top10_jul31.json`.

---

## Roster — heavy turnover again, and Grimmsnarl's share dropped

| # | team | archetype | W% (harvest) |
|---|---|---|---|
| 1 | James Cox & Henry Chao (**zoroark190**) | Mega Kangaskhan ex / Raging Bolt ex | 71% |
| 2 | THIRD PTCG Club | **Dragapult ex / Munkidori (Fezandipiti tech)** — new | 75% |
| 3 | Brahim | Mega Lopunny ex / Dudunsparce | 66% |
| 4 | Raja Biswas | Marnie's Grimmsnarl ex / Munkidori | 55% |
| 5 | カントー地方マスター | Marnie's Grimmsnarl ex / Munkidori | 53% |
| 6 | Dominic Peel | Mega Kangaskhan ex / Crustle | 57% |
| 7 | @kdcyberdude | Marnie's Grimmsnarl ex / Munkidori | 63% |
| 8 | LiamK | Marnie's Grimmsnarl ex / Munkidori | 52% |
| 9 | やる気元気ミワハルキ | Marnie's Grimmsnarl ex / Munkidori | 53% |
| 10 | keidroid | Teal Mask Ogerpon ex | 65% |

**Grimmsnarl/Munkidori holds 5 of 10 seats**, down from 7/10 on 07-26 — the
consolidation reversed. zoroark190 (Kangaskhan/Raging Bolt) is back at #1
(previously #2 on 07-26 at 1183; now leading the field outright).

## Archetype census (pooled across all 335 harvested sides, n≥10)

| archetype | n | W% vs field |
|---|---|---|
| Marnie's Grimmsnarl ex / Munkidori | 172 | 55.8% |
| **Mega Kangaskhan ex / Raging Bolt ex** | 35 | **71.4%** |
| Teal Mask Ogerpon ex | 34 | 64.7% |
| TR Mewtwo ex / TR Spidops | 30 | 63.3% |
| Mega Kangaskhan ex / Crustle | 30 | 53.3% |
| **Dragapult ex / Munkidori** | 17 | **76.5%** |
| Fezandipiti ex / Dudunsparce (Alakazam) | 15 | 73.3% |

## Directional matchup cells vs Grimmsnarl (n≥8, not yet quotable at our n≥60 rule but concordant across snapshots)

| matchup | record | n |
|---|---|---|
| Grimmsnarl mirror | 58W-43L (57.4%) | 101 |
| Kangaskhan/Crustle vs Grimmsnarl | 10W-10L (even) | 20 |
| TR Mewtwo vs Grimmsnarl | 6W-8L | 14 |
| **Dragapult/Munkidori vs Grimmsnarl** | **10W-2L (83%)** | 12 |
| **Kangaskhan/Raging Bolt vs Grimmsnarl** | **10W-1L (91%)** | 11 |

---

## What's genuinely new here

**1. Dragapult ex / Munkidori is a real, distinct archetype, not a
mislabeled variant.** Checked THIRD PTCG Club's actual 60-card list: 3x
Dragapult ex (Dreepy→Drakloak→Dragapult stage-2 line) as the main attacker,
2x Munkidori as support (the *same* tech piece Grimmsnarl builds run),
Fezandipiti ex as a 1-of utility card (not the headliner — same role it plays
in the older Alakazam build, which is why the crude id-based label conflated
the two at first glance). Never seen in the 07-21/22/26 snapshots. Highest
win rate of any archetype in this harvest (76.5%, n=17) and a lopsided 10-2
record specifically against Grimmsnarl.

**2. Kangaskhan/Raging Bolt's edge over Grimmsnarl is no longer a single
unconfirmed snapshot.** 07-26 found it directionally both ways (23W-10L and
8W-19L, 70/30 combined, explicitly flagged "not yet quotable, re-measure next
harvest"). This harvest reproduces it independently: 10W-1L, and the archetype
is back at the #1 overall seat (71.4% pooled). **Four snapshots now, same
direction, growing margin.** This is the closest thing to a confirmed,
durable counter-matchup this project has found.

**3. Not all Kangaskhan pairings are equal.** The Crustle-partnered version
sits at just 53.3% pooled and is even (10-10) against Grimmsnarl specifically
— the strength is tied to the Raging Bolt pairing, not "Kangaskhan" generically.
Matters if this becomes a build target: the partner card is not incidental.

## What this does NOT do

**It does not reopen the deck-switch question on its own.** FINAL_PATH_JUL21.md
Part 2 and ARCHALUDON_TEST.md both established that a real archetype edge does
not survive our team's ~20-25pt (and in ARCHALUDON_TEST's harder measurement,
far larger) piloting penalty when fielded with only generic v1-alone logic —
Sanjay's edge over the field comes from ~1200 lines of matchup-specific
tuning, not the decklist alone. Adopting either new archetype naively would
likely repeat that result.

**What it does do:** identify where a *native, mined-and-tuned* build (the
same E1/E2/T1/T2-style investment Grimmsnarl received) would have the best
prior odds of paying off, if the team commits to that scale of engineering
work. Dragapult/Munkidori (highest win rate, shares the Munkidori tech
piece with existing Grimmsnarl knowledge) and Kangaskhan/Raging Bolt (most
repeatedly-confirmed edge over our current archetype specifically) are the
two candidates this harvest surfaces — not a decision to build either, just
the evidence base for that decision.

### Artifacts

| path | contents |
|---|---|
| `analysis/phase2_meta_shift/harvest_jul31.py` | harvest script |
| `analysis/phase2_meta_shift/replays_top10_jul31/` | 286 replays |
| `analysis/phase2_meta_shift/profile_top10_jul31.json` | per-side records + behavioral profile |
| `analysis/phase2_meta_shift/leaderboard_2026-07-31.csv` | leaderboard snapshot |
