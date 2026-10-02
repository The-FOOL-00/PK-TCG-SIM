# Competition Agents & Candidate Registry

Date: 2026-10-02  
Repository: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`

This registry contains cryptographic verification hashes (SHA256), exact paths, benchmarks, and statuses for the final submitted agent, all major candidate versions, and key historical agents.

---

## 1. Master Agent Registry

| Agent Name | Version / Branch | Artifact Path | SHA256 Checksum | Competition Status | Benchmark Evidence | Architecture & Notes |
|---|---|---|---|---|---|---|
| **Aggressive Surgical (Kaggle Fixed)** | Final / `main` | `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` | `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8` | **FINAL SUBMITTED / PRODUCTION** | Option A: GO; 50-process stress passed; 10k decisions passed; latency 0.001 ms | Fast aggressive base + 5 surgical overrides (Anti-Tank Gust, Energy Spillover, Bench Restraint, Alakazam Cap, Anti-Immunity Gust). |
| **Aggressive Surgical (Pre-build Final)** | Final / `main` | `candidates/final/project_mew_aggressive_surgical_final.tar.gz` | `0a8ae33ec27941d2cf6d5bad92e2826ac8542566cc5ca7799c55347294c58288` | **VERIFIED PRE-BUILD** | 100% postbuild verified; mean latency 0.001 ms | Same policy logic; retained for full audit trail. |
| **Canonical Python Agent** | Release / `main` | `main.py` | `348de06f631c5b10db916a9e7319ebfb9dfe5ee2428f6766ec1cf08d4dc442fd` | **CANONICAL REPOSITORY SOURCE** | Standalone stdlib pilot; smoke test PASS | Single-file pure standard-library Python agent. |
| **Active Deck Configuration** | Release / `main` | `deck.csv` | `3c0db7bc29599ff1a0a910fc3fbf091c0a5b87735db0c0ec62d774a9c010e8dc` | **CANONICAL REPOSITORY DECK** | 60-card legal deck list | Canonical deck list for local evaluation and submission. |
| **V4 Corrected Production Package** | V4.1 / `archive/project-mew-v4` | `candidates/historical/project_mew_v4_corrected_candidate.tar.gz` | `44456613a43b0be713894393334e72271ab10b730f3076ba71a7c7b9733a6261` | **SUBMITTED (ID 55553469)** | Verified production package; 0 regression rate | Fixed P0 import bypass; full verified execution of Patterns 1, 2, 3. |
| **V4 Endgame Bench Restraint** | V4.0 / `archive/project-mew-v4` | `candidates/historical/project_mew_v4_challenger.tar.gz` | `a7ee61995f5dd42c5ca4380d6bb9b76e45c3d923c08cdb0d98b7e434f1c1a894` | **SUBMITTED (ID 55543695)** | 260/300 (86.67% WR vs V3 83.00%, $p=0.0034$); 13/13 reversal | Pattern 3 Bench Restraint; uninvoked in production due to import bypass. |
| **V5 Alakazam Master Challenger** | V5.0 / `main` | `candidates/historical/project_mew_v5_alakazam_master_challenger.tar.gz` | `2906bbd8acf0a4c5cde8f0ea91ed4134a3342b44d110c01cd1add092fca9d7b3` | **PACKAGED / EVALUATED** | Meta shift defense; cross-archetype screen | Dual-archetype research package exploring Alakazam spread tech. |
| **V3 High-Elo Stabilization** | V3.0 / `main` | `candidates/historical/project_mew_v3_challenger.tar.gz` | `3f46daf3b15d59e271c4b418a488817fd3808f4c085df24ff105750e2e255ab9` | **SUBMITTED (ID 55541564)** | 249/300 (83.00% WR); Live peak $\mu = 939.5$ | Minimal surgical overrides: Pattern 1 (Anti-Tank Gust) + Pattern 2 (Spillover). |
| **SHLS Selective Search** | SHLS / `main` | `candidates/historical/project_mew_shls_challenger.tar.gz` | `13e43f58020c6a315d5d21a0ca087588baf0c852998956978b545a060a93534f` | **SUBMITTED (ID 55532708)** | Offline 81.67% WR; live ladder contradiction | Criticality Gate + 2-ply minimax lookahead on top 3 candidate actions. |
| **V2.1 Outcome-Conditional Brake** | V2.1 / `main` | `candidates/historical/project_mew_strong_policy_v21_candidate.tar.gz` | `5511c1a0d337232cca9c47d008c1a4fe4f61650c832365d2c5069010f231e33f` | **SUBMITTED (ID 55529585)** | 238/300 (79.33% WR vs V1 74.33%, $p=0.0074$) | Outcome-conditional brake: triggers only when 1-shot bench KO exists. |
| **V2 Broad Tactical Brake** | V2.0 / `main` | `candidates/historical/project_mew_strong_policy_v2_fixed.tar.gz` | `c20d52b05fa54c312fbe219a3b50db90a9073d4db5def6efe769ce5db3520308` | **SUBMITTED (ID 55528352)** | Over-aggression 0; 6.67% brake-delay regressions | V1 Tactical + Broad Safety Brake on retaliatory lethal boards. |
| **V1 Strong Tactical E17** | V1.0 / `archive/v1-heuristic` | `candidates/historical/project_mew_strong_policy_challenger.tar.gz` | `bb1f9464866f2d85e3a9cd6c5bf4b6b4c7858a5052488978e2914e7ce95bbad5` | **SUBMITTED (ID 55527083)** | 71/120 (59.17% WR); Live peak $\mu = 847.1$ | High-tempo greedy tactical heuristic (1000pt lethal KO, 500pt chip). |
| **V1.5 Strong Tactical E19** | V1.5 / `main` | `candidates/historical/project_mew_ogerpon_deckopt_A.tar.gz` | `f02f49d47011e21a3ce023bca213308754d1eb6574cbf86d2eb9444f71d4a064` | **SUBMITTED (ID 55522053)** | High-velocity opening consistency (96% T1 energy) | E19 high-velocity energy engine (+2 Grass replacing 2 Jumbo Ice Cream). |
| **Teammate: Sanjay Archaludon v3** | Teammate / `main` | `candidates/historical/submission_archaludon_v3.tar.gz` | `4aafba4749e58a8ce1d3cd2e928437f30b5173fb6480ea945af73e3381f9d655` | **TEAMMATE SUBMISSION** | Teammate benchmark sparring partner | Archaludon Metal engine with C++ `cg.dll` determinized search. |
| **Teammate: Grimmsnarl F1** | Baseline / `main` | `candidates/historical/submission_v1_grimm_f1.tar.gz` | `c18313d9491743385defeed1aca9b198c7d851621f77fa41f87875d62089e1c0` | **BENCHMARK BASELINE** | 79.9% envelope closure on Grimmsnarl | Stage-2 Grimmsnarl ex + Rare Candy baseline benchmark. |
| **Mew Alakazam Master V5** | Historical / `main` | `candidates/historical/submission_mew_alakazam_master_v5.tar.gz` | `593b5064b439179be31c937412d03827d47342084dc06da151528c2aa70a14bc` | **HISTORICAL BENCHMARK** | Alakazam spread benchmark | Alakazam Dudunsparce archetype specialist. |
| **Mew Master V4** | Historical / `main` | `candidates/historical/submission_mew_master_v4.tar.gz` | `bdddd1b7613ebe1de2d8c4062a9c4bdc32c325c1097861fd3eea4a1ff37de573` | **HISTORICAL BENCHMARK** | V4 benchmark package | Intermediate Mew Master candidate. |

---

## 2. Policy File Identity Verification

For the final submitted agent:
- Package: `project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`
- Contained `bot/aggressive_surgical_policy.py`:
  - SHA256: `b40c01a68ba43cc2cc93b8183535f19fa7cc7e27ef82c5c2af84d65458032646`
- Contained `main.py` entrypoint:
  - SHA256: `faafeacd4565da79338041400c3faa7370ee37175ab4acf811111067edc65016`
- Contained `deck.csv`:
  - SHA256: `0f8fb632ade2833645af8c6ffe2b282fe24e7446ee8b23f3e468b8410d8ea36c`
- Verified identical policy execution across local test runner and Kaggle execution sandbox.
