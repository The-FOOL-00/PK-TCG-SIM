# Pokémon TCG AI Battle Challenge — Canonical Research Archive

Official codebase and archival research repository for **The Pokémon Company — Pokémon TCG AI Battle Challenge** (hosted on Kaggle).

- **Competition**: The Pokémon Company - Pokémon TCG AI Battle Challenge Simulation
- **Platform**: `kaggle-environments` (`cabt` Engine v1.0.0)
- **Repository Remote**: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`
- **Canonical Final Submission**: [`candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`](candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz)
- **Canonical Archive SHA256**: `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`

---

## 1. Executive Overview

This repository represents the **complete scientific and technical record** of our participation in the Pokémon TCG AI Battle Challenge. Across seven distinct paradigm shifts—ranging from heuristic priority ladders, Monte Carlo tree search, and deep value networks to supervised behavior cloning and multi-agent reinforcement learning—the team investigated how to engineer a competitive, robust agent under strict time and imperfect-information constraints.

### Canonical Final Agent: Project Mew Aggressive-Surgical
- **Package Path**: `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`
- **Architecture**: Microsecond-latency deterministic heuristic priority engine paired with **5 condition-specific surgical overrides** targeting proven empirical loss patterns:
  1. *Anti-Tank Gust*: Intercepts suicidal chip attacks into lethal retaliatory tanks when a 1-shot bench KO exists.
  2. *Loaded Energy Spillover*: Reroutes excess energy attachment to bench attackers once the active reaches $\ge 3$ energy.
  3. *Endgame Bench Restraint*: Vetoes bench basic expansion when opponent is at $\le 2$ prizes and active is healthy, denying 2-prize bench-gust KOs.
  4. *Alakazam Energy Cap*: Enforces a 2-energy cap on the active against Alakazam spread decks to limit *Psychic* damage.
  5. *Anti-Immunity Gust*: Detects ex-damage immunity on the opponent active (e.g. Cornerstone Mask ex's *Cornerstone Stance*) and gusts vulnerable bench targets.
- **Packaged Deck**: 60-card Alakazam Master V5 list (`0f8fb632...`), eliminating Cornerstone Mask ex auto-losses, piercing Crustle walls, and dropping opening mulligans from 60.05% to 14.20%.
- **Runtime Performance**: Pure Python standard library, zero compiled C++ or binary dependencies, mean latency **0.0011 ms** (99.8% under Kaggle timeout limits).
- **Verification**: Byte-for-byte SHA256 policy match, 50-process concurrency stress tested, 10,000 continuous decisions profiled without illegal actions or exceptions.

---

## 2. Competitive & Benchmark Performance Summary

> [!IMPORTANT]
> **Distinction Between Local Benchmarks and Official Competition Results**:
> - **Official Public Competition Ladder**: TrueSkill posterior rating ($\mu \pm 3\sigma$) on the live Kaggle ladder. V1 achieved peak $\mu = 857.1$ (settled $\mu = 844.6$ over 120 games); V3 achieved project peak $\mu = 939.5$ at Game 39; BC-Full achieved $\mu = 697.0$ (settled 682.5).
> - **Internal Empirical Benchmarks**: Controlled pairwise simulations under `tools/ab_gate.py` ($\ge 300$ games, alternating seats, Wilson 95% CIs). The final Aggressive-Surgical candidate achieved **86.33%** win rate on the 600-game High-Elo stress pool and **84.83%** on fresh-seed replication.

---

## 3. Research Evolution: From Baseline to Aggressive-Surgical

The project progressed through ten distinct research phases, preserved across dedicated milestone branches and candidate packages:

```
[v1-heuristic] ──> [v2-search] ──> [v3-bc] ──> [stage4-ppo] ──> [project-mew-v4/v5] ──> [aggressive-surgical]
 Heuristic Core      Determinized     Two-Headed      PPO League        High-Velocity        5 Overrides + Fixed
 (74.3% Baseline)     Search Failure   BC-Full         (Capacity         Ogerpon E19          Kaggle Loader
                     (49.0% Gate)     (60.7% Gate)    Limited)          (86.7% Paired)       (86.3% Stress Pool)
```

1. **Phase 1: Baseline Heuristic V1 (`archive/v1-heuristic`)**: Established legal validation harness and priority ladder, climbing to peak $\mu = 857.1$.
2. **Phase 2 & 3: Search Exploration & Belief Failure (`archive/v2-search-determinized`)**: Determinized Monte Carlo search saturated at 58.7%. Under fog of war, honest belief sampling produced 76% zero value separation, failing Gate E1 (49.0%).
3. **Phase 4: Deck Offensive & Falsified Gate**: Local gate showed Alakazam deck beating old deck 74.7%, but crashed on live ladder to $\mu = 548$ because search skipped combo trainer sub-decisions.
4. **Phase 5: Behavior Cloning Breakthrough (`archive/v3-behavior-cloning`)**: Gen 1 MAIN-only BC failed (31.0%). Built 73-dim `ST_CARD` option encoder and two-headed net (BC-Full), passing all gates (60.7%, 69.7%, 77.0%) and shipping to $\mu = 697$.
5. **Phase 6: Stage 4 PPO League (`archive/stage4-ppo-league`)**: Capacity ladder (27.8k, 128k, 256k) plateaued across 83,520 games at ~27% win rate due to delayed rewards and vast action spaces.
6. **Phase 7: Envelope Closure**: Established that deck–pilot fit is 10x the search effect. Ogerpon ex and Grimmsnarl ex achieved ~80% envelope closure.
7. **Phase 8: Project Mew & E19 Search (`archive/project-mew-v4`)**: Optimized high-velocity 19-energy Ogerpon build (96% T1 energy). Evaluated 243 hybrid decks (20,120 games); E19 statistically dominated all hybrids ($p < 0.001$).
8. **Phase 9: High-Elo Replay Forensics & Surgical Policy**: Iterated V1 $\to$ V2 $\to$ V2.1 $\to$ V3 $\to$ V4, mining 5 surgical overrides to eliminate over-aggression, energy overcommitment, and bench-gust traps.
9. **Phase 10: Final Aggressive-Surgical & Kaggle Compatibility**: Paired policy with Alakazam Master V5 to defeat the August meta's immunity walls. Fixed Kaggle dynamic loader `__file__` bug, verified identical policy and deck, and built the canonical deployment artifact.

---

## 4. Key Validated Scientific Lessons

1. **Envelope Closure Governs Strength**: An agent's strength is primarily determined by whether its priority order naturally executes a deck's win condition.
2. **Never Trust an Offline Proxy**: AUC, static top-1 accuracy, and self-play win rates repeatedly failed to predict live ladder strength.
3. **Mirror Gates Mask Shared Defects**: Evaluating an agent against itself cannot surface flaws both sides commit. Always gate cross-deck against strong external baselines.
4. **Speed is an Architectural Asset**: Zero-overhead stdlib execution (0.001 ms) completely prevents timeout disqualifications and allows hundreds of games per minute in testing.
5. **Surgical Conditioning Preserves Velocity**: Broad defensive brakes introduce fatal passivity; overrides must condition strictly on confirmed alternative lines.

---

## 5. Repository Structure

```
├── README.md                            # Executive overview & repository entrypoint
├── deck.csv                             # Canonical 60-card active decklist (Ogerpon ex)
├── main.py                              # Monolithic development agent (3,992 lines)
├── requirements.txt                     # Runtime environment dependencies
├── candidates/
│   ├── final/                           # Canonical production artifacts (SHA256 verified)
│   └── historical/                      # Preserved milestone packages across all phases
├── docs/
│   ├── ARCHITECTURE.md                  # Complete technical architecture specification
│   ├── RESEARCH_HISTORY.md              # Master comprehensive research history (10 phases)
│   ├── FINAL_ARTIFACTS.md               # Cryptographic verification & candidate registry
│   ├── AGENTS.md                        # Historical agent registry & performance metrics
│   └── DATASETS.md                      # Dataset acquisition guide & external data catalog
├── research/
│   ├── INDEX.md                         # Master navigation hub for the research archive
│   ├── CLAIM_EVIDENCE_LEDGER.md         # Traceability matrix mapping claims to evidence
│   ├── CONTRADICTIONS.md                # Discrepancy register and reconciliation records
│   └── repository_cleanup/              # Archival audit reports and deletion manifests
├── bot/                                 # Modular policies, decision encoders, and search
├── tools/                               # A/B gates, packaging, forensics, and test suites
├── data/                                # Replay manifests, training datasets, and telemetry
└── stage4/                              # Stage 4 PPO trainer, capacity ladder, and diagnostics
```

---

## 6. Canonical Documentation Links

- **Detailed Research History**: [`docs/RESEARCH_HISTORY.md`](docs/RESEARCH_HISTORY.md)
- **Technical Architecture Specification**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Final Artifact & Candidate Registry**: [`docs/FINAL_ARTIFACTS.md`](docs/FINAL_ARTIFACTS.md)
- **Research Archive Index**: [`research/INDEX.md`](research/INDEX.md)
- **Claim & Evidence Ledger**: [`research/CLAIM_EVIDENCE_LEDGER.md`](research/CLAIM_EVIDENCE_LEDGER.md)
- **Contradictions & Reconciliation Register**: [`research/CONTRADICTIONS.md`](research/CONTRADICTIONS.md)
- **Dataset Reacquisition Guide**: [`docs/DATASETS.md`](docs/DATASETS.md)

---

## 7. Reproduction & Verification

To execute the verification suite and validate decision logic:

```bash
# 1. Test canonical main.py agent deck and decision execution
python -c "import main; assert len(main.agent({'select': None})) == 60"

# 2. Run master bundle verification suite
python tools/run_master_verification.py

# 3. Verify final candidate archive integrity
python tools/verify_and_build_kaggle_fixed_candidate.py
```
