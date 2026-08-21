"""Action-Conditioned Q Policy (Q-CEI) with Adaptive Tactical Search.

Evaluates legal options by directly computing Q(s, phase, a) and optionally running
2-ply or 3-ply counterfactual lookahead on critical decisions.
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
from bot.action_encoder import encode_action_features
from bot.q_model import QModel
from bot.opponent_policy import rank_opponent_responses

PHASE_ORDER = [
    GamePhase.SETUP,
    GamePhase.DEVELOPMENT,
    GamePhase.PRIZE_RACE,
    GamePhase.ENDGAME,
    GamePhase.EMERGENCY,
]


class QPolicyEvaluator:
    """Action-Conditioned Q Evaluator supporting 0-ply (direct Q), 2-ply, and 3-ply lookahead."""

    def __init__(self, q_weights_path: str = "q_weights.npz"):
        self.q_model = QModel(q_weights_path)

    def evaluate_decision(
        self,
        obs: dict,
        sel: dict,
        cur: dict,
        me: int,
        tracker: Optional[object] = None,
        belief_model: Optional[BeliefModel] = None,
        search_depth: int = 0,
        n_determinizations: int = 1,
    ) -> Optional[List[int]]:
        """Evaluates legal actions using the action-conditioned Q network."""
        options = sel.get("option") or []
        if len(options) <= 1:
            return None

        stype = sel.get("type")
        min_c = sel.get("minCount", 1)
        max_c = sel.get("maxCount", 1)
        if stype != agent_mod.ST_MAIN or min_c != 1 or max_c != 1:
            return None

        if not self.q_model.loaded:
            return None

        if tracker is None:
            tracker = agent_mod.CardTracker(me)

        if belief_model is None:
            belief_model = BeliefModel(me)

        # 1. State & Phase Encoding
        s_vec = encode_state_with_belief(cur, belief_model, tracker)
        phase = classify_phase(cur, me)
        p_vec = [1.0 if phase == ph else 0.0 for ph in PHASE_ORDER]

        # 2. Candidate Filtering
        cands = filter_candidate_actions(options, cur, me, phase, top_k=4)
        if not cands:
            return None

        # Check for instant lethal
        for idx in cands:
            if classify_action(options[idx], cur, me, phase) == ActionClass.TERMINAL:
                return [idx]

        # 3. Direct Q-Evaluation (Depth 0 - Exp F)
        if search_depth == 0 or obs.get("search_begin_input") is None or agent_mod._search_lib() is None:
            feat_rows = []
            for c_idx in cands:
                a_vec = encode_action_features(options[c_idx], sel, cur, me, phase)
                feat_rows.append(s_vec + p_vec + a_vec)

            q_vals = self.q_model.predict_q(np.asarray(feat_rows, dtype=np.float32))
            best_order = np.argsort(-q_vals)
            best_idx = cands[best_order[0]]
            return [best_idx]

        # 4. Search Evaluation (2-Ply or 3-Ply - Exp G & H)
        sbi = obs.get("search_begin_input")
        rng = agent_mod._SEARCH_RNG
        cand_scores = {c_idx: [] for c_idx in cands}

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
                for c_idx in cands:
                    try:
                        node1 = agent_mod._sb_step(root_id, [c_idx])
                        node1_obs = node1.get("observation") or {}
                        node1_cur = node1_obs.get("current") or {}
                        res1 = node1_cur.get("result", -1)

                        if res1 != -1:
                            val = 1.0 if res1 == me else (0.5 if res1 == 2 else 0.0)
                            cand_scores[c_idx].append(val)
                            continue

                        acting1 = node1_cur.get("yourIndex", me)
                        node1_sel = node1_obs.get("select") or {}
                        opp_options = node1_sel.get("option") or []

                        if acting1 == me or len(opp_options) <= 1:
                            # Direct Q evaluation at node1
                            s1_vec = encode_state_with_belief(node1_cur, belief_model, tracker)
                            ph1 = classify_phase(node1_cur, me)
                            ph1_vec = [1.0 if ph1 == ph else 0.0 for ph in PHASE_ORDER]
                            # Score with dummy action or next candidate
                            a_dummy = [0.0] * 47
                            q1 = self.q_model.predict_q(np.asarray([s1_vec + ph1_vec + a_dummy], dtype=np.float32))[0]
                            cand_scores[c_idx].append(float(q1))
                        else:
                            # Opponent counter-turn
                            node1_id = node1["searchId"]
                            opp_cands = rank_opponent_responses(opp_options, node1_cur, 1 - me, top_m=3)

                            opp_vals = []
                            for o_idx in opp_cands:
                                try:
                                    node2 = agent_mod._sb_step(node1_id, [o_idx])
                                    node2_obs = node2.get("observation") or {}
                                    node2_cur = node2_obs.get("current") or {}
                                    res2 = node2_cur.get("result", -1)

                                    if res2 != -1:
                                        v2 = 1.0 if res2 == me else (0.5 if res2 == 2 else 0.0)
                                    elif search_depth == 2 or len((node2_obs.get("select") or {}).get("option") or []) <= 1:
                                        # 2-Ply Leaf
                                        s2_vec = encode_state_with_belief(node2_cur, belief_model, tracker)
                                        ph2 = classify_phase(node2_cur, me)
                                        ph2_vec = [1.0 if ph2 == ph else 0.0 for ph in PHASE_ORDER]
                                        a_dummy = [0.0] * 47
                                        v2 = float(self.q_model.predict_q(np.asarray([s2_vec + ph2_vec + a_dummy], dtype=np.float32))[0])
                                    else:
                                        # 3-Ply: Our best counter-response from node2
                                        node2_id = node2["searchId"]
                                        node2_sel = node2_obs.get("select") or {}
                                        our3_options = node2_sel.get("option") or []
                                        ph3 = classify_phase(node2_cur, me)
                                        our3_cands = filter_candidate_actions(our3_options, node2_cur, me, ph3, top_k=2)

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
                                                    s3_vec = encode_state_with_belief(node3_cur, belief_model, tracker)
                                                    ph3_vec = [1.0 if ph3 == ph else 0.0 for ph in PHASE_ORDER]
                                                    a_dummy = [0.0] * 47
                                                    v3 = float(self.q_model.predict_q(np.asarray([s3_vec + ph3_vec + a_dummy], dtype=np.float32))[0])
                                                our3_vals.append(v3)
                                            except Exception:
                                                pass
                                        v2 = max(our3_vals) if our3_vals else 0.5

                                    opp_vals.append(v2)
                                except Exception:
                                    pass

                            if opp_vals:
                                cand_scores[c_idx].append(float(np.mean(opp_vals)))
                    except Exception:
                        pass
            finally:
                agent_mod._sb_end()

        # Score aggregation
        ranked = []
        for idx, vals in cand_scores.items():
            if vals:
                ranked.append((float(np.mean(vals)), idx))

        if not ranked:
            return [cands[0]]

        ranked.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return [ranked[0][1]]
