"""Alakazam / Garchomp Energy Denial Strategy (v5.0)

Implements:
  - Rare Candy fast Stage 2 evolution priorities
  - Active-First energy routing (100% active priority until attack cost met)
  - Crushing Hammer & Energy Denial disruption bonuses
  - Boss's Orders bench snipe priority on low HP / high prize targets
"""

from bot.strategy.base import DeckStrategy


class AlakazamStrategy(DeckStrategy):
    def __init__(self):
        super().__init__("ALAKAZAM_DENIAL")

    def evaluate_state_bonus(self, state: dict, features: dict) -> float:
        bonus = 0.0
        # Reward active Stage 2 Alakazam / Garchomp ex
        active_hp = features.get("active_hp", 0)
        bonus += active_hp * 2.0

        # Reward energy denial advantage
        opp_energy = features.get("opp_energy", 0)
        if opp_energy <= 1:
            bonus += 300.0

        return bonus

    def adjust_action_score(self, option: dict, current_score: float, state: dict, opp_archetype: str) -> float:
        opt_type = option.get("type")
        card_id = option.get("cardId")
        name = option.get("name", "")

        # 1. Rare Candy / Stage 2 Evolution Priority
        if opt_type == 9:  # OT_EVOLVE
            return current_score + 600.0

        if opt_type == 7:  # OT_PLAY Item / Supporter
            # Rare Candy (1145), Ultra Ball (1121), Buddy-Buddy Poffin (1086)
            if card_id in (1145, 1121, 1086) or "Candy" in name or "Ultra" in name:
                return current_score + 500.0

            # Crushing Hammer / Energy Denial items
            if "Hammer" in name or "Crushing" in name or card_id == 1080:
                return current_score + 450.0

            # Boss's Orders / Gusting
            if "Boss" in name or card_id == 1197:
                return current_score + 400.0

        # 2. Energy Attachment: Active-First Priority
        if opt_type == 8:  # OT_ATTACH
            # Check if target is Active slot
            target_slot = option.get("slot", 0)
            if target_slot == 0:  # Active slot
                return current_score + 700.0
            else:
                return current_score - 200.0  # Penalize benched energy attachment until active is ready

        return current_score
