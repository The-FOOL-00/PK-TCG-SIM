# Experiment log

All comparisons alternate seats between the two sides. From 2026-07-07 onward,
every gate goes through `tools/ab_gate.py` (300 games minimum, 95% Wilson CI,
PASS only if the CI lower bound is > 50% vs the incumbent).

Statistical caution learned the hard way: a 50-game mirror win rate has a
±14 pt CI — deck_v2's 48% @ n=50 became 25% @ n=150. Never conclude from
< 150 games; never ship on < 300.

---

## 2026-07-07 — WS1: deck redesign (six variants) — DEAD END, nothing shipped

Baseline (old deck mirror, v1 policy both sides, 50 games): 86% of games end
by reason 3 (no-active board wipe); 0.78 mulligans/game; only ~3.4 energy
attached per game; Hammer-lanche (attack 1046) averages 354 damage — deck
energy *density* (35/60) is the win engine, since damage = 100 × basic Water
Energy in the top 6 of the deck.

All variants pass `validate_deck()`. Win rates are the variant's, vs the old
deck, same v1 agent both sides, seats alternated (`tools/deck_compare.py`,
JSON in `runs/`).

| variant | basics | energy | notable changes | n | win rate |
|---|---|---|---|---|---|
| deck_v2 | 12 | 20 | Mantine ×4, Ogerpon ×2, Ultra Ball ×4, Switch | 50 | 48% (24W-26L) |
| deck_v2 (rerun) | 12 | 20 | same list, larger sample | 150 | **25% (38W-112L)** |
| deck_v2b | 12 | 26 | v2 minus item cards | 50 | 38% (19W-31L) |
| deck_v2c | 10 | 31 | Mantine only | 50 | 36% (18W-32L) |
| deck_v2d | 8 | 33 | Mantine replaces Kyogre | 50 | 42% (21W-29L) |
| deck_v2f | 10 | 27 | Kyogre ×4 + Ultra Ball | 50 | 36% (18W-32L) |
| deck_v2g | 10 | 31 | Chewtle ×4 (sub-90-HP theory) | 50 | 40% (20W-30L) |

Deck_v2 did fix its nominal targets (reason-3 losses 42%→20% of games,
mulligans 0.82→0.26/game) but still loses: every added Basic is one-shot
prize fodder (Mega ex KO = 3 prizes, ex = 2, else 1), and cutting energy
starves the Hammer-lanche engine. The old deck and the v1 policy are
co-adapted (active-first energy routing + highest-HP setup active); variant
sides attacked ~3× less. deck_v2 still loses (30%) with v3 routing on BOTH
sides, so the deck itself is inferior, not merely mis-piloted.

**Verdict: old deck stays. No v2 deck bundle. submission.tar.gz rebuilt and
re-verified as exact v1 behavior (all 5 acceptance stages passed).**

## 2026-07-07 — WS2: v3 analytic evaluator behind PTCG_V3_EVAL

`evaluate_state()` + 1-ply analytic option deltas in `main.py`, flag
`PTCG_V3_EVAL` (env var or module attribute; default OFF — shipped bundle is
byte-identical v1 behavior). C1 validation, `resolve_selection`, and the
fallback chain untouched. Bundle stays DLL-free; deltas come from
`card_data.json` only.

- Initial version (pure best-attacker energy routing): **36% (18W-32L, n=50)**
  vs v1, 60% of losses by reason 3 — energy went to a benched Mega while only
  the active attacks and retreat costs 3-4. Fix: `V3_W_ACTIVE` tunable bonus
  on attach/evolve targeting the active slot.
- Hill-climb (`tools/tune_v3.py`, 100-game rounds over V3_W_ACTIVE,
  V3_W_ATTACKER_ENERGY, V3_W_PRIZE, V3_W_KO_THREAT; full history in
  `runs/tune_v3.json`): the single improving move was V3_W_PRIZE 120 → 60
  (52% → 59% round score); every other ×0.5/×2 step lost.
- Final config `{V3_W_ACTIVE: 30, V3_W_ATTACKER_ENERGY: 40, V3_W_PRIZE: 60,
  V3_W_KO_THREAT: 60}` confirm run: **53.0% vs v1 policy over 200 games.**
- Timing with v3 ON: avg 0.024 ms, p99 0.08 ms, max 0.196 ms per decision;
  0 crashes, 0 fallbacks.

## 2026-07-07 — Phase 0 gate: v3 (flag on) vs v1 via ab_gate.py, 300 games

`python tools/ab_gate.py --challenger deck.csv+v3 --incumbent deck.csv
--games 300 --workers 6` (runs/gate_v3_vs_v1_300g.json):

- W/L/D 162/138/0 → win rate **54.0%**, 95% Wilson CI **[48.3%, 59.6%]**
- Crashes: 0/0. Win reasons {3: 150, 1: 12}, loss reasons {3: 134, 1: 4}.
- **VERDICT: FAIL** (CI lower bound 48.3% ≤ 50%). v3 stays OFF; the Phase 1
  learned value model is its designated replacement. Incumbent/current best
  remains the v1 heuristic policy.
- Side finding: strong first-seat advantage — challenger won 108/150 (72%)
  in seat 0 vs 54/150 (36%) in seat 1. Seat alternation in the protocol is
  load-bearing; any comparison that doesn't alternate seats is invalid.

## 2026-07-07 — Phase 1a: self-play value-model data generated

`tools/gen_selfplay.py --games 50000 --workers 8 --out data/selfplay_v1`:
**50,000 games in 39.3 min (1,272 games/min), 1,521,362 decision rows**
across 8 shards (27 MB compressed). Per row: 170-dim `main.encode_state`
vector (encoder added to main.py — shipped policy never calls it; train and
inference share one definition), outcome ±1/0 for the acting player, turn,
game_id. Schema + feature index map: `data/README_DATA.md` +
`data/selfplay_v1/meta.json`. Policy: v1 heuristic both sides, deck.csv,
V3_EVAL off. Acting-player win rate in data 0.544 (both seats logged;
remainder draws).

## 2026-07-07 — Phase 1b: train_value.py validated locally (2k-game subsample)

`training/train_value.py --data data/selfplay_v1 --out runs/train_value_local2k
--max-rows 60000` (1,971 games / 60,355 rows, split BY GAME, 5,423 val):

- logreg (171 params): val logloss 0.6757 after 6 epochs, still improving.
- MLP 170→128→64→1 (30,209 params): **val logloss 0.6099, val AUC 0.7247**
  (coin-flip = 0.693). Calibration monotonic in all 10 buckets
  (e.g. bucket [0.9,1.0): predicted 0.939, actual 0.921).
- Weight file round-trips through the documented inference contract
  (n_layers/W*/b* → relu/sigmoid matmuls) with plain numpy, no repo imports.
- Runtime: seconds on CPU at this size; full 1.5M rows estimated 10–25 min.

Conclusion: signal exists even at 4% of the data; the package is safe to run
remotely. → TRAINING HANDOFF #1 (Kaggle notebook, see
training/README_TRAINING.md). Gate after weights return: PTCG_LEARNED_VALUE
vs v1 through ab_gate.py, 300+ games.

## 2026-07-07 — Phase 3: ladder_watch + meta_miner live; meta_miner card-DB fix

- `tools/ladder_watch.py`: submission 54418735 COMPLETE, μ 504.5 vs
  leaderboard top 1133.5 / top-20 1054.3 / median 673.2 (4,459 teams).
  No INVALID/timeout losses (would be P0).
- `tools/meta_miner.py` bug: it labeled every ladder deck "unknown" because
  it looked cards up in `main.CARDS`, which only contains OUR deck's 9 ids.
  Fix: load the full 1,267-card DB from `EN_Card_Data.csv`. Regenerated
  META.md (40 episodes of 2026-07-06): top-20 field = Cynthia's Garchomp ex
  (12 sides), Dudunsparce/Alakazam (8), Mega Kangaskhan ex/Raging Bolt (8),
  Marnie's Grimmsnarl ex (10 across variants); avg first attack turn 4.7,
  avg game 13.1 turns, 0 bad statuses in sample.

## 2026-07-07 — Phase 1c: learned value model integrated; gate FAIL, stays off

Kaggle full-data training (user-run, 1.52M rows): MLP val AUC **0.8445**,
val logloss 0.4810 (train 0.4800 — no overfit); logreg 0.763/0.577.
`value_weights.npz` + `metrics.json` in repo root.

Integration (`PTCG_LEARNED_VALUE`, default off): MAIN-phase + attach/promote
selections scored tier + 400 × clip(P(win|after) − P(win|now), ±0.25); the
"after" vector built analytically in feature space via `_encode_pokemon_slot`
(same encoder as training — no drift). Numpy inference; pure-python .npz
reader + matmul fallback (parity 8.6e-8) if numpy missing; missing/corrupt
weights → one stderr warning → heuristic tiers (verified: scores byte-equal
v1). C1/resolve_selection/fallback chain untouched. Timing model-ON:
**avg 0.195 ms, max 2.69 ms**/decision (numpy); pure-python ~12 ms per
15-option decision — both trivial vs the 600 s budget. 0 crashes/fallbacks.

Gate (`ab_gate.py`, 300 games, seats alternated,
runs/gate_lv_vs_v1_300g.json): W/L/D 146/154/0 → **48.7%, 95% CI
[43.1%, 54.3%] → VERDICT: FAIL.** Flag stays OFF; v1 remains incumbent;
nothing ships.

In-game calibration from the gate (challenger P(win) per decision vs actual
outcome, 3,123 decisions): monotone and tight at the extremes —
[0.0,0.1)→0.045, [0.9,1.0)→0.973; mid-buckets over-optimistic by ~5–10 pts
(e.g. [0.5,0.6) predicted 0.551, actual 0.451).

**Reading: the value function is accurate but greedy 1-ply use of it does not
beat v1's co-adapted heuristics** — same lesson as v3 (54.0% FAIL). The
mirror match appears to leave little 1-ply headroom; depth is the missing
ingredient, which is exactly rung (b) — Phase 2 search distillation, where
this dataset and encoder are reused as the imitation buffer.

Tooling kept for a future PASS: `build_submission.py --learned-value`
(ships weights, bakes flag on, stamps ptcg-lv-v1.1.0; LV-CHECK verifies the
model loads from the bundle — validated end-to-end, then the v1 bundle was
rebuilt and re-verified as the shipped artifact). ab_gate.py now collects
the calibration table whenever the challenger runs with `+LV_TRACE=true`.
