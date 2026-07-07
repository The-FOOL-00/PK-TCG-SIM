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
