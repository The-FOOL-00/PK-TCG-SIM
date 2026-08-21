"""Hierarchical Action Classifier and Candidate Action Filter for BS-CEI V1.5.

Classifies legal actions into strategic classes:
1. TERMINAL: Instant-lethal attacks or instant-loss prevention.
2. SURVIVAL: Critical benching / retreating to avoid No-Active (Bench-Out) losses.
3. SETUP: Benching basic Pokémon, searching for basics, draw infrastructure.
4. DEVELOPMENT: Evolving Pokémon, attaching energy, preparation.
5. TACTICAL: Attacking, switching, disruption, chip damage.

Enforces the Critical Bench Safety Invariant to eliminate Bench-Out losses:
- If Active is vulnerable or bench is empty, non-terminal attacks NEVER crowd out backup basic benching.
"""

from enum import Enum
from typing import List, Dict, Any, Tuple, Optional
import main as agent_mod
from bot.phase_controller import GamePhase, classify_phase


class ActionClass(Enum):
    TERMINAL = "TERMINAL"
    SURVIVAL = "SURVIVAL"
    SETUP = "SETUP"
    DEVELOPMENT = "DEVELOPMENT"
    TACTICAL = "TACTICAL"
    PASS = "PASS"


def classify_action(opt: dict, cur: dict, me: int, phase: GamePhase) -> ActionClass:
    """Classifies a single legal option into its strategic ActionClass."""
    opt_type = opt.get("type", "")
    card_id = opt.get("cardId")
    card_info = agent_mod.CARDS.get(card_id, {}) if card_id else {}
    ctype = card_info.get("cardType", 0)

    # 1. End Turn / Pass
    if opt_type in ("end_turn", "pass") or opt.get("index") == -1:
        return ActionClass.PASS

    # 2. Attacks
    if opt_type == "attack" or "attack" in str(opt.get("name", "")).lower():
        # Check if instant lethal
        players = cur.get("players") or [{}, {}]
        opp = players[1 - me]
        opp_active = (opp.get("active") or [{}])[0]
        opp_hp = opp_active.get("hp", 999) if opp_active else 999
        my_prizes = len(players[me].get("prize") or [])

        atk_dmg = opt.get("damage", 0)
        # If lethal or takes last prize
        if (atk_dmg >= opp_hp and opp_active.get("isEx", False) and my_prizes <= 2) or (atk_dmg >= opp_hp and my_prizes <= 1):
            return ActionClass.TERMINAL
        return ActionClass.TACTICAL

    # 3. Benching Basic Pokémon
    if ctype == 1 and card_info.get("stage", 0) == 0:
        # Check if bench is currently empty (SURVIVAL level priority)
        benched = sum(1 for p in (cur.get("players", [{}, {}])[me].get("bench") or []) if p is not None)
        if benched == 0 or phase == GamePhase.EMERGENCY:
            return ActionClass.SURVIVAL
        return ActionClass.SETUP

    # 4. Evolution
    if ctype == 1 and card_info.get("stage", 0) > 0:
        return ActionClass.DEVELOPMENT

    # 5. Energy Attachment
    if ctype == 5 or opt_type == "attach_energy":
        return ActionClass.DEVELOPMENT

    # 6. Trainers (Supporters / Items)
    if ctype in (2, 3, 4) or opt_type == "trainer":
        name = str(card_info.get("name", "")).lower()
        # Search/draw infrastructure
        if any(w in name for w in ("ball", "nest", "ultra", "research", "arven", "irida", "pau", "draw")):
            benched = sum(1 for p in (cur.get("players", [{}, {}])[me].get("bench") or []) if p is not None)
            if benched == 0:
                return ActionClass.SURVIVAL
            return ActionClass.SETUP
        return ActionClass.TACTICAL

    # 7. Retreat / Abilities
    if opt_type == "retreat":
        if phase == GamePhase.EMERGENCY:
            return ActionClass.SURVIVAL
        return ActionClass.TACTICAL

    return ActionClass.TACTICAL


def filter_candidate_actions(
    options: List[dict],
    cur: dict,
    me: int,
    phase: GamePhase,
    top_k: int = 4
) -> List[int]:
    """Filters legal options down to top_k strategically prioritized candidates.
    
    Enforces Critical Bench Safety: Non-terminal attacks cannot starve backup basic benching.
    """
    if len(options) <= top_k:
        return list(range(len(options)))

    players = cur.get("players") or [{}, {}]
    mine = players[me]
    my_bench = mine.get("bench") or []
    benched_count = sum(1 for p in my_bench if p is not None)

    # Classify all options
    classified = [(i, opt, classify_action(opt, cur, me, phase)) for i, opt in enumerate(options)]

    # Check for Critical Bench Safety Invariant:
    # If bench is 0 or (bench <= 1 and emergency), SURVIVAL actions take absolute precedence
    survival_cands = [i for i, opt, aclass in classified if aclass == ActionClass.SURVIVAL]
    terminal_cands = [i for i, opt, aclass in classified if aclass == ActionClass.TERMINAL]
    setup_cands = [i for i, opt, aclass in classified if aclass == ActionClass.SETUP]
    dev_cands = [i for i, opt, aclass in classified if aclass == ActionClass.DEVELOPMENT]
    tactical_cands = [i for i, opt, aclass in classified if aclass == ActionClass.TACTICAL]
    pass_cands = [i for i, opt, aclass in classified if aclass == ActionClass.PASS]

    # Instant lethal takes top priority
    selected = list(terminal_cands)

    # If in critical bench danger, force survival/setup candidates
    if benched_count == 0:
        for idx in survival_cands + setup_cands:
            if idx not in selected:
                selected.append(idx)

    # Phase-conditioned prioritization
    if phase in (GamePhase.SETUP, GamePhase.EMERGENCY):
        priority_buckets = [survival_cands, setup_cands, dev_cands, tactical_cands, pass_cands]
    elif phase == GamePhase.PRIZE_RACE:
        priority_buckets = [tactical_cands, dev_cands, survival_cands, setup_cands, pass_cands]
    elif phase == GamePhase.ENDGAME:
        priority_buckets = [tactical_cands, survival_cands, dev_cands, pass_cands]
    else:  # DEVELOPMENT
        priority_buckets = [dev_cands, survival_cands, setup_cands, tactical_cands, pass_cands]

    for bucket in priority_buckets:
        for idx in bucket:
            if idx not in selected and len(selected) < top_k:
                selected.append(idx)

    # Fill up to top_k if not full
    if len(selected) < top_k:
        for i in range(len(options)):
            if i not in selected:
                selected.append(i)
            if len(selected) >= top_k:
                break

    return sorted(selected[:top_k])
