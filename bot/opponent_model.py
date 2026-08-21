"""Probabilistic Opponent Response Model for BS-CEI V1.7.

Estimates the probability distribution P(opponent_response | state, belief) over
legal opponent counter-actions and computes the robust expected value:

    Q_robust(a) = 0.8 * E_o[V(s_after(a, o))] + 0.2 * min_o[V(s_after(a, o))]

Replaces unrealistic pure minimax with realistic probabilistic counterplay modeling.
"""

from enum import Enum
from typing import List, Dict, Any, Tuple
import numpy as np
import main as agent_mod


class OpponentActionCategory(Enum):
    LETHAL = 10000.0
    KO_ACTIVE = 5000.0
    PRIZE_TAKE = 4000.0
    BOSS_TARGET = 3000.0
    ATTACK_DAMAGE = 1000.0
    ENERGY_ATTACH = 500.0
    DEVELOPMENT = 400.0
    TRAINER = 300.0
    PASS = 10.0


def score_opponent_action(opt: dict, cur: dict, opp_seat: int) -> Tuple[float, OpponentActionCategory]:
    """Computes realistic tactical utility score and category for an opponent action."""
    players = cur.get("players") or [{}, {}]
    our_seat = 1 - opp_seat
    our_player = players[our_seat]
    opp_player = players[opp_seat]

    our_active = (our_player.get("active") or [{}])[0]
    our_hp = our_active.get("hp", 999) if our_active else 999
    our_is_ex = our_active.get("isEx", False)
    opp_prizes = len(opp_player.get("prize") or [])

    otype = opt.get("type", "")
    card_id = opt.get("cardId")
    card_info = agent_mod.CARDS.get(card_id, {}) if card_id else {}
    ctype = card_info.get("cardType", 0)

    # 1. Attacks
    if otype == "attack" or "attack" in str(opt.get("name", "")).lower():
        dmg = opt.get("damage", 0)
        p_reward = 2 if our_is_ex else 1
        if dmg >= our_hp:
            if opp_prizes <= p_reward:
                return OpponentActionCategory.LETHAL.value + dmg, OpponentActionCategory.LETHAL
            return OpponentActionCategory.KO_ACTIVE.value + dmg, OpponentActionCategory.KO_ACTIVE
        return OpponentActionCategory.ATTACK_DAMAGE.value + dmg, OpponentActionCategory.ATTACK_DAMAGE

    # 2. Boss / Gust / Target Change
    if ctype in (2, 3, 4) or otype == "trainer":
        name = str(card_info.get("name", "")).lower()
        if any(w in name for w in ("boss", "orders", "gust", "catcher")):
            return OpponentActionCategory.BOSS_TARGET.value, OpponentActionCategory.BOSS_TARGET
        return OpponentActionCategory.TRAINER.value, OpponentActionCategory.TRAINER

    # 3. Energy Attachment
    if ctype == 5 or otype == "attach_energy":
        return OpponentActionCategory.ENERGY_ATTACH.value, OpponentActionCategory.ENERGY_ATTACH

    # 4. Evolution / Benching
    if ctype == 1:
        return OpponentActionCategory.DEVELOPMENT.value, OpponentActionCategory.DEVELOPMENT

    # 5. Pass / End Turn
    return OpponentActionCategory.PASS.value, OpponentActionCategory.PASS


def get_opponent_response_distribution(
    opp_options: List[dict],
    cur: dict,
    opp_seat: int,
    top_m: int = 3,
    temperature: float = 800.0,
) -> List[Tuple[int, float]]:
    """Returns top_m (option_index, probability) pairs normalized via softmax."""
    if not opp_options:
        return []

    scored = []
    for i, opt in enumerate(opp_options):
        score, cat = score_opponent_action(opt or {}, cur, opp_seat)
        scored.append((score, i))

    # Sort descending by score
    scored.sort(key=lambda x: (-x[0], x[1]))
    top_scored = scored[:top_m]

    # Compute softmax probabilities over top_m candidates
    logits = np.array([s for s, _ in top_scored], dtype=np.float64)
    # Shift logits for numerical stability
    logits = (logits - np.max(logits)) / max(temperature, 1.0)
    exp_l = np.exp(logits)
    probs = exp_l / np.sum(exp_l)

    return [(idx, float(probs[k])) for k, (_, idx) in enumerate(top_scored)]
