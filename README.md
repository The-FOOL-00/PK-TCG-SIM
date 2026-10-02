# Pokémon TCG AI Battle Challenge — Repository & Competition Archive

Official codebase and archival repository for **The Pokémon Company — Pokémon TCG AI Battle Challenge Simulation** (hosted on Kaggle).

- **Competition**: The Pokémon Company - PTCG AI Battle Challenge Simulation
- **Platform**: `kaggle-environments` (`cabt` Engine)
- **Repository Remote**: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`
- **Canonical Final Submission**: `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`
- **Canonical SHA256**: `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`

---

## 1. Executive Summary & Final Submission

This repository contains the complete research, development lineage, experimental branches, evaluation tooling, and verified submission packages developed for the Pokémon TCG AI Battle Challenge.

### Canonical Final Agent: Project Mew Aggressive-Surgical
- **Package Path**: `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`
- **Architecture**: Deterministic fast-tactical priority engine paired with 5 condition-specific surgical overrides targeting proven high-Elo failure modes:
  1. *Anti-Tank Gust*: Prioritizes Boss's Orders over high-HP active tanks threatening lethal counter-strikes.
  2. *Loaded Energy Spillover*: Reroutes redundant energy attachment away from loaded active attackers to bench backup.
  3. *Endgame Bench Restraint*: Suppresses redundant bench basic drops when ahead on prize count.
  4. *Alakazam Energy Cap*: Enforces a 2-energy cap on active against Alakazam spread decks to limit Psychic damage.
  5. *Cornerstone Anti-Immunity Gust*: Detects Tera/ex immunity on the opponent active and gusts vulnerable bench targets.
- **Deck Configuration**: 60-card high-tempo Teal Mask Ogerpon ex list (`deck.csv`).
- **Runtime Performance**: Pure Python standard library, zero compiled C++ or binary dependencies, mean latency **0.0011 ms** (99.8% under Kaggle timeout limits).
- **Verification**: Byte-for-byte SHA256 policy match, 50-process concurrency stress tested, 10,000 decisions profiled without illegal actions or exceptions.

---

## 2. Competition Evolution & Historical Milestones

The agent progressed through five major development stages, each preserved with dedicated milestone branches and candidate packages:

```
[v1-heuristic] ──> [v2-search] ──> [v3-bc] ──> [stage4-ppo] ──> [project-mew-v4/v5]
 Heuristic Baseline   Belief-Sampled     Two-Head BC      PPO League       Aggressive-Surgical
 (Gate Pass)          Monte-Carlo       (69.7% Gate)    (Capacity Ladder) (Final Live Submission)
```

1. **Phase 1: Baseline Heuristic (`archive/v1-heuristic`)**
   - Pure heuristic rule-ladder with card utility scoring and basic setup priorities.
2. **Phase 2: Determinized Search (`archive/v2-search-determinized`)**
   - 1-ply analytic belief-sampled Monte-Carlo tree search evaluating turn branches under unobserved card distributions.
3. **Phase 3: Behavior Cloning (`archive/v3-behavior-cloning`)**
   - Two-headed neural policy/value network trained on high-Elo Kaggle ladder replays (achieved 69.7% gate pass against benchmark baselines).
4. **Phase 4: PPO League Self-Play (`archive/stage4-ppo-league`)**
   - Multi-agent reinforcement learning with league matchmaking, GAE advantage estimation, and anchor regularization.
5. **Phase 5: Project Mew & Aggressive-Surgical (`archive/project-mew-v4` & `main`)**
   - Discovered that live ladder meta shifted heavily toward micro-tactical execution speed and anti-gimmick reliability. Merged tactical greedy tempo with the 5 surgical overrides to achieve maximum competitive win-rate.

---

## 3. Repository Structure

```
├── main.py                  # Master agent entrypoint with full heuristic & fallback chain
├── deck.csv                 # Canonical 60-card deck configuration (Ogerpon ex)
├── requirements.txt         # Environment dependencies (kaggle-environments)
├── .gitignore               # Hardened ignore rules preventing secret/clutter leakage
├── candidates/
│   ├── final/               # Canonical final competition packages (SHA256 verified)
│   └── historical/          # Preserved milestone packages across all research stages
├── bot/                     # Core modular bot policies, decision encoders, and search
├── tools/                   # Validation, bundle packaging, and local evaluation suites
├── docs/                    # Architectural specifications and artifact records
│   ├── FINAL_ARTIFACTS.md   # Cryptographic verification and audit of all candidates
│   ├── RESEARCH_HISTORY.md  # Detailed chronicle of experiments and findings
│   ├── AGENTS.md            # Agent catalog and historical performance metrics
│   └── DATASETS.md          # Dataset acquisition guide and external data catalog
├── data/
│   ├── MANIFEST.csv         # Reacquisition catalog for external replay corpora & assets
│   └── README_DATA.md       # Guidelines on official competition data handling
└── research/
    └── repository_cleanup/  # Repository audit reports, deletion manifests, and size logs
```

---

## 4. Verification & Testing

To execute the master verification suite and validate agent decision logic locally:

```bash
# 1. Test canonical main.py agent deck and decision execution
python -c "import main; assert len(main.agent({'select': None})) == 60"

# 2. Run master bundle verification suite
python tools/run_master_verification.py
```

---

## 5. Official Competition Data & Reproducibility

Per Kaggle competition rules, official competition assets (PDF card lists and starter game binaries) are not redistributed in Git. To reacquire official assets:
1. Download official starter materials from the Kaggle Competition Data tab.
2. Refer to [`docs/DATASETS.md`](docs/DATASETS.md) and [`data/MANIFEST.csv`](data/MANIFEST.csv) for schema specifications and replication scripts.
