"""V5 High-Elo Adaptive Policy for Project Mew.

Preserves Strong Tactical offensive speed while adding:
- Pattern 1: Anti-Tank Retaliation Trap
- Pattern 2: Active Energy Spillover
- Pattern 3: Endgame Bench Restraint
- Pattern 4: Immunity Wall & Damage Denial Bypass (Cornerstone Mask ex / Crustle)
"""

from typing import Dict, List, Any
from project_mew_v5_research.bot.v5_failure_patterns import (
    detect_anti_tank_retaliation_trap,
    detect_loaded_active_energy_spillover,
    detect_endgame_bench_gust_trap,
    detect_immunity_wall_bypass
)

def select_v5_action(obs: Dict[str, Any], legal_actions: List[Dict[str, Any]]) -> int:
    """V5 Decision Selector:
    1. Evaluates all legal options under pure Strong Tactical scoring.
    2. Identifies top preferred action index.
    3. Evaluates against minimal high-confidence failure pattern detectors (P1, P2, P3, P4).
    4. If no failure pattern is present (>=95.0% of turns), returns fast path untouched.
    5. If a high-Elo failure pattern is detected, applies narrow verified correction.
    """
    if not legal_actions:
        return 0

    # Step 1: Pure Strong Tactical Scoring
    v1_scores = []
    player = obs.get("player", {})
    opponent = obs.get("opponent", {})
    opp_active = opponent.get("active", {})
    opp_active_hp = opp_active.get("hp", 0) if opp_active else 0

    for idx, act in enumerate(legal_actions):
        atype = act.get("type", 0)
        score = 100.0

        if atype == 1: # Attack
            dmg = act.get("damage", 0)
            if dmg >= opp_active_hp and opp_active_hp > 0:
                score += 1000.0 # Lethal KO
            else:
                score += 500.0  # Aggressive tempo chip
        elif atype == 4: # Trainer / Supporter / Item
            score += 200.0
        elif atype in (2, 3): # Energy / Ability
            target = act.get("target", -1)
            score += 150.0 if target == 0 else 120.0
        elif atype == 5: # Retreat
            score += 50.0
        else: # Pass / End
            score += 0.0

        v1_scores.append((score, idx))

    v1_scores.sort(key=lambda x: x[0], reverse=True)
    v1_best_idx = v1_scores[0][1]

    # Step 2: Minimal High-Elo Correction Layer (P1, P2, P3, P4)
    v1_action = legal_actions[v1_best_idx]
    obs["legal_actions"] = legal_actions

    try:
        # Pattern 4: Immunity Wall Bypass (P0 Priority against Cornerstone ex)
        p4 = detect_immunity_wall_bypass(obs, v1_action)
        if p4 is not None and 0 <= p4 < len(legal_actions):
            return p4

        # Pattern 1: Anti-Tank Retaliation Trap
        p1 = detect_anti_tank_retaliation_trap(obs, v1_action)
        if p1 is not None and 0 <= p1 < len(legal_actions):
            return p1

        # Pattern 2: Loaded Active Energy Spillover
        p2 = detect_loaded_active_energy_spillover(obs, v1_action)
        if p2 is not None and 0 <= p2 < len(legal_actions):
            return p2

        # Pattern 3: Endgame Bench Restraint
        p3 = detect_endgame_bench_gust_trap(obs, v1_action)
        if p3 is not None and 0 <= p3 < len(legal_actions):
            return p3

        # Default Fast Path: Strong Tactical untouched
        return v1_best_idx
    except Exception:
        return v1_best_idx
