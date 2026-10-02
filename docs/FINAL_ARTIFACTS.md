# Final Competition Artifacts & Submission Verification

**Date:** 2026-10-02  
**Repository:** `https://github.com/The-FOOL-00/PK-TCG-SIM.git`  
**Remote Head:** `main` (commit `86abcef`)

This document defines and cryptographically validates the final competition submission, production runtime source, and distribution packages, backed by empirical logs, checksum audits, compatibility reports, and reconciliation of earlier documentation discrepancies.

---

## 1. Actual Final Submitted Artifact

### Primary Production Submission Package
- **Artifact Path**: `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`
- **Agent Name**: `project_mew_aggressive_surgical_kaggle_fixed_candidate` (Submission Fix for Kaggle Environments In-Memory Dynamic Loader)
- **SHA256 Checksum**: `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`
- **Archive Size**: 2,540 bytes
- **Engine / Runtime Target**: Python 3.10+ / Kaggle Environments `kaggle-environments==1.30.1`, Pure Standard Library (zero compiled C++ or binary dependencies)
- **Internal Components & Verified Checksums**:
  - `main.py`: `faafeacd4565da79338041400c3faa7370ee37175ab4acf811111067edc65016` (979 bytes)
  - `bot/aggressive_surgical_policy.py`: `b40c01a68ba43cc2cc93b8183535f19fa7cc7e27ef82c5c2af84d65458032646` (5,482 bytes)
  - `deck.csv`: `0f8fb632ade2833645af8c6ffe2b282fe24e7446ee8b23f3e468b8410d8ea36c` (259 bytes, 60 cards)
  - `bot/__init__.py`: `8ead34c0d52f2b28f263d4088b5976bdc459d7a658fdaabd2109019da649a064` (20 bytes; note: earlier draft recorded 40-char git commit/tree reference `8ead34c0d52f6797f648cf4910242cdbeee5ad2a`)

### Verification Evidence & Test Results
Documented in `kaggle_compatibility_fix_report.json` and `final_submission_manifest.json`:
- **Policy Identity Verification**: `TRUE` (Byte-for-byte SHA256 match with validated policy `b40c01a68ba43cc2cc93b8183535f19fa7cc7e27ef82c5c2af84d65458032646`).
- **Deck Identity Verification**: `TRUE` (Byte-for-byte match with canonical 60-card Alakazam Master V5 deck `0f8fb632ade2833645af8c6ffe2b282fe24e7446ee8b23f3e468b8410d8ea36c`).
- **Kaggle In-Memory Loader Test**: `PASS` (Executes cleanly under Kaggle dynamic module loader without `__file__` dependency).
- **50-Process Concurrency Stress Test**: `PASS` (Zero deadlocks, zero worker crashes, zero memory leaks).
- **10,000 Decisions Stress Run**: `PASS` (100% legal decisions, 0 exceptions, 0 illegal options).
- **Inference Latency**: Mean **0.0011 ms**, P99 **0.0021 ms** (99.8% under the 1,000 ms Kaggle timeout floor).
- **Final Verdict**: `OPTION A: GO — PACKAGE VERIFIED AND READY FOR SUBMISSION`.

---

## 2. Packaged Deck Reconciliation (Crucial Audit Note)

An audit of the repository identified a historical documentation mismatch:
- **Earlier Draft Claim**: Some previous notes stated that the final package carried the E19 Teal Mask Ogerpon ex decklist.
- **Physical Archive Truth**: Inspection of `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` confirms that `deck.csv` (`0f8fb632...`) contains the **60-card Alakazam Master V5 archetype**:
  - 4x Abra (741), 4x Kadabra (742), 4x Alakazam (743)
  - 4x Dunsparce (305), 3x Dudunsparce (66)
  - 4x Rare Candy (1079), 4x Enhanced Hammer (1081), 4x Buddy-Buddy Poffin (1086), 3x Night Stretcher (1097), 1x Sacred Ash (1129)
  - 4x Poké Pad (1152), 3x Boss's Orders (1182), 1x Lana's Aid (1184), 4x Hilda (1225), 4x Dawn (1231), 1x Battle Cage (1264)
  - 4x Telepath Psychic Energy (19), 3x Basic {P} Energy (5), 1x Enriching Energy (13)
- **Scientific Rationale**: As documented in `project_mew_aggressive_surgical/reports/PROJECT_MEW_AGGRESSIVE_SURGICAL_CANDIDATE_RESEARCH_REPORT.md` §15–17, while E19 dominated earlier hybrid searches, the August 2026 meta rotation into Cornerstone Mask ex (damage immunity to Pokémon ex, causing 0% auto-loss for pure Ogerpon ex) and Crustle damage walls led the team to pair the Aggressive-Surgical policy with Alakazam Master V5. This pairing achieved **86.33%** win rate on the 600-game High-Elo stress pool and reduced the opening mulligan rate from **60.05%** down to **14.20%**.

---

## 3. Pre-Build Final Candidate Archive

- **Artifact Path**: `candidates/final/project_mew_aggressive_surgical_final.tar.gz`
- **SHA256 Checksum**: `0a8ae33ec27941d2cf6d5bad92e2826ac8542566cc5ca7799c55347294c58288`
- **Archive Size**: 2,577 bytes
- **Role**: Pre-fix archive built prior to resolving the Kaggle nested loader `__file__` import nuance. Retained alongside the fixed candidate for forensic completeness and provenance verification.

---

## 4. Canonical Repository Source

- **Root Source**: `main.py`
  - **SHA256**: `348de06f631c5b10db916a9e7319ebfb9dfe5ee2428f6766ec1cf08d4dc442fd`
  - **Lines**: 3,992 lines
  - **Role**: Master monolithic agent implementation containing all modular heuristics, sub-decision scoring matrices, feature flags (`PTCG_V3_EVAL`, `PTCG_LEARNED_VALUE`, `PTCG_SEARCH`, `PTCG_BC`), and surgical override engines.
  - **Smoke Test**: Verified via runtime smoke test (`main.agent({'select': None})` returns legal 60-card deck; mock decisions execute cleanly).
- **Active Deck List**: `deck.csv`
  - **SHA256**: `3c0db7bc29599ff1a0a910fc3fbf091c0a5b87735db0c0ec62d774a9c010e8dc`
  - **Role**: 60-card configuration for the active agent (Teal Mask Ogerpon ex high-velocity build).

---

## 5. Historical Preserved Competition Candidates

All historical candidate milestones are preserved and tracked under `candidates/historical/`:

| Candidate Archive | SHA256 Checksum | Size (Bytes) | Evolutionary Role / Milestone |
|---|---|---|---|
| `project_mew_ogerpon_deckopt_A.tar.gz` | `f02f49d47011e21a3ce023bca213308754d1eb6574cbf86d2eb9444f71d4a064` | 945,720 | Optimized Ogerpon decklist candidate A (E19 high velocity) |
| `project_mew_shls_challenger.tar.gz` | `13e43f58020c6a315d5d21a0ca087588baf0c852998956978b545a060a93534f` | 963,053 | Soft-Horizon Lookahead Search (SHLS) policy candidate |
| `project_mew_strong_policy_challenger.tar.gz` | `bb1f9464866f2d85e3a9cd6c5bf4b6b4c7858a5052488978e2914e7ce95bbad5` | 945,737 | Strong tactical baseline policy challenger (V1) |
| `project_mew_strong_policy_v21_candidate.tar.gz` | `5511c1a0d337232cca9c47d008c1a4fe4f61650c832365d2c5069010f231e33f` | 946,679 | Version 2.1 calibrated strong policy package (conditional brake) |
| `project_mew_strong_policy_v2_fixed.tar.gz` | `c20d52b05fa54c312fbe219a3b50db90a9073d4db5def6efe769ce5db3520308` | 946,049 | Version 2.0 fixed strong policy candidate (broad brake) |
| `project_mew_v3_challenger.tar.gz` | `3f46daf3b15d59e271c4b418a488817fd3808f4c085df24ff105750e2e255ab9` | 728,767 | Project Mew v3 evaluation pipeline candidate (Pattern 1 + 2) |
| `project_mew_v4_challenger.tar.gz` | `a7ee61995f5dd42c5ca4380d6bb9b76e45c3d923c08cdb0d98b7e434f1c1a894` | 729,961 | Project Mew v4 hybrid heuristic package (suffered P0 import bug) |
| `project_mew_v4_corrected_candidate.tar.gz` | `44456613a43b0be713894393334e72271ab10b730f3076ba71a7c7b9733a6261` | 758,871 | Project Mew v4 corrected deployment build (Patterns 1, 2, 3) |
| `project_mew_v5_alakazam_master_challenger.tar.gz` | `2906bbd8acf0a4c5cde8f0ea91ed4134a3342b44d110c01cd1add092fca9d7b3` | 738,668 | Alakazam archetype counter-strategy candidate |
| `submission_archaludon_v3.tar.gz` | `4aafba4749e58a8ce1d3cd2e928437f30b5173fb6480ea945af73e3381f9d655` | 2,036,389 | Archaludon ex heavy metal defense candidate (Teammate Sanjay) |
| `submission_mew_alakazam_master_v5.tar.gz` | `593b5064b439179be31c937412d03827d47342084dc06da151528c2aa70a14bc` | 68,083 | Compressed Alakazam master package |
| `submission_mew_master_v4.tar.gz` | `bdddd1b7613ebe1de2d8c4062a9c4bdc32c325c1097861fd3eea4a1ff37de573` | 67,569 | Compressed Project Mew master v4 bundle |
| `submission_v1_grimm_f1.tar.gz` | `c18313d9491743385defeed1aca9b198c7d851621f77fa41f87875d62089e1c0` | 150,669 | Initial v1 Grimmsnarl baseline submission |

---

## 6. Historical Branch Relationship to Milestones

All five archived branches in the repository are linear ancestors of `main`:

```
66ada6c (archive/v1-heuristic)
   └── e8c7e25 (archive/v2-search-determinized)
         └── 148a58c (archive/v3-behavior-cloning)
               └── ce30384 (archive/stage4-ppo-league)
                     └── d7849c8 (archive/project-mew-v4)
                           └── 86abcef (main / origin/main)
```

1. **`archive/v1-heuristic` (`66ada6c`)**: Baseline heuristic agent v1 with legal option evaluation and priority tiers.
2. **`archive/v2-search-determinized` (`e8c7e25`)**: Determinized Monte Carlo search on `cg` API, time governor, and cross-deck gating.
3. **`archive/v3-behavior-cloning` (`148a58c`)**: Two-headed BC network (`BC-full`) imitating top-10 replays across MAIN and sub-decisions.
4. **`archive/stage4-ppo-league` (`ce30384`)**: PPO capacity ladder (27.8k, 128k, 256k), Bit-Match and Leakage Tier-1 gates.
5. **`archive/project-mew-v4` (`d7849c8`)**: High-velocity Ogerpon ex E19 deck exploration, 243-deck global search, and V4 Pattern 3 bench restraint.
6. **`main` (`86abcef`)**: Aggressive-Surgical candidate with 5 overrides, Kaggle compatibility fix, discrepancy audit, and complete research reconstruction.

---

## 7. Key Limitations & Operational Boundaries

1. **Deterministic Heuristic with Overrides**: The final submitted agent does not perform deep 5+ ply multi-turn branch simulations. It prioritizes sub-millisecond execution and deterministic rule reliability.
2. **Imperfect Information Constraints**: Belief sampling in card games with unobserved hands creates flat value landscapes; runtime search without oracle information failed to outperform domain heuristics.
3. **Distribution Shift in Learning**: Neural models and behavior cloning were vulnerable to compounding off-distribution errors and self-deckout in states absent from winning demonstration corpora.
