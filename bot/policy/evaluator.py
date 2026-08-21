"""Project Mew - Heuristic Evaluator & Feature Extractor

Computes state features and provides comprehensive state and option scoring.
"""

from typing import Dict, Any, Tuple
from bot.config import HEURISTIC_WEIGHTS
from bot.opponent.detector import ArchetypePrediction


def extract_state_features(current_obs: dict, my_index: int) -> dict:
    """Extracts analytical features from current observation state."""
    features = {}
    if not current_obs or "players" not in current_obs:
        return features

    players = current_obs.get("players", [])
    if len(players) <= my_index:
        return features

    mine = players[my_index]
    opp = players[1 - my_index]

    # Prizes
    my_prizes = len(mine.get("prize") or [])
    opp_prizes = len(opp.get("prize") or [])
    features["my_prizes"] = my_prizes
    features["opp_prizes"] = opp_prizes
    features["prize_differential"] = opp_prizes - my_prizes

    # Active Pokemon
    my_act = (mine.get("active") or [None])[0]
    opp_act = (opp.get("active") or [None])[0]

    features["my_active_hp"] = my_act.get("hp", 0) if my_act else 0
    features["my_active_max_hp"] = my_act.get("maxHp", 1) if my_act else 1
    features["my_active_hp_ratio"] = features["my_active_hp"] / max(1, features["my_active_max_hp"])

    features["opp_active_hp"] = opp_act.get("hp", 0) if opp_act else 0
    features["opp_active_max_hp"] = opp_act.get("maxHp", 1) if opp_act else 1
    features["opp_active_hp_ratio"] = features["opp_active_hp"] / max(1, features["opp_active_max_hp"])

    # Bench Counts
    my_bench = mine.get("bench") or []
    opp_bench = opp.get("bench") or []
    features["my_bench_count"] = sum(1 for p in my_bench if p)
    features["opp_bench_count"] = sum(1 for p in opp_bench if p)

    # Hand & Discard
    features["my_hand_count"] = len(mine.get("hand") or [])
    features["my_discard_count"] = len(mine.get("discard") or [])

    # Starmie specific count
    starmie_count = 0
    starmie_energy = 0
    all_my_pk = ([my_act] if my_act else []) + [p for p in my_bench if p]
    for pk in all_my_pk:
        if pk and pk.get("id") in (1030, 1031):  # Staryu or Mega Starmie ex
            starmie_count += 1
            starmie_energy += len(pk.get("energies") or [])

    features["starmie_count"] = starmie_count
    features["starmie_energy"] = starmie_energy

    return features


def evaluate_state_score(features: dict, opp_prediction: ArchetypePrediction) -> float:
    """Computes state evaluation score based on extracted features."""
    w = HEURISTIC_WEIGHTS
    score = 0.0

    # 1. Prize Differential
    score += features.get("prize_differential", 0) * w["V3_W_PRIZE"]

    # 2. Active HP Ratio & Bench Presence
    score += features.get("my_active_hp_ratio", 0.0) * w["V3_W_ACTIVE"]
    score += features.get("my_bench_count", 0) * w["V3_W_BENCH"]
    score += features.get("my_hand_count", 0) * w["V3_W_HAND"]

    # 3. Matchup Adjustment
    if opp_prediction.archetype != "UNKNOWN" and opp_prediction.confidence >= 0.6:
        # Matchup specific bonus adjustments
        score += 50.0 * opp_prediction.confidence

    return score
