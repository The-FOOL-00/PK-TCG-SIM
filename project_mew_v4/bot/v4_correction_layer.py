"""V4 Minimal Correction Layer for Project Mew.

Applies verified high-confidence corrections (Pattern 1, Pattern 2, Pattern 3) around V1 Strong Tactical policy.
"""

from typing import Dict, List, Any
from project_mew_v4.bot.v4_failure_patterns import (
    detect_anti_tank_retaliation_trap,
    detect_loaded_active_energy_spillover,
    detect_endgame_bench_gust_trap
)

def apply_v4_minimal_correction(obs: Dict[str, Any], legal_actions: List[Dict[str, Any]], v1_action_idx: int) -> int:
    """Evaluates V1's chosen action against verified high-Elo failure patterns.
    
    Checks in priority order:
    1. Pattern 1: Anti-Tank Retaliation Trap (V3)
    2. Pattern 2: Loaded Active Energy Spillover (V3)
    3. Pattern 3: Endgame Bench Restraint / Anti-Gust Trap (V4 NEW)
    
    If no pattern is active (>=96.5% of turns), returns V1 untouched.
    On any unexpected error, safely falls back to V1.
    """
    if not legal_actions or not (0 <= v1_action_idx < len(legal_actions)):
        return v1_action_idx

    v1_action = legal_actions[v1_action_idx]
    obs["legal_actions"] = legal_actions

    try:
        # Pattern 1: Anti-Tank Retaliation Trap
        p1 = detect_anti_tank_retaliation_trap(obs, v1_action)
        if p1 is not None and 0 <= p1 < len(legal_actions):
            return p1

        # Pattern 2: Loaded Active Energy Spillover
        p2 = detect_loaded_active_energy_spillover(obs, v1_action)
        if p2 is not None and 0 <= p2 < len(legal_actions):
            return p2

        # Pattern 3: Endgame Bench Restraint (NEW)
        p3 = detect_endgame_bench_gust_trap(obs, v1_action)
        if p3 is not None and 0 <= p3 < len(legal_actions):
            return p3

        # Default Fast Path: V1 untouched
        return v1_action_idx
    except Exception:
        # Safe non-sticky fallback to V1
        return v1_action_idx
