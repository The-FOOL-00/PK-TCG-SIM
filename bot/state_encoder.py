"""BS-CEI Unified State + Belief Encoder (194 dimensions).

Combines:
1. 170-dim public board, player, and card multiset features (leakage-audited).
2. 24-dim Bayesian opponent archetype, certainty, and dynamic context features.

Output: 194-dimensional normalized float32 list/array.
"""

from typing import List, Optional
import main as agent_mod
from bot.belief import BeliefModel, N_BELIEF_FEATURES, belief_feature_names

N_PUBLIC_FEATURES = agent_mod.N_STATE_FEATURES  # 170
N_TOTAL_FEATURES = N_PUBLIC_FEATURES + N_BELIEF_FEATURES  # 170 + 24 = 194


def encode_state_with_belief(
    cur: dict,
    belief_model: Optional[BeliefModel] = None,
    tracker: Optional[object] = None
) -> List[float]:
    """Encodes current public state + belief into a 194-dim feature vector."""
    # 1. Extract 170-dim base public features
    base_feats = agent_mod.encode_state(cur)

    # 2. Extract 24-dim belief features
    if belief_model is not None:
        belief_feats = belief_model.update(cur, tracker)
    else:
        # Default neutral belief
        bm = BeliefModel(cur.get("yourIndex", 0))
        belief_feats = bm.update(cur, tracker)

    return base_feats + belief_feats


def total_feature_names() -> List[str]:
    """Combined 194 feature names for explainability and diagnostics."""
    return agent_mod.state_feature_names() + belief_feature_names()
