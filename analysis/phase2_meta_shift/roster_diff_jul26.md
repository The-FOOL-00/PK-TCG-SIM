# Top-10 intelligence — 2026-07-26

Harvest: **277 replays / 391 top-10 sides** across the current top 10, pulled
today via authenticated episode listing + replay CDN. Profile method and units
identical to the 07-21/07-22 reports (per-TURN, §6m unit rule), so the three
snapshots are directly comparable.

Sources: `leaderboard_2026-07-26.csv`, `replays_top10_jul26/`,
`profile_top10_jul26.json`.

---

## Roster — and the churn is now extreme

| # | team | μ | archetype | dtime | FA | FE | hand T3/T5/T7 | xDr/t | atk/t | W% (harvest) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Luca** | 1185 | Grimmsnarl / Munkidori | 178 ms | 4.5 | 3.6 | 6.0/5.4/6.0 | 2.1 | 0.58 | **84%** |
| 2 | **zoroark190** | 1183 | **Mega Kangaskhan / Raging Bolt ex** | 38 ms | 4.1 | — | 7.8/8.2/6.6 | 2.1 | **0.64** | 67% |
| 3 | Yushin Ito | 1162 | Fezandipiti / Dudunsparce | 223 ms | 4.3 | 3.6 | 6.2/8.2/**10.3** | **5.0** | 0.59 | 50% |
| 4 | **Dries @ Tufa Labs** | 1159 | Grimmsnarl / Munkidori | 125 ms | 4.7 | 3.8 | 5.8/5.5/5.2 | 2.4 | 0.58 | 59% |
| 5 | **213tubo** | 1153 | Grimmsnarl / Munkidori | **633 ms** | 4.8 | 3.6 | 5.7/5.3/5.5 | 2.4 | 0.55 | 60% |
| 6 | Majkel1337 | 1153 | TR Mewtwo / Spidops | 168 ms | 4.4 | 4.2 | 6.0/6.7/6.5 | 3.3 | 0.59 | 54% |
| 7 | **JZ** | 1142 | Grimmsnarl / Munkidori | 43 ms | 5.1 | 4.1 | 5.4/4.6/4.7 | 2.4 | 0.54 | 59% |
| 8 | __Taichicchi__ | 1131 | Grimmsnarl / Munkidori | 67 ms | 4.9 | 4.1 | 6.0/5.3/5.8 | 2.6 | 0.57 | 49% |
| 9 | **Dominic Peel** | 1120 | Grimmsnarl / Munkidori | 40 ms | 4.2 | 3.7 | 5.6/5.5/5.2 | 2.4 | **0.64** | 59% |
| 10 | **matheus** | 1120 | Grimmsnarl / Munkidori | 107 ms | 5.6 | 3.9 | 5.7/5.2/5.3 | 2.2 | 0.47 | 44% |

**Bold = new to the top 10 since 07-22.** Six of ten seats are new in four
days. Only Luca, Yushin, Majkel and __Taichicchi__ persist; Luca is the only
team to hold a top-2 seat across both snapshots.

Our own row for contrast (canary, 28 eps): **atk/t ≈ 0.32, first attack T5.5,
9W–19L.** Still outside the top-10 envelope on attack share.

### Three-snapshot churn

| snapshot | #1 | new seats vs prior |
|---|---|---|
| 07-21 morning | Oshbocker (Grimmsnarl) | — |
| 07-22 evening | Luca (Grimmsnarl) | 9 of 10 |
| **07-26** | **Luca (Grimmsnarl)** | **6 of 10** |

The identity of the #1 team is volatile; the *archetype* of the #1 team is not.

---

## Archetype census — Grimmsnarl consolidation, and one genuine new entrant

| archetype | 07-22 seats | **07-26 seats** |
|---|---|---|
| **Marnie's Grimmsnarl ex / Munkidori** | 3 | **7** |
| Fezandipiti ex / Dudunsparce | 2 | 1 |
| TR Mewtwo ex / Spidops | 2 | 1 |
| **Mega Kangaskhan ex / Raging Bolt ex** | 0 | **1 (new, at #2)** |
| Cynthia's Garchomp | 2 | **0 — gone from the top 10** |
| Dragapult / Fez, Kangaskhan / Crustle | 1 each | 0 |

**Grimmsnarl now holds 7 of 10 seats, up from 3.** The field has consolidated
hard onto one archetype rather than diversifying.

## Cross-archetype win matrix (n ≥ 60 quotable)

| archetype | vs pooled field | n | quotable? |
|---|---|---|---|
| **Marnie's Grimmsnarl / Munkidori** | **58.1%** | **258** | ✅ yes |
| Mega Kangaskhan / Raging Bolt ex | 67.3% | 49 | ✗ n<60 |
| TR Mewtwo / Spidops | 56.4% | 39 | ✗ n<60 |
| Fezandipiti / Dudunsparce | 48.9% | 45 | ✗ n<60 |

Directional cells (n ≥ 20, **not** quotable):

| matchup | record | n |
|---|---|---|
| Grimmsnarl **mirror** | 63W–51L | 114 |
| Grimmsnarl vs Fez/Dudunsparce | **31W–13L (70%)** | 44 |
| Grimmsnarl vs TR Mewtwo | 19W–15L | 34 |
| **Kangaskhan/Raging Bolt vs Grimmsnarl** | **23W–10L (70%)** | 33 |
| **Grimmsnarl vs Kangaskhan/Raging Bolt** | **8W–19L (30%)** | 27 |

### The one thing worth watching: a possible Grimmsnarl counter

The two Kangaskhan/Raging Bolt cells agree from both directions —
**70% for Kangaskhan, 30% for Grimmsnarl** across 60 combined games. That is
the first archetype in three snapshots to show a consistent edge over the
field leader, and it took the #2 seat in four days from nowhere.

**It is not yet quotable** (n=49 pooled, below our n≥60 rule; the directional
cells are 33 and 27). Treat as a hypothesis to re-measure next harvest, **not**
as an established counter. Note also the standing finding: even a real
counter-matchup does not survive our measured 20–25 pt piloting penalty on an
unfamiliar deck (FINAL_PATH_JUL21.md Part 2), so this does **not** reopen the
deck question for us.

---

## Durable vs volatile — updated across three snapshots

**DURABLE (held 07-21, 07-22 and 07-26):**

1. **Grimmsnarl/Munkidori is the field-defining archetype.** 58.1% vs field
   (n=258) today; 65.7% (n=102) on 07-22; ~66% on Sanjay's n=1200. Three
   independent measurements, three different weeks.
2. **Both speed classes coexist at the top.** Today: 38–67 ms fast policies
   (zoroark190 #2, JZ, Dominic Peel) alongside 178–633 ms deliberate agents
   (Luca #1, Yushin, 213tubo). 213tubo at **633 ms** is the slowest top-10
   agent we have recorded. Neither class excludes the other.
3. **The per-turn behavioural envelope is stable**: attack-share 0.47–0.64 of
   own turns, first evolution T3.6–4.2, first attack T4.1–5.6. Unchanged
   across all three snapshots.
4. **Engine-heavy decks are identifiable by hand growth.** Yushin remains the
   clearest case: hand 6.2 → 8.2 → **10.3** by T7 with **5.0 extra draws/turn**,
   roughly double the field's 2.1–2.6.
5. **Team identity at the top is volatile; archetype is not.** 6 of 10 seats
   turned over in four days while the archetype mix consolidated.

**VOLATILE (do not optimise against):** which team holds any given rank; exact
μ values below the top 3; the presence of any single new entrant.

---

## Implications for us

- **Our archetype is gone from the top 10.** Cynthia's Garchomp held 2 seats on
  07-22 (#2 Yudai Ueno, #6 junlee789) and holds **0** today. The
  "junlee789 proves Garchomp has a top-5 ceiling" argument from
  FINAL_PATH_JUL21.md is now materially weaker — that pilot has dropped out.
- **Our behavioural gap persists and is unchanged in shape.** Attack share
  ~0.32 vs the field's 0.47–0.64; the top-10 envelope has not moved, so the
  target has not moved.
- **The field is getting harder, not easier.** Seven of ten seats now play the
  strongest measured archetype, and the #1 team wins 84% of its harvested
  games. Rating gains from here require beating a more concentrated field.
- **No action implied for deck choice.** Part 2 of FINAL_PATH_JUL21.md closed
  the counter-deck question on piloting-penalty grounds; nothing in this
  snapshot reopens it, including the Kangaskhan signal.
