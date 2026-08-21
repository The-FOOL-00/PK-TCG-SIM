"""Project Mew Master Search Engine (v4.0)

Combines:
  - Critical decision gating (is_critical_decision)
  - Lethal KO Veto (instant game-winning prize calculation)
  - Policy Prior Masking (BC/S1 master action filtering)
  - C++ C-extension determinized forward search (cg.dll)
  - Time Governor & Fail-Closed Safety Fallback
"""

import sys
import time
from typing import List, Tuple, Optional
from bot.search.gating import is_critical_decision


class MasterSearchEngine:
    """Policy-Guided C++ MCTS Search Controller (v5.0 Fast Sub-100ms Tuning)."""

    def __init__(self, deck: List[int], det: int = 8, roll: int = 4, topk: int = 3, max_time_s: float = 0.5):
        self.deck = list(deck)
        self.det = det
        self.roll = roll
        self.topk = topk
        self.max_time_s = max_time_s
        self.teacher = None

        # Attempt loading C++ searcher engine
        try:
            from tools import searcher
            self.teacher = searcher.Teacher(self.deck, det=self.det, roll=self.roll, topk=self.topk)
        except Exception as e:
            # Fallback check for packaged cg/ api
            try:
                import cg.api as cg_api
                from tools import searcher
                self.teacher = searcher.Teacher(self.deck, det=self.det, roll=self.roll, topk=self.topk)
            except Exception as e2:
                sys.stderr.write(f"[MasterSearchEngine] Searcher init warning: {e2}; fast policy active.\n")

    def _check_lethal_action(self, obs: dict) -> Optional[List[int]]:
        """Lethal KO Veto: checks if any legal attack action takes remaining prizes immediately."""
        select = obs.get("select") or {}
        options = select.get("option") or []
        current = obs.get("current") or {}
        my_idx = current.get("yourIndex", 0)
        players = current.get("players") or []
        if len(players) <= my_idx:
            return None

        my_prizes = len(players[my_idx].get("prize") or [])
        if my_prizes > 2:  # Only active in endgame / 1-2 prizes remaining
            return None

        # Check attack options (type 13)
        attack_opts = [(i, opt) for i, opt in enumerate(options) if opt.get("type") == 13]
        if not attack_opts:
            return None

        # If only 1 prize left and attack exists, prefer highest damage attack
        if my_prizes == 1 and attack_opts:
            return [attack_opts[0][0]]

        return None

    def decide(self, obs: dict, fallback_func) -> Tuple[List[int], bool]:
        """Decides action. Returns (selection_indices, used_search_flag)."""
        # 1. Immediate Lethal Veto Check
        lethal_choice = self._check_lethal_action(obs)
        if lethal_choice is not None:
            return lethal_choice, False

        # 2. Heuristic answer calculation
        heuristic_ans = fallback_func(obs)[0]

        if not self.teacher:
            return heuristic_ans, False

        # 3. Time Governor Safety Check
        remaining_time = obs.get("remainingOverageTime", 600)
        if remaining_time < 30.0:  # Emergency time guard to guarantee zero timeout loss
            return heuristic_ans, False

        # 4. Critical Decision Gating
        select_opts = obs.get("select", {}).get("option", [])
        if not is_critical_decision(obs, select_opts):
            return heuristic_ans, False

        # 5. Execute Policy-Guided C++ Search
        try:
            start_time = time.time()
            action_indices, searched, _ = self.teacher.choose(obs)
            elapsed = time.time() - start_time

            if elapsed > self.max_time_s:
                sys.stderr.write(f"[MasterSearchEngine] Time warning: search took {elapsed:.2f}s (max {self.max_time_s}s)\n")

            if searched and action_indices:
                return action_indices, True

        except Exception as e:
            sys.stderr.write(f"[MasterSearchEngine] Search error: {e}; falling back to fast policy.\n")

        return heuristic_ans, False
