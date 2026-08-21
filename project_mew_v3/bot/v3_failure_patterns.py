"""V3 High-Elo Failure Pattern Detectors for Project Mew.

Identifies the exact, verified failure patterns that caused V1's high-Elo collapse:
Pattern 1 (ANTI_TANK_RETALIATION): Chipping into a >160 HP tank when opponent has lethal retaliation and a 1-shot bench gust KO exists.
Pattern 2 (LOADED_ACTIVE_SPILLOVER): Over-stacking energy on active (>3 energies) when bench needs energy.
"""

from typing import Dict, List, Any, Optional

def detect_anti_tank_retaliation_trap(obs: Dict[str, Any], candidate_action: Dict[str, Any]) -> Optional[int]:
    """Pattern 1 Detector:
    Triggers ONLY when:
    1. Candidate action is an attack.
    2. Defending Active is a High-HP Tank (>160 HP remaining).
    3. Our attack is non-lethal (deals < opponent active HP).
    4. Opponent Active has lethal counter-threat ready (energy >= 2 and threat >= our Active HP).
    5. A legal 1-shot bench gust KO (Boss's Orders / Prime Catcher) exists among legal options.
    """
    atype = candidate_action.get("type", 0)
    if atype != 1: # Only checks attack actions
        return None

    player = obs.get("player", {})
    opponent = obs.get("opponent", {})

    active = player.get("active", {})
    opp_active = opponent.get("active", {})
    bench = player.get("bench", [])
    opp_bench = opponent.get("bench", [])

    act_hp = active.get("hp", 0) if active else 0
    act_energy = active.get("energyCount", 0) if active else 0
    act_dmg = 30 + 30 * act_energy

    opp_hp = opp_active.get("hp", 0) if opp_active else 0
    opp_energy = opp_active.get("energyCount", 0) if opp_active else 0
    opp_threat = 30 + 30 * opp_energy

    # Condition 1: Opponent is a high-HP tank (>160 HP)
    if opp_hp <= 160:
        return None

    # Condition 2: Our attack is non-lethal
    if act_dmg >= opp_hp:
        return None # Lethal attack is always fine

    # Condition 3: Opponent active has lethal counter-threat ready
    if opp_energy < 2 or opp_threat < act_hp or act_hp > 120:
        return None

    # Condition 4: A legal guaranteed 1-shot bench gust KO exists
    legal_actions = obs.get("legal_actions", [])
    for idx, act in enumerate(legal_actions):
        if act.get("type") == 4 and act.get("cardId") in (1182, 1088): # Boss's Orders or Prime Catcher
            has_1shot_bench = any(0 < b.get("hp", 999) <= act_dmg for b in opp_bench if b)
            if has_1shot_bench:
                return idx # Return index of guaranteed bench KO action

    return None


def detect_loaded_active_energy_spillover(obs: Dict[str, Any], candidate_action: Dict[str, Any]) -> Optional[int]:
    """Pattern 2 Detector:
    Triggers ONLY when:
    1. Candidate action attaches energy to Active.
    2. Active Ogerpon already has >= 3 attached energies.
    3. A healthy benched attacker exists.
    """
    atype = candidate_action.get("type", 0)
    if atype not in (2, 3): # Energy attach or Teal Dance
        return None

    target = candidate_action.get("target", -1)
    if target != 0: # Only checks attachments targeting Active
        return None

    player = obs.get("player", {})
    active = player.get("active", {})
    bench = player.get("bench", [])

    act_energy = active.get("energyCount", 0) if active else 0

    if act_energy >= 3 and len(bench) > 0:
        legal_actions = obs.get("legal_actions", [])
        # Find attachment targeting bench
        for idx, act in enumerate(legal_actions):
            if act.get("type") in (2, 3) and act.get("target", -1) > 0:
                return idx

    return None
