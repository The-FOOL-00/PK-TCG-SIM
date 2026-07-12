# Phase 2 — Behavioral diff: how top-10 play shifted (07-10 era → 07-12)

Sources: `pop_previous.json` (1136 sides / 908 episodes) vs `pop_current.json`
(883 sides / 610 episodes). Decision times from `remainingOverageTime` deltas.

## Decision speed: still a fast-policy world, one search agent

| team (current rank) | dtime median then | now |
|---|---|---|
| Majkel1337 (#1) | 77 ms | 136 ms |
| Budew (#2) | — | 43 ms |
| Yushin Ito (#3) | **1521 ms** | **1506 ms** |
| kashiwashira (#4) | — | 30 ms |
| MPGaming (#5) | 30 ms | 31 ms |
| BigBugginnings (#6) | — | 28 ms |
| S4nkurero (#7) | — | 59 ms |
| LiamK (#8) | 40 ms | 45 ms |
| nasuo445 (#9) | 31 ms | 30 ms |
| Eduardo (#10) | — | 36 ms |

Unchanged conclusion from LADDER_INTEL: 9 of 10 top teams decide in 28–136 ms
(policy class). Yushin Ito remains the lone search-class agent (~1.5 s median)
— and slipped from #1 to #3 while the fast Fez/Dudunsparce policies passed him.
Our v2.2.0 (p99 3 ms) is comfortably inside the speed class; speed is not our
gap.

## Tempo: first-attack distribution (% of sides)

| first attack turn | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10+ |
|---|---|---|---|---|---|---|---|---|---|
| previous | 10.8 | 25.7 | 22.0 | 16.1 | 10.3 | 5.4 | 2.9 | 1.5 | 5.4 |
| current | 11.4 | 19.7 | 19.1 | 14.8 | 9.8 | 7.6 | 3.7 | 3.8 | 10.2 |

Median stays T4, but the tail thickened: **T7-or-later share rose from 15.2%
to 25.3%**. That is the Crustle/stall expansion showing up in tempo — a quarter
of current top-10 games don't see an attack before turn 7. The meta got
*slower and grindier*, not faster.

## Game shape

- Win-turns median: 14 → 15.
- End reasons of top-10 **wins**: prizes 69%→64%, no-active 17%→15%,
  **deckout 14%→20%**. Attrition/deckout is now a fifth of all top-10 wins —
  it is a deliberate win condition up there, not an accident (relevant to our
  C2 loss cluster, where we're on the receiving end).
- Dudunsparce engine share of sides: 60% → 47%. The draw engine is still the
  single most common component but no longer a majority, displaced by
  Crustle shells that don't run it.

## Opening signatures (turns 1–6 of won sides)

Structurally similar across eras — the openers are universal:
Buddy-Buddy Poffin and Poké Pad dominate T1-3 plays in both populations
(prev: 490/410 plays; cur: 306/262), followed by draw supporters
(Hilda/Dawn/Lillie's) and the engine basics (Abra then; Dunsparce both eras).
Changes worth noting:
- Rare Candy lines persist (T3-4 Evolve means ~2.0–2.7 both eras) — turbo
  stage-2 evolution is a constant of top play.
- Current winners play slightly fewer cards per early turn (T3 Play mean
  3.16→2.89, T3 Evolve 2.31→1.94) — consistent with more attrition decks that
  bank resources instead of dumping hand.
- New in current T1-3 top plays: Team Rocket's Tarountula/Articuno
  (kashiwashira's stall package), Xerosic's Machinations (disruption).
  Gone: Marnie's Impidimp, Enhanced Hammer (the dropped Grimmsnarl/Alakazam
  packages).

## What this means for us (one line each)

- Speed class: we already match it; irrelevant axis.
- Tempo: our BC's first-attack T6 was near-median before; against a meta whose
  slow tail doubled, T6 is *less* punishing than at μ700 (where Lucario aggro
  attacked T2-3).
- The axis that moved: **attrition competence** — deckout as win condition,
  resource banking, and Crustle-proofing. Exactly the axis where Phase 1 found
  v2.2.0 helpless (C2: 1W-8L, self-deckout loops).
