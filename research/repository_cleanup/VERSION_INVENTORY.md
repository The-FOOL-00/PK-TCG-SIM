# Competition Version Inventory

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`  
Repository: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`

This document provides a comprehensive inventory of all project, research, and agent versions developed throughout the competition lifecycle.

---

## 1. Master Version Matrix

| Version / Identifier | Source Path / Artifact | Historical Milestone | Core Purpose & Mechanism | Benchmark / Outcome | Submission Status | Preservation Decision |
|---|---|---|---|---|---|---|
| **V1 Baseline (ptcg-heuristic-v1.0.0)** | `main.py` (base), `submission_v1_grimm_f1.tar.gz` | Commit `66ada6c` | Deterministic priority ladder: lethal attack > attach > evolve > item > bench > ability. Single-file stdlib Python. | Offline 74.33% WR; Live peak $\mu = 847.1$ (settled $\mu = 844.6$). Suffered over-aggression losses. | Submitted (ID 55527083) | **PRESERVE** (canonical in `main.py`, baseline archive in `candidates/historical/`) |
| **V1.5 Strong Tactical E19** | `project_mew_ogerpon_deckopt_A.tar.gz` | Commit `d7849c8` | Upgraded energy engine to E19 (19 Basic Grass + 2 Grow Grass), maximizing T1 attachment probability (96.0%). | High-velocity opening consistency; benchmarked against standard meta pools. | Submitted (ID 55522053) | **PRESERVE** in `candidates/historical/` |
| **V2 Broad Tactical Brake** | `project_mew_strong_policy_v2_fixed.tar.gz` | Commit `d7849c8` | Broad tactical brake to veto non-lethal attacks into lethal retaliating boards. | Over-aggression dropped to 0, but introduced 6.67% brake-delay regressions. | Submitted (ID 55528352) | **PRESERVE** in `candidates/historical/` |
| **V2.1 Outcome-Conditional Brake** | `project_mew_strong_policy_v21_candidate.tar.gz` | Commit `d7849c8` | Refined brake triggering strictly against >160 HP tanks when a confirmed bench KO alternative exists. | 238/300 (79.33% WR vs V1 74.33%, $p = 0.0074$); 0 brake-delay regressions. | Submitted (ID 55529585) | **PRESERVE** in `candidates/historical/` |
| **V2.2.0 Search & Evaluation (Phase B-F)** | `cg/`, `tools/searcher.py`, `tools/ab_gate.py` | Commit `99e2305` | Belief-sampled determinized Monte-Carlo search on cg API engine. | Offline 58.7% WR; live ladder plateaued at $\mu \approx 548$ vs heuristic $\mu \approx 614$. Search overhead without multi-turn setup killed. | Tested live, discontinued | **PRESERVE** source in `tools/` and `cg/` |
| **Stage 3B Behavior Cloning (BC-Full)** | `bc_weights_clean_v21.npz/`, `training/train_policy.py` | Commit `099cedf` | Two-headed policy network mimicking top-10 harvested human replays (JunLee789, Nasuo). | Offline top-1 69.4%, sub-decision 76.1%; head-to-head 60.7% [55.0, 66.0]. Shipped to ladder $\mu \approx 697$. | Intermediate milestone | **PRESERVE** weights in `bc_weights_clean_v21.npz/` and trainer in `training/` |
| **Stage 4 PPO League / Capacity Ladder** | `stage4/`, `stage4/rl_ours/` | Commits `bca3057`–`ce30384` | Distributed PPO league training with KL-to-BC anchor, GAE, and self-play. | K1 gate fired flat (31.5%–34.5% vs BC start 33.5%); no improvement over 14k games. Stopped per kill criteria. | Experimental / Research | **PRESERVE** trainer code, runbooks, and gate audits in `stage4/` |
| **SHLS (Selective High-Leverage Search)** | `project_mew_shls/`, `project_mew_shls_challenger.tar.gz` | Commit `d7849c8` | Criticality gate + selective 2-ply minimax lookahead on top 3 candidate actions. | Offline 81.67% WR, 87.5% critical reversals. Contradicted by live ladder due to distribution shift. | Submitted (ID 55532708) | **PRESERVE** in `candidates/historical/` |
| **V3 High-Elo Stabilization** | `project_mew_v3/`, `project_mew_v3_challenger.tar.gz` | Commit `d7849c8` | Minimal surgical overrides: Pattern 1 (Anti-Tank Gust) + Pattern 2 (Loaded Active Energy Spillover). | 249/300 (83.00% WR vs V1 74.33%, $p < 10^{-6}$). Live peak $\mu = 939.5$ (project record peak). Uncovered 2-prize bench vulnerability. | Submitted (ID 55541564) | **PRESERVE** in `candidates/historical/` |
| **V4 Endgame Bench Restraint** | `project_mew_v4/`, `project_mew_v4_challenger.tar.gz` | Commit `d7849c8` | Pattern 3 (Endgame Bench Restraint): vetos bench expansion when opponent has $\le 2$ prizes left and active is healthy. | 260/300 (86.67% WR vs V3 83.00%, $p = 0.0034$); 13/13 historical replay reversals. Production bundle had P0 import bypass. | Submitted (ID 55543695) | **PRESERVE** in `candidates/historical/` |
| **V4 Corrected Production Package** | `project_mew_v4_corrected_candidate.tar.gz` | Commit `d7849c8` | Fixed P0 import bypass: full verified production integration of Patterns 1, 2, and 3. | Live control benchmark, zero regression rate, verified production execution. | Submitted (ID 55553469) | **PRESERVE** in `candidates/historical/` |
| **V5 Alakazam Master / Tech** | `project_mew_v5_research/`, `project_mew_v5_alakazam_master_challenger.tar.gz` | Commit `d7849c8` | Dual-archetype tech exploration (Alakazam spread + Crustle/Okidogi defense). | Validated against meta shifts; provided empirical envelope data for writeup. | Evaluated / Packaged | **PRESERVE** in `candidates/historical/` |
| **Aggressive Surgical Final** | `project_mew_aggressive_surgical/`, `project_mew_aggressive_surgical_final.tar.gz` | Commit `45f1ced` | 5 condition-specific surgical overrides on pure aggressive core (Anti-Tank Gust, Energy Spillover, Bench Restraint, Alakazam Cap, Anti-Immunity Gust). | 100% postbuild verified; mean latency 0.001 ms; zero syntax/import overhead. | Pre-submission final package | **PRESERVE** in `candidates/final/` |
| **Aggressive Surgical Kaggle Fixed Candidate** | `project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` | Commit `45f1ced` | Resolved Kaggle runtime loader constraint for submission ID 55557790 while maintaining 100% policy and deck identity. | Option A: GO — Kaggle loader verified, 50-process stress test passed, 10k decisions passed. | **FINAL PRODUCTION SUBMISSION** | **PRESERVE** in `candidates/final/` & documented as canonical |
| **Teammate Agent: Sanjay Archaludon v3** | `submission_archaludon_v3.tar.gz`, `metaX_archaludon_sanjay.csv` | Commit `5b979e9` | C++ engine + determinized search pilot for Metal Archaludon archetype. | Cross-archetype baseline and top-10 sparring partner. | Teammate Submission | **PRESERVE** in `candidates/historical/` |

---

## 2. Inventory Summary

- **Total Versions Identified**: 15 distinct development and competition versions.
- **Final Submitted / Ready Candidate**: `project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` + canonical root `main.py`.
- **Key Historical Candidates to Retain**: 13 packages representing major architectural rungs.
- **Redundant Intermediate Bundles**: Excluded from repository to eliminate working tree bloat.
