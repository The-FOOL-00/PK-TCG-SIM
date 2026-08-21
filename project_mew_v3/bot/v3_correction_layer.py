"""V3 High-Elo Minimal Correction Layer for Project Mew.

Applies minimal, verified high-confidence corrections around V1 Strong Tactical policy.
"""

from typing import Dict, List, Any
from project_mew_v3.bot.v3_failure_patterns import (
    detect_anti_tank_retaliation_trap,
    detect_loaded_active_energy_spillover
)

def apply_v3_minimal_correction(obs: Dict[str, Any], legal_actions: List[Dict[str, Any]], v1_action_idx: int) -> int:
    """Evaluates V1's chosen action against verified high-Elo failure patterns.
    
    If no failure pattern is detected (>=97% of turns), returns V1's action untouched.
    If a high-confidence pattern is detected, applies the narrow verified correction.
    On any unexpected exception, safely falls back to V1.
    """
    if not legal_actions or not (0 <= v1_action_idx < len(legal_actions)):
        return v1_action_idx

    v1_action = legal_actions[v1_action_idx]
    obs["legal_actions"] = legal_actions

    try:
        # Pattern 1: Anti-Tank Retaliation Trap
        p1_correction = detect_anti_tank_retaliation_trap(obs, v1_action)
        if p1_correction is not None and 0 <= p1_correction < len(legal_actions):
            return p1_correction

        # Pattern 2: Loaded Active Energy Spillover
        p2_correction = detect_loaded_active_energy_spillover(obs, v1_action)
        if p2_correction is not None and 0 <= p2_correction < len(legal_actions):
            return p2_correction

        # Default Fast Path: V1 untouched
        return v1_action_idx
    except Exception:
        # Safe non-sticky fallback to V1
        return v1_action_idx
