"""Mega Starmie ex / Dusknoir Deck Strategy

Specialized strategy implementation for the Mega Starmie ex / Dusknoir candidate deck.
"""

from bot.strategy.base import DeckStrategy


class StarmieStrategy(DeckStrategy):
    def __init__(self):
        super().__init__("STARMIE_DUSKNOIR")

    def evaluate_state_bonus(self, state: dict, features: dict) -> float:
        bonus = 0.0
        # Reward active/bench Mega Starmie ex presence
        starmie_count = features.get("starmie_count", 0)
        bonus += starmie_count * 150.0

        # Reward basic energy on Mega Starmie ex
        starmie_energy = features.get("starmie_energy", 0)
        if starmie_energy >= 1:  # 1 Energy enables Jetting Blow
            bonus += 200.0

        return bonus

    def adjust_action_score(self, option: dict, current_score: float, state: dict, opp_archetype: str) -> float:
        opt_type = option.get("type")
        card_id = option.get("cardId")

        # 1. High priority for evolving Staryu (1030) to Mega Starmie ex (1031)
        if opt_type == 9:  # OT_EVOLVE
            if card_id == 1031:  # Mega Starmie ex
                return current_score + 500.0

        # 2. Prefer attaching energy to Staryu / Mega Starmie ex if under 1 energy
        if opt_type == 8:  # OT_ATTACH
            if card_id in (1030, 1031):
                return current_score + 350.0

        # 3. Supporter/Item search priority for evolution pieces
        if opt_type == 7:  # OT_PLAY (Item / Supporter)
            if card_id in (1086, 1145, 1121):  # Buddy-Buddy Poffin, Mega Signal, Ultra Ball
                return current_score + 250.0

        return current_score
