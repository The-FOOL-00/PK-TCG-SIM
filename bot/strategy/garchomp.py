"""Cynthia's Garchomp ex Strategy Plugin.

Features:
- Active-First Energy Routing (prioritizes Active Garchomp ex or Gible/Gabite).
- Turn 2 Rare Candy Evolution priority.
- Energy Denial / Boss's Orders targeting.
"""

from bot.strategy.base import BaseStrategy

# Card IDs for Garchomp ex engine
CARD_GIBLE = 379
CARD_GABITE = 380
CARD_GARCHOMP_EX = 381
CARD_RARE_CANDY = 1080
CARD_CRUSHING_HAMMER = 1085
CARD_BOSS_ORDERS = 1058

class GarchompStrategy(BaseStrategy):
    """Domain-specific heuristic evaluator for Garchomp ex deck."""

    def score_option(self, option, obs):
        score = 0.0
        opt_type = option.get("type", 0)
        card_id = option.get("cardId", 0)

        # 1. Rare Candy Evolution Priority (Turn 2 Stage 2 Garchomp ex)
        if opt_type == 14 and card_id == CARD_RARE_CANDY:  # Play Trainer Item
            score += 1500.0

        # 2. Active Energy Attachment Priority
        if opt_type == 8:  # Attach Energy
            active = obs.get("current", {}).get("players", [{}])[0].get("active", [])
            active_id = active[0].get("id") if active else None
            if active_id in (CARD_GARCHOMP_EX, CARD_GABITE, CARD_GIBLE):
                score += 1200.0  # Priority energy to active attacker

        # 3. Energy Denial & Gusting
        if opt_type == 14:
            if card_id == CARD_CRUSHING_HAMMER:
                score += 800.0
            elif card_id == CARD_BOSS_ORDERS:
                score += 900.0

        return score
