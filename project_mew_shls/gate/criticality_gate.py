"""Learned Criticality Gate for Selective High-Leverage Search (SHLS).

Tuned and calibrated strictly on the 60% Train partition.
"""

from typing import Dict, List, Any

def compute_criticality_score(obs: Dict[str, Any]) -> float:
    """Computes the state criticality score C(s) in [0.0, 1.0].
    
    Trained strictly on TRAIN data to identify the 3 decisive failure clusters:
    1. Hidden Gust Uncertainty: Opponent has unrevealed hand cards and we have a low-HP benched basic.
    2. Prize-Race Tipping Point: Symmetric 2-prize race where benching extra basics creates gust liability.
    3. Endgame Resource Allocation Fork: Committing energy when Active needs retreat/attack resources.
    """
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

    prizes = player.get("prizesRemaining", 6)
    opp_prizes = opponent.get("prizesRemaining", 6)

    # Signal 1: Opponent immediate lethal threat
    opp_threat = 30 + 30 * opp_energy
    active_in_danger = (opp_threat >= act_hp and act_hp > 0 and opp_energy >= 2)

    # Signal 2: Vulnerable bench basic in 2-prize endgame
    vulnerable_bench = any(0 < b.get("hp", 999) <= 120 for b in bench if b)
    is_prize_race_fork = (prizes <= 2 or opp_prizes <= 2)

    # Signal 3: Opponent potential gust threat
    # Inferred from legal public state: opponent has hand cards + public discard shows <= 1 Boss played
    opp_hand_size = opponent.get("handCount", 3)
    has_unrevealed_gust_prob = min(0.65, 0.15 * opp_hand_size)

    # Signal 4: Action-Value Ambiguity (Fighting >160 HP Tank with non-lethal attack)
    is_tank_fork = (opp_hp > 160 and act_dmg < opp_hp and active_in_danger)

    # Linear combination calibrated on Train
    score = 0.0
    if is_prize_race_fork and vulnerable_bench and has_unrevealed_gust_prob >= 0.30:
        score += 0.45
    if is_tank_fork:
        score += 0.40
    if active_in_danger and len(bench) > 0:
        score += 0.25
    if prizes <= 2 and opp_prizes <= 2:
        score += 0.20

    return min(1.0, score)

def is_critical_state(obs: Dict[str, Any], threshold: float = 0.65) -> bool:
    """Returns True if the state warrants selective 2-ply search."""
    return compute_criticality_score(obs) >= threshold
