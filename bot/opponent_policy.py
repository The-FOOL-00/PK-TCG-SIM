"""Opponent Response Policy for Adversarial 2-Ply and 3-Ply Search.

Ranks opponent legal options in counterfactual simulations:
1. Instant lethal attack (takes final prize)
2. KO active Pokémon (damage >= active HP)
3. Highest damage attack
4. Development (bench basic, evolve, energy attach)
5. Pass / End turn
"""

from typing import List, Dict, Any
import main as agent_mod


def rank_opponent_responses(
    opp_options: List[dict],
    cur: dict,
    opp_seat: int,
    top_m: int = 3
) -> List[int]:
    """Ranks opponent legal actions and returns top_m candidate indices."""
    if len(opp_options) <= top_m:
        return list(range(len(opp_options)))

    players = cur.get("players") or [{}, {}]
    our_seat = 1 - opp_seat
    our_player = players[our_seat]
    our_active = (our_player.get("active") or [{}])[0]
    our_hp = our_active.get("hp", 999) if our_active else 999
    our_prizes = len(our_player.get("prize") or [])
    opp_prizes = len(players[opp_seat].get("prize") or [])

    scored_options = []
    for i, opt in enumerate(opp_options):
        otype = opt.get("type", "")
        card_id = opt.get("cardId")
        card_info = agent_mod.CARDS.get(card_id, {}) if card_id else {}
        ctype = card_info.get("cardType", 0)

        score = 0.0
        if otype == "attack" or "attack" in str(opt.get("name", "")).lower():
            dmg = opt.get("damage", 0)
            if dmg >= our_hp:
                # KO attack
                is_ex = our_active.get("isEx", False)
                p_reward = 2 if is_ex else 1
                if opp_prizes <= p_reward:
                    score = 10000.0  # Lethal
                else:
                    score = 5000.0 + dmg
            else:
                score = 1000.0 + dmg
        elif ctype == 5 or otype == "attach_energy":
            score = 500.0
        elif ctype == 1:
            score = 400.0  # Bench basic or evolve
        elif ctype in (2, 3, 4) or otype == "trainer":
            score = 300.0
        else:
            score = 10.0

        scored_options.append((score, i))

    scored_options.sort(key=lambda x: (-x[0], x[1]))
    return [idx for _, idx in scored_options[:top_m]]
