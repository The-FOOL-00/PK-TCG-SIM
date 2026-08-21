"""Tactical Energy Attachment Sequencer for BS-CEI V1.5c / V1.7.

Evaluates energy attachment candidates between Active and Benched backup attackers.
Detects CRITICAL active HP situations where the active is likely to be KO'd next turn,
prioritizing powering a fresh benched basic (e.g. Staryu) for revenge attack readiness.
"""

from typing import Dict, Any, List, Optional, Tuple
import main as agent_mod


def evaluate_attachment_equity(
    target_slot: int,
    cur: dict,
    me: int,
) -> float:
    """Calculates tactical equity score for attaching energy to slot (0=active, 1..N=bench)."""
    players = cur.get("players") or [{}, {}]
    our_p = players[me]
    opp_p = players[1 - me]

    our_active = (our_p.get("active") or [{}])[0]
    our_bench = our_p.get("bench") or []
    opp_active = (opp_p.get("active") or [{}])[0]

    our_act_hp = our_active.get("hp", 100) if our_active else 100
    our_act_energy = len(our_active.get("energy") or []) if our_active else 0

    opp_attacks = opp_active.get("attacks") or []
    opp_max_dmg = max([a.get("damage", 0) for a in opp_attacks], default=50)

    # Detect Active Threat State
    is_critical_active = (our_act_hp <= opp_max_dmg) or (our_act_hp <= 30)
    has_backup_bench = len(our_bench) > 0

    score = 100.0

    if target_slot == 0:
        # Attaching to Active
        if is_critical_active and has_backup_bench:
            # Active is about to be knocked out: penalize sinking more energy into it
            if our_act_energy >= 2:
                score -= 300.0  # Already has attack cost, extra energy is wasted upon KO
            else:
                score -= 100.0
        else:
            # Active is healthy or needs energy to attack this turn
            if our_act_energy < 2:
                score += 500.0  # Powers active attack
            else:
                score += 50.0
    else:
        # Attaching to Bench Slot (1-indexed into bench)
        b_idx = target_slot - 1
        if 0 <= b_idx < len(our_bench):
            b_mon = our_bench[b_idx]
            b_energy = len(b_mon.get("energy") or [])
            # If active is critical, powering backup attacker creates immediate revenge readiness
            if is_critical_active:
                score += 600.0
            elif b_energy < 2:
                score += 300.0  # Developing secondary attacker
            else:
                score += 50.0

    return score
