"""Project Mew Test Suite (v4.0)

Unit and integration tests for:
  - Deck validation
  - Opponent archetype detector
  - Strategy modules
  - Heuristic evaluator
  - Search gating & MasterSearchEngine Lethal Veto
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import validate_deck
from bot.opponent.detector import OpponentDetector, ArchetypePrediction
from bot.strategy.starmie import StarmieStrategy
from bot.policy.evaluator import extract_state_features, evaluate_state_score
from bot.search.gating import is_critical_decision
from bot.search.mcts import MasterSearchEngine


class TestDeckValidation(unittest.TestCase):
    def test_deck_validation(self):
        cards_db = validate_deck.load_card_database()
        self.assertTrue(len(cards_db) > 0, "Card database should not be empty")

        deck = validate_deck.read_deck_file(REPO / "metaC_garchomp_nasuo.csv")
        self.assertEqual(len(deck), 60, "Deck size should be 60")

        errors, breakdown = validate_deck.validate_deck(deck, cards_db)
        self.assertEqual(len(errors), 0, f"Deck validation errors: {errors}")
        self.assertGreater(breakdown["basic_pokemon"], 0, "Should have basic Pokemon")
        self.assertLessEqual(breakdown["ace_spec"], 1, "Should have <= 1 ACE SPEC")


class TestOpponentDetector(unittest.TestCase):
    def test_detection(self):
        detector = OpponentDetector()

        # Mock observation with Starmie cards
        obs = {
            "players": [
                {"active": [], "bench": [], "discard": []},
                {"active": [{"id": 1031}], "bench": [{"id": 1030}], "discard": []}
            ]
        }
        pred = detector.update(obs, my_index=0)
        self.assertEqual(pred.archetype, "STARMIE")
        self.assertGreaterEqual(pred.confidence, 0.85)

    def test_unknown_detection(self):
        detector = OpponentDetector()
        obs = {
            "players": [
                {"active": [], "bench": [], "discard": []},
                {"active": [{"id": 99999}], "bench": [], "discard": []}
            ]
        }
        pred = detector.update(obs, my_index=0)
        self.assertEqual(pred.archetype, "UNKNOWN")
        self.assertEqual(pred.confidence, 0.0)


class TestStarmieStrategy(unittest.TestCase):
    def test_strategy_adjustments(self):
        strat = StarmieStrategy()
        self.assertEqual(strat.name, "STARMIE_DUSKNOIR")

        # Test evolution adjustment for Mega Starmie ex (1031)
        opt = {"type": 9, "cardId": 1031}
        base_score = 2800.0
        adjusted = strat.adjust_action_score(opt, base_score, {}, "UNKNOWN")
        self.assertGreater(adjusted, base_score)


class TestEvaluator(unittest.TestCase):
    def test_feature_extraction(self):
        obs = {
            "players": [
                {
                    "prize": [{}, {}, {}, {}],  # 4 prizes remaining
                    "active": [{"hp": 330, "maxHp": 330, "id": 1031}],
                    "bench": [{"id": 1030}],
                    "hand": [{}, {}, {}]
                },
                {
                    "prize": [{}, {}, {}, {}, {}, {}],  # 6 prizes remaining
                    "active": [{"hp": 70, "maxHp": 70}],
                    "bench": []
                }
            ]
        }
        feats = extract_state_features(obs, my_index=0)
        self.assertEqual(feats["my_prizes"], 4)
        self.assertEqual(feats["opp_prizes"], 6)
        self.assertEqual(feats["prize_differential"], 2)  # We are leading by 2 prizes

        pred = ArchetypePrediction("ALAKAZAM", 0.85)
        score = evaluate_state_score(feats, pred)
        self.assertGreater(score, 0.0)


class TestSearchGating(unittest.TestCase):
    def test_routine_decision(self):
        obs = {
            "select": {"type": 0, "minCount": 1, "maxCount": 1, "option": [{"type": 8}]},
            "current": {"yourIndex": 0, "players": [{"prize": [{}, {}, {}, {}, {}, {}]}, {"prize": [{}, {}, {}, {}, {}, {}]}]}
        }
        self.assertFalse(is_critical_decision(obs, obs["select"]["option"]))

    def test_endgame_critical_decision(self):
        obs = {
            "select": {"type": 0, "minCount": 1, "maxCount": 1, "option": [{"type": 8}, {"type": 13}]},
            "current": {"yourIndex": 0, "players": [{"prize": [{}, {}]}, {"prize": [{}, {}, {}, {}, {}, {}]}]}  # 2 prizes left
        }
        self.assertTrue(is_critical_decision(obs, obs["select"]["option"]))


class TestMasterSearchEngine(unittest.TestCase):
    def test_lethal_veto(self):
        engine = MasterSearchEngine(deck=[1001]*60)
        obs = {
            "select": {"type": 0, "minCount": 1, "maxCount": 1, "option": [{"type": 8}, {"type": 13}]},
            "current": {"yourIndex": 0, "players": [{"prize": [{}]}, {"prize": [{}, {}, {}, {}, {}, {}]}]}  # 1 prize left
        }
        ans, searched = engine.decide(obs, lambda o: ([0], False))
        self.assertEqual(ans, [1])  # Should pick attack option at index 1
        self.assertFalse(searched)  # Lethal veto triggered, no deep search required


if __name__ == "__main__":
    unittest.main()
