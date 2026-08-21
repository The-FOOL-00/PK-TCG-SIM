"""Selective Tactical Safety Brake Engine for Project Mew.

Implements Mode D: Strong Tactical + Selective Safety Brake:
1. Retaliation Lethal Brake: Avoids blind chip damage into incoming lethal when Gust / Retreat is superior.
2. Energy Preservation Distribution: Routes Teal Dance energy to healthy benched attackers when Active is loaded (>=3 energy) or facing lethal.
3. Tactical Gust Priority: Identifies and executes KOs on vulnerable benched targets over chipping high-HP tanks.
"""

import math
from typing import Dict, List, Any, Optional

def score_action_with_brake(obs: Dict[str, Any], action: Dict[str, Any], action_idx: int, base_score: float) -> float:
    """Modifies the base tactical score with selective safety brakes."""
    atype = action.get("type", 0)
    
    # 0 = PASS / END, 1 = ATTACK, 2 = ATTACH, 3 = ABILITY, 4 = TRAINER, 5 = RETREAT
    # Let's extract board context safely
    player = obs.get("player", {})
    opponent = obs.get("opponent", {})
    
    active = player.get("active", {})
    opp_active = opponent.get("active", {})
    bench = player.get("bench", [])
    opp_bench = opponent.get("bench", [])
    
    active_hp = active.get("hp", 0) if active else 0
    opp_active_hp = opp_active.get("hp", 0) if opp_active else 0
    active_energy = active.get("energyCount", 0) if active else 0

    # Rule 1: Energy Preservation on Teal Dance / Attachment
    # If Active already has >= 3 energy (sufficient for Myriad Leaf Shower full power)
    # or Active has <= 60 HP (vulnerable to incoming 1-shot), prefer attaching to Bench!
    if atype in (2, 3): # Energy attach or Teal Dance ability
        target = action.get("target", -1) # 0 = Active, 1..5 = Bench
        if target == 0: # Targeting Active
            if active_energy >= 3:
                # Active is already fully energized; penalize over-stacking active
                return base_score - 150.0
            if active_hp <= 60 and len(bench) > 0:
                # Active is in critical one-shot range; route energy to healthy bench
                return base_score - 200.0
        elif target > 0: # Targeting Bench
            if active_energy >= 3 or active_hp <= 60:
                # Healthy bench attachment gets bonus!
                return base_score + 180.0

    # Rule 2: Retaliation Lethal Brake on Non-Lethal Attack
    if atype == 1: # Attack action
        attack_dmg = action.get("damage", 0)
        is_lethal = (attack_dmg >= opp_active_hp and opp_active_hp > 0)
        
        if is_lethal:
            # Immediate Lethal Knockout: Highest possible priority
            return base_score + 1000.0
        else:
            # Non-lethal chip damage: Check if opponent active can 1-shot our active
            opp_energy = opp_active.get("energyCount", 0) if opp_active else 0
            # If opponent has >= 2 energy and our active is low or <= 120 HP, non-lethal attack is risky
            if opp_energy >= 2 and active_hp <= 120:
                # If we have a legal Gust or Retreat option, deprioritize blind chip attack
                return base_score - 80.0

    # Rule 3: Gust Priority on High-Value / Low-HP Bench Targets
    if atype == 4: # Trainer card (Boss's Orders / Prime Catcher)
        card_id = action.get("cardId", 0)
        if card_id in (1182, 1088): # Boss's Orders or Prime Catcher
            # If opponent has a damaged or low-HP bench Pokémon that we can KO, boost gust!
            has_koable_bench = any(b.get("hp", 999) <= 120 for b in opp_bench if b)
            if has_koable_bench:
                return base_score + 450.0

    return base_score
