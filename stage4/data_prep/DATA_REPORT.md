# Stage 4 / Branch B — Stop 1: data preparation report (2026-07-12)

## Deck

`stage4/deck_list0.csv` — the consensus Alakazam engine list, reconstructed
from replays and **byte-identical between Majkel1337 (#1) and Yushin Ito (#3)**.
60 cards / 22 distinct. vs `metaB_alakazam.csv` (Majkel's old rank-1 list):
+1 Fezandipiti ex, +1 Shaymin, +3 Xerosic's Machinations, +3 Nighttime Mine;
−1 Dudunsparce, −1 Dunsparce, −1 Rare Candy, −1 Enhanced Hammer,
−2 Night Stretcher, −1 Battle Cage, −1 Basic Psychic Energy.

Discovery that moved the plan up: **list-0 predates the 07-10 snapshot** — it
is a community list. bono (prev #6) piloted it through 07-06..09 and Yushin
already ran it in that window at **76% (52W-16L)**. All volume below is
already on disk; no waiting for new dailies.

## Extraction (winning sides only, exact-list filter, per-pilot npz)

Source: 457 list-0 episodes pooled from `data/top_replays_bulk` +
`analysis/phase2_meta_shift/replays_current_top10` → `stage4/data/replays_list0/`.
Encoders: the BC-full pipeline unchanged (`tools/extract_bc_data.py`,
DYN_DECK_TABLES keyed to list-0; MAIN 41-dim, ST_CARD 73-dim, PL decomposition).

| pilot | win-games | MAIN decisions | ST_CARD steps | CARD idx-0 floor | list-0 W% in sample |
|---|---|---|---|---|---|
| Yushin Ito (#3, search 1.5s) | 123 | 4,511 | 3,744 | 57.8% | 68% (123W-58L pooled) |
| bono (prev #6, dropped) | 86 | 4,043 | 2,280 | 53.8% | 51% (86W-80L) |
| Majkel1337 (#1, policy 136ms) | 33 | 1,482 | 867 | 48.2% | 56% (33W-26L) |
| **total** | **242** | **10,036** | **6,891** | | |

vs BC-full-Garchomp's diet: 81 win-games / ~7k MAIN / 2.4k CARD →
**3.0× the games, 1.4× MAIN, 2.9× CARD.** Dailies add ~85 win-sides/day
(retrain option before gates if timeline allows).

ST_CARD context profile (new deck): deck fetches 1,492, **prize fetches
1,085** (new dominant context — the engine interacts with prizes far more
than Garchomp did; encoder handles area=prize natively), bench drops 545,
promotes 696, hand discards 259, gust/switch picks 353.

## C1/C2 coverage (win-side opponent classes)

- **C2 (Crustle stall): 53 anti-Crustle winning games** across the three
  pilots (Yushin 34, bono 11, Majkel 8) = 22% of the training diet. Note the
  Stop-2 addition applies: coverage alone did not save BC-full; the
  expression test on held-out Crustle situations is the real check.
- **C1 (fighting-aggro race)**: only 10 wins vs Lucario/Archaludon-class
  (those archetypes are rare in top-pool matchmaking). Mitigation: C1's
  failure mechanism is race conversion, and list-0's entire game plan is the
  race — mirror + alakazam-family wins (121 games) exercise exactly the
  closure behavior we lacked. Flagged honestly: direct anti-Lucario evidence
  is thin; G7b's archetype pool will test it.

## Pilot-mix question for training (decision at Stop 2)

Baseline plan: train on **Yushin + Majkel** (156 games, 5,993 MAIN, 4,611
CARD — current top-3 pilots only), with per-pilot val split; run a
+bono variant (adds 4k MAIN but a 51% pilot) and a Yushin-only variant as
ablations, pick by combined val + held-out C2 expression eval.

## Held-out C1/C2 eval set (Stop 2 requirement)

From Phase 1's v2.2.0 replays: the 8 Crustle losses (C2) + 14 aggro-race
losses (C1) are on disk. Plan: replay list-0 winners' Crustle games (the 53
above, val-split held out by game) for expression testing, plus the
Phase 1 loss situations as qualitative probes (different deck, so those
serve narrative, not metrics).

## Timeline position

Day 1 of ~9-day projection to G7a; data prep DONE same-day instead of
waiting for dailies (volume already sufficient). Next: train BC-v2
(trainer reuse from `training/train_bc_full.py`).
