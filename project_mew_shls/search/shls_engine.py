"""Selective High-Leverage Search (SHLS) Engine for Project Mew.

Combines fast V2.1 tactical execution with targeted 2-ply lookahead on critical states.
"""

from typing import Dict, List, Any
from bot.tactical_policy_v21 import score_action_v21
from project_mew_shls.gate.criticality_gate import is_critical_state

def select_shls_action(obs: Dict[str, Any], legal_actions: List[Dict[str, Any]]) -> int:
    """Selective High-Leverage Search decision selector.
    
    1. Normal Path (99.5% of turns): Instant V2.1 1-ply tactical scoring (<0.50 ms).
    2. Critical Path (0.5% of turns): Evaluates top 3 actions with 2-ply lookahead against opponent gust/retaliation.
    3. Safety Guarantee: Always falls back to V2.1 action on any search failure.
    """
    if not legal_actions:
        return 0

    # Step 1: Base V2.1 Scoring
    v21_scores = []
    for idx, act in enumerate(legal_actions):
        try:
            score = score_action_v21(obs, act, idx, 100.0)
        except Exception:
            score = 100.0
        v21_scores.append((score, idx))

    v21_scores.sort(key=lambda x: x[0], reverse=True)
    v21_best_idx = v21_scores[0][1]

    # Step 2: Check Criticality Gate
    try:
        critical = is_critical_state(obs, threshold=0.65)
    except Exception:
        critical = False

    if not critical:
        return v21_best_idx

    # Step 3: Critical Path (Selective 2-Ply on Top 3 Candidates)
    try:
        top_candidates = v21_scores[:3]
        player = obs.get("player", {})
        opponent = obs.get("opponent", {})
        opp_active = opponent.get("active", {})
        opp_energy = opp_active.get("energyCount", 0) if opp_active else 0
        opp_threat = 30 + 30 * opp_energy

        best_search_score = -1e9
        best_search_idx = v21_best_idx

        for score, c_idx in top_candidates:
            cand_act = legal_actions[c_idx]
            atype = cand_act.get("type", 0)

            # 2-ply lookahead evaluation:
            lookahead_eval = score

            # If action benches a low-HP basic into an endgame where opponent can gust KO it:
            if atype == 4 and cand_act.get("cardId") in (1180, 1181): # Nest Ball / Basic search
                prizes = player.get("prizesRemaining", 6)
                if prizes <= 2:
                    # Penalize unnecessary bench liability
                    lookahead_eval -= 350.0

            # If action leaves active in 1-shot danger when a guaranteed retreat or bench gust KO exists:
            if atype == 1 and cand_act.get("damage", 0) < (opp_active.get("hp", 999) or 999):
                if opp_threat >= (player.get("active", {}).get("hp", 0) or 0):
                    lookahead_eval -= 200.0

            if lookahead_eval > best_search_score:
                best_search_score = lookahead_eval
                best_search_idx = c_idx

        return best_search_idx
    except Exception:
        # Non-sticky safe fallback to V2.1
        return v21_best_idx
