"""Action Feature Encoder for Action-Conditioned Q-CEI.

Produces a standardized 47-dimensional action representation:
1. 41-dim base option features (type one-hot, card type one-hot, slot features, damage, KO flag, rank)
2. 6-dim one-hot strategic ActionClass (TERMINAL, SURVIVAL, SETUP, DEVELOPMENT, TACTICAL, PASS)

Output: 47-dimensional normalized float32 list/array per action.
"""

from typing import List, Dict, Any, Optional
import main as agent_mod
from bot.phase_controller import GamePhase
from bot.action_filter import classify_action, ActionClass

N_ACTION_BASE_FEATURES = 41
N_ACTION_CLASS_FEATURES = 6
N_TOTAL_ACTION_FEATURES = N_ACTION_BASE_FEATURES + N_ACTION_CLASS_FEATURES  # 47

ACTION_CLASS_ORDER = [
    ActionClass.TERMINAL,
    ActionClass.SURVIVAL,
    ActionClass.SETUP,
    ActionClass.DEVELOPMENT,
    ActionClass.TACTICAL,
    ActionClass.PASS,
]


def encode_action_features(
    opt: dict,
    sel: dict,
    cur: dict,
    me: int,
    phase: GamePhase,
    v1_rank: float = 0.0,
    v1_top: float = 0.0,
) -> List[float]:
    """Encodes a single legal action into a 47-dimensional feature vector."""
    # 1. Base 41-dim option encoding
    base_feats = agent_mod.encode_option(opt, sel, cur, me, v1_rank=v1_rank, v1_top=v1_top)

    # 2. 6-dim one-hot ActionClass encoding
    aclass = classify_action(opt, cur, me, phase)
    class_onehot = [1.0 if aclass == ac else 0.0 for ac in ACTION_CLASS_ORDER]

    return base_feats + class_onehot


def encode_all_actions(
    sel: dict,
    cur: dict,
    me: int,
    phase: GamePhase,
) -> List[List[float]]:
    """Encodes all legal options in the current decision."""
    options = sel.get("option") or []
    n = len(options)
    if n == 0:
        return []

    scores = [agent_mod._score_main(o or {}, sel, cur, me) for o in options]
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    ranks = [0.0] * n
    for r, i in enumerate(order):
        ranks[i] = r / (n - 1) if n > 1 else 0.0
    top_idx = order[0] if n else None

    encoded_list = []
    for i, opt in enumerate(options):
        is_top = 1.0 if (i == top_idx) else 0.0
        encoded = encode_action_features(
            opt or {}, sel, cur, me, phase, v1_rank=ranks[i], v1_top=is_top
        )
        encoded_list.append(encoded)

    return encoded_list
