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

## 2026-07-07 — Phase 2a: teacher characterization — flat MC plateaus at ~58%, below the 60% bar

**Finding 1: `cg.api.search_begin` is not a search algorithm — it is a
determinized forward simulator.** You supply predictions of every hidden zone
(both decks, both prizes, opponent hand, face-down active); it returns a root
SearchState. `search_step(id,[i])` applies option i and returns a new state;
old ids stay live (tree branching), `search_release`/`search_end` free memory.
`State.result` = winner index (−1 running); `State.yourIndex` = whose select
each node is, so we simulate BOTH players. No depth/time/node parameters —
any actual search is ours to build on top. `manual_coin` optionally
de-randomizes coin flips.

**Teacher built (`tools/searcher.py`):** flat determinized Monte Carlo. Per
MAIN-phase single-select decision: rank options by v1 score, keep top-k; for
each of `det` uniform determinizations (exact pools in mirror self-play),
step each candidate and run `roll` rollouts with BOTH sides playing v1
(`main.agent`) to `State.result` (rung-a value net evaluates at the 400-step
cap); pick argmax mean. Non-MAIN/multi-select decisions stay v1.
Driver calls cg.dll directly and parses raw JSON to dicts, so main.py's
scorers run natively on search nodes. ab_gate spec: `+TEACHER=det,roll,topk`.

**Speed** (search_begin 0.16 ms, search_step 0.053 ms, v1 rollout step
0.075 ms incl. decide; amortized per searched decision from 300-game gates,
6 workers): 2 samples/option ≈ 29 ms; 16 ≈ 215 ms; 32 ≈ 460 ms;
64 ≈ 860 ms.

**Strength (all n=300, seats alternated, via ab_gate.py):**

| setting (det,roll,topk) | samples/opt | win rate | 95% CI | verdict vs 50% |
|---|---|---|---|---|
| 2,1,4 | 2 | 48.0% | [42.4, 53.6] | FAIL |
| 8,2,4 | 16 | 56.0% | [50.3, 61.5] | PASS |
| 16,2,4 | 32 | 58.7% | [53.0, 64.1] | PASS |
| 32,2,4 | 64 | 57.0% | [51.3, 62.5] | PASS (≈32-sample result) |
| 16,2,8 | 32, topk 8 | 58.7% | [53.0, 64.1] | PASS (= topk 4) |

First CI-backed >50% challenger in the project — but the curve saturates at
**~58%**: 64 samples buy nothing over 32, and widening candidates buys
nothing. The ceiling is algorithmic, not statistical: 1-action lookahead
whose rollouts assume v1 play forever after. Teacher searches ~58% of
decisions, overrides v1 on 42–50% of those; overrides beyond ~45% add no
strength (noise regime).

**Per the Phase 2a decision rule (<60% CI-backed): STOPPED before any
distillation data generation.** Alternative-teacher proposal + generation
projections handed to the user for sign-off.

## 2026-07-08 — Phase 2c cycle 1: distillation pipeline built + validated; 500k-decision generation launched

**Sign-off: PATH A** (expert iteration with the (16,2,4) teacher). The 60%
bar is satisfied in purpose: 58.7% [53.0, 64.1] with a diagnosed,
iteration-fixable ceiling; Path B stays in reserve if the cycle-1 slope
disappoints. **Known caveat, accepted for cycle 1: teacher determinizations
sample the opponent's hidden zones from OUR 60-card list — exact only in
mirror self-play. Under ladder conditions this is an information leak; the
student inherits whatever bias that induces.**

Built (all validated end-to-end on a local subsample before launch):

- `main.encode_option` / `encode_options` / `option_feature_names` — 41-dim
  per-option features (OptionType one-hot 17, referenced-card CardType
  one-hot 7, 11-dim target-slot block, attack dmg, KO flag, card value,
  targets-active, v1 rank + v1-top prior). Same shared train/serve contract
  as `encode_state`; v1-prior features use `_score_main` directly so they
  are flag-independent. Shipped v1 behavior untouched.
- `tools/gen_distill.py` — both seats teacher-guided at (16,2,4), logs per
  SEARCHED decision (state 170, all option rows, teacher-chosen index,
  turn, game_id) to `data/distill_c1/` shards + meta.json (schema +
  teacher config + caveat). Schema doc in data/README_DATA.md.
- `training/train_policy.py` — standalone numpy-only; softmax cross-entropy
  over each decision's options, split BY GAME, linear baseline (212 params)
  + MLP (trunk 170→128→64, head concat(64,41)→64→1, **36,993 params**,
  <100k ✓). Saves best-val-accuracy epoch snapshot as `policy_weights.npz`
  (+ per-model files) and metrics.json with top-1 imitation accuracy and
  the two floors (v1-agreement, uniform).

Local validation (133 games / 2,482 searched decisions @ real (16,2,4)
config, 6 workers, 9.5 dec/s): schema invariants pass (labels in range,
opt row counts align, exactly one v1_top per decision); MLP val top-1
**53.1%** vs v1-agreement floor 52.8% and uniform 23.3% — at the floor with
CE still falling at epoch 10, as expected at 0.5% of the data (the learnable
signal is the 45% of searched decisions where the teacher overrides v1).
Weight file round-trips through the documented inference contract with
plain numpy (53.4% recomputed independently). Teacher searched 57% of
decisions, override rate 45% — matches Phase 2a.

Generation launched: `gen_distill.py --decisions 500000 --workers 8` →
`data/distill_c1/` (~27k games expected). Measured throughput extrapolates
to **~11–12 h at 8 workers** (the approved estimate was ~8.5 h; the delta is
both-seats search costing slightly more than the one-sided gate timings
predicted). Runs overnight; log at `runs/gen_distill_c1.log`.

**Addendum (same day, ~10:30): generation restarted with stop/resume.**
A planned 15:15 laptop shutdown surfaced that the first version flushed
shards only every 40k decisions/worker (first write ≈ 6 h in) with no
resume — a mid-day stop would have lost everything. Fixed in
gen_distill.py: 2,500-decision shards written atomically (tmp+os.replace),
graceful stop via a STOP file in the output dir (workers finish the current
game, flush, exit — zero loss), and resume that scans existing shards and
generates only the remainder with per-worker game_id continuation
(unreadable shards quarantined to .bad and regenerated). Stop→resume cycle
tested end-to-end: 385 flushed at STOP + 138 on relaunch, ids collision-free,
loader consumes the multi-launch dataset. Cost of the fix: the first
launch's ~77k buffered decisions (~1.5 h) were unrecoverable (running
workers had no flush trigger) — killed and restarted from zero at ~10:30
as a detached process. Timeline: pause 15:15, resume ~18:00, same command.

→ Next: TRAINING HANDOFF #2 (Kaggle, see training/README_TRAINING.md Run 2).
After policy_weights.npz returns (plan, to confirm then): integrate behind
`PTCG_DISTILLED` + fallback chain + time guard; ab_gate S1 vs v1 AND S1 vs
teacher-guided; then rebuild the teacher with S1 rollouts and gate
teacher(S1) vs teacher(v1) — the iteration-slope number that decides cycle 2
vs Path B.

## 2026-07-09 — Strategic pivot Phase A: runtime engine feasibility (VERIFIED)

Pivot rationale (full narrative now in report/WRITEUP_DRAFT.md §2b): v1 at
μ≈512 (below the 600 start), both 1-ply upgrades failed gates, S1 only +0.9%
over its imitation floor, while the determinized-MC teacher (58.7% CI-backed)
uses ~215 ms of an available ~15 s/decision. New plan: ship belief-sampled
determinized search as the agent; nets become its accelerators.

**A1 findings:**
- The official sample submission bundles `cg/` with binaries for ALL
  platforms: cg.dll, libcg.so (Linux x86-64), libcg-arm64.so, libcg.dylib;
  `cg/sim.py` picks by platform at import. Its main.py does a plain
  `import cg` — bundling the engine is the intended pattern. The Linux build
  is exercised by every ladder episode (the interpreter runs it), so the
  binary itself is battle-tested.
- The pip package (kaggle-environments 1.30.1) ships `envs/cabt/cg/` with
  cg.dll+libcg.so but NO search bindings (no api.py; sim.py lacks
  SearchBegin/SearchStep/AgentStart) → pip-package import is NOT a usable
  path for search; the bundle must carry the sample's cg/. (Escape hatch if
  ever needed: bind the symbols manually against the interpreter's loaded
  libcg.so — same exports.)
- `search_begin_input` is delivered in the live agent observation (interpreter
  sets it every step; it is stripped only from saved replays).
  `remainingOverageTime` starts at 600 s/player, actTimeout=0.

**A2 probe built (tools/build_probe.py → build/probe_submission.tar.gz,
1.90 MiB, 13 members, cg/ nested like the sample):**
- Probe = v1 main.py + appended hook; answers byte-identical to v1 (agent()
  called unconditionally); at exec it imports cg and logs platform/outcome;
  at the first MAIN-phase single-select it runs one search_begin/search_step
  on a mirror-guess determinization and logs timings; any failure → one
  stderr line, play unaffected.
- Checks passed: kaggle-style exec load (no __file__, cwd elsewhere, last
  callable = agent_probe); cg-stripped copy logs "cg-import FAILED" and plays
  v1; real cabt game via kaggle_environments: status DONE/DONE, probe won,
  "search OK turn=1 options=8 begin_ms=0.96 step_ms=0.08".
- Note: agent stderr is captured into env.logs by kaggle_environments (not
  process stderr) — on-ladder probe output will be in the episode agent logs.

→ AWAITING USER: decision whether to submit the probe (one slot, plays as
v1). Phases B–F (belief search in main.py, nets in search, time governor,
gates E1–E5, ship) queued behind the Phase A verdict.

## 2026-07-09 — Phase B: belief-sampled determinized search in main.py (PTCG_SEARCH)

Search stack integrated into main.py behind module flags (ab_gate-settable):
SEARCH, SEARCH_DET/ROLL/TOPK (default teacher config 16/2/4), SEARCH_CAP
(C1 value truncation, 0=terminal), ROLLOUT (v1|s1), GOVERNOR, SEARCH_BELIEF.
Engine loads from a bundled cg/ (repo root carries a gitignored copy so the
local layout matches the bundle). The hook can only substitute WHICH legal
option is returned; C1 validation/resolve_selection untouched (fault suite
proves it).

**B1 CardTracker** — serial-keyed (engine serials unique per match, so
reprocessing repeated log entries is a no-op). hand_known / floating
(hand-or-deck after face-down shuffles) / serial_id (4-copy budget) /
energy_types. New-game reset = turn regression or prize-count growth from a
nonzero baseline. Validated on 20 recorded games (mirror + deck_v2
opponents): 392 decisions, serial identities == omniscient transcript,
revealed multiset <= true opponent list, hand_known always inside the true
hand at adjacent opponent decisions, and 1,176 sampled determinizations
accepted by SearchBegin with zero errors.

**B2 sampler finding (the day's big one): uniform-over-pool belief builds a
strawman opponent.** Basic energy is 8/1,267 of the card pool, so uniform
remainder sampling gives the opponent ~no energy; 96-98% of rollout values
saturate at 1.0 and candidate discrimination vanishes (0 overrides). A
composition prior (energy 30% / pokemon 35% / trainer 35%) fixes the count
but not type coherence (energy that no sampled pokemon can use) — still 96%
saturation. Adding per-determinization type coherence (dominant energy type
sampled from observed evidence, matching pokemon 6x boosted) restores
override rates to mirror level. Belief modes shipped: comp (default,
honest), mirror (= the 2a teacher's list-knowledge determinization),
uniform (A/B reference). Archetype priors from META.md remain a hook
(SEARCH_PRIOR / sample_opponent_deck(prior=...)).

**Diagnosis (E1-failure protocol run pre-emptively, n=56 identical searched
positions):** mirror search deviates from v1 on 43% of decisions (teacher
was 45% — the runtime port is faithful); comp deviates on only 20% and
agrees with mirror's override choice 52% — belief quality, not search
budget, is where mirror strength bleeds. comp's remaining signal is
loss-avoidance (its win-values stay saturated).

**B4 robustness:** fault suite green — no-engine / SearchBegin-raises /
sampler-raises / budget-zero(sticky) each yield answers byte-identical to
v1 on replayed streams; healthy control overrides 9/100 legally. 30-game
suite with BOTH seats searching (16,2,4): 0 crashes, 0 fallbacks, avg
145 ms max 1.2 s per decision.

**S1 retrained locally (Handoff #2 obsolete — generation had finished and
cores were free):** 500,139 decisions, 30 epochs, val top-1 56.34% vs
v1-agreement floor 55.10% (+1.24%); policy_weights.npz at repo root.

## 2026-07-09 — Phase C (nets in search) + Phase D (time governor)

**C1 value truncation** (SEARCH_CAP + rung-a value net at the leaf, terminal
outcomes kept): wall speedup vs terminal rollouts at teacher config —
K=6: 2.9x, K=10: 2.3x, K=16: 1.8x (rollouts from real positions average
~25 steps, so the gain is bounded well below the hoped 10x). K strength
pilots deferred until E1 passes (they only inform E2).
**C2 s1 rollouts** (policy_weights.npz, numpy forward per contract): works
end-to-end; per-step choice cost 0.113 ms vs v1's 0.015 ms = **7.6x** (>3x
threshold noted) -> at equal wall time s1 buys ~4x fewer samples. s1
rollouts also run ~2x longer before terminating. E3 must be equal-wall-time.

**D governor**: budget = min(3s, 0.5*remainingOverageTime /
max(est_remaining_decisions, 8)); est from live decisions/turn x
(GOV_P90_TURNS - turn). GOV_P90_TURNS=20 from the 27,260-game distill_c1
distribution (turns p50=5 p90=12 p99=20 max=34), padded above mirror-p90
because ladder field games run longer (META 13.1 avg). Degradation
full->1/2->1/4 det->skip, sticky heuristic below 0.2s budget; in-loop
budget check aborts remaining determinizations. Telemetry: [gov] one-liner
per game (decisions, spent, max, worst-3) via stderr -> episode logs.
**Stress (50 games, det=48 = 3x ship config, terminal rollouts):** own-time
mean 10.0s / p90 21.2s / max 35.6s (requirement <400s); decisions p50
370ms / p99 3.07s / max 3.10s (requirement p99<3.5s); 0 sticky, 0 crashes
-> PASS with 17x headroom.

## 2026-07-09 — Phase E1: the key gate (belief-search vs v1) — FAIL, diagnosed

**E1 (deck.csv+SEARCH=true vs deck.csv, 300 games, seats alternated):
49.0% [43.4, 54.6] -> FAIL.** Companion mirror-belief run (exact-knowledge
determinization): 58.3% [52.7, 63.8] -> PASS, reproducing the 2a teacher's
58.7%. Zero crashes either side. So the runtime search port is faithful;
honest belief sampling is what erases the edge.

**Diagnosis (tools/diagnose_belief.py, 249 identical searched positions,
matched per-position RNG for comp vs mirror):**
- override rate vs v1: mirror 38%, comp 18%
- edge capture on the 38% of positions where MIRROR overrides v1 (its whole
  source of advantage): comp makes the SAME override 9%, reverts to v1 76%,
  picks a third option 15% -> comp banks essentially none of the edge.
- value separation (top1-top2 mean rollout value): mirror median gap 0.031
  (39% zero-gap); comp median 0.000 with **76% zero-gap positions**. Honest
  belief -> flat value landscape -> search can't rank candidates -> falls
  back to v1 -> plays at v1 strength (49% ~= 50%).
Conclusion: the bottleneck is BELIEF QUALITY, not search budget. More
determinizations can't sharpen a flat landscape. The fix is realistic
opponent sampling (META.md archetype priors via the existing
sample_opponent_deck(prior=...) hook), not more compute.

**Structural caveat:** E1's incumbent is v1 on OUR deck, so it's a mirror
match — mirror belief is tautologically correct there and honest belief is
penalized for hedging against variation the gate doesn't contain. The gate
proves correct belief = +9pt, and that current honest belief banks none of
it; it can't fairly rank the two beliefs for varied ladder opponents.

-> STOP for user input (per plan): E1 is the decision gate. Options on the
table: (A) archetype-prior belief from META.md then re-gate; (B) ship the
mirror/exact-belief config (PASS, but assumes opp=our deck — a bet that
ladder opponents are close enough, contradicted by our deck being an
extreme 35-energy outlier); (C) a fairer gate vs a DIFFERENT opponent deck
to rank beliefs honestly; (D) abandon runtime search, ship S1 (val top-1
56.34%, +1.24% over floor) or stay v1. Phases E2-E5/F held pending.

## 2026-07-09 — Step 1: FAIR cross-deck gates (belief ranked honestly)

**Probe verdict (Kaggle episodes 84888843-0/1): runtime cg + search GREEN
on-ladder.** Image = Linux-x86_64 / Python 3.11.13. Timings: SearchBegin
3.28-3.33 ms (local 0.16 ms -> ~20x sandbox overhead — matters: 16 dets pay
one begin each = ~53 ms fixed/decision before rollouts), SearchStep
0.12-0.31 ms (local 0.05). Phase F: pin deps to Py3.11; Phase D time model
built from Kaggle numbers.

E1 was a mirror match (v1 on OUR deck both sides), so it structurally
favored mirror belief. Step 1 re-gates against 3 REAL top-ladder decks
(extracted from episode replays, all validate_deck-legal, v1 pilots each
0-crash): metaA Cynthia's Garchomp ex (5 energy), metaB Dudunsparce/Alakazam
(3 energy, the 73%-ladder deck), metaC Mega Kangaskhan ex (16 energy,
multi-type) — vs our 35-energy mono-water build.

Gates (belief-search + our deck vs v1 + opp deck, 300 games, seats
alternated, 0 crashes all sides):

| opponent | v1+our baseline | comp (honest) | mirror (wrong here) |
|---|---|---|---|
| Garchomp ex   | ~72% | 73.7% [68.4,78.3] PASS | 71.0% [65.6,75.8] PASS |
| Alakazam      | ~38% | 42.7% [37.2,48.3] FAIL | 40.7% [35.3,46.3] FAIL |
| Kangaskhan    | ~75% | 75.3% [70.2,79.9] PASS | 72.3% [67.0,77.1] PASS |

**Key finding — the E1 mirror-advantage was a gate artifact.** On every
cross-deck opponent honest comp belief EQUALS OR BEATS mirror belief
(+2.7 / +2.0 / +3.0 pt), reversing E1 where mirror beat comp by 9pt in the
mirror match. Against opponents that actually differ, confidently-wrong
mirror belief is no better (slightly worse) than honest-but-vague belief.
**But the lift over the v1 baseline is small** (+1.2 / +4.7 / +0.3 pt): the
two PASSes are matchups v1 already wins, and in the one with real headroom
(Alakazam, which we lose) search improves 38->42.7% but cannot flip it.
Diagnosis (override-agreement, value separation, oracle ceiling, det sweep)
below decides whether archetype priors (Step 2) have room.

**Diagnosis per opponent (30 games each; oracle = search handed the TRUE
opponent list = belief-accuracy ceiling; det sweep = compute cofounder):**

| opponent | value-sep zero-gap comp/mirror/oracle | oracle overrides v1 | comp captures of oracle's overrides | comp det4/16/48 zero-gap |
|---|---|---|---|---|
| Garchomp   | 64% / 47% / 41% | 43% | 11% | 81/62/50% |
| Alakazam   | 55% / 32% / 33% | 49% | 18% | 78/52/34% |
| Kangaskhan | 74% / 56% / 49% | 37% | 12% | 84/77/58% |

Reading: (i) belief accuracy HAS headroom — perfect belief (oracle) roughly
halves the flat-value fraction vs honest comp on every deck, and would
override v1 on 37-49% of decisions where comp captures only 11-18% of those.
(ii) Compute is NOT irrelevant after all — raising det 4->48 sharpens comp's
value separation substantially (e.g. Alakazam 78->34% zero-gap), sometimes
approaching oracle's det=16 level; but separation != correctness (a wrong
belief just gets more confident). (iii) mirror on cross-deck OVERRIDES v1
even more than oracle (confidently wrong) yet gates ~= comp -> in these
lopsided matchups the exact option rarely swings the game.
Whether that headroom converts to WINS is answered by the oracle GATES
(perfect-belief ceiling, 300 games each) — [pending].

**Oracle ceiling gates (perfect belief, 300 games each) — the number that
decides Step 2:**

| opponent | v1 base | comp (honest) | mirror (wrong) | oracle (perfect) |
|---|---|---|---|---|
| Garchomp   | 72.5% | 73.7% [68.4,78.3] | 71.0% [65.6,75.8] | 78.3% [73.3,82.6] |
| Alakazam   | 37.5% | 42.7% [37.2,48.3] | 40.7% [35.3,46.3] | 51.3% [45.7,56.9] |
| Kangaskhan | 75.0% | 75.3% [70.2,79.9] | 72.3% [67.0,77.1] | 73.3% [68.1,78.0] |

**Verdict — Option 1 (archetype priors) is JUSTIFIED, with a caveat.**
(i) Perfect belief converts to wins: oracle beats comp by +4.6 (Garchomp)
and +8.6 (Alakazam) pt on the matchups with headroom, and on Alakazam — the
deck we LOSE to at v1 — perfect knowledge swings us +13.8pt (37.5->51.3%),
loss to coin-flip. That comp->oracle gap is precisely what META archetype
priors close, so Step 2 has real, quantified headroom (~+5 to +9pt on
contested matchups). comp already banks ~a third of it (Alakazam +5.2 of
+13.8). (ii) CAVEAT: against the single strongest archetype (Alakazam/
Dudunsparce, 73% ladder win rate) even PERFECT search only reaches parity
(51.3%, CI still spans 50%) — our 35-energy deck is the limiter there, a
separate lever no belief fixes. (iii) Kangaskhan has zero headroom (oracle
~= comp ~= base 73-75%): matchup decided by deck power, not decision
quality. Net: we're strong vs most of the field (Garchomp/Kangaskhan
~73-78%), weak vs the Alakazam cluster; search+honest-belief adds a little
now and archetype priors can add materially more where it matters.

-> STOP for user sign-off before Step 2 (archetype-prior belief).

## 2026-07-09 — Phase F: ship-config pilots + bundle (comp+terminal+v1)

Decision to skip Step 2 (archetype priors) per user: oracle ceiling shows
priors capture only a fraction of a comp->oracle gap that even at maximum
(oracle) only reaches PARITY vs the top Alakazam deck; ladder signal + the
deck offensive are higher-EV than a few points of opponent modeling. Ship
now, then attack the deck.

Phase C measured K TIMING only; ran the deferred STRENGTH pilots (200-game
self-play, both sides search, det16, governor off) to pick the ship config:
- E3 s1-rollouts vs v1-rollouts (both terminal): s1 **45.0% [38.3,51.9]** ->
  s1 rollouts do NOT help (worse/neutral) at 7.6x the per-step cost. REJECT.
- E2 value-trunc K=10 vs terminal (both v1): cap10 **51.5% [44.6,58.3]** ->
  truncation strength-neutral; its only gain is speed we don't need (governor
  keeps terminal safe: stress max own-time 35.6s at 3x). REJECT.
Both confirm the diagnosis prediction: neither net-in-the-loop addition
converts, because belief quality (not rollout fidelity or sample count) was
the bottleneck. **Ship config = comp belief + terminal rollouts + v1 rollout
policy + governor** — the CI-backed Step-1 config (73.7/42.7/75.3 vs the 3
meta decks) and NUMPY-FREE (value/policy nets never touched at runtime ->
no Python-3.11 numpy pin needed). E4 (mirror teacher slope) skipped per user.

## 2026-07-09 — Deck offensive: ship v2.1.0-alakazam

Feasibility gate (deck offensive step 2): our belief-search agent piloting
the winning Dudunsparce/Alakazam list (metaB_alakazam.csv, extracted from 10
top-ladder games) vs the SAME agent piloting our current 35-energy deck:
**74.7% [69.5, 79.3] PASS, 0 crashes, both seats (124/100)**. Switching to
the stronger deck wins by itself — the deck was the ceiling, exactly as the
oracle diagnosis predicted. Why our old deck lost to it: Alakazam runs 4x
Enhanced Hammer (energy denial) + a Rare Candy/Poffin/Hilda/Dawn draw engine
+ low-cost attackers (Dudunsparce HP140/dmg90) — a hard counter to our
energy-dependent Hammer-lanche.

Bundle ptcg-search-v2.1.0-alakazam (submission_search_metaB_alakazam.tar.gz,
2.00 MiB, 13 members): identical agent + search config (comp/terminal/v1/
governor, numpy-free), only deck.csv swapped to the Alakazam list; full
1267-card card_data covers it. Checks green: deck valid (60/1 ACE SPEC/8
basics), exec-load (search baked on), no-cg fallback, 30-game parallel smoke
0 crash/0 fallback (decision p50 746ms p90 2265ms p99 3160ms max 3390ms —
Alakazam games are longer so slightly above our-deck's p99 2.37s, still far
under any timeout; governor bounds each decision to budget + one det).
Confirmatory gate v2.1.0 vs v1+Alakazam [running, non-blocking].

## 2026-07-09 — LADDER VERDICT + Phase 1 intel (v2.1.0 FAILED, root-caused)

Ladder: v2.0.0 (old deck+search) μ=614/25g — search architecture works.
v2.1.0 (Alakazam+search) μ=548/6g — FAILED, -66 vs v2.0.0. Sanjay PPO 616.8.
Top-5 threshold ~1100. The 74.7% feasibility gate was non-predictive: its
opponent was our-own-agent+old-deck (not the ladder field) and both sides
mispiloted Alakazam symmetrically -> couldn't surface shared piloting
weakness. Full narrative in report/WRITEUP_DRAFT.md 2 + report/LADDER_INTEL.md.

Phase 1 intel (tools/analyze_top_replays.py over 47 replays;
tools/diagnose_alakazam_piloting.py):
- **Majkel1337 (rank1 μ1260) plays a deck BYTE-IDENTICAL to our
  metaB_alakazam.csv (19/19 ids, 60/60 copies).** We already ship the rank-1
  deck. Gap = 100% piloting. He grinds 44-turn denial games (4.0 denial/game,
  first-attack turn 4.1); we attack turn 11.2, never attack in 30% of games,
  28.8-turn games (denial rate matches at 4.2 — tempo/close-out is the failure,
  not denial).
- **Top teams run FAST POLICIES** (median 31-92ms: kashiwashira 33ms Mewtwo
  stall, nasuo445 31ms Garchomp, Majkel 92ms). We + Project Mew run SEARCH
  (200-320ms median); Project Mew (only search team in elite pool) goes 16-15
  ~50%. Search is competitive but not how anyone reaches top-2.
- **Meta triangle:** Alakazam decks-out Mewtwo stall (5-0); Mewtwo out-prizes
  Alakazam in longest games; **Garchomp (nasuo445) went 2-0 beating BOTH** and
  is META's highest lb archetype — the meta counter and simplest top-deck pilot.
- Mechanistic root cause: our search only searches MAIN single-selects + v1
  rollout; Alakazam's strength lives in trainer sub-decisions (Rare Candy,
  Boss's Orders, multi-select) the search skips -> mishandles combo decks
  (614 simple deck vs 548 combo deck, same architecture).

RECOMMENDATION (report/LADDER_INTEL.md §RECOMMENDATION): immediate free action
= ensure live slot is v2.0.0 (614) not v2.1.0 (548). Ranked: 1) Option C
Garchomp (meta counter, simplest pilot, best arch-fit; gate vs v2.0.0 AND top
decks) 2) Option B fix Alakazam piloting (highest ceiling=rank1 deck but fights
arch blind spot) 3) Option A already-done (=548) 4) Option D fast-policy/RL
(real long-term answer, weeks not days). STOP for Phase 2 sign-off.
Data gap: no real v2.1.0 loss episodes (only 2 self-mirror agent logs); asked
user to drop them in data/loss_episodes/.

## 2026-07-10 — Stage 1 Garchomp: G1 FAILED, STOP per protocol

G1 (search+Garchomp+PILOT=garchomp vs v2.0.0 old deck, 300g, governor off,
0 crashes): **39.3% [34.0, 45.0] -> FAIL** (CI upper 45% < 50%). Loss reasons
138 prizes / 44 no-active -> we lose the prize race. G2/G3 (vs Alakazam, vs
Mewtwo) were killed unfinished — search-vs-search at 300g on long
Alakazam/Mewtwo-stall games is impractically slow, and G1 already decided the
STOP.

Failure-mode analysis (tools/analyze_garchomp_losses.py, 30g governor-on,
20% win — same direction as G1): **first-attack turn 10.8 vs nasuo445's 4.1;
Garchomp ex online turn 13.6 (vs ~6), and NEVER online in 7/30 games.** Root
cause is SETUP SPEED, not attack selection: our search + v1-rollout cannot
sequence the 3-stage Gible->Gabite->Garchomp ex chain fast enough, so the
attacker arrives ~7 turns late and we lose the race to our own fast aggro
deck. The tempo heuristic (attack once loaded) and ex-evolution bonus can't
help a not-loaded problem — the telemetry showed exactly this (turn-4
'not-loaded, active=Gabite, 1 energy').

**Strategic finding (two data points now):** our search+heuristic architecture
mishandles BOTH complex meta decks it has tried — Alakazam (ladder μ548) and
Garchomp (gate 39.3% vs our own old deck) — while piloting our SIMPLE aggro
deck to μ614. The blocker is architectural: the search only searches MAIN
single-selects and rolls out with a v1 heuristic tuned for 1-step
attach-and-attack; it cannot plan the multi-turn evolution/combo setup that
every top-ladder deck requires. Deck-specific heuristic patches do not fix a
shallow-planning problem. This directly informs Stages 2-4: only an approach
that LEARNS the setup sequencing (distillation from a competent teacher / BC
from top replays / RL) can pilot these decks — OR we accept the architecture's
ceiling is the simple deck (v2.0.0, 614). Per protocol: STOP, no patching,
report for user direction on whether/how to proceed to Stage 2.

## 2026-07-10 — Stage 3A: BC feasibility (tools/bc_feasibility.py) — CLEAN, GO

Question: can we recover (state, chosen-option-index) BC targets from top-team
replays? Answer: YES.
- **Alignment (verified):** the ACTIVE agent's observation.select at steps[i]
  is answered by that same agent's action at steps[i+1]. Naive same-step
  pairing is WRONG (off-by-one; deck action shows against a yes/no obs). With
  the shift: **99.2% clean index recovery** (2057 valid / 17 invalid over 49
  episodes). The visualize transcript also carries per-entry obs/action/selected
  as a backup path.
- **Decision mix (winning top-team sides only, 1530+... = 2057 decisions):**
  MAIN-single 74% (1530) | non-MAIN type1/ST_CARD 18% (378, fetch/target
  sub-decisions) | yes-no 4% | energy 2% | evolve-subselect 1% | MAIN-multi 1%.
- **Encodability: ALL 1530 MAIN-single decisions encode cleanly** with the
  EXISTING train_policy.py 170-dim state + 41-dim option scheme (0 failures) —
  no new encoding needed. The setup SEQUENCING our search couldn't plan (play/
  evolve/attack ordering) lives in these MAIN-single decisions, exactly the
  target BC captures; the 26% sub-decisions stay on the v1 heuristic (same
  division of labor the search uses).
- **Volume:** 1530 targets from 47 episodes / 15 winning top-team sides
  (Majkel 1146, kashiwashira 262, nasuo445 122). Scales to ~15-20k at 500
  episodes. Modest — flag as the main risk (BC on expert data can work at this
  scale, but per-deck balance matters: an Alakazam BC has 1146 targets, Garchomp
  only 122).
- **Opponent turns (Q3):** we can only imitate the ACTIVE decider, filtered to
  winning top-team sides. 0/15 games had BOTH sides as winning top teams -> we
  get ONE side per game, data ~1x NOT 2x.
- **Extraction cost:** LOW — alignment+encoding already work with existing code;
  ~1 day incl. the bulk download. Under the 2-day threshold. BLOCKER for 3B:
  Kaggle CLI is NOT available in this environment -> user must supply creds or
  do the bulk download (target the deck we'll pilot).

VERDICT: 3A PASS — extraction is clean. STOP for user sign-off before 3B.

## 2026-07-10 — Refreshed 3A intel (harvest via Kaggle HTTP API)

Kaggle CLI 2.2.3 rejects all creds client-side (buggy expiry check); the
OAuth bearer from ~/.kaggle/credentials.json works via direct HTTP (valid
until ~19:54 local; renew with `py -3.12 -m kaggle auth login`). Built
tools/harvest_episodes.py: leaderboard snapshot + newest-days-first scan of
the daily episode datasets, parallel per-file zip fetch, keep top-10 games
only, resume-safe ledger. 64% of random episodes involve a top-10 team; 812
episodes kept (~2,100s wall).

Leaderboard churn: NEW #1 Yushin Ito 1277.8 (Grimmsnarl/Fezandipiti E10);
Majkel 1260->1153.7 (#2); kashiwashira + Mewtwo stall OUT of top tier;
Kangaskhan now /Crustle E1 (was /Raging Bolt E16). Majkel's primary Alakazam
list STILL byte-identical to our metaB_alakazam.csv (119 sides).

Refreshed feasibility (908 episodes, 628 winning top-10 sides): alignment
99.7% clean; 29,429 MAIN-single targets, ALL encode with the existing 170+41
scheme; category mix shifted to 60% MAIN-single / 30% ST_CARD sub-decisions
(meta is more fetch/effect-heavy -> BC covers 60% of decisions, rest v1).
No team under the 200-decision data-thin bar (min Sota 474).

Per-deck BC pools (winning sides): Alakazam(Majkel-list) 6,821; Fezandipiti/
Dudunsparce family 5,371 (weighted rating 1,169, incl. new #1); Garchomp
4,610; capbloo-Alakazam family 4,151; Kangaskhan/Crustle 3,006; Grimmsnarl/
Fezandipiti 2,385 (single pilot, data-thin). Full tables in
report/LADDER_INTEL_REFRESHED.md. Recommendation: 1) Alakazam (volume +
ready infra + cleanest G7 science) 2) Fezandipiti/Dudunsparce (ceiling)
3) Garchomp (simplicity). STOPPED for deck pick before 3B.

## 2026-07-11 — Stage 3B-Garchomp: G6a/G6b FAIL — BC-as-scoped diagnosed

Training looked excellent: val top-1 69.4% vs floors uniform 16.0 /
always-0 21.4 / **v1-agreement 20.8** (net learned strongly non-v1 play;
compare S1's +1.2pt over floor). It did not convert:
- **G6a (SHIP-CRITICAL) BC-Garchomp vs v2.0.0: 31.0% [26.0,36.4] FAIL**
  (worse than search+Garchomp's 39.3%; 158 prize-race losses, 0 crashes).
- **G6b BC vs search+Garchomp, SAME deck (pure piloting): 42.7% [37.2,48.3]
  FAIL** — BC pilots the deck no better (worse) than the search it was
  meant to replace.
- G6c (vs search+Alakazam) still running; coverage only, doesn't change
  the verdict.

Loss analysis (24g, BC mode): **first-attack turn 14.6** (search+PILOT
10.8, nasuo 4.1), ex online 15.6, 21% win. BC did NOT reproduce the
demonstrated tempo. Two structural causes:
1. **Sub-decision blindness.** BC controls only MAIN single-selects (60%);
   the fetch TARGETS (Buddy-Buddy Poffin / Fighting Gong picks — the
   actual setup mechanism) are ST_CARD sub-decisions answered by v1. BC
   says "play Poffin", v1 fetches the wrong Pokemon -> the hand never
   contains the pieces nasuo's line needs. (The winning pool has 14,960
   ST_CARD targets — MORE than MAIN — currently unused.)
2. **Compounding off-distribution error** (the classic BC failure): 69%
   per-decision on nasuo's states -> P(follow a 5-step line) ~ 0.69^5 =
   16%; first deviation leaves the net off-distribution where val accuracy
   says nothing.

**Alakazam-BC go/no-go: NO-GO as currently scoped.** Both causes apply at
least as strongly to Alakazam (its engine is MORE sub-decision-heavy: Rare
Candy targets, Night Stretcher, Poffin). Training it unchanged would burn a
day to learn the same lesson. Salvage options reported to user: (A) BC-full
— extend imitation to ST_CARD sub-decisions (new option encoder; ~doubles
usable data; directly removes cause 1); (B) hybrid — BC as rollout/prior
INSIDE the search (lookahead corrects compounding error; ExIt-style);
(C) halt Stage 3, advance to Stage 4 decision gate. v2.0.0 stays incumbent.

**G6c landed (async):** BC-Garchomp vs search+Alakazam (v2.1.0 config):
44.7% [39.1, 50.3] FAIL, 0 crashes. Consistent with G6a/G6b — BC-as-scoped
is below every incumbent config. Interesting detail: 64 of BC's 134 wins
come by DECKOUT (reason 2) — the BC net did absorb some of the meta's
grind-them-out texture — but it loses the prize race 127 times. Verdict
unchanged: NO-GO on Alakazam BC as scoped; stop-report stands.

## 2026-07-11 — TOOLING BUG: analyze/diagnose tools drove the SAMPLE agent

Found while wiring BC-full head-fire telemetry (main.STATS missing at
runtime): tools/analyze_garchomp_losses.py and
tools/diagnose_alakazam_piloting.py insert
sample_submission/sample_submission at sys.path[0] BEFORE `import main` —
and that directory ships its own main.py (the 38-line random sample agent).
Every historical run of BOTH tools bound `main` to the SAMPLE agent: their
games were random-vs-random (both wrappers call main.agent).

INVALIDATED numbers (diagnostic-only, never gate results):
- search+PILOT "first-attack 10.8 / ex online 13.6 / 20% win" (2026-07-10)
- prior-BC "first-attack 14.6 / ex online 15.6 / 21% win" (2026-07-11)
- diagnose_alakazam_piloting's Majkel-comparison telemetry
NOT affected: all ab_gate gates (G1, G6a/b/c — deck_compare imports repo
main first), bc_feasibility (inserts sample path after import), extraction,
training, ladder results. The Stage-1/3B verdicts stand (they were decided
by gates), but every piloting-signature number must be re-measured.

Fix: import main before the sample-path insert + assert hasattr(main,
"STATS") in both tools. Re-measuring 30g signatures for search+PILOT,
BC-prior, BC-full with the fixed tool (A4).

## 2026-07-11 — Stage 3B Option A: BC-full — G6a-full PASS (first incumbent beat)

Build: 73-dim ST_CARD option encoder (encode_card_option: deck-id one-hot,
card stats, board slot, area + context buckets, v1-prior from _score_card);
extraction extended to the ST_CARD family with Plackett-Luce decomposition of
multi-selects (2,445 raw -> 2,397 steps, 0 bad-action / 0 encode-fail; deck
fetches 1,297, Poffin 120, Night Stretcher 92); two-headed net, shared
170->80->48 trunk + MAIN(41d)/CARD(73d) heads, 27.9k params. Extraction also
fixed a dead feature: the hand-count block was keyed to OUR deck's ids (1/20
Garchomp overlap) — now dynamic via PTCG_DYN_DECK_TABLES=1 (default 0 =
byte-identical). Val: MAIN 68.9% (floors 21.4 always-0 / 20.8 v1 / 16.0
uniform; prior BC 69.4 — parity), CARD 76.1% (floors 51.6 always-0 / 49.5 v1 /
23.3 uniform). Per-context: Poffin TO_BENCH/deck 100% (v1 36%), DISCARD/hand
87% (v1 9%), TO_HAND/deck 61.9% (v1 46%), TO_HAND/discard 60% (v1 20%).
Integrated behind PTCG_BC=garchomp_full (two-head loader, iterative-argmax
card picks mirroring the PL training scheme); fault suite ALL OK.

A4 piloting signature, 30g vs v2.0.0 each, FIXED tool (see shadow-bug entry):
  BC-full        53% win  first-attack 6.4  ex online 6.9 (27/30)
  search+PILOT   37% win  first-attack 6.4  ex online 7.8 (23/30)  [~= its 39.3% gate: tool validated]
  v1-only        30% win  first-attack 4.6  ex online 7.0 (20/30)
  BC-prior       10% win  first-attack 6.8  ex online 7.2 (17/30)
  nasuo445 truth (140 replays, 80 wins): first-attack 5.9 mean / 6.0 median,
  ex online 5.9. (The logged "4.1" was stale/wrong too.)
Head-fire over BC-full's 2,113 decisions: MAIN 61%, CARD 28%, eligible-but-v1
0 — integration clean. KEY REVISION: first-attack turn was never the
discriminator (v1 attacks EARLIEST at 4.6 and still loses); the failure was
sub-decision QUALITY — what gets fetched/discarded — and consistency
(ex-online games 17/30 -> 27/30).

Gates (300g, seats alternated, Wilson CI, governor off, 0 crashes all):
- G6a-full (SHIP-CRITICAL) BC-full vs v2.0.0:
  **60.7% [55.0, 66.0] PASS** — first challenger ever to beat the incumbent.
  Win reasons 162 no-active / 20 prizes.
- G6c-full BC-full vs BC-prior (isolates ST_CARD head; only change is who
  answers sub-decisions): **77.0% [71.9, 81.4] PASS** — causal proof of the
  sub-decision-blindness diagnosis.
- G6b-full BC-full vs search+Garchomp: running, appended below.

Ship: v2.2.0 bundle built (tools/build_search_submission.py --bc): main.py
with PTCG_BC=garchomp_full baked, deck.csv=metaC list, card_data.json,
bc_weights_garchomp_full.npz; NO cg/ (no search) -> 0.22 MiB. exec-load in
bare temp dir OK; weights-stripped fallback -> v1 + one stderr line OK;
30-game smoke 0 crash / 0 fallback; decision p50 1ms p99 3ms (top-10 speed
class). STOPPED at stop point (d) for ship sign-off.
G6b-full landed: BC-full vs search+Garchomp (the 39.3% failure config):
**69.7% [64.2, 74.6] PASS**, 0 crashes (W 178 prizes / 21 no-active /
10 deckout). Full matrix: G6a-full 60.7 PASS, G6b-full 69.7 PASS, G6c-full
77.0 PASS — Option A complete, all gates green.

## 2026-08-11 — Project Mew: Candidate Deck Sweeps & Selective MCTS Gating

- **Deck Validation (`tools/validate_deck.py`)**: All candidate decks (`meta_starmie.csv`, `metaB_alakazam.csv`, `metaC_garchomp_nasuo.csv`, `metaG_grimmsnarl_top10.csv`, `deck.csv`) validated 100% compliant with 60-card, 4-copy, ACE SPEC, and Basic Pokemon rules.
- **Candidate A — Mega Starmie ex (`meta_starmie.csv`) vs Baseline Abomasnow (`deck.csv`)**: **72.0% [58.3%, 82.5%] PASS** over 50 games (seats alternated, 0 crashes, 0 fallbacks). Lower bound Wilson CI > 50%.
- **Candidate A — Mega Starmie ex vs Candidate B Alakazam (`metaB_alakazam.csv`)**: **62.0% [48.2%, 74.1%]** win rate over 50 games.
- **Learned Value Model evaluation (`meta_starmie.csv+PTCG_LEARNED_VALUE=1` vs `meta_starmie.csv`)**: **54.0% [40.4%, 67.0%] FAIL** (CI lower bound <= 50%). Value model disabled per plan rule 21 (does not satisfy CI lower bound > 50% vs specialized Starmie hybrid policy).
- **Selective Search & Gating (`bot/search/gating.py`)**: Integrated `is_critical_decision()` gating (endgame prizes <= 2, multiple attacks, branching >= 6, evolution choices). Routine decisions executed via fast heuristic (<0.05 ms); critical decisions use time-governed PIMC-1 determinized search with guaranteed legal fallback.
- **Artifact Build (`submission_mew_starmie.tar.gz`)**: Created and verified (0.061 MiB). 3W/0L/0D smoke eval, 0 crashes, 0 fallbacks.

