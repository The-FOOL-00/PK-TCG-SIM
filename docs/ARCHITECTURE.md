# Architecture Specification — Final Production Agent & System Design

**Date:** 2026-10-02  
**Repository:** `https://github.com/The-FOOL-00/PK-TCG-SIM.git`  
**Production Artifact:** `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`  
**Artifact SHA256:** `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`  
**Canonical Repository Entrypoint:** `main.py` (`348de06f631c5b10db916a9e7319ebfb9dfe5ee2428f6766ec1cf08d4dc442fd`)

---

## 1. Architectural Philosophy: Why Fast Heuristic + Surgical Overrides

Across 20+ pre-registered experiments spanning tree search, value nets, behavior cloning, and reinforcement learning, the team established that:
1. **Offline Accuracy Does Not Predict Ladder Strength**: Models boasting high validation accuracy (AUC 0.8445, BC top-1 69.4%) failed to transfer to live competition due to distribution shifts, unobserved opponent hand cards, and multi-turn resource traps.
2. **Speed is an Architectural Asset**: Top-tier ladder bots operate with decision times between 28 ms and 136 ms. Operating at sub-millisecond latency (<0.06 ms) completely eliminates timeout disqualifications and permits exhaustive local simulation.
3. **Envelope Closure Governs Deck Viability**: A fixed priority ladder succeeds only when a deck's natural line aligns with that ladder. Complex setup decks requiring deep lookahead collapse under greedy pilots, whereas decks with immediate acceleration or Stage-2 collapse mechanisms achieve high envelope closure.

The final system architecture abandons heavy search and neural inference in favor of a **deterministic high-tempo aggressive core** augmented by **five condition-specific surgical overrides** that directly address empirical loss clusters without degrading baseline velocity.

---

## 2. Production Artifact Architecture (`project_mew_aggressive_surgical_kaggle_fixed_candidate`)

The final deployment package is a pure-standard-library Python distribution packaged as a gzip tarball (2,540 bytes):

```
project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz
├── bot/
│   ├── __init__.py                     (SHA256: 8ead34c0d52f2b28f263d4088b5976bdc459d7a658fdaabd2109019da649a064)
│   └── aggressive_surgical_policy.py   (SHA256: b40c01a68ba43cc2cc93b8183535f19fa7cc7e27ef82c5c2af84d65458032646)
├── deck.csv                            (SHA256: 0f8fb632ade2833645af8c6ffe2b282fe24e7446ee8b23f3e468b8410d8ea36c)
└── main.py                             (SHA256: faafeacd4565da79338041400c3faa7370ee37175ab4acf811111067edc65016)
```

### 2.1 Package Entrypoint (`main.py`)
To ensure complete compatibility with Kaggle Environments (`kaggle-environments==1.30.1`), which executes code dynamically via `get_last_callable` without setting the `__file__` global, `main.py` is stripped of filesystem-dependent paths:

```python
"""Pokemon TCG AI Battle Challenge agent.
Production-Safe Aggressive-Surgical High-Elo Candidate.
"""
import sys

try:
    from bot.aggressive_surgical_policy import select_aggressive_surgical_action
except Exception:
    def select_aggressive_surgical_action(obs, legal_actions):
        return legal_actions[0].get("index", 0) if legal_actions else 0

def agent(obs):
    """Main agent entry point."""
    try:
        legal_actions = obs.get("legal_actions", [])
        if not legal_actions:
            return 0
        return select_aggressive_surgical_action(obs, legal_actions)
    except Exception as err:
        sys.stderr.write(f"[AGENT_FALLBACK_ERROR]: {err}\n")
        legal = obs.get("legal_actions", [])
        return legal[0].get("index", 0) if legal else 0
```

### 2.2 Decision Pipeline Flowchart

```
                 Incoming State Observation (obs)
                               │
                               ▼
                    Extract legal_actions
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
          Empty actions?             Non-empty actions
                 │                           │
                 ▼                           ▼
              Return 0         Evaluate 5 Surgical Patterns
                                             │
      ┌───────────────────────┬──────────────┼───────────────────────┬──────────────────────┐
      │                       │              │                       │                      │
Pattern 5               Pattern 1      Pattern 3               Pattern 2              Pattern 4
Anti-Immunity           Anti-Tank      Bench Restraint         Energy Spillover       Alakazam Cap
      │                       │              │                       │                      │
Target non-immune       Target 1-shot  Filter out benching     Route attachment       Route attachment
bench via Gust          bench via Gust & re-score              to bench               to bench
      │                       │              │                       │                      │
      └───────────────────────┴──────────────┼───────────────────────┴──────────────────────┘
                                             │
                                     No Pattern Fired
                                     (95.09% of Turns)
                                             │
                                             ▼
                               Execute Base Aggressive Action
                                             │
                             1. Lethal KO (1000 + dmg)
                             2. Energy Accel (600)
                             3. Card Draw / Tutoring (400)
                             4. Non-Lethal Attack (500 + dmg)
                             5. Bench Basic (300)
                             6. Pass / Delay (0)
```

---

## 3. The 5 Condition-Specific Surgical Overrides

Across 185 historical live games and 1,225 high-ladder replays, losses clustered into specific avoidable tactical failures. The 5 surgical overrides directly patch these failure modes:

### Override 1: Anti-Tank Retaliation Gust (`detect_pattern_1_anti_tank_gust`)
- **Trigger**: Opponent active has $\ge 160$ Max HP, possesses a lethal counter-attack ready on their turn, and our bench has a confirmed 1-shot KO target available.
- **Action**: Intercepts suicidal chip attack into the tank; plays `BOSS_ORDERS` or `GUST` to eliminate the fragile benched Pokémon.
- **Historical Evidence**: Eliminates the 8 over-aggression losses identified in V1 live matches. Trigger rate: **1.45%**.

### Override 2: Active Energy Spillover (`detect_pattern_2_loaded_energy_spillover`)
- **Trigger**: Active attacker already holds $\ge 3$ attached energies and our bench contains at least 1 backup Pokémon.
- **Action**: Routes additional attachments (`ATTACH_BENCH` or `TEAL_DANCE_BENCH`) to bench attackers rather than over-saturating the active.
- **Historical Evidence**: Prevents energy dissipation when the active is knocked out. Trigger rate: **1.82%**.

### Override 3: Endgame Bench Restraint (`detect_pattern_3_endgame_bench_restraint`)
- **Trigger**: Opponent has $\le 2$ prize cards remaining, our active is healthy ($\ge 140$ HP, $\ge 2$ energy), and bench already contains $\ge 1$ ready attacker.
- **Action**: Vetoes basic bench expansion (`NEST_BALL`, `BUDDY_POFFIN`, `BENCH_BASIC`); redirects to the next highest aggressive action (`ATTACK` or `ATTACH`).
- **Historical Evidence**: Prevents offering a 2-prize bench-gust KO that loses the game. Reverses **13 of 13** V3 live failure replays ($p = 0.0034$). Trigger rate: **0.85%**.

### Override 4: Alakazam Energy Cap (`detect_pattern_4_alakazam_energy_cap`)
- **Trigger**: Opponent identified as Alakazam archetype, active has $\ge 2$ energy, and bench contains $\ge 1$ Pokémon.
- **Action**: Caps energy attachment on the active to exactly 2; diverts further energy to bench.
- **Historical Evidence**: Alakazam's *Psychic* deals $10 + 30 \times E_{\text{opp\_active}}$. Restricting active energy to 2 caps incoming damage at 70 instead of 130+, forcing a 3-shot clock instead of a 2-shot clock. Trigger rate: **0.52%**.

### Override 5: Anti-Immunity Gust (`detect_pattern_5_anti_immunity_gust`)
- **Trigger**: Opponent active possesses an ex-damage immunity ability (e.g. Cornerstone Mask Ogerpon ex's *Cornerstone Stance* or Mimikyu's *Safeguard*) and opponent bench is non-empty.
- **Action**: Vetoes attacks dealing 0 damage; executes `BOSS_ORDERS` or `GUST` to bring up a vulnerable bench target.
- **Historical Evidence**: Eliminates the 0% auto-loss observed against Cornerstone Mask ex in high-Elo August meta. Trigger rate: **0.27%**.

---

## 4. Default Base Aggressive Priority Engine

When no surgical pattern fires (95.09% of decisions), the engine executes an unconstrained greedy priority ladder:

$$\text{Score}(a) = \begin{cases} 
1000 + \text{damage} & \text{if } a \text{ is a lethal knockout attack} \\
600 & \text{if } a \in \{\text{TEAL\_DANCE}, \text{ATTACH\_ENERGY}, \text{ATTACH\_ACTIVE}\} \\
500 + \text{damage} & \text{if } a \in \{\text{ATTACK}, \text{MYRIAD\_LEAF\_REAP}, \text{PSYCHIC}\} \\
400 & \text{if } a \in \{\text{BUG\_CATCHING\_SET}, \text{PROFESSORS\_RESEARCH}, \text{IONO}, \text{BUDDY\_POFFIN}\} \\
300 & \text{if } a \in \{\text{NEST\_BALL}, \text{BENCH\_BASIC}\} \\
10 & \text{for routine legal options} \\
0 & \text{if } a \in \{\text{PASS}, \text{END\_TURN}\}
\end{cases}$$

Key Sequencing Properties:
1. **Lethal Priority**: If any legal attack knocks out the defending Pokémon, it outranks all setup.
2. **Pre-Attack Acceleration**: Energy attachments and draw cards score higher than non-lethal attacks, ensuring the agent powers up and draws cards before ending its turn with an attack.
3. **Terminal Discipline**: Non-lethal attacks end the turn and thus score above basic expansion, maintaining maximum offensive pressure.

---

## 5. Packaged Deck Composition (`deck.csv`)

The deck packaged within `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` is the 60-card **Alakazam Master V5** decklist (`0f8fb632ade2833645af8c6ffe2b282fe24e7446ee8b23f3e468b8410d8ea36c`):

| Card ID | Quantity | Card Name | Expansion / Collection | Role |
|---|---|---|---|---|
| **741** | 4 | Abra | Base Set | Line Starter |
| **742** | 4 | Kadabra | Base Set | Evolution Bridge |
| **743** | 4 | Alakazam | Base Set | Payoff Attacker (*Psychic*, bench spread) |
| **305** | 4 | Dunsparce | Base Set | Draw Engine Starter |
| **66** | 3 | Dudunsparce | Base Set | Draw Engine Payoff (*Run Away Draw*) |
| **1079** | 4 | Rare Candy | Trainer Item | Stage-2 Evolution Acceleration |
| **1081** | 4 | Enhanced Hammer | Trainer Item | Special Energy Denial |
| **1086** | 4 | Buddy-Buddy Poffin | Trainer Item | Basic Search Tutoring |
| **1097** | 3 | Night Stretcher | Trainer Item | Discard Recursion |
| **1129** | 1 | Sacred Ash | Trainer Item | Deck Shuffling / Anti-Deckout |
| **1152** | 4 | Poké Pad | Trainer Item | Item / Supporter Recovery |
| **1182** | 3 | Boss's Orders | Trainer Supporter | Tactical Gust (Target Selection) |
| **1184** | 1 | Lana's Aid | Trainer Supporter | Recovery Tech |
| **1225** | 4 | Hilda | Trainer Supporter | Consistent Draw |
| **1231** | 4 | Dawn | Trainer Supporter | Setup Tutoring |
| **1264** | 1 | Battle Cage | Trainer Stadium | Damage Control / Anti-Bench Disruption |
| **19** | 4 | Telepath Psychic Energy | Special Energy | Attacker Power / Synergy |
| **5** | 3 | Basic {P} Energy | Basic Energy | Basic Psychic Energy |
| **13** | 1 | Enriching Energy | Special Energy | ACE SPEC / Tech Energy |
| **Total** | **60** | | | **100% Rule Compliant** |

### Deck Mechanics & Mulligan Rate:
- **Basic Count**: 8 Basics (4 Abra + 4 Dunsparce).
- **Mulligan Probability**: $P(\text{Mulligan}) = \frac{\binom{52}{7}}{\binom{60}{7}} = 14.20\%$, down dramatically from the 60.05% mulligan rate of 4-Basic Ogerpon builds.
- **Evolution Consistency**: 4 Rare Candy + 4 Kadabra ensure that Abra evolves into Alakazam by Turn 2 in $>82\%$ of games.

---

## 6. Monolithic Repository Core (`main.py`)

In addition to the lightweight submission bundle, the repository maintains `main.py` (3,992 lines) as the canonical research and local evaluation agent:
1. **Validation & Resolution Harness**: Wraps every decision in `_validate_result` and `resolve_selection`, ensuring zero illegal action indices.
2. **Feature Flags**: Supports toggling all historical research interventions via environment variables or module attributes:
   - `PTCG_V3_EVAL`: 1-ply analytic option evaluation.
   - `PTCG_LEARNED_VALUE`: 170-dim MLP value function scoring.
   - `PTCG_SEARCH`: Belief-sampled determinized Monte-Carlo tree search.
   - `PTCG_BC`: Two-headed Behavior Cloning inference.
3. **Card Tracker & Belief Sampling**: Provides omniscient and belief-sampled determinizations over unobserved deck and hand zones.
4. **Time Governor**: Adaptive budget allocation tracking `remainingOverageTime` with exponential moving averages and graceful degradation ladders.

---

## 7. Performance Constraints & Empirical Verification

| Specification Metric | Target Requirement | Measured System Value | Verification Source |
|---|---|---|---|
| **Decision Latency (Mean)** | < 1,000 ms | **0.0011 ms** | `kaggle_compatibility_fix_report.json` |
| **Decision Latency (P99)** | < 1,000 ms | **0.0021 ms** | `kaggle_compatibility_fix_report.json` |
| **Single-Decision Max** | < 15,000 ms | **0.0540 ms** | 10k Decisions Profile |
| **Memory Footprint** | < 250 MB | **< 15 MB** | Standard Python Interpreter |
| **External Dependencies** | Standard Library Only | **Zero C++ / Zero NumPy** | Import Audit |
| **50-Process Stress** | 0 Deadlocks / 0 Crashes | **50 / 50 PASSED** | Multiprocessing Pool Test |
| **Continuous Decisions** | 100% Legal Selections | **10,000 / 10,000 PASSED** | Stress Engine Runner |
| **Dynamic Exec Compatibility** | No `__file__` Dependency | **100% Compatible** | Kaggle Loader Verification |
