# Phase 1 — v2.2.0 (BC-full Garchomp) ladder loss analysis

Date: 2026-07-12. Submission **54573192** (`submission_bc_metaC_garchomp_nasuo.tar.gz`,
v2.2.0-bc-full-garchomp), submitted 2026-07-11 13:31 UTC, **displaced 2026-07-12
05:41 UTC** by a teammate submission (see "Slot context" below). Final frozen
score **μ=682.5** (peak ~797 at game 13, settled via a losing tail).

Record over its active window: **25W / 32L / 0D** (57 episodes incl. 1
self-validation win). All 56 ladder replays pulled via the replay CDN
(`tools/harvest_episodes.py --fetch-ids`; daily datasets exclude same-day
submissions' episodes, so the CDN fallback added this session was required).
Deck verified = `metaC_garchomp_nasuo.csv` in all 56 games.

> **Small-sample warning: N = 32 losses (< 50).** Archetype-level records are
> 1–14 games each; treat per-matchup rates as directional, not estimates.

## Data-validity checks (step 1.3 gates)

- **BC fallback ("[bc] weights unavailable")**: replay JSONs carry no agent
  stderr, so we used a behavioral test instead: if the fallback had fired the
  agent IS v1, whose picks are deterministic — per-game agreement with v1
  would be ~1.00. Measured MAIN agreement: min 0.00 / median 0.23 / max 0.75;
  ST_CARD: median 0.59. **No game is v1-exact → BC weights loaded in every
  game. Phase 1 premise valid.**
- **Statuses**: all 56 games DONE for our seat; zero INVALID/ERROR/TIMEOUT.
  No P0.

## Headline: losses are NOT setup failures

| signature (median) | wins | losses |
|---|---|---|
| our first attack turn | 6.0 | 6.0 |
| opponent first attack turn | 3.0 | 3.0 |
| Garchomp ex online turn | 6.0 | 6.0 |
| game length (turns) | 17.5 | 15.5 |
| opponent μ | 722 | 744 |

Setup quality is **identical** in wins and losses; Garchomp comes online T5–9
in 29/32 losses. What differs is prize conversion after setup: **27/32 losses
end with ≤2 prizes taken** (0 prizes in 9 of them) while the opponent takes 6.
We lose the damage race from an established board — v2.2.0 sets up and then
trades down. Wins skew *longer* (17.5 vs 15.5 turns): we win grindy games,
lose mid-length races.

## Loss clusters (32 losses)

**C1 — Lost the race to fighting aggro, board established (≈14 losses, 44%).**
Prize losses T12–18 vs fast attackers (opp first attack T2–3): Mega Lucario
ex/Hariyama (9 losses — our worst matchup at **5W-9L**; 25% of all games),
Archaludon ex/Cinderace (3L), Mega Starmie variants (2L). Garchomp online T5–9,
we attack from T5–7, but convert 0–2 prizes while they take 6. Pattern in the
final turns: attack-spam with id531/id532 into targets that don't die, RETREAT
churn, Boss's Orders spent without a KO follow-up.

**C2 — Stall / deckout decks: near-total blindness (≈8 losses, 25%).**
Vs the Crustle family (Crustle/Dwebble, Crustle/Great Tusk, Crustle/Fezandipiti,
Ogerpon/Crustle): **1W-8L**, including all 4 deckout losses (T21/T35/T41/T43).
End-game logs show BC firing Cynthia's Gabite's ability every turn then END —
deck-thinning into its own deckout with no attack pressure and no card-economy
management. nasuo's harvest presumably contained few stall matchups; BC has no
plan for them. The 3 non-deckout Crustle losses are the same shape (T19–T26
slow prize losses, ≤2 prizes taken).

**C3 — Mirror losses (3 losses, 9%).** Cynthia's Garchomp variants: 0W-3L.
Opponent mirrors out-pilot or out-build us (one runs a Gabite-heavy variant).

**C4 — Setup accidents (3 losses, 9%).** The only games Garchomp never came
online: one T4 no-active donk vs Lucario, one T12 no-active vs Dragapult, one
T14 bench-management loss. Rare — the G6c "setup quality" win carried over to
the ladder.

Remaining: 4 close prize races (3–5 prizes taken) — competitive games lost on
margins.

## Where the ladder disagrees with G6a (60.7% vs v2.0.0)

No contradiction on strength: 25W/32L (44%) came against a median-μ~730 pool,
not the μ614 incumbent — a ~700-equilibrium rating is *consistent* with the
gate. The real gap is **archetype coverage**: the gate tested one opponent
(our search agent on the Abomasnow list, a slow deck). The μ700–750 ladder
pool is ~25% Mega Lucario aggro and ~15% Crustle stall — two population-level
styles the gate never sampled, and exactly where the losses concentrate
(C1+C2 = 69% of losses). G6a measured "beats our old agent", which the ladder
confirms; it could not measure "survives the μ750 metagame", which is what
capped the rating.

## Slot context (affects interpretation, discovered during this phase)

- Teammate (Sanjay) submitted `submission_v3.tar.gz` (Mega Lucario/Hariyama
  agent) 07-11 16:01 → displaced our v2.0.0 anchor; then `submission_v4.tar.gz`
  07-12 05:41 → **displaced v2.2.0**. Neither of our agents is on the ladder
  now. Sanjay's v3 froze at **μ=751.9** (34W/27L; its 60 replays preserved at
  `replays_raw_sanjay_sub54577670/` as Phase 3 input); one of his earlier 07-11
  submissions froze at **803.4**.
- v2.2.0's rating window was 16 hours, 56 games — enough to place it μ~700±30,
  not enough for a settled tail.

## Files

- `episodes_meta.json` — 57-episode metadata (opponent, μ before/after, reward)
- `replays_raw/` — 56 replay JSONs (gitignored)
- `losses_table.csv` — per-game extraction (all games, wins included)
- `analyze_losses.py` — parser/extractor (reusable for any submission)
- `replays_raw_sanjay_sub54577670/`, `sanjay_sub54577670_*.{json,csv}` —
  teammate-sub data kept separate for Phase 3
