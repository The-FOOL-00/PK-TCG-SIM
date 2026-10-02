# Project Research History & Architectural Evolution

Date: 2026-10-02  
Repository: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`

This document chronicles the technical journey, empirical discoveries, architectural rungs, and experimental postmortems across the entire Pokemon TCG AI Battle Challenge.

---

## 1. Executive Summary: The Core Finding

Across the competition, the team investigated six distinct paradigm shifts:
1. Pure Heuristic Priority Ladders (V1)
2. Broad Tactical Braking & Vetoes (V2, V2.1)
3. Analytic Evaluation & 1-Ply Search (V3-Eval, Rung A Value Net)
4. Determinized Monte-Carlo Search (V2.2.0, SHLS)
5. Supervised Behavior Cloning from Top-10 Replays (Stage 3A/3B)
6. Deep Reinforcement Learning via PPO League Self-Play (Stage 4)
7. Condition-Specific Surgical Overrides (V3, V4, Aggressive Surgical)

**The Central Takeaway**: High offline benchmark accuracy (AUC 0.845, BC top-1 69.4%, search win rates >80%) repeatedly failed to transfer to the live ladder due to distribution shifts, compounding errors in sub-decisions, and tempo loss. The simplest architecture—a deterministic heuristic pilot running in <0.01 ms with 5 empirically mined surgical overrides—proved superior to complex neural and search pipelines, achieving the highest authenticated peak rating ($\mu = 939.5$) and zero timeouts.

---

## 2. Chronological Version Evolution

### Phase 1: V1 Strong Tactical Baseline
- **Goal**: Establish a bug-free, zero-crash baseline agent that executes legal moves at microsecond latency.
- **Main Mechanism**: Single-file stdlib Python priority ladder: `Lethal KO (100,000) > Energy Attachment (3,000) > Evolution (2,800) > Item (2,400) > Bench (2,300) > Ability (2,200) > Non-Lethal Chip (~1,100) > Pass/Terminal`.
- **Benchmark / Result**: 74.33% offline baseline WR. Live ladder reached initial peak $\mu = 847.1$ (settled $\mu = 844.6$ over 120 games).
- **Failure or Success**: **Success as a baseline**, but exposed a critical vulnerability: tactical over-aggression (attacking blindly into high-HP retaliatory tanks).
- **What Survived**: The core priority ladder and legal validation harness remain the foundation of every subsequent agent.

---

### Phase 2: V2 & V2.1 Tactical Braking
- **Goal**: Eliminate over-aggression losses by introducing safety vetoes.
- **Main Mechanism**:
  - **V2**: Broad defensive brake that vetoed non-lethal attacks when the active faced lethal counter-attack.
  - **V2.1**: Outcome-conditional brake: triggers strictly against $>160$ HP tanks when a confirmed 1-shot bench target is available via Boss's Orders.
- **Benchmark / Result**:
  - V2 eliminated over-aggression losses but introduced 6.67% `EXCESSIVE_BRAKE_DELAY` losses (passing/retreating harmlessly).
  - V2.1 scored 238/300 (79.33% WR vs V1 74.33%, $p = 0.0074$) with zero brake-delay regressions.
- **Failure or Success**: **Partial Success**. Proved that broad defensive rules harm tempo; only surgical, conditional overrides work.
- **What Survived**: The concept of selective targeting and the condition `opp_hp >= 160 AND has_1shot_bench_target`.

---

### Phase 3: Search & Learned Value Models (Phase B–F)
- **Goal**: Use tree search and deep value functions to outplay heuristic rules.
- **Main Mechanism**:
  - Learned MLP value model (1.52M rows of self-play, 170-dim board state encoder).
  - Belief-sampled determinized Monte-Carlo search implemented on the C++ `cg` simulator engine.
- **Benchmark / Result**:
  - Learned value model achieved AUC 0.845 offline, but head-to-head achieved only 48.7% [43.1, 54.3] (KILL).
  - Search scored 58.7% offline, but on the live ladder settled at $\mu \approx 548$ vs heuristic $\mu \approx 614$ (KILL).
- **Failure or Success**: **FAILURE**. Root-caused to belief distribution error (opponent hand is unobserved; assuming uniform random cards led to catastrophic misplays against ladder humans). Search was also unable to plan multi-turn setup across draw-heavy decks.
- **What Survived**: Fast state encoding routines (`main.encode_state`) and the standardized 300-game A/B comparison protocol (`tools/ab_gate.py`).

---

### Phase 4: Stage 3B Behavior Cloning (BC-Full)
- **Goal**: Imitate top-10 human and bot play harvested from public ladder replays.
- **Main Mechanism**: Two-headed neural network trained on 29.4k top-10 decision targets (JunLee789 Garchomp and Nasuo replays), predicting main-phase actions and sub-decision card selections.
- **Benchmark / Result**: Offline top-1 accuracy 69.4% (floor 20.8%), sub-decision accuracy 76.1%. In head-to-head vs heuristic incumbent, achieved **60.7% [55.0, 66.0]**, shipping to ladder $\mu \approx 697$.
- **Failure or Success**: **QUALIFIED SUCCESS**. Strongest neural model, but suffered from compounding errors when falling off the human demonstration manifold.
- **What Survived**: Trained BC weights (`bc_weights_clean_v21.npz`) and distillation training scripts in `training/`.

---

### Phase 5: Stage 4 PPO League / Capacity Ladder
- **Goal**: Surpass human demonstration ceiling via self-play reinforcement learning.
- **Main Mechanism**: Parallelized PPO trainer (`stage4/rl_ours/`) featuring league self-play, KL-penalty anchoring to BC-v2, Generalized Advantage Estimation (GAE), and capacity scaling (128k to 256k).
- **Benchmark / Result**: Evaluated against formal K1 gate (ckpt044/059 vs incumbent): achieved 31.5% and 34.5% WR (both flat vs BC-v2 start of 33.5%); zero improvement across 14,000 games.
- **Failure or Success**: **KILLED PER PROTOCOL**. The action space was too large and reward signal too delayed for PPO to learn tactical setup without destabilizing the policy.
- **What Survived**: PPO trainer implementation, fork-deadlock fixes, preflight gates, and `stage4/LAB_RUNBOOK.md`.

---

### Phase 6: Project Mew & E19 Energy Optimization
- **Goal**: Optimize deck structure and tactical sequencing for Teal Mask Ogerpon ex.
- **Main Mechanism**:
  - Hypergeometric analysis of energy opening probabilities (E19 configuration).
  - 243-deck hybrid search evaluating over 20,120 simulated games across 7 archetype pools.
- **Benchmark / Result**: E19 achieved 96.0% Turn-1 energy probability and 78.3% Turn-2 double attachment. Dominated all 243 hybrid variations ($p < 0.001$).
- **Failure or Success**: **MASSIVE SUCCESS**. Proved that deck velocity and prize pacing dominate tactical nuances.
- **What Survived**: Canonical deck configuration (`deck.csv`) and hybrid search tooling (`project_mew_v4_research/`).

---

### Phase 7: Surgical Overrides (V3, V4 & Aggressive Surgical)
- **Goal**: Combine maximum aggressive tempo with pinpoint tactical patches for specific high-Elo loss patterns.
- **Main Mechanism**: Fast aggressive heuristic core augmented with 5 surgical overrides:
  1. **Pattern 1 (Anti-Tank Gust)**: Vetoes suicide into retaliatory tanks if a bench KO exists.
  2. **Pattern 2 (Energy Spillover)**: Routes excess energy to healthy bench attackers once active reaches 3 energy.
  3. **Pattern 3 (Endgame Bench Restraint)**: Vetoes bench expansion when opponent is at $\le 2$ prizes and active is healthy, denying bench-gust game-ending KOs.
  4. **Pattern 4 (Alakazam Energy Cap)**: Caps active energy at 2 vs Alakazam to limit Psychic damage scaling.
  5. **Pattern 5 (Anti-Immunity Gust)**: Gusts around Cornerstone Mask ex and immunity walls.
- **Benchmark / Result**:
  - V3 reached project peak $\mu = 939.5$ on live ladder.
  - V4 achieved 260/300 (86.67% WR vs V3 83.00%, $p = 0.0034$) and 13/13 reversal of live failure replays.
  - Final Aggressive Surgical passed 50-process concurrency stress and 10k continuous decision tests with zero errors.
- **Failure or Success**: **FINAL COMPETITION CHAMPION**.
- **What Survived**: Final production agent package (`candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`) and canonical `main.py`.

---

## 3. Methodological Lessons Learned

1. **Pre-Registration Prevents Self-Deception**: Local evaluators consistently "lied" when arms were selected post-hoc. Enforcing $\ge 300$ games with alternating seats and pre-registered Wilson 95% confidence intervals eliminated spurious breakthroughs.
2. **Speed is an Architectural Asset**: Zero-overhead stdlib execution (0.001 ms) allowed hundreds of games per minute during local testing and gave 100% immunity to timeout losses on Kaggle.
3. **Simplicity Over Complexity**: Neural networks and MCTS could not compensate for imperfect information (unseen opponent hands) and multi-turn resource traps. Deterministic domain heuristics with empirical override triggers achieved the highest live performance.
