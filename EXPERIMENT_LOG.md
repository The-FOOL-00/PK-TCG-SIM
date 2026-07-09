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
