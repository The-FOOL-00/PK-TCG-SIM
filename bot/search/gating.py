"""Project Mew - Selective Search Gating & Critical Decision Classifier

Classifies decisions as routine vs critical to gate MCTS / PIMC search invocation.
"""

from typing import Dict, Any, List


def is_critical_decision(obs: dict, legal_options: List[dict]) -> bool:
    """Returns True if state requires selective forward search, False for fast heuristic.
    
    Critical criteria:
    1. Multiple legal attack choices available.
    2. Endgame state (either player has <= 2 prizes remaining).
    3. High option branching on MAIN turn (>= 5 options).
    4. Important evolution / switching commitment decisions.
    """
    if not obs or "current" not in obs or "select" not in obs:
        return False

    sel = obs["select"]
    cur = obs["current"]

    # Only MAIN-phase single-select decisions are searchable
    if sel.get("type") != 0 or sel.get("minCount", 1) != 1 or sel.get("maxCount", 1) != 1:
        return False

    options = sel.get("option") or []
    if len(options) <= 1:
        return False

    players = cur.get("players") or [{}, {}]
    me = cur.get("yourIndex", 0)
    mine = players[me] if len(players) > me else {}
    opp = players[1 - me] if len(players) > (1 - me) else {}

    # 1. Endgame (Prizes <= 2)
    my_prizes = len(mine.get("prize") or [])
    opp_prizes = len(opp.get("prize") or [])
    if my_prizes <= 2 or opp_prizes <= 2:
        return True

    # 2. Count attack options (OT_ATTACK = 13)
    attack_count = sum(1 for o in options if o and o.get("type") == 13)
    if attack_count >= 2:
        return True

    # 3. High option complexity on MAIN phase
    if len(options) >= 6:
        return True

    # 4. Evolution / Stage 1 or Stage 2 choices (OT_EVOLVE = 9)
    evolve_count = sum(1 for o in options if o and o.get("type") == 9)
    if evolve_count >= 2:
        return True

    return False
