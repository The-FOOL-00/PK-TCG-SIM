# Ladder Intelligence — REFRESHED 2026-07-10

Sources: live leaderboard snapshot (`data/leaderboard_snapshot_2026-07-10.csv`),
908 freshly harvested episodes of the current top-10 across the last 4 daily
datasets (`data/top_replays_bulk/`, gitignored), analyzed with
`tools/bc_feasibility.py --dir data/top_replays_bulk`.

## 1. Current top-10 (2026-07-10)

| rank | team | rating |
|---|---|---|
| 1 | **Yushin Ito** | **1277.8** |
| 2 | Majkel1337 | 1153.7 |
| 3 | MPGaming | 1153.1 |
| 4 | WinDecks | 1138.3 |
| 5 | LiamK | 1127.7 |
| 6 | bono | 1122.2 |
| 7 | nasuo445 | 1107.1 |
| 8 | Sota Uchiyama | 1102.9 |
| 9 | wkonishi | 1097.8 |
| 10 | capbloo | 1089.8 |

Big churn vs our 07-06/07-09 intel: **Yushin Ito is a brand-new #1** (+124
over #2), Majkel1337 fell 1260→1153.7, **kashiwashira dropped out of the
top-12 entirely** (the Mewtwo-stall archetype left the top tier with them).
Our v2.0.0 sits at μ=614; team incumbent (Sanjay PPO) 616.8.

## 2. Harvest + per-team decision volume

812 top-10 episodes kept this harvest (908 total files incl. probe), scanning
1,392 episodes across 2026-07-06…09 (64% of random episodes involve a top-10
team — matchmaking clusters the top). Winning-side decisions recovered after
the step-i/i+1 alignment:

| team | episodes kept | winning MAIN-single targets | total winning decisions |
|---|---|---|---|
| Majkel1337 | 150 | **6,668** | 9,829 |
| nasuo445 | 145 | 4,610 | 7,402 |
| Yushin Ito | 210 | 4,525 | 9,221 |
| capbloo | 158 | 4,151 | 7,088 |
| bono | 178 | 3,770 | 6,362 |
| MPGaming | 75 | 1,999 | 2,936 |
| LiamK | 95 | 1,704 | 2,668 |
| WinDecks | 71 | 801 | 1,494 |
| wkonishi | 27 | 727 | 1,007 |
| Sota Uchiyama | 27 | 474 | 1,136 |

**No team below the 200-decision data-thin threshold** (min: Sota 474).
Sota/wkonishi are at 27 episodes (just under the 28 quota; ≥15 required — OK).

## 3. Alignment check (refreshed set)

**99.7% clean** (49,143 valid / 147 invalid) — better than the original 99.2%.
The step-i-observation ↔ step-i+1-action alignment holds across the field.

## 4. Decision-category mix (vs original 3A)

| category | refreshed | original 3A |
|---|---|---|
| MAIN-single (BC-usable) | **60%** (29,429) | 74% |
| ST_CARD sub-decisions (fetch/target) | 30% | 18% |
| yes/no, energy, evolve-sub, other | 9% | 7% |
| MAIN-multi | 1% | 1% |

**All 29,429 MAIN-single decisions encode cleanly** (0 failures) with the
existing 170+41 scheme. The mix shifted: the current top meta is more
fetch/effect-heavy (Fezandipiti / Grimmsnarl / Poffin engines), so BC now
covers ~60% of decisions rather than 74% — the other 40% stays on the v1
heuristic. Slightly reduced coverage; flagged.

## 5. Per-deck BC target pool (winning sides, all top-10 pooled)

| deck (energy) | teams (sides) | targets | weighted avg rating |
|---|---|---|---|
| **Dudunsparce / Alakazam (E3)** | Majkel1337 (119), wkonishi (27) | **6,821** | 1,143 |
| **Fezandipiti ex / Dudunsparce (E2+E3)** | bono (137), **Yushin Ito (68)**, LiamK (26) | **5,371** | **1,169** |
| **Cynthia's Garchomp / Roserade (E5)** | nasuo445 (145) | **4,610** | 1,107 |
| Alakazam / Alakazam + Alakazam/Dudunsparce (E2) | capbloo (158) | 4,151 | 1,090 |
| Mega Kangaskhan ex / Crustle (E1) | MPGaming (75), bono (41) | 3,006 | 1,142 |
| Marnie's Grimmsnarl ex / Fezandipiti ex (E10) | **Yushin Ito (120)** | 2,385 | **1,278** |
| Cornerstone Ogerpon ex / Crustle (E8) | LiamK (65) | 962 | 1,128 |
| Mega Starmie ex / Dusknoir (E9) | WinDecks (71) | 801 | 1,138 |
| Marnie's Grimmsnarl ex / Dudunsparce (E10) | Majkel1337 (29) | 539 | 1,154 |
| Marnie's Grimmsnarl ex / Munkidori (E10) | Sota Uchiyama (27) | 474 | 1,103 |

Note: **Majkel's primary Alakazam list (119 sides) is still byte-identical to
our shipped `metaB_alakazam.csv`** — deck files, card_data and gate infra for
it are already in the repo.

## 6. Meta shift vs the week-old intel

- **New at the very top:** Marnie's Grimmsnarl ex / Fezandipiti ex is the new
  #1's flagship (120 sides, 1278 rating) — last week this archetype sat mid-pack
  at 33% win rate. **Fezandipiti ex / Dudunsparce** is the biggest riser
  (played by #1, #5 and #6).
- **Dropped out:** Team Rocket's Mewtwo stall (kashiwashira) — gone from the
  top tier. The Mega Kangaskhan **/ Raging Bolt (E16)** variant also vanished;
  Kangaskhan now runs **/ Crustle at E1** (near-energyless — a surprise
  entrant variant we had not seen).
- **Alakazam family: still the largest, no longer #1.** Three of the top-10
  (Majkel #2, wkonishi #9, capbloo #10) pilot Alakazam variants — ~11.9k
  pooled targets — but the crown moved to Grimmsnarl/Fezandipiti.
- **Field diversified:** 10 distinct archetypes across the top-10 (vs a
  Garchomp/Alakazam/Kangaskhan-concentrated picture last week). Dudunsparce
  appears in 5 of the 10 decks as the universal draw engine.

## 7. RECOMMENDATION — top-3 BC target decks

Ranking principle: for *imitation*, engine complexity is much less of a
blocker than it was for search/heuristics — the demonstrations *contain* the
sequencing knowledge; volume and pilot quality dominate. (Small-data caveat:
29k targets total ≈ 6% of the S1 corpus; nets must stay small/regularized.)

1. **Dudunsparce / Alakazam (E3) — primary recommendation.**
   Volume: **6,821** targets (largest single-list pool), from the #2 and #9
   pilots. We already ship this exact list: deck file, card_data, and the G7
   comparison (BC vs our failed search+Alakazam, μ=548) are ready today — the
   scientifically cleanest test of whether BC solves the sequencing failure.
   Ceiling proxy 1,143 and we have Majkel's full game-plan signature from the
   earlier intel (44-turn denial grind).
2. **Fezandipiti ex / Dudunsparce (E2/E3) — highest ceiling.**
   5,371 pooled targets from three independent pilots including the new #1
   (weighted rating 1,169, the highest of any multi-team archetype). Risk:
   three different piloting styles = label noise; deck/card_data not yet
   staged (half a day of prep).
3. **Cynthia's Garchomp / Roserade (E5) — simplest engine.**
   4,610 targets from one coherent pilot (nasuo445). Best architecture-fit
   fallback if BC underfits on complex engines, and the deck is already
   staged from Stage 1. Lowest ceiling (1,107) of the three.

Not recommended despite rating: Grimmsnarl/Fezandipiti (the #1's deck) has
only 2,385 targets from a single pilot — data-thin for a first BC attempt;
revisit after the pipeline is proven, potentially pooling with Grimmsnarl
variants (3,398 combined).

**STOPPED here per plan — awaiting deck pick before Phase 3B training.**
