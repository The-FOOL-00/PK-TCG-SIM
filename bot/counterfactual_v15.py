"""BS-CEI V1.7 / V1.8 Counterfactual Action Evaluator.

Features:
1. Phase-Aware Candidate Filtering (bot/action_filter.py & bot/phase_controller.py).
2. Critical Bench Safety Invariant: Prevents Bench-Out starvation.
3. 2-Ply and Adaptive 3-Ply Pure Adversarial Minimax:
   - 2-Ply Minimax: max_a min_o V0(s2)
   - Adaptive 3-Ply Minimax: max_a min_o max_a' V0(s3) on critical/uncertain decisions.
4. Configurable Belief Worlds (2 by default).
5. Non-sticky isolated fallback.
"""

import sys
import time
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

import main as agent_mod
from bot.belief import BeliefModel
from bot.state_encoder import encode_state_with_belief
from bot.phase_controller import classify_phase, GamePhase
from bot.action_filter import filter_candidate_actions, classify_action, ActionClass
from bot.opponent_model import get_opponent_response_distribution


class CounterfactualEvaluatorV15:
    """Phase-Aware Hierarchical, 2-Ply, and Adaptive 3-Ply Adversarial Evaluator."""

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
            return None
        try:
            self._model = agent_mod._lv_load(fp)
        except Exception:
            pass
        return self._model

    def evaluate_actions(
        self,
        obs: dict,
        sel: dict,
        cur: dict,
        me: int,
        tracker: Optional[object] = None,
        belief_model: Optional[BeliefModel] = None,
        use_2ply: bool = False,
        use_3ply: bool = False,
        use_probabilistic_opponent: bool = False,
        n_determinizations: int = 2,
    ) -> Optional[List[int]]:
        """Evaluates legal options for a MAIN-phase selection.
        
        Args:
            use_2ply: If True, evaluates adversarial lookahead.
            use_3ply: If True, extends lookahead to 3-ply on critical/uncertain turns.
            use_probabilistic_opponent: If True, weights opponent responses by probability; if False, uses minimax.
            n_determinizations: Number of hidden-world samples (2 by default).
        """
        options = sel.get("option") or []
        if len(options) <= 1:
            return None

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

        # 1. Phase Classification
        phase = classify_phase(cur, me)

        # 2. Hierarchical Candidate Filtering with Bench Safety Invariant
        candidate_indices = filter_candidate_actions(options, cur, me, phase, top_k=4)
        if not candidate_indices:
            return None

        # Check for instant lethal in candidates
        for idx in candidate_indices:
            if classify_action(options[idx], cur, me, phase) == ActionClass.TERMINAL:
                return [idx]

        # 3. Counterfactual Simulation
        candidate_scores = {idx: [] for idx in candidate_indices}
        rng = agent_mod._SEARCH_RNG

        # Determine if 3-ply should be triggered for this state
        is_critical_turn = False
        if use_3ply:
            players = cur.get("players") or [{}, {}]
            our_p = players[me]
            opp_p = players[1 - me]
            our_prizes = len(our_p.get("prize") or [])
            opp_prizes = len(opp_p.get("prize") or [])
            our_active = (our_p.get("active") or [{}])[0]
            our_hp = our_active.get("hp", 100) if our_active else 100
            if our_prizes <= 3 or opp_prizes <= 3 or our_hp <= 40 or phase in (GamePhase.PRIZE_RACE, GamePhase.ENDGAME, GamePhase.EMERGENCY):
                is_critical_turn = True

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
                root_id = root["searchId"]
                for cand_idx in candidate_indices:
                    try:
                        node1 = agent_mod._sb_step(root_id, [cand_idx])
                        node1_obs = node1.get("observation") or {}
                        node1_cur = node1_obs.get("current") or {}
                        res1 = node1_cur.get("result", -1)

                        if res1 != -1:
                            val = 1.0 if res1 == me else (0.5 if res1 == 2 else 0.0)
                            candidate_scores[cand_idx].append(val)
                            continue

                        if not use_2ply:
                            # 1-Ply Filtered Evaluation
                            vec1 = encode_state_with_belief(node1_cur, belief_model, tracker)
                            p_win1 = agent_mod._lv_predict(model, [vec1])[0]
                            acting1 = node1_cur.get("yourIndex", me)
                            val = p_win1 if acting1 == me else (1.0 - p_win1)
                            candidate_scores[cand_idx].append(val)
                        else:
                            # 2-Ply / Adaptive 3-Ply Adversarial Lookahead
                            node1_sel = node1_obs.get("select") or {}
                            opp_options = node1_sel.get("option") or []
                            acting1 = node1_cur.get("yourIndex", me)

                            if acting1 == me or len(opp_options) <= 1:
                                # Still our turn or forced step
                                vec1 = encode_state_with_belief(node1_cur, belief_model, tracker)
                                p_win1 = agent_mod._lv_predict(model, [vec1])[0]
                                val = p_win1 if acting1 == me else (1.0 - p_win1)
                                candidate_scores[cand_idx].append(val)
                            else:
                                node1_id = node1["searchId"]
                                opp_phase = classify_phase(node1_cur, 1 - me)
                                opp_cands = filter_candidate_actions(opp_options, node1_cur, 1 - me, opp_phase, top_k=3)
                                opp_leaf_vals = []

                                for opp_idx in opp_cands:
                                    try:
                                        node2 = agent_mod._sb_step(node1_id, [opp_idx])
                                        node2_obs = node2.get("observation") or {}
                                        node2_cur = node2_obs.get("current") or {}
                                        res2 = node2_cur.get("result", -1)

                                        if res2 != -1:
                                            v2 = 1.0 if res2 == me else (0.5 if res2 == 2 else 0.0)
                                        elif is_critical_turn:
                                            # Ply 3: Our Best Counter-Response
                                            node2_id = node2["searchId"]
                                            node2_sel = node2_obs.get("select") or {}
                                            our3_options = node2_sel.get("option") or []
                                            acting2 = node2_cur.get("yourIndex", me)

                                            if acting2 == me and len(our3_options) > 1:
                                                our3_phase = classify_phase(node2_cur, me)
                                                our3_cands = filter_candidate_actions(our3_options, node2_cur, me, our3_phase, top_k=2)
                                                our3_vals = []
                                                for our3_idx in our3_cands:
                                                    try:
                                                        node3 = agent_mod._sb_step(node2_id, [our3_idx])
                                                        node3_obs = node3.get("observation") or {}
                                                        node3_cur = node3_obs.get("current") or {}
                                                        res3 = node3_cur.get("result", -1)
                                                        if res3 != -1:
                                                            v3 = 1.0 if res3 == me else (0.5 if res3 == 2 else 0.0)
                                                        else:
                                                            vec3 = encode_state_with_belief(node3_cur, belief_model, tracker)
                                                            v3 = float(agent_mod._lv_predict(model, [vec3])[0])
                                                        our3_vals.append(v3)
                                                    except Exception:
                                                        pass
                                                v2 = max(our3_vals) if our3_vals else float(agent_mod._lv_predict(model, [encode_state_with_belief(node2_cur, belief_model, tracker)])[0])
                                            else:
                                                vec2 = encode_state_with_belief(node2_cur, belief_model, tracker)
                                                p_win2 = agent_mod._lv_predict(model, [vec2])[0]
                                                v2 = p_win2 if acting2 == me else (1.0 - p_win2)
                                        else:
                                            # Standard 2-Ply Leaf
                                            vec2 = encode_state_with_belief(node2_cur, belief_model, tracker)
                                            p_win2 = agent_mod._lv_predict(model, [vec2])[0]
                                            acting2 = node2_cur.get("yourIndex", me)
                                            v2 = p_win2 if acting2 == me else (1.0 - p_win2)

                                        opp_leaf_vals.append(v2)
                                    except Exception:
                                        pass

                                val = min(opp_leaf_vals) if opp_leaf_vals else (1.0 - agent_mod._lv_predict(model, [encode_state_with_belief(node1_cur, belief_model, tracker)])[0])

                                candidate_scores[cand_idx].append(val)
                    except Exception:
                        pass
            finally:
                agent_mod._sb_end()

        # Score aggregation across belief worlds
        ranked = []
        for idx, vals in candidate_scores.items():
            if vals:
                ranked.append((float(np.mean(vals)), idx))

        if not ranked:
            return [candidate_indices[0]]

        ranked.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return [ranked[0][1]]
