# Master Research History & Provenance Reconstruction

**Project:** Pokemon TCG AI Battle Challenge Simulation  
**Platform:** Kaggle (`cabt` Engine / `kaggle-environments==1.30.1`)  
**Repository Remote:** `https://github.com/The-FOOL-00/PK-TCG-SIM.git`  
**Current Commit:** `86abcef` (`main`)  
**Canonical Final Artifact:** `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`  
**Canonical Artifact SHA256:** `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`

---

## 1. Executive Summary

Throughout the Pokemon TCG AI Battle Challenge, the research team investigated seven major architectural paradigms:
1. **Deterministic Heuristic Priority Ladders** (V1)
2. **1-Ply Analytic Evaluators & Value Networks** (V3-Eval, Rung-A MLP)
3. **Belief-Sampled Determinized Monte-Carlo Tree Search** (V2.0.0, V2.1.0, SHLS)
4. **Supervised Behavior Cloning from Elite Replays** (BC Gen 1, BC-Full Gen 2)
5. **Multi-Agent Deep Reinforcement Learning** (Stage 4 PPO League Capacity Ladder)
6. **Empirical Deck–Pilot Fit & Envelope Closure** (Grimmsnarl, Garchomp, Ogerpon)
7. **Condition-Specific Surgical Overrides** (V2, V2.1, V3, V4, Aggressive-Surgical)

### The Central Scientific Lesson
Offline proxy metrics repeatedly failed to predict competitive strength on the live Kaggle ladder. High offline validation accuracy (value net AUC 0.8445, BC top-1 accuracy 69.4%, search win rates >80% in self-play) collapsed upon ladder deployment due to three fundamental obstacles:
- **Belief Flatness under Hidden Information**: Opponent hand cards and prize layouts are unobserved. Sampling uniform or unconditioned card pools produces flat value landscapes where tree search cannot discriminate between options.
- **Sub-Decision Blindness & Compounding Drift**: In combo and setup archetypes, the true tactical lever lives in the `ST_CARD` sub-decision layer (which Pokemon a fetch retrieves, what a discard gives up). Heuristics or neural policies that answered only MAIN-phase decisions while falling back to default rules drifted off the demonstration manifold within 3–5 turns.
- **Symmetric Mis-Piloting in Mirror Gates**: Local evaluations conducted against self-play mirrors or weak baselines systematically masked shared piloting defects. A deck switch that scored **74.7%** locally crashed by **66 TrueSkill points** on the live ladder because both sides were mis-piloting the deck identically.

The winning architecture emerged not by escalating model complexity, but through **envelope closure**: choosing an archetype whose natural line of play aligns with a fast, deterministic priority engine running at microsecond latency (<0.06 ms), augmented by **five condition-specific surgical overrides** that intercept proven high-Elo failure states without slowing down baseline tempo.

---

## 2. Competition Context & Rules of Engagement

The simulation environment (`cabt`) introduces severe structural constraints:
- **Per-Game Time Bank**: 600 seconds of overage time per player with an immediate per-step action timeout `actTimeout = 0`. Any decision exceeding remaining overage or raising an unhandled exception results in an immediate `INVALID` or `TIMEOUT` forfeiture.
- **Imperfect Information**: Decks (up to 60 cards), hands (up to 10+ cards), and prize pools (6 cards) are hidden zones. The official forward simulator (`cg.api.search_begin`) requires complete determinizations of all hidden cards to advance game states.
- **Evaluation Discipline (`tools/ab_gate.py`)**:
  - Sample size $\ge 300$ games per gate.
  - Strict seat alternation by construction (measured first-seat advantage was 72% in Seat 0 vs 36% in Seat 1 in identical mirror matchups).
  - Wilson 95% Confidence Intervals: an intervention was deemed a `PASS` only if the CI lower bound exceeded 50.0% against the incumbent.

---

## 3. Chronological Research Timeline

### Phase 1: Baseline Heuristic V1 & Initial Live Climb (July 7, 2026)
*Commit Reference: `66ada6c` (`archive/v1-heuristic`)*

- **Hypothesis**: A deterministic, zero-crash priority ladder executing standard TCG tactical fundamentals can establish a competitive floor at microsecond latency.
- **Implementation**: Single-file Python standard library agent in `main.py`:
  $$\text{Lethal KO (100,000)} > \text{Attach Energy (3,000)} > \text{Evolve (2,800)} > \text{Item (2,400)} > \text{Bench (2,300)} > \text{Ability (2,200)} > \text{Chip Attack (~1,100)} > \text{Pass/End (0)}$$
- **Deck Strategy**: 35-Energy mono-Water deck utilizing Abomasnow's *Hammer-lanche* ($100 \times \text{Basic Water Energy in top 6 cards of deck}$; average damage 354).
- **Outcome & Evidence**: 74.33% offline win rate vs random. Live ladder submission 54418735 entered at $\mu = 504.5$, climbing across 120 games to a peak $\mu = 857.1$ ($\sigma = 35.0$) at Game 109, settling at $\mu = 844.6$.
- **Observed Vulnerability**: Over-aggression into high-HP retaliatory tanks accounted for 16.3% of losses.
- **Deck Redesign Experiment (WS1)**: Evaluated 6 deck variants (`deck_v2` through `deck_v2g`). At $n=50$, `deck_v2` read 48%; upon re-running at $n=150$, win rate collapsed to **25% (38W-112L)**. Cutting energy starved Hammer-lanche, while adding Basics provided easy prize targets for opponent ex attackers. **Verdict: Dead end; old deck retained.**

### Phase 2: Search Exploration & Value Net Gating (July 7–8, 2026)
*Commit References: `e39e282` to `571210f`*

- **Hypothesis 1 (Analytic Evaluator, WS2)**: 1-ply analytic option scoring (`evaluate_state`) will improve energy routing.
  - *Result*: 300-game gate vs V1: **54.0% [48.3%, 59.6%] -> FAIL** (CI lower bound $\le 50\%$).
- **Hypothesis 2 (Learned Value Model, Phase 1c)**: A neural value function trained on self-play outcomes will guide tactical selection better than hand-tuned heuristics.
  - *Implementation*: Generated 50,000 self-play games (1,521,362 decision rows) using 170-dim state encoder. Trained MLP ($170 \to 128 \to 64 \to 1$, 30,209 params). Validation AUC reached **0.8445**, logloss 0.4810.
  - *Result*: 300-game gate vs V1: **48.7% [43.1%, 54.3%] -> FAIL**. Greedy 1-ply exploitation of an accurate value function failed to beat co-adapted heuristics.
- **Hypothesis 3 (Determinized Monte-Carlo Teacher, Phase 2a)**: Forward simulation via `cg.api.search_begin` with rollouts will surpass 60% win rate.
  - *Result*: Evaluated flat MC across sample budgets:
    - 2 samples/opt: 48.0% [42.4, 53.6] -> FAIL
    - 16 samples/opt: 56.0% [50.3, 61.5] -> PASS
    - 32 samples/opt: **58.7% [53.0, 64.1] -> PASS**
    - 64 samples/opt: 57.0% [51.3, 62.5] -> PASS (saturated)
  - Curve saturated at ~58.7%, failing the pre-registered 60% bar for distillation.

### Phase 3: Runtime Search Pivot & The Belief Bottleneck (July 9, 2026)
*Commit References: `0b48ac5` to `e8c7e25` (`archive/v2-search-determinized`)*

- **Strategic Pivot (Phase A)**: Instead of distilling search into a small network, bundle the official C++ simulator (`cg/`) and run belief-sampled determinized search directly at inference time.
  - Probe bundle validated on live Kaggle environment (Python 3.11.13, Linux x86-64). Discovered a **20x sandbox overhead** (`SearchBegin` 3.28 ms on Kaggle vs 0.16 ms locally).
- **Time Governor (Phase D)**: Built an adaptive time manager allocating $t = \min(3.0, 0.5 \times \text{overage} / \text{decisions\_left})$. Passed 50-game stress test at 3x ship budget (max own-time 35.6s / 600s, 0 timeouts).
- **The Belief Failure (Gate E1)**:
  - Uniform remainder sampling gave opponents zero energy (basic energy was only 8 of 1,267 pool cards), causing 96–98% rollout value saturation.
  - Added composition priors and type coherence.
  - *Gate E1 (300 games vs V1)*: Honest belief search scored **49.0% [43.4%, 54.6%] -> FAIL**. Exact-knowledge mirror belief scored **58.3% [52.7%, 63.8%] -> PASS**.
  - *Diagnosis (`tools/diagnose_belief.py`)*: In 76% of positions, honest belief produced **zero value separation** between options. The search could not rank moves and reverted to V1. The bottleneck was **belief quality, not search compute**.
- **Fair Cross-Deck Gating (Step 1)**:
  - Re-gated against real top-ladder opponents (Cynthia's Garchomp ex, Dudunsparce/Alakazam, Mega Kangaskhan ex).
  - Honest belief equaled or beat mirror belief on all cross-deck opponents (+2.7, +2.0, +3.0 pt), proving the E1 mirror advantage was a gate artifact.
  - Oracle ceiling (handing the true opponent decklist to the search) swung Alakazam win rate from 37.5% to **51.3% (+13.8 pt)**. But even oracle search could only reach parity against Alakazam due to our 35-Energy deck's structural limitations.

### Phase 4: Deck Offensive & The Falsified Gate (July 9–10, 2026)
*Commit References: `8ce7622` to `2807e5d`*

- **The Action**: Swapped deck to the winning Dudunsparce/Alakazam list (`metaB_alakazam.csv`, 3 energy, draw engine).
- **The Gate**: Local feasibility test (our search agent on Alakazam vs our search agent on 35-Energy deck): **74.7% [69.5%, 79.3%] PASS**. Shipped as `v2.1.0-alakazam`.
- **The Falsification**: On the live ladder, `v2.1.0` scored **$\mu = 548$ over 6 games**, dropping 66 points below the old deck's $\mu = 614$.
- **Replay Forensics (`tools/analyze_top_replays.py`)**:
  - Majkel1337 (rank 1, $\mu = 1260$) played a deck **byte-identical** to our `metaB_alakazam.csv` (19/19 card IDs, 60/60 copies).
  - The entire gap was piloting: Majkel attacked by turn 4.1 and ground out 44-turn denial games; our search attacked on turn 11.2 and never attacked in 30% of games.
  - **Mechanistic Root Cause**: Tree search operated only on MAIN single-selects; combo decks win in the trainer sub-decision layer (Rare Candy, Buddy-Buddy Poffin, Night Stretcher) which the search skipped.
  - **Methodological Law**: A gate whose opponent is oneself cannot detect a shared piloting weakness.

### Phase 5: Behavior Cloning Breakthrough (July 10–11, 2026)
*Commit References: `bb2517c` to `148a58c` (`archive/v3-behavior-cloning`)*

- **Stage 3A**: Mined 812 top-10 replays (29,429 MAIN-single targets). Shifted observation-action pairing by +1 step, achieving 99.7% clean index recovery.
- **Stage 3B Gen 1 (MAIN-only BC)**: Trained on Garchomp replays. Offline top-1 accuracy reached **69.4%** (floor 20.8%).
  - *Gate G6a (vs v2.0.0)*: **31.0% [26.0%, 36.4%] -> FAIL**.
  - *Gate G6b (vs search+Garchomp, same deck)*: **42.7% [37.2%, 48.3%] -> FAIL**.
  - *Causes*: Sub-decision blindness (fetch targets answered by naive v1) and compounding off-distribution drift ($0.69^5 \approx 16\%$ probability of following a 5-step sequence).
- **Tooling Shadow-Bug Discovery**: Diagnostic tools `analyze_garchomp_losses.py` and `diagnose_alakazam_piloting.py` were discovered to prepend `sample_submission/` to `sys.path`, accidentally importing the 38-line random sample agent. All historical diagnostic signatures were invalidated and re-measured.
- **Stage 3B Option A (BC-Full Breakthrough)**:
  - Built a 73-dim `ST_CARD` option encoder and Plackett-Luce multi-select decomposition.
  - Trained a two-headed network ($170 \to 80 \to 48$ trunk, 27.9k params).
  - Validation: MAIN head 68.9% (floor 21.4%), ST_CARD head 76.1% (floor 51.6%). Poffin bench fetches reached 100% accuracy (vs V1's 36%).
  - *Gate G6a-full (vs v2.0.0)*: **60.7% [55.0%, 66.0%] -> PASS** (first incumbent beat).
  - *Gate G6c-full (vs BC-prior)*: **77.0% [71.9%, 81.4%] -> PASS** (causal proof of sub-decision importance).
  - *Gate G6b-full (vs search+Garchomp)*: **69.7% [64.2%, 74.6%] -> PASS**.
  - Shipped as `v2.2.0`, reaching live ladder peak **$\mu = 697$** (settled 682.5).
- **The Imitation Pathology**: Against stall opponents, BC suffered 41–52 self-deckouts per 100 games. Because winning demonstration replays end by turn 12–15, thin-deck endgame states were absent from the training manifold. An ablatable draw-brake ($N=10$ not-ahead) failed Gate G7a at **39.0% [33.7%, 44.6%] -> FAIL**.

### Phase 6: Stage 4 Reinforcement Learning & Capacity Ladder (July 11–13, 2026)
*Commit References: `3cd7370` to `ce30384` (`archive/stage4-ppo-league`)*

- **Architecture**: Distributed PPO trainer with league self-play, KL-penalty anchoring to BC-v2, and Generalized Advantage Estimation (GAE).
- **Tier-1 Verification Gates**: Bit-match audit passed with 0 argmax flips ($2 \times 10^{-6}$ error), 6/6 leakage audit passed.
- **Run 1 (27.8k Narrow Policy)**: Trained across 83,520 games (347 iterations). Win rate vs v2.2.0 remained dead flat at **~27.1%** across 309 converged iterations; critic value loss plateaued at 0.033; KL anchor leveled at 0.018. Formal K1 gates (ckpt044/059) scored 31.5% and 34.5% (flat vs BC-v2 start of 33.5%). Diagnosed as **capacity-limited**.
- **Run 2 (128k Wide Net2WiderNet)**: Trunk expanded to $170 \to 320 \to 160 \to 48$, 134,274 params. Function-preserving identity insertion verified (0 flips / 2,400 states). Throughput reached 13.6k games/hour. Win rate remained flat at ~26%.
- **Run 3 (256k Contingency)**: $512 \to 256$ trunk (260,418 params) prepped; Gumbel AlphaZero scoped.
- **Conclusion**: PPO without dense intermediate rewards could not learn multi-turn setup sequencing without destabilizing tactical competence. Further RL exploration halted per protocol.

### Phase 7: Envelope Closure & Deck–Pilot Fit (July 14–22, 2026)
*Documentation: `report/WRITEUP_FULL.md`, `stage4/rl_ours/FINAL_PATH_JUL21.md`*

- **The Discovery**: Running the same generic V1 agent across different decks revealed massive prize velocity differences:
  $$\text{Closure} = \frac{\text{Agent Prize Velocity}}{\text{Top-10 Archetype Envelope Velocity}}$$
- **Canonical Envelope Closure Sweep (100 games each)**:
  - **Teal Mask Ogerpon ex**: Velocity 0.4726, Envelope 0.5845 $\to$ **80.9% Closure**
  - **Marnie's Grimmsnarl ex (+ Rare Candy)**: Velocity 0.4574, Envelope 0.5725 $\to$ **79.9% Closure**
  - **Cynthia's Garchomp ex**: Velocity 0.2628, Envelope 0.4950 $\to$ **53.1% Closure**
  - **Team Rocket's Mewtwo ex / Spidops**: Velocity 0.3303, Envelope 0.6754 $\to$ **48.9% Closure**
  - **Dragapult ex**: Velocity 0.2324, Envelope 0.5021 $\to$ **46.3% Closure**
  - **Mega Kangaskhan ex / Raging Bolt**: Velocity 0.3025, Envelope 0.6729 $\to$ **45.0% Closure**
  - **Fezandipiti ex / Dudunsparce**: Velocity 0.2061, Envelope 0.5084 $\to$ **40.5% Closure**
- **The 2x2 Factorial**:
  - Deck effect (Garchomp to Grimmsnarl): **+0.1946 velocity**
  - Search effect: **-0.0198 to -0.0286 velocity**
  - *The deck effect was 10x the search effect and of opposite sign.*
- **The Decisive Control**: Running our agent + shipped rules on a top player's own deck reduced its velocity from 0.2510 to 0.2207 (live pilot achieved 0.4718). A top deck is not transferable without execution built specifically for it.

### Phase 8: Project Mew, Ogerpon E19, & 243-Deck Global Search (August 2026)
*Documentation: `project_mew_v4_research/reports/FINAL_PROJECT_MEW_REPORT.md`*

- **Motivation**: Capitalizing on Ogerpon ex's 80.9% envelope closure (Basic Pokemon, immediate energy acceleration via *Teal Dance*, scaling attack *Myriad Leaf Shower*).
- **Hypergeometric Deck Optimization (E19)**:
  - 4x Teal Mask Ogerpon ex, 19 Basic Grass Energy, 2 Grow Grass Energy, 35 Trainers.
  - $P(\ge 1 \text{ Energy in Opening 7}) = 96.02\%$
  - $P(\ge 2 \text{ Energy in Opening 7}) = 78.28\%$
  - Bug Catching Set ($N=52, K=23, n=7$): $P(\ge 2 \text{ Hits}) = 90.67\%$
  - Mulligan rate: $60.05\%$ (inherent to 4 Basics).
- **Global Anti-E19 Hybrid Search (243 Decks, 20,120 Games)**:
  - Evaluated 10 counter-mechanisms (Fire weakness, Safeguard immunity, Energy denial, HP tanks, etc.).
  - Top hybrid (`HYB_F6_OgerponSafeguard_M2_1159` - Ogerpon + 2 Mimikyu + Hero's Cape) scored only **49.0% [39.4%, 58.7%]** vs E19.
  - Splitting Grass/Fire energy destroyed Bug Catching Set consistency. E19 statistically dominated all 243 evaluated hybrid candidates ($p < 0.001$).

### Phase 9: Tactical Forensics & Surgical Override Evolution (August 15–16, 2026)
*Documentation: `PROJECT_MEW_EVIDENCE_LEDGER.md`, `aggressive_branch_registry.json`*

The Project Mew tactical engine evolved through disciplined empirical iteration:
1. **V1 Strong Tactical (`bb1f9464...`)**: Pure greedy KO > chip > energy accel. 120 live games, peak $\mu = 857.1$, settled $\mu = 844.6$. Conflated in informal notes as "~995 peak".
2. **V2 Broad Tactical Brake (`c20d52b0...`)**: Vetoed non-lethal attacks into lethal retaliation. Over-aggression losses dropped from 8 to 0, but introduced 4 `EXCESSIVE_BRAKE_DELAY` losses (6.67% rate).
3. **V2.1 Outcome-Conditional Brake (`5511c1a0...`)**: Triggered strictly against $>160$ HP tanks when a 1-shot bench KO existed via Boss's Orders. 300g paired test: **238/300 (79.33% WR vs V1 74.33%, $p = 0.0074$)**, 0 brake-delay regressions.
4. **SHLS Selective Search (`13e43f58...`)**: 2-ply lookahead on critical turns. Offline 81.67% WR, but contradicted on live ladder due to distribution shift.
5. **V3 High-Elo Stabilization (`3f46daf3...`)**: Minimal surgical overrides (Pattern 1 Anti-Tank Gust + Pattern 2 Active Energy Spillover). Reached authenticated project peak **$\mu = 939.5$** on live ladder at Game 39 (84.6% early WR), before collapsing to 795.0. Forensics on 23 losses revealed 13 losses concentrated in `UNNECESSARY_BENCH_EXPANSION_IN_2PRIZE_ENDGAME`.
6. **V4 Endgame Bench Restraint (`a7ee6199...`)**: Added Pattern 3 (Endgame Bench Restraint). Paired benchmark: **260/300 (86.67% WR vs V3 83.00%, $p = 0.0034$)**, 13/13 reversal of V3 live failure replays. However, production archive suffered a P0 bug: `main.py` did not import `v4_policy`, causing the live agent to execute unpatched V1 heuristics.
7. **V4 Corrected Candidate (`44456613...`)**: Fixed import hook, full execution of Patterns 1, 2, 3 verified.
8. **August Meta Shift & V5 Exploration**: Live ladder shifted to 40.1% Alakazam spread, 17.7% Crustle damage walls, and 1.96% Cornerstone Mask ex (*Cornerstone Stance* takes 0 damage from Pokemon ex, dealing pure Ogerpon ex a 0% auto-loss).

### Phase 10: Final Aggressive-Surgical Candidate & Kaggle Packaging (August 16, 2026)
*Documentation: `kaggle_compatibility_fix_report.json`, `tools/verify_and_build_kaggle_fixed_candidate.py`*

- **The Final Agent**: Fast aggressive tactical priority engine paired with 5 condition-specific surgical overrides:
  1. *Pattern 1 (Anti-Tank Gust)*: Intercepts attacks into lethal retaliating tanks if bench KO exists.
  2. *Pattern 2 (Energy Spillover)*: Routes energy to bench when active has $\ge 3$ energy.
  3. *Pattern 3 (Endgame Bench Restraint)*: Suppresses benching basics when opponent is at $\le 2$ prizes.
  4. *Pattern 4 (Alakazam Energy Cap)*: Caps active energy at 2 vs Alakazam to limit Psychic damage.
  5. *Pattern 5 (Anti-Immunity Gust)*: Gusts around Cornerstone Mask ex and immunity walls.
- **Deck Selection**: Paired with the 60-card **Alakazam Master V5** decklist (`0f8fb632...`), eliminating the 0% Cornerstone auto-loss, piercing Crustle walls (85% WR), and reducing mulligans from 60.05% to 14.20%.
- **Pre-Build Candidate (`0a8ae33e...`)**: Initial final package built.
- **Kaggle Loader Verification & Emergency Fix**:
  - Kaggle Environments' in-memory dynamic module loader (`get_last_callable`) does not set the `__file__` global, causing `NameError: name '__file__' is not defined`.
  - Executed 15-phase emergency fix in `tools/verify_and_build_kaggle_fixed_candidate.py`: stripped `__file__`, verified byte-for-byte policy identity (`b40c01a6...`) and deck identity (`0f8fb632...`), ran 50-process multiprocessing stress test, and executed 10,000 continuous decisions without errors.
  - Built canonical final package: `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` (SHA256: `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`).

---

## 4. Master Research Findings Matrix

| Research Question | Empirical Experiment | Measured Outcome | Core Evidence Source | Scientific Implication | Status |
|---|---|---|---|---|---|
| **Can 1-ply analytic evaluation outperform heuristic tiers?** | WS2 hill-climbed evaluator behind `PTCG_V3_EVAL` vs V1 (300g) | 54.0% [48.3%, 59.6%] | `runs/gate_v3_vs_v1_300g.json` | 1-ply evaluation leaves little headroom in mirror play. | **Rejected** |
| **Does an offline-accurate value net improve decisions?** | Phase 1c MLP value net (AUC 0.8445) vs V1 (300g) | 48.7% [43.1%, 54.3%] | `runs/gate_lv_vs_v1_300g.json` | Greedy 1-ply value use disrupts co-adapted heuristics. | **Rejected** |
| **Does determinized MCTS overcome the 1-ply ceiling?** | Phase 2a flat MC teacher on `cg` API (300g) | Plateaus at 58.7% [53.0%, 64.1%] | `EXPERIMENT_LOG.md` L194 | Algorithmic ceiling: rollouts assume heuristic play forever. | **Partially Supported** |
| **Does belief sampling preserve search strength under fog of war?** | Phase E1 honest belief search vs V1 (300g) | 49.0% [43.4%, 54.6%] | `runs/gate_e1_comp.json` | 76% zero-gap positions; belief quality, not compute, binds search. | **Rejected** |
| **Does switching to a top ladder deck guarantee improvement?** | v2.1.0 Alakazam search ship (74.7% local gate) | Ladder $\mu = 548$ (down 66 pt from v2.0.0 $\mu = 614$) | `report/LADDER_INTEL.md` | Search skips combo sub-decisions; local mirror gates mask shared bugs. | **Rejected** |
| **Does Behavior Cloning replicate human expert play?** | Stage 3B Gen 1 MAIN-only BC vs V1 (300g) | 31.0% [26.0%, 36.4%] | `EXPERIMENT_LOG.md` L697 | Sub-decision blindness and compounding off-distribution drift. | **Rejected** |
| **Does extending BC to sub-decisions restore strength?** | Stage 3B Option A two-headed net (MAIN + ST_CARD) | 60.7% [55.0%, 66.0%] vs V1; 77.0% vs Gen 1 | `runs/gate_G6a_full_bcfull_vs_v200.json` | Piloting combo decks lives in the sub-decision layer. | **Supported** |
| **Can PPO self-play transcend the imitation ceiling?** | Stage 4 capacity ladder (27.8k, 128k, 256k PPO, 83.5k games) | Win rate flat at ~27.1% vs v2.2.0 | `stage4/rl_ours/ppo/verdict.py` | Delayed rewards and vast state space cause capacity-limited plateau. | **Rejected** |
| **Does deck selection matter more than policy complexity?** | 2x2 Factorial (Garchomp vs Grimmsnarl, V1 vs Search) | Deck effect: +0.1946; Search effect: -0.0198 to -0.0286 | `report/WRITEUP_FULL.md` §4.3 | Deck-pilot fit is 10x search effect; search is net-negative on both. | **Supported** |
| **Does broad tactical braking prevent over-aggression?** | V2 broad safety brake vs V1 (60g forensic audit) | Over-aggression 0; 6.67% brake delay losses | `runs/v1_v2_forensics/` | Broad brakes solve symptoms but introduce fatal passivity. | **Partially Supported** |
| **Do condition-specific surgical overrides avoid tempo loss?** | V2.1 outcome-conditional brake vs V1 (300g) | 79.33% vs 74.33% ($p = 0.0074$), 0 brake delay | `runs/v21_validation/` | Overrides must condition strictly on confirmed alternative lines. | **Supported** |
| **Does endgame bench restraint eliminate gust liabilities?** | V4 Pattern 3 vs V3 (300g paired test) | 86.67% vs 83.00% ($p = 0.0034$), 13/13 reversals | `project_mew_v4/reports/` | Restraining bench expansion in 2-prize endgame denies gust KOs. | **Supported** |
| **Does global hybrid search defeat E19 energy density?** | 243-deck hybrid search (20,120 games) | E19 dominates all 243 hybrids; best hybrid 49% | `project_mew_v4_research/` | Multi-energy splits destroy tutoring consistency and opening tempo. | **Supported** |
| **Does Aggressive-Surgical defeat diverse high-Elo meta?** | 5 overrides + Alakazam Master V5 vs 600g stress pool | 86.33% WR (vs V4 61.17%, +25.16% WR) | `project_mew_aggressive_surgical/` | Overrides pierce immunity and tank walls while maintaining tempo. | **Supported** |

---

## 5. Master Falsifications & Negative Results

Documenting failed hypotheses is central to preserving scientific integrity:

| Approach | Expected Benefit | Observed Reality | Root Mechanism | What Replaced It |
|---|---|---|---|---|
| **Deck Variants (`deck_v2`–`deck_v2g`)** | Adding Basics prevents bench-out losses | Collapsed from 48% (n=50) to 25% (n=150) | Added Basics diluted Hammer-lanche energy density and fed opponent ex prizes | Retained mono-Water baseline |
| **1-Ply Analytic Evaluator (WS2)** | Dynamic option scoring improves routing | Failed gate at 54.0% [48.3%, 59.6%] | Micro-optimizing 1-ply moves does not alter macro prize race | Learned value modeling |
| **Learned MLP Value Function** | AUC 0.8445 value net guides optimal choices | Failed gate at 48.7% [43.1%, 54.3%] | Greedy 1-ply value queries disrupted co-adapted heuristic ties | Lookahead search |
| **Belief-Sampled Search (E1)** | Tree search finds tactical lines under fog | Scored 49.0% [43.4%, 54.6%] vs V1 | 76% of positions had zero value separation under honest belief | Cross-deck gating & BC |
| **Alakazam Search Ship (v2.1.0)** | Local 74.7% gate promised dominant ladder play | Crashed to $\mu = 548$ on live ladder (-66 pt) | Search skipped combo trainer sub-decisions; both sides mis-piloted locally | Behavior Cloning (BC-Full) |
| **MAIN-only Behavior Cloning** | 69.4% top-1 accuracy replicates expert play | Failed gates at 31.0% and 42.7% | Sub-decision blindness; fetch targets handled by naive V1 | Two-headed BC-Full |
| **Inference Draw Brake (N=10)** | Prevents self-deckout against stall decks | Decisively failed gate at 39.0% [33.7%, 44.6%] | Compounding hesitation; thin-deck states were absent from training manifold | Shift to fast aggro archetypes |
| **PPO Capacity Ladder** | Scaling to 128k/256k overcomes RL plateau | Win rate flat at 27.1% over 83.5k games | Sparse terminal reward; action space too large for unguided exploration | Envelope closure & heuristics |
| **Broad Tactical Safety Brake (V2)** | Vetoing attacks into retaliation saves active | Eliminated over-aggression but caused 6.67% delay losses | Agent passed/retreated harmlessly, losing tempo | Outcome-conditional brake (V2.1) |
| **SHLS Selective Search** | 2-ply lookahead on critical turns fixes blunders | Offline 81.67% WR, but failed live ladder | Lookahead evaluated heuristic scores without modeling opponent hand dynamics | Surgical heuristic overrides |
| **Secondary Attacker Deck Hybrids** | Teching Fire attackers beats Grass counters | 0.0%–6.0% WR vs E19 | Fire attackers diluted Grass energy, disabling Teal Dance acceleration | Pure mono-energy engines |
| **Mined Rule `KE_SUP`** | Replicating expert supporter timing | Dropped win rate by 7.0 pt (25.0% vs 32.0%) | After supporter resolved, agent re-scored and skipped attacking | Strict free-action whitelist |
| **Mined Rule `KE_WELL`** | Routing attaches to Wellspring attacker | Dropped win rate by 3.5 pt (28.5% vs 32.0%) | Diverting energy starved primary attacker; attack rate fell 7.2 pt | Active energy prioritization |

---

## 6. Performance Evolution: Local Benchmarks vs Competition Ladder

> [!IMPORTANT]
> Local development metrics must never be conflated with official Kaggle ladder ratings. Local benchmarks reflect controlled pairwise simulations under specific test pools; Kaggle ratings reflect TrueSkill $\mu$ ($\pm 3\sigma$) on the public asynchronous ladder.

| Agent Version | Evaluation Environment | Sample Size | Win Rate / Score | Opponent / Benchmark | Date | Source Artifact |
|---|---|---|---|---|---|---|
| **V1 Heuristic** | Local Simulation | 300 games | 74.33% WR | Heuristic baseline mirror | 2026-07-07 | `EXPERIMENT_LOG.md` L15 |
| **V1 Heuristic** | Public Kaggle Ladder | 120 live games | Settled $\mu = 844.6$ (Peak $\mu = 857.1$) | Diverse public ladder | 2026-07-07 | `aggressive_peak_reconstruction.json` |
| **V3 Evaluator** | Local A/B Gate | 300 games | 54.00% [48.3%, 59.6%] | V1 Incumbent | 2026-07-07 | `runs/gate_v3_vs_v1_300g.json` |
| **Learned Value Net** | Local A/B Gate | 300 games | 48.67% [43.1%, 54.3%] | V1 Incumbent | 2026-07-07 | `runs/gate_lv_vs_v1_300g.json` |
| **Flat MC Search (32s)** | Local A/B Gate | 300 games | 58.67% [53.0%, 64.1%] | V1 Incumbent | 2026-07-07 | `EXPERIMENT_LOG.md` L194 |
| **Belief Search (Comp)** | Local A/B Gate | 300 games | 49.00% [43.4%, 54.6%] | V1 Incumbent | 2026-07-09 | `runs/gate_e1_comp.json` |
| **Belief Search (Mirror)**| Local A/B Gate | 300 games | 58.33% [52.7%, 63.8%] | V1 Incumbent | 2026-07-09 | `runs/gate_e1_mirror.json` |
| **v2.0.0 Search** | Public Kaggle Ladder | 25 live games | Settled $\mu = 614.0$ | Diverse public ladder | 2026-07-09 | `report/LADDER_INTEL.md` |
| **v2.1.0-Alakazam** | Local Feasibility | 224 games | 74.70% [69.5%, 79.3%] | v2.0.0 (Old Deck) | 2026-07-09 | `EXPERIMENT_LOG.md` L542 |
| **v2.1.0-Alakazam** | Public Kaggle Ladder | 6 live games | Settled $\mu = 548.0$ | Diverse public ladder | 2026-07-09 | `report/LADDER_INTEL.md` |
| **Stage 1 Garchomp** | Local A/B Gate | 300 games | 39.33% [34.0%, 45.0%] | v2.0.0 Incumbent | 2026-07-10 | `EXPERIMENT_LOG.md` L600 |
| **BC Gen 1 (MAIN-only)**| Local A/B Gate | 300 games | 31.00% [26.0%, 36.4%] | v2.0.0 Incumbent | 2026-07-11 | `EXPERIMENT_LOG.md` L697 |
| **BC-Full (Option A)** | Local A/B Gate | 300 games | 60.67% [55.0%, 66.0%] | v2.0.0 Incumbent | 2026-07-11 | `runs/gate_G6a_full_bcfull_vs_v200.json` |
| **BC-Full (Option A)** | Local A/B Gate | 300 games | 77.00% [71.9%, 81.4%] | BC Gen 1 Control | 2026-07-11 | `runs/gate_G6c_full_bcfull_vs_bcprior.json` |
| **BC-Full (Option A)** | Local A/B Gate | 300 games | 69.67% [64.2%, 74.6%] | Search + Garchomp | 2026-07-11 | `runs/gate_G6b_full_bcfull_vs_search.json` |
| **v2.2.0 (BC-Full)** | Public Kaggle Ladder | 57 live games | Settled $\mu = 682.5$ (Peak $\mu = 697.0$) | Diverse public ladder | 2026-07-12 | `report/WRITEUP_FULL.md` L782 |
| **BC-v2 + Draw Brake** | Local A/B Gate | 300 games | 39.00% [33.7%, 44.6%] | v2.2.0 Incumbent | 2026-07-12 | `stage4/runs/gate_G7a_bcv2brake_vs_v220.json` |
| **PPO Run 1 (27.8k)** | Local Capacity Gate | 83,520 games | Flat ~27.1% WR | v2.2.0 Incumbent | 2026-07-13 | `stage4/rl_ours/ppo/verdict.py` |
| **V1.5 Strong Tactical**| Local Benchmark | 300 games | 74.33% WR | Base Tactical Benchmark | 2026-08-15 | `PROJECT_MEW_EVIDENCE_LEDGER.md` L50 |
| **V2.1 Conditional Brake**| Local Paired Test | 300 games | 79.33% WR ($p = 0.0074$) | V1 Baseline | 2026-08-15 | `runs/v21_validation/` |
| **SHLS Selective Search**| Offline Validation | 300 games | 81.67% WR | V1 Baseline | 2026-08-15 | `project_mew_shls/reports/` |
| **V3 High-Elo Stabilize**| Local Paired Test | 300 games | 83.00% WR ($p = 8.7 \times 10^{-7}$) | V1 Baseline | 2026-08-16 | `project_mew_v3/reports/` |
| **V3 High-Elo Stabilize**| Public Kaggle Ladder | 65 live games | Peak $\mu = 939.5$ (Settled 795.0) | Diverse public ladder | 2026-08-16 | `aggressive_peak_reconstruction.json` |
| **V4 Bench Restraint** | Local Paired Test | 300 games | 86.67% WR ($p = 0.0034$) | V3 Baseline | 2026-08-16 | `project_mew_v4/reports/` |
| **Aggressive-Surgical** | Local Paired Test | 300 games | 85.67% WR ($p = 0.0007$) | V4 Control Baseline | 2026-08-16 | `PROJECT_MEW_AGGRESSIVE_SURGICAL_...` |
| **Aggressive-Surgical** | High-Elo Stress Pool | 600 games | 86.33% WR (+25.16% vs V4) | 6 Meta Matchups (100g each)| 2026-08-16 | `PROJECT_MEW_AGGRESSIVE_SURGICAL_...` |
| **Aggressive-Surgical** | Fresh-Seed Replication| 600 games | 84.83% WR (509/600 W) | Paired replication seeds | 2026-08-16 | `PROJECT_MEW_AGGRESSIVE_SURGICAL_...` |

---

## 7. Final Agent Selection: The Decision Path

The selection of `project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` as the final competition deployment was governed by an explicit elimination chain:

1. **Elimination of Tree Search & MCTS**:
   - In 76% of positions under fog of war, belief-sampled search produced identical rollout values, collapsing into tie-break noise.
   - Cross-deck 2x2 factorial proved search had a non-positive effect (-0.02 velocity) while consuming 200–500 ms and introducing governor failure modes.
2. **Elimination of Supervised Behavior Cloning & PPO**:
   - BC models suffered from sub-decision drift and self-deckout in thin-deck states absent from winning human replays.
   - PPO plateaued across 83,520 games at ~27% win rate due to delayed terminal rewards and vast action spaces.
3. **Elimination of Broad Defensive Brakes (V2)**:
   - Broad defensive vetoes reduced over-aggression but introduced a 6.67% `EXCESSIVE_BRAKE_DELAY` failure rate, surrendering tempo.
4. **Elimination of Pure Ogerpon E19 in the Late Meta**:
   - While E19 dominated early local sweeps, the August 2026 meta rotated into 17.7% Crustle walls and 1.96% Cornerstone Mask ex. Because Cornerstone Mask ex takes 0 damage from Pokemon ex, pure Ogerpon ex suffered an unavoidable 0% auto-loss.
5. **Selection of Aggressive-Surgical + Alakazam Master V5**:
   - Combining the fast aggressive core with 5 targeted overrides (Anti-Tank Gust, Energy Spillover, Bench Restraint, Alakazam Cap, Anti-Immunity Gust) kept override frequency to 4.91%, maintaining 95% fast aggressive tempo.
   - Pairing with Alakazam Master V5 eliminated the Cornerstone 0% auto-loss (scoring 88% vs Cornerstone), breached Crustle mitigation (85% WR), and reduced opening mulligans from 60.05% to 14.20%.
   - Achieved **86.33%** win rate on the 600-game High-Elo stress pool, **84.83%** on fresh-seed replication, and passed 50-process concurrency stress testing with sub-millisecond execution.

---

## 8. Methodological Lessons Learned

1. **Measure Deck–Pilot Fit First**: Envelope closure predicts whether a deck is pilotable by an agent before any match is played.
2. **Mirror Gates Mask Shared Weaknesses**: An agent playing against itself cannot expose flaws they both commit. Always gate cross-deck against strong external baselines.
3. **Never Trust an Offline Proxy**: AUC, static top-1 accuracy, and search win rates against self-play failed repeatedly to transfer to ladder strength.
4. **A Free Action Before a Terminal Action is Free**: Sequencing rules (E1/E2) that take costless board-advancing plays before ending a turn with an attack consistently improve tempo.
5. **Rule Composition is Competitive**: Stacking multiple rules that target the same decision slot (e.g. once-per-turn abilities) suppresses secondary rule fire rates by up to 99%. Rules must be evaluated alone and stacked.
6. **A Rule That Did Not Fire Has Not Been Tested**: Every rule must carry an in-flight fire counter to verify engagement in validation.

---

## 9. Reproducibility & Replication Guide

Every major experiment in this archive is cataloged by its reproduction feasibility:

### Fully Reproducible (Code + Data Persist in Workspace)
- **Baseline Heuristic Execution & Validation**: Run `python -c "import main; assert len(main.agent({'select': None})) == 60"`.
- **Master Verification Test**: Run `python tools/run_master_verification.py`.
- **A/B Gating Protocol**: Run `python tools/ab_gate.py --help`.
- **Hypergeometric Deck Probability Audits**: Exact mathematical formulas in `PROJECT_MEW_EVIDENCE_LEDGER.md`.
- **Behavior Cloning Inference**: Neural weights `bc_weights_clean_v21.npz` and `bc_weights_garchomp_full.npz` execute via `training/train_bc_full.py`.
- **PPO Trainer Architecture**: Complete trainer and verification gates located in `stage4/rl_ours/ppo/`.
- **Final Candidate Packaging & Compatibility Verification**: Run `python tools/verify_and_build_kaggle_fixed_candidate.py`.

### Partially Reproducible (Code Exists; External Data Re-Acquisition Required)
- **Top-10 Replay Mining & Harvest**: Harvester scripts `tools/harvest_episodes.py`, `analysis/phase2_meta_shift/harvest_jul21.py`, and `stage4/rl_ours/fetch_mine.py` require valid Kaggle credentials (`~/.kaggle/kaggle.json`). Re-acquisition procedure documented in `docs/DATASETS.md`.
- **Self-Play Training Data Generation**: `tools/gen_selfplay.py` and `tools/gen_distill.py` can regenerate 1.5M rows locally using the bundled simulator.

### Historical Artifacts (Preserved Checksums & Run Reports)
- **Live Ladder Snapshots**: Preserved in `aggressive_peak_reconstruction.json`, `analysis/phase2_meta_shift/`, and `data/live_complete_history/`.
- **Kaggle In-Memory Loader Audit**: Recorded in `kaggle_compatibility_fix_report.json` and `aggressive_surgical_policy_audit.json`.
