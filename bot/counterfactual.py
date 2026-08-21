"""BS-CEI V1 Counterfactual 1-Step Action Evaluator.

Evaluates legal candidate actions by simulating 1-step forward transitions in the C++ engine,
encoding the resulting state with the 194-dim state+belief encoder, and computing the
expected win probability using the trained Win-Value Network V(s', belief).

Features:
- Pure 1-step forward simulation (zero deep MCTS rollouts).
- Dynamic non-sticky fallback: isolated per-action and per-decision error handling.
- Anti-deckout awareness: state transitions that deplete deck without lethal are penalized by V(s').
"""

import sys
import time
from typing import List, Tuple, Dict, Any, Optional

import numpy as np

import main as agent_mod
from bot.belief import BeliefModel
from bot.state_encoder import encode_state_with_belief


class CounterfactualEvaluator:
    """1-step engine counterfactual action evaluator for BS-CEI V1."""

    def __init__(self, value_model_path: str = "value_weights.npz"):
        self.value_model_path = value_model_path
        self._model = None
        self._model_tried = False

    def get_model(self):
        if self._model is not None or self._model_tried:
            return self._model
        self._model_tried = True
        fp = agent_mod._find_file(self.value_model_path)
        if fp is None:
            print(f"[bs-cei] WARNING: {self.value_model_path} not found; heuristic fallback", file=sys.stderr, flush=True)
            return None
        try:
            self._model = agent_mod._lv_load(fp)
            print(f"[bs-cei] Value model loaded successfully from {fp}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[bs-cei] WARNING: Failed loading {fp} ({e}); heuristic fallback", file=sys.stderr, flush=True)
        return self._model

    def evaluate_actions(
        self,
        obs: dict,
        sel: dict,
        cur: dict,
        me: int,
        tracker: Optional[object] = None,
        belief_model: Optional[BeliefModel] = None,
        n_determinizations: int = 1,
    ) -> Optional[List[int]]:
        """Evaluates legal options for a MAIN-phase selection via 1-step engine simulation.
        
        Returns [best_action_index] or None if evaluation was skipped/failed.
        """
        options = sel.get("option") or []
        if len(options) <= 1:
            return None

        # Only evaluate MAIN-phase single-select decisions
        stype = sel.get("type")
        min_c = sel.get("minCount", 1)
        max_c = sel.get("maxCount", 1)
        if stype != agent_mod.ST_MAIN or min_c != 1 or max_c != 1:
            return None

        sbi = obs.get("search_begin_input")
        if not sbi or agent_mod._search_lib() is None:
            return None

        model = self.get_model()
        if model is None:
            return None

        if tracker is None:
            tracker = agent_mod.CardTracker(me)

        if belief_model is None:
            belief_model = BeliefModel(me)

        # Evaluate candidate options
        candidate_values = {i: [] for i in range(len(options))}
        rng = agent_mod._SEARCH_RNG

        for _d in range(n_determinizations):
            try:
                det = agent_mod._sample_determinization(obs, tracker, rng)
            except Exception:
                continue

            try:
                root = agent_mod._sb_begin(sbi, **det)
            except Exception:
                continue

            try:
                for i, opt in enumerate(options):
                    try:
                        node = agent_mod._sb_step(root["searchId"], [i])
                        node_obs = node.get("observation") or {}
                        node_cur = node_obs.get("current") or {}
                        res = node_cur.get("result", -1)

                        if res != -1:
                            # Immediate terminal state
                            if res == me:
                                val = 1.0
                            elif res == 2:  # Draw
                                val = 0.5
                            else:
                                val = 0.0
                        else:
                            # Evaluate resulting state with value model
                            vec = encode_state_with_belief(node_cur, belief_model, tracker)
                            p_win = agent_mod._lv_predict(model, [vec])[0]
                            # Flip if resulting state is opponent's turn
                            acting_seat = node_cur.get("yourIndex", me)
                            val = p_win if acting_seat == me else (1.0 - p_win)

                        candidate_values[i].append(val)
                    except Exception:
                        pass
            finally:
                agent_mod._sb_end()

        # Score aggregation
        scored_candidates = []
        for i, val_list in candidate_values.items():
            if val_list:
                mean_val = float(np.mean(val_list))
                scored_candidates.append((mean_val, i))

        if not scored_candidates:
            return None

        # Pick option with maximum expected win probability
        scored_candidates.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        best_idx = scored_candidates[0][1]
        return [best_idx]
