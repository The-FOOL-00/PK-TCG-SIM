"""V5 Failure Pattern Detectors for Project Mew.

Incorporates:
- Pattern 1: Anti-Tank Retaliation Trap (V3/V4 verified)
- Pattern 2: Loaded Active Energy Over-Stacking (V3/V4 verified)
- Pattern 3: Endgame Bench Restraint / Anti-Gust Trap (V4 verified)
- Pattern 4: Immunity Wall & Damage Denial Bypass (V5 NEW — counters Cornerstone Mask ex & Crustle)
"""

from typing import Dict, List, Any, Optional

# Card IDs for Reference
ID_TEAL_OGERPON_EX = 96
ID_CORNERSTONE_OGERPON_EX = 1092
ID_CRUSTLE = 1079
ID_BATTLE_CAGE = 1176
ID_BOSS_ORDERS = 1182
ID_PRIME_CATCHER = 1088
ID_NEST_BALL = 1180
ID_ULTRA_BALL = 1181
ID_POFFIN = 1094

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
        if act.get("type") == 4 and act.get("cardId") in (ID_BOSS_ORDERS, ID_PRIME_CATCHER):
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
    """Pattern 3 (V4 Verified): Endgame Bench Restraint."""
    atype = candidate_action.get("type", 0)
    card_id = candidate_action.get("cardId", 0)

    is_bench_action = (atype == 4 and card_id in (ID_NEST_BALL, ID_ULTRA_BALL, ID_POFFIN)) or (atype == 0 and candidate_action.get("inPlayArea") == "bench")
    if not is_bench_action:
        return None

    player = obs.get("player", {})
    opponent = obs.get("opponent", {})

    opp_prizes = opponent.get("prizesRemaining", 6)
    active = player.get("active", {})
    act_hp = active.get("hp", 0) if active else 0
    act_energy = active.get("energyCount", 0) if active else 0

    if opp_prizes > 2:
        return None

    if act_hp < 120 or act_energy < 2:
        return None

    opp_discard = opponent.get("discard", [])
    boss_discarded = sum(1 for c in opp_discard if c in (ID_BOSS_ORDERS, ID_PRIME_CATCHER))
    if boss_discarded >= 2:
        return None

    legal_actions = obs.get("legal_actions", [])
    for idx, act in enumerate(legal_actions):
        if act.get("type") == 1:
            return idx
    for idx, act in enumerate(legal_actions):
        if act.get("type") in (2, 3):
            return idx

    return None


def detect_immunity_wall_bypass(obs: Dict[str, Any], candidate_action: Dict[str, Any]) -> Optional[int]:
    """Pattern 4 (V5 NEW): Wall & Immunity Counter-Bypass.
    
    Triggers when:
    1. Opponent active is Cornerstone Mask Ogerpon ex (ID 1092, immune to ex) or Crustle (ID 1079 with wall).
    2. Our active is a Pokemon ex (e.g. Teal Mask Ogerpon ex ID 96).
    3. Candidate action is attacking into 0-damage immunity.
    4. Legally redirects to:
       a) Boss's Orders / Prime Catcher on a vulnerable bench target, OR
       b) Energy attachment to a non-ex tech attacker on bench, OR
       c) Setup action to prepare counter line.
    """
    atype = candidate_action.get("type", 0)
    if atype != 1:
        return None

    player = obs.get("player", {})
    opponent = obs.get("opponent", {})
    active = player.get("active", {})
    opp_active = opponent.get("active", {})
    opp_bench = opponent.get("bench", [])

    act_id = active.get("id", 0) if active else 0
    opp_id = opp_active.get("id", 0) if opp_active else 0

    is_our_active_ex = (act_id in (ID_TEAL_OGERPON_EX, 1086, 1046, 1095, 1114, 1134))
    is_opp_immune = (opp_id == ID_CORNERSTONE_OGERPON_EX)

    if not (is_our_active_ex and is_opp_immune):
        return None

    # Opponent active is 100% immune to our active's damage!
    legal_actions = obs.get("legal_actions", [])

    # Priority A: Gust to any benched target
    for idx, act in enumerate(legal_actions):
        if act.get("type") == 4 and act.get("cardId") in (ID_BOSS_ORDERS, ID_PRIME_CATCHER):
            if len(opp_bench) > 0:
                return idx

    # Priority B: Attach energy to benched non-ex attacker if present
    for idx, act in enumerate(legal_actions):
        if act.get("type") in (2, 3) and act.get("target", -1) > 0:
            return idx

    # Priority C: Play card advantage / draw / setup
    for idx, act in enumerate(legal_actions):
        if act.get("type") == 4:
            return idx

    return None
