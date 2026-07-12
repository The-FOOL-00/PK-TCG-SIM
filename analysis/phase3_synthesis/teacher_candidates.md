# Phase 3 — BC teacher-pool candidates (current top-10, 2026-07-12)

Volume estimates: "sides/day" extrapolates the 07-11 single-day scan (kept
counts ÷ ~1.2 days). Daily datasets publish with a 1-day lag; harvest window
runs forward from each team's deck-switch date. Win-side counts matter most:
extraction keeps winning sides only.

## The headline candidate is a LIST, not a team

The Phase 2 label "Fezandipiti ex / Dudunsparce" at ranks 1/3/8 resolves, at
exact-list level, to variants of ONE Alakazam engine — and **ranks 1 and 3
pilot a byte-identical 60-card list** ("list-0"):

- **list-0** = `metaB_alakazam.csv` (Majkel's old rank-1 list, already in repo)
  with a 7-card update: **+ Fezandipiti ex, + Shaymin, +3 Xerosic's
  Machinations, +3 Nighttime Mine; − Dudunsparce/Dunsparce line, −2 Night
  Stretcher, − Rare Candy, − Enhanced Hammer, − Battle Cage, −1 Psychic Energy.**
- Pilots: Yushin Ito (113 games, **71 wins, 63%**) + Majkel1337 (57 games,
  32 wins, 56%) in the 2-day sample → **170 games / 103 win-sides in 2 days,
  ~85 win-sides/day combined.** A week of dailies ≈ 500+ win sides — more than
  the 81 win-games that trained BC-full-Garchomp.
- Caveat: two pilots = two policies on one deck. Majkel is a fast policy
  (136 ms — pattern-consistent, ideal imitation target). Yushin is the search
  agent (1.5 s — decisions come from hidden compute; noisier targets, but his
  63% is the best list-0 result). Whether to train on Majkel-only, or both, or
  both-with-pilot-flag is a Stage-4 data-prep decision.

## Candidate table

| teacher | rank (μ) | archetype / list | sample W% | est. win-sides/day | dtime | read |
|---|---|---|---|---|---|---|
| **Majkel1337** | 1 (1231) | list-0 + own variant (list-1: 115g/52w) | 49% overall; 56% on list-0 | ~27 on list-0 (+~43 on list-1) | 136 ms | proven #1 pilot, fast-policy class, window opens ~07-10 |
| **Yushin Ito** | 3 (1210) | list-0 (113/176 sides) | **63% on list-0** | ~59 | 1.5 s | best list-0 record but search-class: imitation targets noisy; 42% vs Crustle (34/45 losses deckout) — do NOT imitate his stall handling |
| Budew | 2 (1221) | Mega Kangaskhan/Crustle (1 list) | 56% | ~78 | 43 ms | best attrition pilot; deck class we've never piloted; would inherit 5-seat mirror battles |
| kashiwashira | 4 (1183) | TR Mewtwo/Spidops stall (1 list) | 59% | ~49 | 30 ms | stall specialist, stable list since 07-08 era; niche style |
| **BigBugginnings** | 6 (1149) | Dragapult ex/Fezandipiti ex (1 list) | **67% (46/69)** | ~38 | 28 ms | best sample W%; no-active specialist (7/11 anti-Crustle wins); single stable list; lower volume |
| LiamK | 8 (1134) | list-0-adjacent (Dunsparce variant, 71g/39w) | 55% | ~33 | 45 ms | third data source for the engine family but list differs — not poolable at exact-list level |
| S4nkurero | 7 (1145) | Ogerpon/Crustle | 50% (n=18) | ~9 | 59 ms | too thin |
| Eduardo | 10 (1125) | Kangaskhan/Crustle | (n=6) | ~3 | 36 ms | too thin |
| nasuo445 | 9 (1127) | Cynthia's Garchomp (incumbent teacher) | 47% (was 56%) | ~21 | 30 ms | declining; 3W-12L vs list-0 archetype — structurally countered |

## Recommendation shortlist

1. **list-0 (Majkel + Yushin)** — highest-μ deck, meta-consensus, two pilots
   of the exact same list, volume arrives fastest, and we already know the
   deck family (metaB): card-context tables and prior deck intel carry over.
2. **BigBugginnings** — reserve/secondary: best W%, single list, fast policy,
   embodies the no-active anti-Crustle line; half the volume.
3. Budew — only if we decide to join the attrition metagame; highest style
   risk.
