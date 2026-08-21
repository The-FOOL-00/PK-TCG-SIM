"""Project Mew - Config & Heuristic Weights
"""

# Centralized Heuristic Weight Parameters
HEURISTIC_WEIGHTS = {
    # Action Type Weights
    "WEIGHT_LETHAL": 100000.0,
    "WEIGHT_BENCH_URGENT": 3500.0,
    "WEIGHT_ATTACH_ENERGY": 3000.0,
    "WEIGHT_EVOLVE": 2800.0,
    "WEIGHT_PLAY_ITEM": 2400.0,
    "WEIGHT_BENCH": 2300.0,
    "WEIGHT_PLAY_SUPPORTER": 2150.0,
    "WEIGHT_ATTACH_TOOL": 2100.0,
    "WEIGHT_ABILITY": 2060.0,
    "WEIGHT_PLAY_STADIUM": 2030.0,
    "WEIGHT_ATTACK_BASE": 1000.0,
    "WEIGHT_RETREAT": -500.0,
    "WEIGHT_DISCARD_IN_PLAY": -300.0,
    "WEIGHT_END": -1000000.0,

    # Value Function Weights (State Evaluation)
    "V3_W_PRIZE": 60.0,            # Prize differential
    "V3_W_BOARD_HP": 0.10,          # Board HP differential
    "V3_W_ATTACKER_ENERGY": 40.0,   # Useful energy on attacker
    "V3_W_KO_THREAT": 60.0,         # Immediate KO available
    "V3_W_BENCH": 12.0,             # Bench presence
    "V3_W_HAND": 2.0,               # Hand size bonus
    "V3_W_ACTIVE": 30.0,            # Active slot preference
    
    # Priority Factors
    "ACTIVE_TARGET_BONUS": 100.0,
    "POWERING_UP_BONUS": 50.0,
    "EVO_TARGET_BONUS": 150.0,
}

# Search / MCTS Settings
SEARCH_CONFIG = {
    "DEFAULT_DET": 16,
    "DEFAULT_ROLL": 2,
    "DEFAULT_TOPK": 4,
    "MAX_DECISION_TIME_S": 3.0,
    "SAFETY_MARGIN_S": 10.0,
}
