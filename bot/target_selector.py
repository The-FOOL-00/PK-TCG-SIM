"""Tactical Target Selector for BS-CEI V1.5c / V1.7.

Evaluates attack targets dynamically using prize tempo, KO sequence feasibility,
and retaliation risk, avoiding hardcoded rules while boosting high-equity 2-prize
and game-winning target candidates.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import main as agent_mod


def evaluate_target_equity(
    target_slot: int,
    opp_pokemon: dict,
    attack_dmg: int,
    cur: dict,
    me: int,
) -> float:
    """Calculates tactical equity score for attacking a specific opponent Pokémon."""
    if not opp_pokemon:
        return 0.0

    players = cur.get("players") or [{}, {}]
    our_p = players[me]
    opp_p = players[1 - me]

    our_prizes = len(our_p.get("prize") or [])
    opp_prizes = len(opp_p.get("prize") or [])

    hp = opp_pokemon.get("hp", 100)
    is_ex = opp_pokemon.get("isEx", False)
    prize_val = 2 if is_ex else 1

    score = 100.0

    # 1. Immediate Knockout Value
    if attack_dmg >= hp:
        score += 2000.0 * prize_val
        if our_prizes <= prize_val:
            # Immediate Game Lethal!
            score += 100000.0
        return score

    # 2. Two-Turn Knockout Sequence (e.g. 130 + 130 >= 210 HP EX)
    if attack_dmg * 2 >= hp:
        # High value 2-hit sequence on 2-prize EX
        if is_ex:
            score += 800.0
        else:
            score += 300.0

    # 3. Prize Differential & Tempo
    # If we are behind in prizes, cracking EX targets is the fastest comeback path
    if our_prizes > opp_prizes and is_ex:
        score += 400.0

    # 4. Energy on Target Threat
    attached_e = len(opp_pokemon.get("energy") or [])
    if attached_e >= 2:
        score += 250.0  # Removing or softening an energized threat

    # 5. Position: Active target vs Bench target
    if target_slot == 0:
        score += 100.0

    return score
