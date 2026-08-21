# Phase B refresh (2026-07-21) — current top-10 vs the 07-12 snapshot

Populations:
- **Previous** = leaderboard 2026-07-12 (`leaderboard_2026-07-12.csv`), replays
  `replays_current_top10/` (883 sides).
- **Current** = leaderboard 2026-07-21 (`leaderboard_2026-07-21.csv`), replays
  `replays_top10_jul21/` (277 episodes, 350 top-10 sides, ~30/team via the
  submission-targeted harvest `harvest_jul21.py` — no daily-dataset scanning).
- Our own row = `replays_projectmew_jul21/` (60 episodes of the two live
  submissions, both teammate's: v7 54855847 μ877.8, v8 54863817 μ723.3-settling).

## Roster: 9 of 10 seats churned in 9 days

| rank | team | μ | archetype | dtime med |
|---|---|---|---|---|
| 1 | **Oshbocker** | 1212 | **Marnie's Grimmsnarl ex / Munkidori** | 57 ms |
| 2 | THIRD PTCG Club | 1186 | TR Mewtwo ex stall | 52 ms |
| 3 | Yushin Ito | 1163 | Fezandipiti ex / Dudunsparce | 211 ms |
| 4 | LumenLiquidity | 1158 | Dudunsparce / Alakazam | 58 ms |
| 5 | **junlee789** | 1152 | **Cynthia's Garchomp ex / Roserade — our BC deck** | **1055 ms (search-class)** |
| 6 | GUOHAOYANG | 1149 | Grimmsnarl / Munkidori | 69 ms |
| 7 | __Taichicchi__ | 1145 | TR Mewtwo ex stall | 54 ms |
| 8 | jiatu.l | 1132 | Grimmsnarl / Munkidori | 29 ms |
| 9 | ポケカ前線 | 1123 | Grimmsnarl / Munkidori | 80 ms |
| 10 | 齐乐 | 1119 | Fezandipiti ex / Dudunsparce | 36 ms |

Only **Yushin Ito** survived from the 07-12 list (was #3, still #3 — but the
teammate's Jul-19/20 intel "Yushin #1 on Alakazam" is stale: he pilots
Fez/Dudunsparce). Dropped: Majkel (#1→16), Budew (#2→38), kashiwashira
(#4→29), MPGaming (#5→205), BigBugginnings (#6→28), S4nkurero (#7→19),
LiamK (#8→55), nasuo445 (#9→83, teacher now far off-meta), Eduardo (#10→101).
Our team: **#427, μ877.8** (teammate's v7 search agent holds it).

## Archetype census (07-12 → 07-21)

| archetype | then | now |
|---|---|---|
| Crustle attrition shells | **5** | **0 — extinct** |
| Grimmsnarl ex / Munkidori | 0 | **4 (incl. #1)** |
| Fez / Dudunsparce | 3 | 2 |
| TR Mewtwo stall | 1 | 2 |
| Dudunsparce / Alakazam | 0 | 1 |
| Cynthia's Garchomp (our deck) | 1 (nasuo, #9) | 1 (junlee789, **#5**) |

Confirms the teammate's Grimmsnarl reading (his 1200-game measurement: 66%
overall, no RPS cycle): Grimmsnarl/Munkidori is now the plurality top deck and
holds #1. The Crustle wall we tuned the stall-gate against has vanished from
the top — attrition is now stall (Mewtwo) or engine-race (Fez/Dudu), not
Crustle chip.

## Decision-speed class

8 of 10 under ~80 ms (fast policies), but **two search-class agents now sit in
the top 5**: Yushin (211 ms) and junlee789 (**~1.1 s/decision, #5, μ1152 —
piloting our exact BC archetype**). The 07-12 claim "search is a dead class at
the top" is weakened: a determinized-search pilot on Cynthia's Garchomp
outranks every fast Garchomp pilot we ever measured. Relevant to the
teammate's shell (1.3–2 s/decision, same class).

## Per-turn behavioral profile (own turns; §6n-comparable)

No `Ability` log type exists in this replay schema, so ability-use-when-legal
is not directly measurable; `xDr/t` = extra draws per own turn (draws beyond
the turn draw) is the draw-engine-usage proxy.

| team | FA | FE | hand T3/T5/T7 | xDr/t | atk-share/turn |
|---|---|---|---|---|---|
| Oshbocker (#1) | 4.2 | 3.6 | 6.1 / 5.4 / 4.8 | 2.2 | **0.64** |
| THIRD (#2) | 5.7 | 5.4 | 5.5 / 6.3 / 6.0 | 2.8 | 0.49 |
| Yushin (#3) | 3.8 | 3.5 | 7.4 / 9.0 / 9.3 | **4.6** | 0.60 |
| LumenLiquidity (#4) | 4.7 | 3.5 | 6.6 / 7.7 / 9.7 | 3.9 | 0.46 |
| junlee789 (#5) | 5.1 | 3.7 | 5.5 / 4.7 / 5.6 | 2.2 | 0.56 |
| 齐乐 (#10) | 5.1 | 3.7 | 6.7 / 9.3 / 8.5 | 4.0 | 0.54 |
| **Project Mew (live, v7/v8)** | **6.1** | **5.1** | **4.5 / 4.2 / 4.3** | 2.1 | **0.24** |

Read: every top team attacks in 46–64% of its own turns; our live agent 24%.
Their hands grow or hold 5.5–9.3; ours decays to ~4.3. First attack T3.8–5.7
vs our T6.1; first evolution T3.5–5.4 vs our T5.1. This is the teammate's §6n
gap (ability timing → hand size → late assembly → losing the race) reproduced
from an independent harvest with independent metrics — same deficit, two
angles. Engine-heavy decks (Yushin, 齐乐, LumenLiquidity: 3.9–4.6 extra
draws/turn) show what "using the draw engine" looks like at the top; our 2.1
on a Dudunsparce-carrying deck is the measurable form of his
"61% ability-use-when-legal vs their 88%".

## What changed for path planning

1. Grimmsnarl/Munkidori is the deck to beat (4 seats incl. #1) — and the
   teammate's v7 is 0W–5L against it with a structural excuse (no Grass).
2. Our Garchomp archetype is top-5 viable **under a search pilot** (junlee789).
   The "deck at its ceiling" worry is dead on the ladder too, not just in his
   pilot-vs-deck experiment (§6m).
3. Teacher pool for any BC-v3: Yushin's sub 54773249 exposes 1000 episodes,
   junlee789's 54775633 exposes 1000, jiatu.l 779, 齐乐 639 — plenty of fresh
   top-1000 games one API page away (`_episodes_meta.json` has the ids).
4. nasuo445 (our old teacher) at #83 confirms teacher staleness; Majkel's and
   Yushin's old Alakazam lists (our list-0) no longer appear in the top 10 —
   LumenLiquidity is the lone Alakazam seat.
