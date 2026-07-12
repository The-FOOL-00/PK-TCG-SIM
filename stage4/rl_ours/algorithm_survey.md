# RL algorithm survey — list-0 engine, Stage 4 Branch B continuation

Status: SURVEY ONLY. No implementation until algorithm choice, reuse-vs-rebuild,
and full user sign-off. Written 2026-07-12 against:
- our state: BC-v2 (list-0, two-headed, 27.8k params) + brake N=10 not-ahead
  = **39.0% [33.7, 44.6] vs v2.2.0** (G7a FAIL, kill criterion honored);
- teammate state: `stage4/rl_design/SANJAY_SESSION_REPORT.md` — AZ pipeline
  (PUCT-MCTS + ISMCTS + SL warm-start + gatekeeping) infrastructure validated,
  training run `az_v3_run1` regressing 34–35% → 5% vs its engine target over
  20 iterations, never promoting past its own SL warm-start.

---

## 1. Problem specification

**State.** cabt (pin 1.30.1) Observation: full public board (both actives,
benches, energies, tools, discards, stadium), own hand contents, counts only
for hidden zones (`handCount`, `deckCount`), prize arrays as *cards remaining*
(contents hidden — own prizes are 6 unknown cards from our own deck). Own deck
composition known minus drawn/prized; order unknown. Opponent deck composition
inferable from archetype, never observed. Our shipped encoder `encode_state`
is 170-dim (hand-count block via deck-identity tables, board summary,
deckCount/60, prizes). Imperfect information is real but shallow relative to
poker: most game state is public; hidden zones are draws from
known-composition multisets.

**Action space.** Two selection types. MAIN: variable option list, ≤41
encodable option types (PLAY/ATTACH/EVOLVE/ABILITY/RETREAT/ATTACK/END),
single pick. ST_CARD: card-target sub-selections, 73-dim card vocabulary,
possibly multi-pick (served as iterative argmax mirroring a Plackett-Luce
decomposition); sub-decision chains (e.g. Poffin → 2 fetch targets) mean one
MAIN action spawns dependent ST_CARD decisions. All picks route through
`resolve_selection()` + C1 asserts; illegal/timeout ⇒ INVALID ⇒ loss.
From the 242-game list-0 harvest: ~41 MAIN + ~28 ST_CARD decisions per game
per seat ⇒ **~70 sequential decisions per game**.

**Reward.** Sparse terminal win/loss (prizes / opponent deckout / no-active).
Game end reasons in our own G7a: prizes 65%, deckout 25%, no-active 9% — the
deckout channel is live strategy at the top of the ladder (20% of top-10 wins,
Phase 2), not an edge case.

**Transition.** Perfect, cheap, deterministic-given-seed local simulator
(cg engine DLL, in-process). Fully resettable and tree-searchable at training
time. This is the single most important asymmetry in the whole survey: we do
NOT need to learn a model, and we CAN generate unlimited on-policy games —
bounded only by CPU.

**Inference constraint (ship).** Kaggle ladder: Linux x86-64, Python 3.11.13,
numpy-only, no torch. Our locked speed class: ~1ms p50 / 3ms p99, hard STOP
above 10ms p99. Ladder time budget (~600s/game) would physically allow
seconds-per-move search, but the project already ran that experiment —
runtime-search v2.0.0 shipped at μ614 and was displaced by fast policies; the
1ms fast-policy class is a standing decision, not open here. **The shipped
artifact is a raw policy net.** Any algorithm whose strength lives in
test-time search pays a train/ship mismatch tax.

**Training constraint.** Home box (~6 usable cores, verified by our 300-game
gates), user's lab machines (GPU present, **core count unknown until
arrival** — self-play is CPU-bound, teammate verified on Colab: 2 vCPU),
~4 calendar weeks minus ship buffer (§11). Measured game cost with two fast
policies in-process: ~10–15s/game/core (G7a: 300 games, 6 workers, ≈11 min).
MCTS multiplies this by the simulation budget.

**What the algorithm must actually fix.** Two documented, gate-confirmed BC
failure modes: (a) compounding error off the expert state distribution
(static 82–97% decision accuracy coexisting with 39–45% head-to-head), and
(b) win-only data blindness — behaviors absent from winners' trajectories
(deck economy) are unlearnable from our corpus. Both are exactly the failure
modes that **on-policy training with negative signal** repairs, and that more
imitation provably does not (we ran that experiment twice: G6 44.7%, G7a 39.0%).

---

## 2. Algorithm candidates

Evaluation axes per the spec: sample efficiency (games needed), wall-clock
(CPU-seconds per game × games), converged policy quality *as a raw net*,
robustness (plateau/regress/diverge), ship compatibility (1ms numpy).

### 2.1 AlphaZero, vanilla (teammate's current)
Silver et al. 2018 (Science). Search-generated policy/value targets are the
best-quality learning signal per *game* in this list — that is real. Costs:
each game is ~n_sims × n_det net evals + engine steps (his config 100×2:
~10× the cost of a policy-only game); the visit-count policy target is only
as good as the search, which at 100 sims over ≤41 actions with a still-weak
value net and 2 determinizations is noisy; and the trained artifact is a
*search-support* net — the published raw-net-vs-search gap is large (raw
AlphaZero policy in Go ≈ strong amateur vs superhuman with search). Observed
next door: 34→5% regression with the SL prior destroyed (diagnosis §4).
Vanilla AZ under his exact conditions is empirically the one algorithm on
this list we have *watched fail this week*. Fixable (§4), but at equal
compute it is dominated by its Gumbel variant on every axis. **Rank 4.**

### 2.2 Gumbel AlphaZero
Danihelka et al., ICLR 2022. Replaces PUCT + visit-count targets with Gumbel
top-k sampling + sequential halving at the root and *completed Q-values* as
the policy target; provides a policy-improvement guarantee at arbitrarily
small simulation counts (paper shows Go learning intact at n=16, where
vanilla AZ degrades). Directly attacks our two AZ pain points: CPU-bound
self-play (16–32 sims vs 200 net evals per decision ⇒ ~5–8× cheaper games)
and garbage targets at low sims (a plausible contributor to the regression).
Still inherits: determinization-noise in value targets under hidden info,
train/ship mismatch (we ship the raw net, the gate signal that matters must
be measured search-off), and the full MCTS engineering surface on top of the
teammate's loop. The strongest search-based option for us by a clear margin.
**Rank 2.**

### 2.3 Sampled AlphaZero
Hubert et al., ICML 2021. Solves action spaces too large to enumerate at the
root (they demonstrate on continuous control / 19×19 Go variants). Our root
has ≤41 legal options, fully enumerable and maskable; ST_CARD sub-decisions
are ≤73-way. The machinery buys nothing here — our action space is small;
our problem is signal quality and CPU, which Sampled AZ does not address.
**Rank 7.**

### 2.4 MuZero
Schrittwieser et al., Nature 2020. Learns dynamics + reward + value jointly;
its value proposition is *planning without a simulator* (Atari) or where the
simulator is expensive. We have a perfect in-process simulator whose step
cost is far below a learned-model unroll of a 427k-param net, and
deterministic rules (evolution chains, energy costs, prize triggers) that a
learned model would spend capacity re-deriving with errors. Model-learning
here is strictly wasted capacity plus a new failure surface (model drift
poisoning value targets — a known MuZero pathology in low-data regimes).
The one importable idea — Reanalyze (recomputing targets for old buffer
games with the current net) — is an orthogonal buffer trick usable in any
AZ variant. **Rank 8.**

### 2.5 Stochastic MuZero
Antonoglou et al., ICLR 2022. Honest reading: it extends MuZero to
*stochastic transitions* via learned chance codes (2048, backgammon — both
perfect-information stochastic games). It is frequently misread as an
imperfect-information method; it is not — opponent private state (POMDP,
requires belief representations à la ReBeL, Brown et al. 2020) is a
different problem than chance nodes. It would model our shuffles/draws more
principledly than determinization models our hidden hands, while inheriting
all of MuZero's wasted-model cost above, and there is no published
deployment in a hidden-hand card game. Four weeks is not the timeline to be
first. **Rank 9.**

### 2.6 PPO (league self-play, KL-anchored, warm-started)
Schulman et al. 2017. Evaluated seriously, per instruction — and it wins
(§3). Modern form for games like ours is not naked PPO but the recipe:
warm-start from the SL/BC policy, optimize the *raw policy* directly by
self-play against an opponent league (frozen BC, past checkpoints, the
incumbent engine, archetype pool), with a KL(π‖π_BC) anchor to prevent
prior destruction, GAE + a value baseline warm-started from win/loss, and
potential-based shaping (prize differential, deckout proximity) to densify
the ~70-decision credit assignment. Published comparables in *card games
specifically, shipping search-free millisecond policies*:
- **DouZero** (Zha et al., ICML 2021): DouDizhu, huge action space, sparse
  reward — pure sampled-return policy gradient, *no search at train or
  test*, trained days on 48 cores / 4 GPUs, beat all prior (including
  search-based) DouDizhu AIs. The single closest published analogue to our
  compute + ship constraints.
- **AlphaHoldem** (Zhao et al., AAAI 2022): HUNL poker — imperfect info far
  deeper than ours — end-to-end self-play PPO-family (trinal-clip),
  millisecond CPU inference, competitive with search-based agents.
- **Suphx** (Li et al. 2020, Mahjong) and **OpenAI Five** (Berner et al.
  2019): policy-gradient family carrying imperfect info and ~20k-decision
  horizons respectively.
Sample efficiency per game is worse than search-guided targets — that is
PPO's real cost — but games are ~8–10× cheaper (no simulations), and we
warm-start at 39% vs the gate opponent, needing +12–18 points, not
from-scratch competence. Failure mode is plateau-near-anchor (recoverable,
diagnosable), not the observed AZ collapse; two-player-zero-sum PG cycling
is real in theory (why NFSP/leagues exist — Heinrich & Silver 2016,
Vinyals et al. 2019) and is handled by the league mix, and our actual
objective is beating a *fixed* incumbent gate plus a ladder population, not
Nash. Ships natively: the artifact PPO optimizes IS the deliverable — zero
train/ship mismatch, unlike every AZ/MuZero variant. **Rank 1.**

### 2.7 DAgger / iterated imitation
Ross et al. 2011. Fixes exactly compounding error — but requires a
*queryable* expert stronger than the student. Our teachers are unqueryable
ladder replays (Majkel/Yushin); nasuo is documented stale; the only local
queryable expert is the determinized-search teacher (`tools/searcher.py`),
at which point DAgger-with-search-expert ≡ Expert Iteration (Anthony et al.
2017) ≡ the AZ family with extra steps and no value bootstrapping. Capped
by searcher strength (unmeasured vs BC-v2). Useful concept, dominated as an
algorithm. **Rank 5.**

### 2.8 Offline RL: CQL / IQL / BCQ
Kumar et al. 2020; Kostrikov et al. 2021; Fujimoto et al. 2019. The honest
size check kills this: our corpus is 242 winning list-0 games (~17k
decisions both heads), expandable by harvest to perhaps 1–2k games
including *losses* (which would, for the first time, add negative examples
— the corpus's structural upgrade). That is 10²–10³× below the D4RL-scale
datasets these methods are characterized on, and win-only slices reduce
IQL/AWR to advantage-weighted BC. Offline RL also cannot visit our
policy's own failure states (the compounding-error fix requires *our*
states, and we have a simulator that generates them for free — using
offline RL here is choosing the harder problem voluntarily). Worth keeping:
advantage-weighted BC on a wins+losses harvest as a cheap data-shape
experiment inside the imitation fallback, not as the program. **Rank 6.**

### 2.9 Decision Transformer
Chen et al. 2021. Return-conditioned sequence modeling. With binary terminal
reward, return-to-go conditioning degenerates to "condition on win=1" ≈ BC
on winners — which is precisely the thing that has now failed two gates.
Known weakness in stochastic environments (Paster et al., NeurIPS 2022)
applies to shuffle/draw variance. 242 games cannot train a transformer, and
a numpy transformer at 1ms is pointless engineering for a worse BC.
**Rank 10.**

### 2.10 Hybrid: BC + rejection-sampled fine-tune (self-imitation)
Generate self-play games with BC-v2 vs a league, keep winners, fine-tune on
them, iterate. This fixes distribution shift (training states become our
own visitation) but *keeps* the win-only selection bias — it learns from
games where the pathology didn't fire, so deck-economy behavior stays
unlearned; expected gain is real but small. Its true role: it is PPO with
binary advantage and no negative gradient — i.e., a strictly weaker sibling
of rank 1 that shares ~90% of the pipeline. We should run it *as the week-1
pipeline shakeout* for the PPO stack (same rollout workers, same league,
same gates, trivial update rule) and inherit whatever points it finds for
free. **Rank 3** (as staging + fallback, not destination).

### Ranking summary

| rank | algorithm | one-line verdict |
|---|---|---|
| 1 | PPO league, KL-anchored, warm-started | optimizes the exact shipped artifact; cheapest games; no-cliff failure mode; DouZero/AlphaHoldem precedent |
| 2 | Gumbel AlphaZero | best search-based option; the designated pivot if PPO plateaus; fixes AZ's low-sim target quality |
| 3 | BC + rejection-sampled fine-tune | week-1 shakeout of the PPO pipeline; small free gains; fallback |
| 4 | Vanilla AlphaZero (fixed config) | fixable (§4) but dominated by Gumbel at equal compute |
| 5 | DAgger/ExIt (search expert) | collapses into the AZ family; capped by searcher strength |
| 6 | Offline RL (IQL best-of-family) | dataset 100–1000× too small; simulator makes it voluntarily hard mode |
| 7 | Sampled AlphaZero | solves a large-action problem we do not have |
| 8 | MuZero | learns a model we already own perfectly |
| 9 | Stochastic MuZero | models chance, not hidden information; no precedent in-domain |
| 10 | Decision Transformer | binary-return conditioning ≈ the BC that already failed twice |

---

## 3. Recommendation

**PPO league self-play, warm-started from BC-v2, KL-anchored to it, with
potential-based prize/deck shaping. Runner-up and designated pivot: Gumbel
AlphaZero on the teammate's infrastructure.**

Why PPO beats Gumbel AZ *for this problem* (not in general):

1. **Ship-artifact identity.** We ship a raw 1ms numpy policy. PPO's
   training objective is that object's win rate. Every AZ variant trains a
   search-support net and ships its byproduct; the teammate's own gate
   measures vs-engine *at 30 sims* — a number we cannot ship. All published
   AZ-family results quoted in its favor are search-on numbers; the
   raw-net gap is real and unmeasured in his pipeline.
2. **CPU economics under core-count uncertainty.** Games are the budget.
   Policy-only games: ~10–15s/core. His AZ games (100 sims × 2 det):
   ~8–10× that; Gumbel at 32 sims: ~3–5×. If the lab machine is
   CPU-light (his Colab reading: 2 vCPU; GPU-dense labs are routinely
   CPU-light), PPO's games/hour advantage is the difference between a
   converged run and an abandoned one.
3. **Failure-mode asymmetry, observed not theorized.** The AZ collapse
   (34→5%) happened *this week, on this game, on validated infrastructure*.
   PPO-with-anchor's characteristic failure is plateau at the anchor —
   diagnosable at a gate, recoverable by loosening the KL coefficient,
   never worse than the BC we start from. Under a hard deadline, an
   algorithm whose worst case is "no improvement" beats one whose observed
   case is "destroys the warm start."
4. **The learning signal matches the diagnosed disease.** Our two BC
   failures are compounding error and win-only blindness. On-policy PPO
   games are by construction our own state distribution (fixes the first)
   and contain our losses — including the 52 G7a self-deckouts — as
   negative gradient (fixes the second, the thing the brake only splints).
   Search-quality targets are *additional* signal quality on top; the
   diseases themselves don't require search to cure.

**Would the §4 fixes close AZ's gap?** Partially, and honestly: a fixed
config (buffer 10k→200k+, opp_frac ramp 0→0.4, KL anchor, Gumbel targets at
16–32 sims) would most likely restore monotone improvement — the regression
is a config pathology, not an algorithm refutation. What the fixes do NOT
change: games still cost 3–5× more than PPO's, the gate-vs-ship artifact
mismatch remains, and every point of improvement must survive the
raw-policy export. At equal calendar time and unknown cores, fixed-AZ is a
worse expected-value bet; at 32+ cores with PPO plateaued, it becomes the
right bet — hence pivot status with a pre-registered trigger (§9).

---

## 4. Regression diagnosis of `az_v3_run1` (34–35% → 5% over 20 iters)

Ordered by estimated contribution:

1. **Replay buffer 10k samples — the primary suspect.** 40 games/iter ×
   ~140 decisions/game (both seats) ≈ 5–6k samples/iter ⇒ the buffer holds
   <2 iterations of data (hit cap by it≈4, matching the first gate collapse
   at it=5). Canonical AZ buffers hold 10²–10³ iterations (0.5–1M+
   positions). Effect: each update epoch fits the last ~90 games' noisy
   targets with no averaging, and the SL prior is overwritten within a few
   hundred gradient steps. Fix: ≥200k samples, plus mixing 10–20% frozen SL
   data into every batch for the first ~30 iters (decaying), plus an
   explicit KL(π‖π_SL) penalty. Any one of the three would have slowed the
   collapse; all three are standard.
2. **opp_frac=0.4 vs a 65%-winning opponent from iteration 1.** 40% of
   games are near-uniform losses against the engine before the net's own
   search targets mean anything. Value head learns "most states lose" ⇒
   flattened/pessimistic Q ⇒ PUCT exploration degenerates ⇒ policy targets
   worsen ⇒ feedback loop. The it=15 partial recovery (8→15%) then new low
   (5%) is the signature of a net oscillating around a destroyed prior, not
   noise (gate n=60 gives ±12pt CI, but 22/8/15/5 are all ≫3σ below 34).
   Fix: curriculum — opp_frac 0.0–0.1 for the first ~20 iters, ramp to 0.4
   only after gate_vs_engine recovers past the SL baseline.
3. **n_det=2 determinizations.** ISMCTS aggregates over sampled hidden
   states; at 2 samples the root statistics have enormous hidden-info
   variance (Cowling et al. 2012 use 40+ determinizations). With 100 sims
   split over 2 determinized trees, per-tree search is 50 sims over ≤41
   actions — target quality near the prior-destruction floor. Fix: n_det
   8–16 with fewer sims each, or Gumbel targets which stay valid at 16
   sims/tree.
4. **No KL anchor / lr unreported.** The report does not state lr; with any
   typical Adam lr (1e-3–1e-4) and the tiny buffer, prior half-life is
   hours. This is subsumed by fix 1 but should be logged explicitly in any
   relaunch (check: `--lr` in his az.py defaults).
5. **Net size 427k: not a suspect.** Small nets train stably; we ship 28k.
   If anything it bounds the ceiling, not the collapse.
6. **Warm-start quality: not the cause but context.** 82.2% teacher-match
   cloning to 34% vs-teacher head-to-head is our own BC finding reproduced
   independently on a different net/encoder/deck — third instance of
   imitation-accuracy ≠ strength in this project. It means the run needed
   genuine improvement, and got poisoned instead.

**Disposition:** since §3 chose PPO, this diagnosis is *reference* — but
items 1 (buffer/anchor) and 2 (opponent curriculum) transfer directly into
the PPO design (anchor coefficient, league scheduling), and the whole table
becomes the config plan if the Gumbel-AZ pivot triggers.

---

## 5. Reuse-vs-rebuild of teammate's infrastructure (for PPO)

| piece | verdict | detail |
|---|---|---|
| Leakage audit (6/6) | **reuse the methodology, re-run on our stack** | His 3 checks (structural, encoder-invariance, determinizer-invariance) are the right pre-run gate. Our `encode_state` consumes the same cabt obs (hidden info structurally absent) but has never been plant-tested — port `leakage_test.py` to our encoder, ~an hour, mandatory sanity gate in the lab package. |
| His encoder | **replace with ours** | Ours is ship-proven, 170-dim, and BC-v2's weights are tied to it; using his would orphan the warm start and add a torch→numpy port of a second encoder. |
| ISMCTS/determinization | **shelve, don't delete** | Unused by PPO. Required again only on the Gumbel-AZ pivot, where it's already validated — that's precisely why the pivot is cheap. |
| Engine-as-league-opponent (`engine_opp.py`) | **reuse the concept, our implementation** | Our `ab_gate`/`deck_compare` already loads arbitrary `main.py` bundles in-process with per-call attr/deck control — strictly more general (it can field v2.2.0, v1 archetypes, AND his v3 engine as league members). His in-process-safety verification (distinct `cg`/`sdk_cg` packages) carries over as a checklist item if his v3 engine joins our league. |
| SL warm-start pipeline (`clone_datagen.py` + `sl_pretrain.py`) | **not needed at same-size; reuse pattern if we widen** | The torch training net mirrors our 170→80→48 two-headed architecture and is initialized by *direct weight copy* from `bc_weights_list0_b.npz` — the warm start is exact and free. Only if we widen the net (§7) do we re-distill BC-v2 into it, and then his datagen-at-scale pattern (584k decisions, 0 errors) is the template. |
| Gatekeeping (`_gate_match`) | **reuse the mechanism, change the measurement** | Promotion-gate + frozen-best is right and transfers. Two mandatory changes: gates run the RAW policy (search-off — we ship raw), and the reference is the v2.2.0 bundle via our ab_gate protocol, not his engine. |
| Worker safety (liveness/respawn) | **reuse** | His respawn-on-dead-worker logic is proven over a 20+ iter run including a caught MemoryError. Multi-day unattended lab runs need exactly this; our ProcessPoolExecutor harness has no equivalent. Adopt his supervisor loop, swap the game function to PPO rollouts. |
| torch→numpy export | **reuse with adapter** | His export path exists; ours must land in the `bc_weights_*.npz` format `main.py` already loads. Small adapter, write once, verify with a bit-exactness test (torch forward vs numpy forward on 1k states). |
| Colab/gpu_lab packaging pattern | **reuse the pattern** | Drive-synced checkpoints, sanity-gates-before-long-runs, core-count-first checklist — all directly copied into §8. |

Net: his session's *engineering* survives almost entirely; his *algorithm
loop* (az.py MCTS core) is the one piece PPO replaces. No week of his work
is wasted by this choice, and the Gumbel-AZ pivot would reactivate the
shelved pieces rather than rebuild.

---

## 6. Dataset plan

**Warm start: none needed.** Direct weight copy `bc_weights_list0_b.npz` →
torch mirror. The 242-game harvest already lives inside those weights.

**Training data: pure on-policy self-play** (the algorithm's whole point).
League composition at launch: frozen BC-v2 (anchor twin), v2.2.0 bundle,
v1-piloted archetype pool (Lucario aggro = C1 axis, Crustle + the
strengthened stall pilot = C2 axis when built), past checkpoints (uniform
over last K), self-mirror. Ratios scheduled per §4 lesson: heavy
self/anchor early, incumbent share ramped in.

**The real harvest's remaining jobs:** (a) held-out static accuracy as a
drift/forgetting monitor (not a promotion signal — we know it doesn't
predict strength); (b) optional 5–10% replay-mixing term early, same
anti-forgetting role as the KL anchor; (c) if the imitation fallback ever
reactivates, harvest *losses* this time.

**Generated-at-scale dataset (his 584k-style): only on the widen-net
branch**, as the re-distillation corpus. Not otherwise.

---

## 7. Shipping path

**Fast-policy head, unchanged serving machinery.** The PPO policy is the
same architecture class main.py's BC path already serves (trunk + MAIN head
+ ST_CARD head, iterative argmax at serve). Export torch→npz, load via the
existing `PTCG_BC` path (new tag), full fallback chain and C1 asserts
untouched. Sampling at train, argmax at ship.

**Latency.** Current 27.8k-param net measures in the ~1ms p50 class on our
box including encoding. If we widen for RL headroom (170→256→128 two-head,
~90k params ≈ 90k MACs), the matmul delta is microseconds in numpy —
encoding cost dominates and is unchanged. Expected: p50 ~1ms, p99 well
under the 3ms class, order-of-magnitude margin to the 10ms STOP. Measured
(not estimated) at the ship battery as always. The brake remains available
as an inference flag; whether RL obsoletes it is an ablation at the ship
gate (expectation: RL with deckout losses in-gradient should learn what the
brake hardcodes).

**Net width decision** (needs sign-off with everything else): stay at 27.8k
(zero-risk warm start, possibly capacity-limited for RL) vs widen to ~90k
(re-distill first — one extra pipeline stage, teammate-validated pattern).
Recommendation: start 27.8k for the week-1 shakeout, widen only if gates
plateau with healthy KL (the capacity signature).

---

## 8. Lab-portable package — `stage4/rl_ours/lab_package/` design

Self-contained, zero-network-assumption folder (pattern: his `gpu_lab/`):

```
lab_package/
  README_FIRST.md          # the arrival checklist below
  engine/                  # cg DLL + card data (Linux .so + Windows .dll)
  agent/                   # main.py snapshot, deck csvs, bc_weights_list0_b.npz
  trainer/                 # ppo loop, torch net mirror, league, export
  gates/                   # ab_gate-derived raw-policy gate + leakage_test port
  vendored/                # torch CPU/CUDA wheels for the pinned python, numpy
  checkpoints/             # synced out; npz export every gate
  scripts/                 # launch.sh, resume.sh, benchmark_games.py, smoke_20.py
```

**Pre-run sanity gates (mandatory, in order):** (1) `leakage_test` port on
our encoder — 3/3 or stop; (2) `smoke_20.py` — 20 league games, 0 crashes /
0 illegal / 0 timeouts or stop; (3) `benchmark_games.py` — 100 games,
records games/hour/core, sets `--workers` and games-per-iter; (4) torch↔numpy
forward bit-match on 1k states or stop.

**First action on arrival (his Colab lesson, verbatim policy):** check
`nproc` BEFORE anything else. GPU-dense labs are often CPU-light and
self-play is CPU-bound; the GPU only accelerates the update step, which for
a ≤90k net is negligible. If cores ≤4, the plan degrades to
home-box-plus-lab in parallel, not lab-replaces-home.

**Expected throughput** at the measured 10–15s/game/core (policy-only games;
benchmark on arrival supersedes these):

| cores | games/hour | games/day |
|---|---|---|
| 4 | ~1,100 | ~26k |
| 8 | ~2,200 | ~53k |
| 16 | ~4,400 | ~106k |
| 32 | ~8,800 | ~211k |

DouZero-scale reference: days × 48 cores from scratch; we warm-start at 39%
vs the gate target and need +12–18 points, so 100k–500k games is the
working estimate — 2–10 days at 8 cores, 1–3 at 32.

**Checkpoint sync:** checkpoints + gate logs written to a single
`checkpoints/` dir; user carries it back (USB/drive) or syncs if the lab
has network; every gate writes both `latest.pt` and the npz export so ANY
carried-home snapshot is immediately gateable on the home box with the
standard 300-game battery. Resume is `resume.sh` (reads latest.pt), proven
pattern from his Colab flow.

---

## 9. Gate structure and kill criteria (pre-registered)

**Training-time (cheap, raw policy always, seats alternated):**
- `gate_vs_v220`: 200 games vs the v2.2.0 bundle every ~25k games
  (≈ every lab-day at 8 cores). THE progress signal. BC baseline: 39.0%.
- `gate_vs_anchor`: 200 games vs frozen BC-v2 — measures genuine
  improvement vs prior-destruction, the axis his run lacked until too late.
- Monitors (not gates): held-out static accuracy, mean KL from anchor,
  self-deckout rate in league games vs the stall-axis opponent, game-length
  distribution.

**Kill criteria (the his-regression-shall-not-repeat-silently clauses):**
- K1 (collapse): `gate_vs_v220` < 29% (BC−10) on two consecutive gates →
  HALT run, revert to last passing checkpoint, diagnose anchor/lr before
  any relaunch. This fires within ~2 lab-days of onset, not 20 iterations.
- K2 (plateau): no gate ≥ 44% (BC+5) within the first 150k games, or no
  gate ≥ 48% within 300k games → stop PPO; decide pivot (Gumbel-AZ with §4
  config if cores ≥16 and ≥10 days remain; otherwise hold v2.2.0 / data-
  shape fallback).
- K3 (anchor-strangulation check, the false-plateau guard): if K2 fires
  with mean KL pinned at the constraint, one (1) pre-registered retry at
  0.5× KL coefficient is allowed before K2 is final. No other iteration.

**Ship battery (unchanged methodology, STOP for user sign-off):**
G8a: 300 games Wilson vs v2.2.0, PASS = CI-low >50%. G8b: strengthened
actively-deckout-seeking stall gate (pilot behavior stats reported before
interpretation, self-deckout rate primary). G8c: ablations — RL-vs-BC-v2
same-deck (isolates the RL delta), brake on/off. Speed: p50/p99 ≤ class.
Bundle pre-flight per standing rules. **No Kaggle submission by me, ever.**

---

## 10. Honest expected μ range

Anchors: v2.2.0 settled μ≈682–697. Top-10 engine pilots (Majkel/Yushin,
same deck we'd field) sit at ladder top. BC-v2+brake is 39% vs v2.2.0 ⇒
sub-incumbent if shipped; RL must cross ~55–60% head-to-head to clear the
Wilson gate.

- **Low (P≈30–40%): μ ~682–700.** K2 fires or ship battery fails ⇒ we hold
  v2.2.0 (possibly re-frozen) — the floor is our current ladder position,
  because the gate structure makes shipping a worse agent nearly impossible.
- **Central (P≈40–50%): μ ~700–730.** PPO clears the gate at 55–65% vs
  v2.2.0. Head-to-head vs one Garchomp incumbent doesn't transfer 1:1 to a
  mixed pool, but the deck itself is pool-validated at rank 1/3 — piloting
  it merely *adequately* should convert some of the deck's structural edge.
- **High (P≈15–25%): μ ~730–760.** RL materially closes the pilot gap on a
  deck whose human pilots hold #1/#3; requires cores ≥16, a clean 2+ week
  run, and the deckout-economy fix emerging in-gradient (watch the
  self-deckout monitor).

Drivers, high end vs low end, in order: **lab core count** (throughput is
the whole budget), **anchor/league stability** (the K1/K2 axis),
**matchup-vs-pool transfer** (G7a measured one matchup; the ladder is a
population). Published comparables justify the *shape* of the claim, not
precision: DouZero and AlphaHoldem show search-free PG reaching
top-of-field play in card games at roughly our compute class; nothing
published maps algorithm → Kaggle μ, so these ranges are project-anchored
estimates, not citations. No top-8/top-1 claim is made.

---

## 11. Deadline verification

Teammate's report states **2026-08-14**; our project memory says 08-16.
Per instruction, ALL planning below builds to the earlier date until the
user confirms from the competition page. Working backwards from Aug 14
minus 24–48h ladder convergence:

- **Aug 12 (hard internal freeze):** final bundle submitted-by-user, ladder
  converging. Nothing trains after Aug 10.
- **Aug 8–10:** ship battery (G8a/b/c + speed + pre-flight), user sign-off
  window, buffer for one battery re-run.
- **Jul 26 – Aug 8:** main lab training window (~2 weeks), gates every
  lab-day, K1/K2 live.
- **Jul 20–26:** week-1 shakeout — pipeline build, sanity gates, rejection-
  sampling baseline run (rank-3 doubles as integration test), first PPO
  iterations on the home box.
- **Jul 13–20:** this sign-off, then port/build (trainer, league, export,
  lab package), local smoke.
- If the user confirms Aug 16, everything shifts +2 days of margin — margin,
  not scope.

~10 days of genuine slack exist in this plan; K2's 300k-game bound is
reachable even at 8 cores inside the window.

---

## 12. Top 3 risks, numeric kill criteria

1. **PPO plateaus at the anchor (most likely failure).** Kill: K2 —
   no gate ≥44% by 150k games / ≥48% by 300k games (one KL-halving retry
   via K3). Response: pivot decision (Gumbel-AZ per §4 config if ≥16 cores
   and ≥10 days remain; else hold v2.2.0).
2. **Prior destruction despite the anchor (his failure, our variant).**
   Kill: K1 — two consecutive gates <29% vs v2.2.0 → halt within ~2
   lab-days, revert, diagnose before relaunch. Silent version is impossible
   by construction: gates are calendar-scheduled and logged with CIs.
3. **Gate-pass without ladder transfer (the μ548 Alakazam ghost).** We can
   pass vs v2.2.0 and still misread the pool — G7a's own lesson inverted.
   Kill: ship battery requires BOTH G8a (Wilson vs v2.2.0) AND G8b
   (self-deckout rate ≤ v2.2.0's own 10/100 baseline vs the strengthened
   stall pilot) AND the archetype sanity sweep; any miss = no ship, and
   post-ship the standing rescope trigger (Aug 10) still protects the
   ladder position with v2.2.0 as the resubmittable floor.

Secondary risks logged, not top-3: lab has ≤4 cores (degrade to
parallel home+lab, timeline holds at reduced K2 bound of 150k games);
torch/numpy export mismatch (bit-match sanity gate catches on day 1);
two-headed log-prob bug class (unit-test the Plackett-Luce decomposition
against the serve path before any training).

---

**STOP.** Survey complete. No implementation begins until the user signs
off: (1) algorithm = PPO league (pivot: Gumbel-AZ), (2) reuse-vs-rebuild
table §5, (3) net-width start point §7, (4) timeline-to-Aug-12 §11.

---

## Sign-off amendments (user, 2026-07-12) — these override the sections above

All four sign-offs granted with the following modifications, which are the
binding versions:

**Leakage audit (amends §5, §8).** Our own audit on OUR encoder + OUR
determinizer (if/when used) is a hard pre-training gate, not inherited from
the teammate's 6/6 on his stack. Pre-registered: **any leakage-audit fail =
immediate STOP; no training without our own 6/6 pass.**

**K2 pivot ladder (amends §9, §12).** If K2 plateau fires (no gate ≥44% by
150k games / ≥48% by 300k), the first pivot is **capacity growth, not
Gumbel-AZ**: copy the 27.8k weights into a wider net (128k first, then 256k
if needed) with new-column initialization, re-anchor the KL, continue PPO.
Gumbel-AZ pivots only after BOTH capacity levels plateau. Added mid-run
diagnostic to separate the two conditions: if training reward reaches ~90th
percentile of small-net-achievable while ladder gates stay <44%, log as
**capacity-limited** (grow net) — distinct from **plateau** (algorithm
pivot). Distinct diagnoses, distinct fixes.

**nproc fork gate (amends §8, §11).** Core count on arrival is a fork gate
with three pre-registered configs, not a checklist item:
- **≥16 cores — central config.** ~4,400+ games/h (~106k/day at 16c);
  ~40–50 PPO update epochs/day at 4–6k games/iter; target ≥300k total games
  inside the Jul 26–Aug 8 window with full K2 headroom; expected μ range as
  §10 central-to-high (700–730, tail to 760).
- **8–16 cores — reduced config.** ~2,200–4,400 games/h (53–106k/day);
  games-per-iter halved to keep update cadence; K2 bound reachable but
  without re-run slack — one training restart consumes the margin; μ
  expectation trimmed to §10 central (700–720), high tail de-weighted.
- **<8 cores — Colab-scale, explicit go/no-go.** Lab supplements rather
  than replaces the home box (6 cores). **Kill criterion: if combined
  sustained throughput <1,500 games/h (≈36k/day), the 150k-game K2 floor is
  not reachable by Aug 8 → NO-GO on the RL run entirely**; ride v2.2.0
  (BC-v2 at 39.0% is not a shippable alternative) and bank the survey +
  pipeline for the writeup.

**Timeline.** Approved contingent on the user verifying Aug 14 vs Aug 16
from the competition page; Aug 14 assumed for all scoping until then.

Approved as-is: dataset = none (§6), shipping = raw policy head (§7),
gates G8a/b/c unchanged (§9).
