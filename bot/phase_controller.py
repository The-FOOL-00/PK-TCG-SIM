"""Strategic Game-Phase Controller for BS-CEI V1.5.

Classifies the dynamic game state into one of 5 strategic operational phases:
1. SETUP: Initial board stabilization (lone active, fragile bench, setup pieces unevolved).
2. DEVELOPMENT: Midgame expansion (active attacking, powering/evolving backup bench attackers).
3. PRIZE_RACE: Symmetrical offensive combat (both sides established, trading KOs).
4. ENDGAME: Final prize convergence (<=2 prizes remaining, decisive lethal turns).
5. EMERGENCY / SURVIVAL: Critical jeopardy (opponent lethal threat, lone vulnerable active, deckout hazard).

The classification is state-driven (active HP, bench count, energy load, prize deficit, KO threat)
rather than turn-driven alone.
"""

from enum import Enum
from typing import Dict, Any, Tuple


class GamePhase(Enum):
    SETUP = "SETUP"
    DEVELOPMENT = "DEVELOPMENT"
    PRIZE_RACE = "PRIZE_RACE"
    ENDGAME = "ENDGAME"
    EMERGENCY = "EMERGENCY"


def classify_phase(cur: dict, me: int = 0) -> GamePhase:
    """Classifies the dynamic strategic phase from public game state."""
    players = cur.get("players") or [{}, {}]
    mine = players[me]
    opp = players[1 - me]

    my_active = mine.get("active") or []
    my_bench = mine.get("bench") or []
    my_prizes = len(mine.get("prize") or [])
    my_deck = mine.get("deckCount") or 0

    opp_active = opp.get("active") or []
    opp_bench = opp.get("bench") or []
    opp_prizes = len(opp.get("prize") or [])

    # Extract our Active status
    my_active_card = my_active[0] if my_active else None
    my_active_hp = my_active_card.get("hp", 0) if my_active_card else 0
    my_active_max_hp = my_active_card.get("maxHp", 1) if my_active_card else 1
    my_active_energy = len(my_active_card.get("energy") or []) if my_active_card else 0

    # Count benched basics / backup ready attackers
    benched_count = sum(1 for p in my_bench if p is not None)
    benched_energies = sum(len(p.get("energy") or []) for p in my_bench if p is not None)

    # Opponent Active status
    opp_active_card = opp_active[0] if opp_active else None
    opp_active_energy = len(opp_active_card.get("energy") or []) if opp_active_card else 0

    # 1. EMERGENCY / SURVIVAL CONDITIONS
    # - Lone active with zero bench, or active HP <= 50% with <= 1 bench against loaded opponent
    # - Immediate deckout hazard (deck <= 5)
    is_lone_active = (benched_count == 0)
    is_fragile_active = (my_active_hp <= 70 or my_active_hp <= my_active_max_hp * 0.4)
    opp_loaded = (opp_active_energy >= 2)

    if (is_lone_active and opp_loaded) or (is_fragile_active and benched_count <= 1 and opp_loaded) or my_deck <= 4:
        return GamePhase.EMERGENCY

    # 2. ENDGAME CONDITIONS
    # - Either player has <= 2 prizes left
    if my_prizes <= 2 or opp_prizes <= 2:
        return GamePhase.ENDGAME

    # 3. SETUP CONDITIONS
    # - Bench count <= 1 and total board energy <= 2
    # - Active is basic stage 0 without enough energy to execute main attack
    if benched_count <= 1 or (my_active_energy < 2 and benched_energies == 0):
        return GamePhase.SETUP

    # 4. PRIZE RACE CONDITIONS
    # - We have an established attacker (>=2 energy) and at least 2 benched backups
    if my_active_energy >= 2 and benched_count >= 2:
        return GamePhase.PRIZE_RACE

    # 5. DEVELOPMENT (Default mid-game progression)
    return GamePhase.DEVELOPMENT
