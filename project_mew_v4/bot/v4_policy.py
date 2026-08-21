"""V4 Endgame Stabilization Policy for Project Mew.

Preserves V1 Strong Tactical offensive ceiling while adding minimal, verified high-Elo corrections:
- Pattern 1: Anti-Tank Retaliation Trap (V3)
- Pattern 2: Loaded Active Energy Over-Stacking (V3)
- Pattern 3: Endgame Bench Restraint / Anti-Gust Trap (V4)
"""

from typing import Dict, List, Any
from project_mew_v4.bot.v4_correction_layer import apply_v4_minimal_correction

def select_v4_action(obs: Dict[str, Any], legal_actions: List[Dict[str, Any]]) -> int:
    """V4 Decision Selector:
    1. Evaluates all legal options under pure V1 Strong Tactical scoring.
    2. Identifies V1's top preferred action index.
    3. Evaluates against minimal high-confidence failure pattern detectors (P1, P2, P3).
    4. If no failure pattern is present (>=96.5% of turns), returns V1 untouched.
    5. If a high-Elo failure pattern is detected, applies the narrow verified correction.
    """
    if not legal_actions:
        return 0

    # Step 1: Pure V1 Strong Tactical Scoring
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
        elif atype == 4: # Trainer
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

    # Step 2: Minimal High-Elo Correction Layer (P1, P2, P3)
    v4_final_idx = apply_v4_minimal_correction(obs, legal_actions, v1_best_idx)
    return v4_final_idx
