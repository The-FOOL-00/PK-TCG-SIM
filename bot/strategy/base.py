"""Deck Strategy Base Class

Defines the strategy interface for deck-aware decision making.
"""

from typing import Dict, Any, List


class DeckStrategy:
    """Base strategy class for deck-aware policy customization."""

    def __init__(self, name: str):
        self.name = name

    def evaluate_state_bonus(self, state: dict, features: dict) -> float:
        """Returns state evaluation bonus points based on strategy goals."""
        return 0.0

    def adjust_action_score(self, option: dict, current_score: float, state: dict, opp_archetype: str) -> float:
        """Adjusts the heuristic score of an option based on deck strategy and opponent archetype."""
        return current_score

    def get_bench_target_priority(self, candidate_slots: List[dict], opp_archetype: str) -> List[int]:
        """Returns ordered indices for bench targeting (e.g. Boss's Orders / Snipe attacks)."""
        return list(range(len(candidate_slots)))


class DefaultStrategy(DeckStrategy):
    def __init__(self):
        super().__init__("DEFAULT")
