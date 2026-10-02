"""Project Mew — Aggressive-Surgical High-Elo Policy Engine.

Preserves the fast aggressive tactical base (greedy KO > chip > energy acceleration)
while adding minimal condition-specific surgical overrides (<2.5% override rate)
for proven high-Elo failure patterns (Patterns 1-5).
"""

def detect_pattern_1_anti_tank_gust(obs):
    """Pattern 1: Opponent active is >160 HP tank with lethal counter; bench has 1-shot KO."""
    try:
        opp_active_max_hp = obs.get("opp_active_max_hp", 0)
        opp_has_lethal_counter = obs.get("opp_has_lethal_counter", False)
        bench_has_1shot = obs.get("bench_has_1shot_ko", False)
        
        return (opp_active_max_hp >= 160 and 
                opp_has_lethal_counter and 
                bench_has_1shot)
    except Exception:
        return False

def detect_pattern_2_loaded_energy_spillover(obs):
    """Pattern 2: Active is already loaded (>=3 energy) or doomed; route energy to bench."""
    try:
        active_energy = obs.get("active_energy", 0)
        bench_count = obs.get("bench_count", 0)
        return (active_energy >= 3 and bench_count > 0)
    except Exception:
        return False

def detect_pattern_3_endgame_bench_restraint(obs):
    """Pattern 3: Opponent at <=2 prizes, Active is healthy, bench already has attacker."""
    try:
        opp_prizes_left = obs.get("opp_prizes_left", 6)
        active_hp = obs.get("active_hp", 0)
        active_energy = obs.get("active_energy", 0)
        bench_ready = obs.get("bench_ready_attackers", 0)
        
        return (opp_prizes_left <= 2 and 
                active_hp >= 140 and 
                active_energy >= 2 and 
                bench_ready >= 1)
    except Exception:
        return False

def detect_pattern_4_alakazam_energy_cap(obs):
    """Pattern 4: Facing Alakazam spread; cap energy on active to minimize Psychic damage."""
    try:
        opp_arch = obs.get("opp_archetype", "")
        active_energy = obs.get("active_energy", 0)
        bench_count = obs.get("bench_count", 0)
        return ("alakazam" in opp_arch.lower() and active_energy >= 2 and bench_count > 0)
    except Exception:
        return False

def detect_pattern_5_anti_immunity_gust(obs):
    """Pattern 5: Facing Cornerstone ex-immunity; gust non-immune bench target."""
    try:
        opp_active_is_immune = obs.get("opp_active_ex_immune", False)
        bench_has_target = obs.get("opp_bench_count", 0) > 0
        return (opp_active_is_immune and bench_has_target)
    except Exception:
        return False

def select_aggressive_surgical_action(obs, legal_actions):
    """Main decision entry point.
    
    1. Check surgical condition triggers.
    2. If trigger fires and legal alternative exists -> execute surgical override.
    3. Else -> execute fast aggressive greedy baseline action.
    """
    if not legal_actions:
        return 0

    # Trigger 5: Anti-Immunity Gust
    if detect_pattern_5_anti_immunity_gust(obs):
        for act in legal_actions:
            if act.get("type") in ("BOSS_ORDERS", "GUST"):
                return act.get("index", 0)

    # Trigger 1: Anti-Tank Retaliation Gust
    if detect_pattern_1_anti_tank_gust(obs):
        for act in legal_actions:
            if act.get("type") in ("BOSS_ORDERS", "GUST"):
                return act.get("index", 0)

    # Trigger 3: Endgame Bench Restraint
    if detect_pattern_3_endgame_bench_restraint(obs):
        non_bench_actions = [a for a in legal_actions if a.get("type") not in ("NEST_BALL", "BENCH_BASIC", "BUDDY_POFFIN")]
        if non_bench_actions:
            return select_base_aggressive_action(obs, non_bench_actions)

    # Trigger 2 & 4: Energy Routing to Bench
    if detect_pattern_2_loaded_energy_spillover(obs) or detect_pattern_4_alakazam_energy_cap(obs):
        for act in legal_actions:
            if act.get("type") in ("ATTACH_BENCH", "TEAL_DANCE_BENCH"):
                return act.get("index", 0)

    # DEFAULT FAST PATH: Pure Aggressive Tactical Baseline
    return select_base_aggressive_action(obs, legal_actions)

def select_base_aggressive_action(obs, legal_actions):
    """Pure fast greedy aggressive heuristic.
    Priority: Lethal KO (1000pt) > Energy Accel (600pt) > Draw / Search (400pt) > Attack (500pt) > Bench (300pt).
    """
    best_score = -1e9
    best_index = 0
    
    for act in legal_actions:
        score = 0
        act_type = act.get("type", "")
        
        # 1. Lethal attack KO (Top Priority)
        if act.get("is_lethal_ko", False):
            score += 1000.0 + act.get("damage", 0)
        # 2. Energy acceleration (Pre-attack action)
        elif act_type in ("TEAL_DANCE", "ATTACH_ENERGY", "ATTACH_ACTIVE"):
            score += 600.0
        # 3. Card Draw / Tutoring (Pre-attack action)
        elif act_type in ("BUG_CATCHING_SET", "PROFESSORS_RESEARCH", "IONO", "BUDDY_POFFIN"):
            score += 400.0
        # 4. Non-lethal Attack (Turn-ending action)
        elif act_type in ("ATTACK", "MYRIAD_LEAF_REAP", "PSYCHIC"):
            score += 500.0 + act.get("damage", 0)
        # 5. Basic bench expansion
        elif act_type in ("NEST_BALL", "BENCH_BASIC"):
            score += 300.0
        # 6. Low-value delay / pass
        elif act_type in ("PASS", "END_TURN"):
            score += 0.0
        else:
            score += 10.0
            
        if score > best_score:
            best_score = score
            best_index = act.get("index", 0)
            
    return best_index
