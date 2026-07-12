# Phase 2 — Roster diff: previous top-10 vs current top-10

Populations compared:
- **Previous** = leaderboard snapshot 2026-07-10 (`data/leaderboard_snapshot_2026-07-10.csv`),
  the list the 812-episode BC harvest targeted. Replays: `data/top_replays_bulk/`
  (908 episodes, 1136 top-10 sides, all 10 teams covered 27–210 sides).
- **Current** = leaderboard pulled 2026-07-12 (`leaderboard_2026-07-12.csv`).
  Replays: `replays_current_top10/` (610 episodes from the 07-10/07-11 daily
  datasets, 883 top-10 sides; Eduardo n=6 and S4nkurero n=18 are thin).
- Note: LADDER_INTEL.md (07-08 era) is an older third snapshot — kashiwashira
  was rank 2 then, dropped out of the 07-10 list, and is now back at #4.

## Rank table

| team | 07-10 rank | 07-12 rank (μ) | deck then → now |
|---|---|---|---|
| Majkel1337 | 2 | **1** (1231) | Dudunsparce/Alakazam → **Fezandipiti ex/Dudunsparce** (full switch, 172/172 sides) |
| Budew | — | **2** (1221) | *new* — Mega Kangaskhan ex/Crustle |
| Yushin Ito | 1 | **3** (1210) | Grimmsnarl/Fezandipiti → **Fezandipiti ex/Dudunsparce** (113/176 sides, rest Grimmsnarl) |
| kashiwashira | — (was #2 on 07-08) | **4** (1183) | returnee — Team Rocket's Mewtwo ex/Spidops stall |
| MPGaming | 3 | **5** (1167) | Mega Kangaskhan ex/Crustle (unchanged) |
| youtube.com/@BigBugginnings | — | **6** (1149) | *new* — Dragapult ex/Fezandipiti ex |
| S4nkurero | — | **7** (1145) | *new* — Cornerstone Mask Ogerpon ex/Crustle |
| LiamK | 5 | **8** (1134) | Ogerpon/Crustle → mostly **Fezandipiti ex/Dudunsparce** (71/93 sides) |
| nasuo445 | 7 | **9** (1127) | Cynthia's Garchomp ex/Roserade — **unchanged, byte-identical to our `metaC_garchomp_nasuo.csv` in 43/43 sides** |
| Eduardo Rocha de Andrade | — | **10** (1125) | *new* — Mega Kangaskhan ex/Crustle |

**Dropped out**: WinDecks (#4, Mega Starmie/Dusknoir), bono (#6, Fez/Dudunsparce),
Sota Uchiyama (#8, Grimmsnarl/Munkidori), wkonishi (#9, Dudunsparce/Alakazam),
capbloo (#10, Dudunsparce/Alakazam). **5 of 10 seats churned in 2 days.**

## Archetype census shift

| archetype | prev top-10 pilots | current top-10 pilots |
|---|---|---|
| Fezandipiti ex / Dudunsparce | 1 full + partials (bono; Yushin/LiamK partial) | **3 primary** (Majkel #1, Yushin #3, LiamK #8) |
| Dudunsparce / Alakazam | 3 (Majkel, wkonishi, capbloo) | **0 — extinct at the top** |
| Crustle shells (Kangaskhan/Ogerpon + Crustle) | 2–3 (MPGaming, LiamK, bono partial) | **5** (Budew #2, MPGaming #5, S4nkurero #7, LiamK partial, Eduardo #10) |
| Mewtwo stall (Team Rocket's) | 0 | 1 (kashiwashira #4) |
| Dragapult ex / Fezandipiti ex | 0 | 1 (BigBugginnings #6) |
| Mega Starmie / Dusknoir | 1 (WinDecks) | 0 |
| Grimmsnarl variants | 2 | partial (Yushin's second sub) |
| Cynthia's Garchomp (our BC deck) | 1 (nasuo) | 1 (nasuo, slipping) |

Two-day meta story: **the Alakazam draw-combo pillar collapsed and was replaced
by a Fezandipiti/Dudunsparce consensus at ranks 1/3/8, while Crustle attrition
shells doubled to half the top-10.** The top is now: 3 Fez/Dudunsparce engines +
5 Crustle-family attrition decks + 1 dedicated stall + 1 Dragapult + Garchomp
hanging on at #9.

## Sanjay-deck overlap check (requested addition)

**Zero** sides in either top-10 population play any Lucario deck (checked all
1136 + 883 sides for any card named \*Lucario\*). Mega Lucario ex/Hariyama was
25% of the μ700 pool in Phase 1 yet is entirely absent above μ1100. Sanjay's
stack is riding a **mid-ladder wave, not the top meta** — its μ751/803 freezes
say it beats the μ700 field, but nothing in the current top-10 suggests the
archetype scales; the decks that killed us at μ700 (Lucario) are themselves
missing from the top-10, presumably filtered out by the Crustle/stall/engine
decks up there.

## nasuo445 status check (teacher)

Still top-10 (#9, μ1127) but **declining**: rank 7 → 9, sample win rate
56% (81/145) → 47% (20/43), and the deck list is frozen while ranks 1–8
churned around it. Teacher-staleness implications → Phase 3.
