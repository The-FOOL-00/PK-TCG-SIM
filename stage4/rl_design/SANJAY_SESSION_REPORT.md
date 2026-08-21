# Session Report — AlphaZero-vs-v3 Training Pipeline

Covers everything done in this session, start to finish, in order. Written
2026-07-12, ~21:30, while `az_v3_run1` training is still live and pending a
continue/stop decision at iteration 25.

---

## 1. Starting context

Coming into this session, the project had two parallel tracks already
established from prior work:

- **The deterministic engine track** (`strong_code_submission`, aka v4):
  a hand-crafted, rule-based Pokemon TCG battle engine, hardened across 5
  rounds of real-loss-log analysis. Judged near its practical ceiling —
  only 3 genuine bugs found and fixed across 23 real losses (endgame
  prize-denial, Crustle ex-immunity attack-lock, bench-out win detection).
  `submission_v3` is the same engine minus the last fix (bench-out).
- **The AlphaZero/RL track** (`rl/az.py`, `rl/search_agent.py` etc.): a
  PUCT-MCTS self-play training loop with PIMC/ISMCTS determinization for
  imperfect information, previously stabilized (P0 bug fixes) and warm-started
  via behavior-cloning from a competitor's public agent (oshbocker), but that
  clone had plateaued at only ~16% h2h vs its own teacher.

The user asked: since the deterministic track has plateaued, should we pursue
AZ training. Confirmed yes, and the direction was refined via a clarifying
question to: **use the deterministic engine (v4 at the time) as the AZ
training target/opponent**, not continue imitating the old oshbocker teacher.

## 2. Implementation plan (`IMPLEMENTATION_PLAN.md`)

Before writing any code, audited what already existed vs. what the user's
roadmap (determinization/ISMCTS, masked policy+value net, bootstrap from the
deterministic bot, gatekeeping, non-regression) actually required building:

| Roadmap item | Status found |
|---|---|
| ISMCTS/determinization | Already built (`_determinize` in `search_agent.py`) |
| Policy+value net, action masking | Already built (`policy.py`, `encoding.py`) |
| Bootstrap policy prior from det. bot | Pipeline existed (`clone_datagen.py` + `sl_pretrain.py`), just needed re-running with the right teacher |
| Pretrain value head on win/loss | Already built into `sl_pretrain.py` |
| AZ self-play loop | Already built (`az.py`) |
| Gatekeeping (only promote at >55%) | **Missing** — built this session |
| Opponent diversity (play the det. bot) | **Missing** — only net-vs-net league play existed |
| Non-regression / fallback | Established protocol existed (`h2h_bundles.py`, n>=300 gates) |

This produced a 5-phase plan: Phase 0 (leakage audit) → Phase 1 (engine as
league opponent) → Phase 2 (bootstrap dataset + SL) → Phase 3 (gatekeeping)
→ Phase 4 (training runs) → Phase 5 (non-regression shipping gate).

## 3. Phase 0 — information-leakage audit

Built `scripts/leakage_test.py`. Three checks, all **PASS (6/6)**:
1. Structural: opponent hand contents are `None` in the raw obs (never
   exposed); no deck-order field exists for either player; only counts
   (`handCount`, `deckCount`) are present.
2. Encoder invariance: planted fake ground-truth hidden info into a copied
   obs dict; the encoder's output tensors were bit-identical with and
   without the plant — proves the encoder physically cannot read hidden info
   even if it were present.
3. Determinizer invariance: same test against `_determinize()` — bit-identical
   determinizations regardless of planted ground truth, and zone sizes
   (`opponent_hand`, `opponent_deck`, etc.) exactly matched public counts.

This confirmed the existing ISMCTS/PIMC implementation was sound and did not
need to be rebuilt — only verified.

## 4. Phase 1 — deterministic engine as an in-process league opponent

New file `rl/engine_opp.py`: loads a submission bundle's `battle_engine.py`
in-process (not subprocess) and exposes `engine_pick(obs)` with the same
crash-safe fallback contract as a real submission's `main.py`.

**Why in-process is safe** (verified before wiring, not assumed): the
deterministic engine has `USE_SEARCH=False` — it never touches its own C
engine's search/battle globals, only calls `all_card_data()` at import. Its
package is named `cg`, distinct from the RL stack's `sdk_cg`, so both DLL
bindings coexist in one process without collision.

`rl/az.py` changes:
- `--engine-opp <bundle_dir>` CLI flag.
- `_selfplay_game()` extended to accept `opp_pick_fn` + `opp_deck` (engine
  pilots its own deck, since engines are deck-tuned).
- Worker-side: `opp_frac` coin-flip now splits between engine opponent and
  net opponent 50/50 if both are configured.
- Per-opponent-kind stats: `league_wr_engine=X` / `league_wr_net=X` logged
  separately.

**Smoke test** (`scripts/smoke_engine_opp.py`): 50 games, in-process engine
opponent, MCTS learner side. Result: **0 crashes, 0 illegal picks, 0
timeouts.** Re-run later against `submission_v3` specifically: 20/20 clean.

## 5. Phase 3 — AlphaZero-style gatekeeping

New function `_gate_match()` in `az.py`: plays `n_games` real MCTS matches
(temp=0, i.e. greedy-search) between the current net and a frozen opponent
(either `best.pt` or the deterministic engine), alternating seats, counting
draws as 0.5.

Wired into the training loop: every `--gate-every` iterations,
1. Current net vs `best.pt` → promote `best.pt` only if score ≥
   `--gate-thresh` (default 0.55). Training always continues from `latest.pt`
   regardless — gating is evaluation-only, standard AlphaZero practice, never
   blocks training.
2. Current net vs the engine opponent → logged as `gate_vs_engine`, **the
   real progress signal**: this climbing past ~50% over a sustained trend is
   what "surpassing the deterministic engine" looks like.

**End-to-end verification**: ran a tiny 2-iteration, 2-worker training loop
with `--engine-opp` and `--gate-every 1` before trusting the mechanism.
Exercised every code path (engine league games, best.pt init, a PROMOTED
gate result, a "kept" gate result, the vs_engine gate) cleanly.

All of Phases 0/1/3 committed as `d138e53` and `f3e0394`.

## 6. Phase 2 — bootstrap dataset + SL pretrain (first attempt, targeted v4)

`scripts/clone_datagen.py` already supported `--teacher <bundle_dir>` with
no code changes needed. Ran:
- **Datagen**: 5,000 games, teacher = `strong_code_submission` (v4),
  mirror + 20% cross-deck games. Result: 581,483 decisions, **0 errors**,
  balanced outcome (2,524/2,470/6).
- **SL pretrain** launched on GPU (`rl/sl_pretrain.py`, 10 epochs): reached
  epoch 4/10 (teacher_match 78.4%, climbing cleanly) before being
  interrupted by the v4→v3 switch (see next section). No data lost — just
  restarted against the v3 dataset instead.

Built the automation to chain these stages together:
- `scripts/baseline_eval_v4.py` — measures the fresh SL clone's win rate vs
  the target engine at two search depths (30 sims / 100 sims), n=200 each.
  (Name is stale from the v4-first attempt; works fine against v3 via
  `--bundle submission_v3`.)
- `scripts/chain_after_sl.sh` — polls for SL completion (log-content polling,
  not process-liveness polling, since PID visibility proved unreliable
  across this shell's process boundary on Windows/Git-Bash), then
  auto-runs baseline eval → stages the warm-start checkpoint → launches AZ
  training. Includes a 30-minute stall-detection abort so an orphaned
  watcher self-terminates instead of running forever.

Committed as `62ef8e5`.

## 7. Mid-session pivot: v4 → v3

**User reported v4 was reading badly on the real Kaggle ladder.** Per
explicit instruction, switched the entire AZ pipeline target from v4
(`strong_code_submission`) to v3 (`submission_v3`).

Context preserved for future reference: v3 and v4 differ by exactly one
code fix — v4 adds bench-out win-condition detection, which was verified
non-regressing in every controlled h2h test run during its original
development (51.0% vs baseline n=400, gains concentrated in thin-bench
endgames the general gauntlet under-represents). So the bad ladder reading
is more likely ladder variance/opponent-pool than the fix itself (there's
documented precedent: the same exact code read 800 vs 720 Elo on different
ladder days earlier in the project) — but the instruction was followed
regardless, and this note exists so a future session doesn't have to
rediscover that nuance blind.

Actions taken:
1. Killed the in-progress v4 SL pretrain process.
2. Re-ran datagen with `submission_v3` as teacher: 5,000 games, 584,805
   decisions, 0 errors, balanced outcome (2,534/2,460/6).
3. Re-ran the v3-engine-opp smoke test (20 games) — clean, 0 issues.
4. Rewrote `chain_after_sl.sh` to target v3 throughout (`sl_v3`, `clone_v3.pt`,
   `az_v3_run1`, `submission_v3`).
5. New wrapper `scripts/run_v3_pipeline.sh`: waits for datagen completion →
   launches SL pretrain → hands off to `chain_after_sl.sh`. Fully unattended,
   single command.
6. New `scripts/sync_gpu_lab.sh`: background loop copying `clone_v3.pt` and
   `az_v3_run1` checkpoints into `gpu_lab/` (and later `gpu_lab_colab/`)
   every 60 seconds, so those folders stay current without manual steps.

Committed as `ac5e8de`.

## 8. SL pretrain results (v3, final)

10/10 epochs completed cleanly. Held-out (never-trained-on) teacher_match
progression: 12.9% (untrained) → 68.4% → 73.9% → ... → **82.2% final**.
Value loss stayed flat around 0.63-0.70 throughout (no overfitting
divergence between train and held-out loss).

## 9. Baseline evaluation (v3 clone vs v3 engine, before any AZ training)

`baseline_v3.json`, n=200 games each:
- Light search (30 sims): **34.25%**
- Full search (100 sims): **35.25%**

This is the number the AZ loop's `gate_vs_engine` needed to climb past 50%
to represent real progress. Notably higher than the old oshbocker-clone's
16% baseline from earlier project work — starting from a stronger prior
since this is a same-project self-clone rather than a competitor's agent.

## 10. `IMPLEMENTATION_PLAN.md`'s belief-state question, answered

Mid-session the user asked how imperfect information is handled. Answer
given (and preserved in `HANDOFF.md`): determinization/ISMCTS (Phase 0's
mechanism), not an explicit belief-vector net input. Concretely:
overlap-weighted sampling over known archetypes consistent with observed
cards → fill the unseen remainder to match exact observed counts → repeat
fresh per simulation across `n_det` determinizations → MCTS aggregates.
Verified leak-free (Phase 0).

## 11. AZ training launch (`az_v3_run1`)

Config: `--init-from clone_v3.pt --engine-opp submission_v3 --opp-frac 0.4
--workers 4 --games-per-iter 40 --iters 200 --n-sims 100 --n-det 2
--gate-every 5 --gate-games 60 --gate-sims 30 --gate-thresh 0.55 --device cuda`

**This run was explicitly framed as a pre-start/validation run for the GPU
lab tomorrow (2026-07-13), not the full training run** — 200 iterations on
4 CPU workers would take an estimated 35-40+ hours, far beyond one evening.
Its purposes: (a) validate the full pipeline under real sustained load, not
just smoke tests, (b) produce a warm-start checkpoint further along than
the raw SL clone, (c) establish an early `gate_vs_engine` trend to compare
against once lab-scale training starts.

### Timeline of issues encountered during the run

- **Iteration 10**: a worker process hit `MemoryError` while pickling a
  large game's samples through the multiprocessing pipe (likely an
  outlier-length game). The existing liveness-detection/respawn logic
  (built during earlier P0 stabilization work, before this session) caught
  it correctly: `[worker 1] dead/hung (dead); respawning, skipping 2 games`
  — training continued with only 2 games of data lost. Not a bug in this
  session's changes; the safety net worked as designed.
- **Stale-log confusion**: an earlier orphaned `chain_after_sl.sh` watcher
  process (launched before the v3 switch, watching the now-dead
  `sl_v4.log`) self-aborted via its 30-minute stall detection, writing a
  confusing-looking error to the OLD `chain_after_sl.log` file well after
  the real v3 pipeline had already moved past that stage. Diagnosed by
  checking `run_v3_pipeline.log` (the real pipeline's actual output stream)
  instead — no actual conflict, just two log files with similar names from
  two different pipeline attempts.

### Gate results so far (the core finding of this session's training run)

| iteration | vs_best | vs_engine (the real signal) | league_wr_engine (raw per-iter, noisy) |
|---|---|---|---|
| baseline (pre-training) | — | **34-35%** | — |
| it=5 | 0.48 (kept) | **22%** | 0.11–0.36 across it 1-5 |
| it=10 | 0.37 (kept) | **8%** | 0.10–0.25 across it 6-10 |
| it=15 | 0.40 (kept) | **15%** | 0.12–0.21 across it 11-15 |
| it=20 | 0.27 (kept) | **5%** (new low) | 0.05–0.16 across it 16-20 |

**Verdict as of it=20: the net is regressing from its SL starting point, not
improving.** `vs_best` never once crossed the 0.55 promotion threshold — the
warm-started clone has never been beaten by any later checkpoint. `vs_engine`
shows a clear downward trend from the 34-35% starting point, with a brief
partial recovery at it=15 that did not hold — it=20 hit a new low (5%),
worse than it=10.

Sanity checks stayed solid throughout (ruling out a broken pipeline as the
cause): `greedy_winrate_vs_random` held 80-95% across all eval points, 0
timeouts across 20 iterations, only the one MemoryError (handled).

**Working hypothesis for the cause** (not yet confirmed): with the replay
buffer capped at 10,000 samples (hit by ~iteration 4) and `opp_frac=0.4`
throwing 40% of self-play games against a strong deterministic opponent from
iteration 1, the net likely received noisy/adversarial training signal
before its own MCTS-search targets were good enough to make use of it — a
plausible "training destroys the SL prior before search catches up" failure
mode for a small net (427K params) with a small buffer. Not yet diagnosed
further; the user asked to watch through iteration 25 before deciding.

**Status at time of writing this report: waiting on the it=25 gate to
confirm the trend, with a stop/diagnose recommendation already given if it
doesn't recover.** This is the single open decision point — see the "Next
steps" section.

## 12. GPU lab folder (`gpu_lab/`)

Self-contained folder (~15MB) built for copying to the physical GPU lab
tomorrow: `rl/`, `sdk_cg/`, `submission_v3/`, `decks/`, `scripts/`,
`EN_Card_Data.csv`, `requirements.txt`, `pyproject.toml`,
`IMPLEMENTATION_PLAN.md`, `HANDOFF.md`, fallback checkpoint
(`az_clone_run1/latest.pt`), plus `clone_v3.pt` and `az_v3_run1/` checkpoints
kept continuously current by `sync_gpu_lab.sh`.

`gpu_lab/SETUP.md` documents: dependency install, mandatory sanity checks
before any long run (`leakage_test.py`, `smoke_engine_opp.py`), the exact
resume command (auto-detecting CPU core count for `--workers`), what each
training log line means, and the Phase 5 non-regression gate table.

Key point flagged explicitly: **self-play is CPU-bound, not GPU-bound** — a
"GPU lab" doesn't guarantee strong self-play throughput if its CPU core
count is modest, which is common in GPU-dense/CPU-light ML lab machines.
Core count must be checked on arrival, not assumed.

## 13. Colab folder (`gpu_lab_colab/`)

Built as a parallel, free, unattended-overnight option, with expectations
set honestly upfront: Colab typically gives ~2 vCPUs, so self-play (the
actual bottleneck) will likely run with fewer workers than even this box's
4 — a supplement to the lab run, not a replacement.

Contents: same code as `gpu_lab/` plus `pokemon_az_colab.ipynb` (a full
notebook: mount Drive → extract an uploaded zip → install deps → run
sanity checks → auto-detect CPU count and launch training, writing all
checkpoints to Google Drive so a session disconnect doesn't lose progress)
and `COLAB_SETUP.md`.

**Issues hit and fixed during actual Colab use:**
- `pip install -r requirements.txt` failed: `numpy<2.0` (pinned for
  `kaggle-environments`, which nothing in the AZ training path actually
  imports) conflicted with Colab's preinstalled numpy 2.x. Fixed by
  rewriting `gpu_lab_colab/requirements.txt` to install nothing extra
  (confirmed via grep that only `numpy`/`torch` are used, no legacy
  `np.float`/`np.int` aliases anywhere in `rl/` or `scripts/`).
- User asked about running on Colab's TPU instead. Explained why this
  wouldn't help: PyTorch-on-TPU requires `torch_xla` (not a `--device` swap),
  and critically, the actual bottleneck (self-play calling the C engine via
  ctypes) runs on host CPU regardless of accelerator — a TPU has zero effect
  on it. The small net (427K params) also isn't compute-bound enough on a
  GPU to benefit from more matrix-multiply throughput.
- Confirmed on the actual Colab runtime: `cuda available: True`, `cpu count:
  2` — exactly as predicted. Training launched there with `--workers 1`,
  resumed correctly from the Drive-synced `az_v3_run1/latest.pt` checkpoint.

## 14. `HANDOFF.md`

A separate, purpose-built document (also copied into `gpu_lab/`) for
resuming this exact work in a brand new session with zero prior context.
Contains: TL;DR, why-v3-not-v4, full repo map of session changes, exact
`az.py` diff summary with commit hashes, current run config + baseline
numbers, PowerShell status commands, resume command, GPU lab plan, the
belief-state explanation, the non-regression gate table, and explicit open
threads (the unresolved v3/v4 ladder discrepancy, the fact that v4 has no
SL dataset of its own if ever reinstated as target).

## 15. All commits this session (chronological)

```
d138e53  AZ-from-v4 plan + Phase 0/1: leakage gate (6/6 pass), v4 engine as in-process league opponent
f3e0394  Phase 3: AlphaZero gatekeeping (best.pt promotion at >=55%, engine-opp yardstick gate)
62ef8e5  Add SL->baseline->AZ chain protocol and v4 baseline-eval script
ac5e8de  Switch AZ training pipeline target from v4 to v3; add run_v3_pipeline.sh and sync_gpu_lab.sh
79a981c  Add session handoff doc: AZ-vs-v3 pipeline state, resume instructions, open threads
1af16b5  Add Colab-specific training folder: notebook + setup doc
8d6c0cb  Fix Colab dependency conflict: drop kaggle-environments/numpy<2.0 pin
```

## 16. Current status (as of writing) and the open decision

**`az_v3_run1` is still running**, past iteration 20, heading toward the
promised iteration 25 checkpoint. The `gate_vs_engine` trend (34-35% → 22% →
8% → 15% → 5%) shows the net getting worse than its SL starting point, not
better, with no confirmed recovery yet.

**Recommendation already given, pending user decision**: finish observing
to it=25 (low cost, confirms the trend either way), then if it hasn't
clearly turned around, stop and diagnose rather than let it run overnight —
most likely fix would be lowering `--opp-frac` early (less adversarial
pressure before search targets are any good) and/or lowering `--lr`, before
relaunching for the actual overnight/lab-scale run.

## 17. Everything not yet done / still open

- it=25 gate result not yet in — the immediate next thing to check.
- No decision yet on whether to stop `az_v3_run1`, adjust hyperparameters,
  and relaunch, or let it continue as-is.
- The v3-vs-v4 ladder discrepancy is still unexplained — worth a second
  ladder read of v4 at some point rather than concluding the bench-out fix
  itself was bad, given the documented history of large ladder variance on
  identical code.
- No SL dataset/checkpoint exists for v4 (only v3) if the target ever
  reverts.
- Colab run is live in parallel (`workers=1`) but not being actively
  monitored in this report's timeframe — worth checking its own
  `gate_vs_engine` trend independently before assuming it mirrors the home
  run.
- Physical GPU lab visit (2026-07-13) hasn't happened yet — `gpu_lab/`
  is staged and ready, core-count check is the first action item there.
- Kaggle competition deadline: 2026-08-14.
