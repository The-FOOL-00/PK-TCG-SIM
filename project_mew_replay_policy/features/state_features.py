"""Observable state feature extraction with strict zero-leakage guarantee."""

from typing import Dict, List, Any

def encode_observable_state(obs: Dict[str, Any]) -> List[float]:
    """Encodes legally observable state into a fixed 32-dim numerical vector.
    
    Zero future leakage:
    - No future cards
    - No hidden opponent hand/deck
    - No outcome information
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

    # Bench summary
    bench_count = len(bench)
    bench_avg_hp = sum(b.get("hp", 0) for b in bench) / max(1, bench_count)
    bench_energies = sum(b.get("energyCount", 0) for b in bench)

    opp_bench_count = len(opp_bench)
    opp_bench_koable = sum(1 for b in opp_bench if 0 < b.get("hp", 999) <= act_dmg)

    features = [
        act_hp / 300.0,
        act_energy / 5.0,
        act_dmg / 300.0,
        opp_hp / 300.0,
        opp_energy / 5.0,
        float(opp_hp > 160), # High-HP tank indicator
        float(act_dmg >= opp_hp and opp_hp > 0), # Lethal attack available
        prizes / 6.0,
        opp_prizes / 6.0,
        (opp_prizes - prizes) / 6.0, # Prize differential
        bench_count / 5.0,
        bench_avg_hp / 300.0,
        bench_energies / 5.0,
        opp_bench_count / 5.0,
        opp_bench_koable / 5.0,
        float(opp_bench_koable > 0), # Immediate bench gust KO available
        float(act_energy >= 3),      # Loaded active indicator
        float(act_hp <= 120 and opp_energy >= 2) # Active in retaliation danger
    ]
    
    # Pad to 32 dimensions
    while len(features) < 32:
        features.append(0.0)

    return features[:32]
