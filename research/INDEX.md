# Master Research Archive Index & Navigation Hub

**Repository:** `https://github.com/The-FOOL-00/PK-TCG-SIM.git`  
**Current Head:** `main` (commit `86abcef`)  
**Scope:** Complete research provenance, experimental reports, candidate artifacts, and empirical ledgers.

---

## 1. Primary Canonical Documents

These documents represent the synthesized technical authority for the repository:

- [`README.md`](../README.md): High-level executive overview, verified results, and repository entrypoint.
- [`docs/RESEARCH_HISTORY.md`](../docs/RESEARCH_HISTORY.md): Canonical comprehensive research narrative covering all 10 phases, experiments, and findings.
- [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md): Technical architecture specification of the final production agent and 5 surgical overrides.
- [`docs/FINAL_ARTIFACTS.md`](../docs/FINAL_ARTIFACTS.md): Cryptographic verification, archive contents, and candidate registry.
- [`research/CLAIM_EVIDENCE_LEDGER.md`](CLAIM_EVIDENCE_LEDGER.md): Traceability matrix linking every key technical claim to empirical files.
- [`research/CONTRADICTIONS.md`](CONTRADICTIONS.md): Register of historical discrepancies, measurement artifacts, and their resolutions.
- [`docs/DATASETS.md`](../docs/DATASETS.md): Catalog of external datasets, replay corpora, and reacquisition scripts.

---

## 2. Index by Research Theme

### Theme A: Baseline Strategy & Heuristic Priority Ladders
- Primary Code: `main.py` (`348de06f...`)
- Historical Branch: `archive/v1-heuristic` (`66ada6c`)
- Key Artifact: `candidates/historical/project_mew_strong_policy_challenger.tar.gz` (`bb1f9464...`)
- Reports & Logs:
  - `EXPERIMENT_LOG.md` (Lines 1–110: WS1 deck variants, WS2 analytic evaluator, Phase 0 gate)
  - `v1_metrics.json`
  - `aggressive_peak_reconstruction.json` (V1 120-game live climb to $\mu = 857.1$)

### Theme B: Determinized Search & imperfect Information
- Primary Code: `tools/searcher.py`, `bot/search/expectimax.py`
- Historical Branch: `archive/v2-search-determinized` (`e8c7e25`)
- Key Artifact: `candidates/historical/project_mew_shls_challenger.tar.gz` (`13e43f58...`)
- Reports & Logs:
  - `EXPERIMENT_LOG.md` (Lines 162–558: Phase 2a flat MC teacher, Phase B CardTracker, Phase E1 belief failure, Step 1 cross-deck gates)
  - `runs/gate_e1_comp.json` (Honest belief search vs V1: 49.0% FAIL)
  - `runs/gate_e1_mirror.json` (Mirror belief search vs V1: 58.3% PASS)
  - `tools/diagnose_belief.py` (76% zero value separation under honest belief)
  - `report/WRITEUP_FULL.md` (§3.4–§3.7: Search characterization, sandbox overhead, belief bottleneck)

### Theme C: Supervised Learning & Behavior Cloning
- Primary Code: `training/train_bc_full.py`, `training/train_policy.py`
- Historical Branch: `archive/v3-behavior-cloning` (`148a58c`)
- Key Weights: `bc_weights_clean_v21.npz`, `bc_weights_garchomp_full.npz`
- Reports & Logs:
  - `EXPERIMENT_LOG.md` (Lines 629–807: Stage 3A feasibility, Stage 3B Gen 1 failure, tooling bug, Stage 3B Option A BC-Full PASS)
  - `runs/gate_G6a_full_bcfull_vs_v200.json` (BC-Full vs v2.0.0: 60.7% PASS)
  - `runs/gate_G6c_full_bcfull_vs_bcprior.json` (BC-Full vs BC Gen 1: 77.0% PASS)
  - `runs/gate_G6b_full_bcfull_vs_search.json` (BC-Full vs Search: 69.7% PASS)
  - `stage4/runs/gate_G7a_bcv2brake_vs_v220.json` (Draw brake failure: 39.0% FAIL)

### Theme D: Multi-Agent Reinforcement Learning (PPO League)
- Primary Code: `stage4/rl_ours/ppo/` (`train.py`, `net.py`, `rollout.py`, `verdict.py`)
- Historical Branch: `archive/stage4-ppo-league` (`ce30384`)
- Documentation:
  - `HANDOFF.md` (Run 1 capacity-limited verdict, Run 2 128k Net2WiderNet, Run 3 256k)
  - `stage4/rl_ours/LAB_RUNBOOK.md` (Execution protocols, Tier-1 preflight gates)
  - `stage4/rl_ours/gumbel_az_scoping.md` (Gumbel AlphaZero scoping)
  - `stage4/rl_ours/GATE_K1_ckpt044_059.md` (Formal K1 gate measurements)

### Theme E: Envelope Closure & Deck–Pilot Fit
- Primary Documentation: `report/WRITEUP_FULL.md` (§4), `report/REVIEW_NOTE.md`
- Key Figures: `report/figures/fig1_closure.png`, `report/figures/fig3_sequencing.png`, `report/figures/fig4_trap_scatter.png`
- Core Measurements:
  - `stage4/rl_ours/prize_velocity.py` (Prize velocity derivation)
  - `stage4/rl_ours/DECK_SWEEP.md` (Sweep across 7 archetypes)
  - `report/WRITEUP_FULL.md` (§4.3: 2x2 factorial proving deck effect is 10x search effect)

### Theme F: Project Mew, Ogerpon E19, & Deck Optimization
- Primary Code: `tools/energy_density_experiment.py`, `tools/run_counter_search.py`
- Historical Branch: `archive/project-mew-v4` (`d7849c8`)
- Reports & Documentation:
  - `project_mew_v4_research/reports/FINAL_PROJECT_MEW_REPORT.md` (Global Anti-E19 hybrid search across 243 decks / 20,120 games)
  - `runs/energy_neighborhood/energy_full_validation_results.json` (E19 hypergeometric validation)
  - `PROJECT_MEW_EVIDENCE_LEDGER.md` (Claims 7 & 8: E19 optimality proof)

### Theme G: High-Elo Replay Forensics & Surgical Policy Evolution
- Primary Code: `bot/aggressive_surgical_policy.py`
- Candidate Archives: `candidates/historical/project_mew_strong_policy_v21_candidate.tar.gz`, `candidates/historical/project_mew_v3_challenger.tar.gz`, `candidates/historical/project_mew_v4_corrected_candidate.tar.gz`
- Reports & Documentation:
  - `aggressive_surgical_policy_audit.json` (Specification of 5 surgical overrides)
  - `aggressive_branch_registry.json` (V1 through V4 corrected candidate registry)
  - `project_mew_v3/reports/v3_high_elo_stabilization_summary.json` (V3 83.00% WR paired test)
  - `project_mew_v4/reports/v4_validation_and_benchmarking_summary.json` (V4 86.67% WR paired test)
  - `project_mew_v5_research/reports/FINAL_PROJECT_MEW_V5_REPORT.md` (August meta shift into Alakazam, Crustle, and Cornerstone)
  - `project_mew_aggressive_surgical/reports/PROJECT_MEW_AGGRESSIVE_SURGICAL_CANDIDATE_RESEARCH_REPORT.md` (Final candidate 86.33% stress pool validation)

### Theme H: Production Packaging & Kaggle Runtime Compatibility
- Primary Tools: `tools/verify_and_build_kaggle_fixed_candidate.py`, `tools/run_master_verification.py`
- Reports & Audits:
  - `kaggle_compatibility_fix_report.json` (Kaggle loader fix removing `__file__`, 50-process concurrency stress test)
  - `final_submission_manifest.json` (Final build manifest and latency benchmarks)
  - `research/repository_cleanup/` (Repository cleanup reports, size audits, and branch verification)

---

## 3. Index by Candidate Version

| Version / Identifier | Submission ID | Artifact Path | SHA256 Checksum | Evolutionary Status |
|---|---|---|---|---|
| **V1 Strong Tactical** | 55527083 | `candidates/historical/project_mew_strong_policy_challenger.tar.gz` | `bb1f9464866f2d85e3a9cd6c5bf4b6b4c7858a5052488978e2914e7ce95bbad5` | Baseline heuristic (peak $\mu = 857.1$) |
| **V1.5 Ogerpon Deckopt**| 55522053 | `candidates/historical/project_mew_ogerpon_deckopt_A.tar.gz` | `f02f49d47011e21a3ce023bca213308754d1eb6574cbf86d2eb9444f71d4a064` | E19 high-velocity deck introduction |
| **V2 Broad Brake** | 55528352 | `candidates/historical/project_mew_strong_policy_v2_fixed.tar.gz` | `c20d52b05fa54c312fbe219a3b50db90a9073d4db5def6efe769ce5db3520308` | Fixed over-aggression; 6.67% delay regression |
| **V2.1 Conditional Brake**| 55529585 | `candidates/historical/project_mew_strong_policy_v21_candidate.tar.gz` | `5511c1a0d337232cca9c47d008c1a4fe4f61650c832365d2c5069010f231e33f` | Outcome-conditional brake (79.33% WR) |
| **SHLS Search** | 55532708 | `candidates/historical/project_mew_shls_challenger.tar.gz` | `13e43f58020c6a315d5d21a0ca087588baf0c852998956978b545a060a93534f` | Selective 2-ply search; contradicted live |
| **V3 High-Elo Stabilize**| 55541564 | `candidates/historical/project_mew_v3_challenger.tar.gz` | `3f46daf3b15d59e271c4b418a488817fd3808f4c085df24ff105750e2e255ab9` | Pattern 1 + 2 (Peak $\mu = 939.5$) |
| **V4 Bench Restraint** | 55543695 | `candidates/historical/project_mew_v4_challenger.tar.gz` | `a7ee61995f5dd42c5ca4380d6bb9b76e45c3d923c08cdb0d98b7e434f1c1a894` | Pattern 3; uninvoked due to P0 import bug |
| **V4 Corrected** | 55553469 | `candidates/historical/project_mew_v4_corrected_candidate.tar.gz` | `44456613a43b0be713894393334e72271ab10b730f3076ba71a7c7b9733a6261` | Verified production package (86.67% WR) |
| **V5 Alakazam Master** | N/A | `candidates/historical/project_mew_v5_alakazam_master_challenger.tar.gz` | `2906bbd8acf0a4c5cde8f0ea91ed4134a3342b44d110c01cd1add092fca9d7b3` | Alakazam spread counter package |
| **Final Pre-Build** | N/A | `candidates/final/project_mew_aggressive_surgical_final.tar.gz` | `0a8ae33ec27941d2cf6d5bad92e2826ac8542566cc5ca7799c55347294c58288` | Pre-fix package (had `__file__` bug) |
| **Final Kaggle-Fixed** | N/A | `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` | `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8` | **CANONICAL PRODUCTION ARTIFACT** |
