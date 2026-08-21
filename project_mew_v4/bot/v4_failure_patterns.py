"""V4 Failure Pattern Detectors for Project Mew.

Incorporates:
- Pattern 1: Anti-Tank Retaliation Trap (V3)
- Pattern 2: Loaded Active Energy Over-Stacking (V3)
- Pattern 3: Endgame Bench Restraint / Anti-Gust Trap (V4 NEW)
"""

from typing import Dict, List, Any, Optional

def detect_anti_tank_retaliation_trap(obs: Dict[str, Any], candidate_action: Dict[str, Any]) -> Optional[int]:
    """Pattern 1: Retaliation trap against >160 HP tanks."""
    atype = candidate_action.get("type", 0)
    if atype != 1:
        return None

    player = obs.get("player", {})
    opponent = obs.get("opponent", {})
    active = player.get("active", {})
    opp_active = opponent.get("active", {})
    opp_bench = opponent.get("bench", [])

    act_hp = active.get("hp", 0) if active else 0
    act_energy = active.get("energyCount", 0) if active else 0
    act_dmg = 30 + 30 * act_energy

    opp_hp = opp_active.get("hp", 0) if opp_active else 0
    opp_energy = opp_active.get("energyCount", 0) if opp_active else 0
    opp_threat = 30 + 30 * opp_energy

    if opp_hp <= 160 or act_dmg >= opp_hp:
        return None

    if opp_energy < 2 or opp_threat < act_hp or act_hp > 120:
        return None

    legal_actions = obs.get("legal_actions", [])
    for idx, act in enumerate(legal_actions):
        if act.get("type") == 4 and act.get("cardId") in (1182, 1088):
            has_1shot_bench = any(0 < b.get("hp", 999) <= act_dmg for b in opp_bench if b)
            if has_1shot_bench:
                return idx

    return None


def detect_loaded_active_energy_spillover(obs: Dict[str, Any], candidate_action: Dict[str, Any]) -> Optional[int]:
    """Pattern 2: Routing energy to bench when Active has >=3 energy."""
    atype = candidate_action.get("type", 0)
    if atype not in (2, 3):
        return None

    target = candidate_action.get("target", -1)
    if target != 0:
        return None

    player = obs.get("player", {})
    active = player.get("active", {})
    bench = player.get("bench", [])
    act_energy = active.get("energyCount", 0) if active else 0

    if act_energy >= 3 and len(bench) > 0:
        legal_actions = obs.get("legal_actions", [])
        for idx, act in enumerate(legal_actions):
            if act.get("type") in (2, 3) and act.get("target", -1) > 0:
                return idx

    return None


def detect_endgame_bench_gust_trap(obs: Dict[str, Any], candidate_action: Dict[str, Any]) -> Optional[int]:
    """Pattern 3 (NEW in V4): Endgame Bench Restraint.
    
    Triggers ONLY when:
    1. Candidate action is playing/benching a Basic Pokémon (e.g. Nest Ball, Basic from hand).
    2. Opponent has <= 2 prizes remaining (immediate game-ending gust threat).
    3. Our Active Ogerpon is fully operational (HP >= 120, Energy >= 2) and capable of closing the match.
    4. Opponent has not exhausted all Boss's Orders in public discard (public Boss count < 2).
    5. Action is deprioritized in favor of direct active attack / energy acceleration.
    """
    atype = candidate_action.get("type", 0)
    card_id = candidate_action.get("cardId", 0)

    # Condition 1: Candidate action benches a basic Pokémon
    is_bench_action = (atype == 4 and card_id in (1180, 1181)) or (atype == 0 and candidate_action.get("inPlayArea") == "bench")
    if not is_bench_action:
        return None

    player = obs.get("player", {})
    opponent = obs.get("opponent", {})

    opp_prizes = opponent.get("prizesRemaining", 6)
    active = player.get("active", {})
    act_hp = active.get("hp", 0) if active else 0
    act_energy = active.get("energyCount", 0) if active else 0

    # Condition 2: Opponent is at <= 2 prizes
    if opp_prizes > 2:
        return None

    # Condition 3: Active is healthy & energized
    if act_hp < 120 or act_energy < 2:
        return None

    # Condition 4: Opponent has public gust threat (public discard has < 2 Boss's Orders)
    opp_discard = opponent.get("discard", [])
    boss_discarded = sum(1 for c in opp_discard if c in (1182, 1088))
    if boss_discarded >= 2:
        return None # Opponent exhausted all gust cards; benching is safe

    # Resolution: Find direct attack or active energy action
    legal_actions = obs.get("legal_actions", [])
    # Prefer immediate attack
    for idx, act in enumerate(legal_actions):
        if act.get("type") == 1:
            return idx
    # Otherwise prefer energy attachment
    for idx, act in enumerate(legal_actions):
        if act.get("type") in (2, 3):
            return idx

    return None
