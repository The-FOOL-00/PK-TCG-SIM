"""Refined Outcome-Conditional Tactical Safety Brake (V2.1) for Project Mew.

Key Principles:
1. Fast-Aggro Exception: In mirror (210 HP) and fast basic races, ALWAYS attack and push damage. Never delay attack.
2. Outcome-Conditional Gust: Boost Boss's Orders / Prime Catcher ONLY if our active can immediately 1-shot KO the benched target this turn.
3. Tank Retaliation Invariant: Brake attack ONLY against high-HP tanks (>160 HP remaining) with lethal retaliation when a confirmed 1-shot benched gust target exists.
"""

from typing import Dict, List, Any

def score_action_v21(obs: Dict[str, Any], action: Dict[str, Any], action_idx: int, base_score: float) -> float:
    atype = action.get("type", 0)
    
    player = obs.get("player", {})
    opponent = obs.get("opponent", {})
    
    active = player.get("active", {})
    opp_active = opponent.get("active", {})
    bench = player.get("bench", [])
    opp_bench = opponent.get("bench", [])
    
    active_hp = active.get("hp", 0) if active else 0
    opp_active_hp = opp_active.get("hp", 0) if opp_active else 0
    active_energy = active.get("energyCount", 0) if active else 0

    # Calculate active attack power (Myriad Leaf Shower: 30 + 30 * active_energy)
    active_attack_dmg = 30 + 30 * active_energy

    # Rule 1: Bench Energy Distribution (when Active has >= 3 energies)
    if atype in (2, 3): # Energy Attach or Teal Dance
        target = action.get("target", -1) # 0 = Active, >0 = Bench
        if target == 0 and active_energy >= 3 and len(bench) > 0:
            return base_score - 120.0
        elif target > 0 and active_energy >= 3:
            return base_score + 150.0

    # Rule 2: Outcome-Conditional Gust (Boss's Orders / Prime Catcher)
    # ONLY boost if Active has enough attack damage to 1-shot KO the benched target!
    if atype == 4:
        card_id = action.get("cardId", 0)
        if card_id in (1182, 1088): # Boss's Orders / Prime Catcher
            koable_bench = any(0 < b.get("hp", 999) <= active_attack_dmg for b in opp_bench if b)
            if koable_bench:
                # Guaranteed 1-shot KO conversion!
                return base_score + 500.0

    # Rule 3: Tank Retaliation Invariant
    if atype == 1: # Attack
        attack_dmg = action.get("damage", 0)
        is_lethal = (attack_dmg >= opp_active_hp and opp_active_hp > 0)

        if is_lethal:
            return base_score + 1000.0
        else:
            # Check if opponent is a high-HP Tank (>160 HP)
            is_high_hp_tank = (opp_active_hp > 160)
            opp_energy = opp_active.get("energyCount", 0) if opp_active else 0
            
            # If fighting a high-HP tank with lethal counter-attack ready AND a 1-shot bench gust exists
            if is_high_hp_tank and opp_energy >= 2 and active_hp <= 120:
                koable_bench = any(0 < b.get("hp", 999) <= active_attack_dmg for b in opp_bench if b)
                if koable_bench:
                    return base_score - 100.0 # Redirect to gust

    return base_score
