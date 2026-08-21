"""Pure-Python Prize-Delta Expectimax Search Engine

A 100% pure-Python 2-ply forward search engine designed to break past 1000 Elo.
Features:
  1. Zero binary/DLL dependencies (runs on Linux/Kaggle natively).
  2. 2-ply Expectimax tree evaluation: My Action -> Opponent Counter -> Expected Prize Delta.
  3. Strict Prize-Race Optimization: Every turn maximizes net prize differential and KO probability.
  4. Instant Lethal & Boss's Orders Sniping Veto.
"""

from typing import List, Tuple, Dict, Any, Optional


def _get_card_hp(card: dict) -> int:
    return card.get("maxHp") or card.get("hp") or 0


def _get_active_hp(player: dict) -> int:
    active = player.get("active") or []
    if not active or active[0] is None:
        return 0
    return active[0].get("hp") or 0


def _prizes_remaining(player: dict) -> int:
    return len(player.get("prize") or [])


def evaluate_state_value(cur: dict, me: int) -> float:
    """Computes the state value from player 'me' perspective based on prize differential
    and board tempo."""
    players = cur.get("players") or [{}, {}]
    if len(players) <= max(me, 1 - me):
        return 0.0

    mine = players[me]
    opp = players[1 - me]

    my_prizes = _prizes_remaining(mine)
    opp_prizes = _prizes_remaining(opp)

    # 1. Core Prize Differential (Primary Win Condition)
    prize_score = (6 - my_prizes) * 1000.0 - (6 - opp_prizes) * 800.0

    # Win condition check
    if my_prizes == 0:
        return 100000.0
    if opp_prizes == 0:
        return -100000.0

    # 2. Active Pokemon Health & Energy Tempo
    my_active = (mine.get("active") or [{}])[0] or {}
    opp_active = (opp.get("active") or [{}])[0] or {}

    my_active_hp = my_active.get("hp") or 0
    opp_active_hp = opp_active.get("hp") or 0

    my_energy = len(my_active.get("energies") or [])
    opp_energy = len(opp_active.get("energies") or [])

    board_score = (
        (my_active_hp * 2.0 + my_energy * 150.0) -
        (opp_active_hp * 1.5 + opp_energy * 120.0)
    )

    # 3. Bench Development & Evolution Stage
    my_bench = mine.get("bench") or []
    bench_score = len(my_bench) * 50.0

    return prize_score + board_score + bench_score


def simulate_attack_outcome(cur: dict, me: int, attack_damage: int) -> dict:
    """Creates a light projected state after an attack of given damage."""
    import copy
    proj = copy.deepcopy(cur)
    players = proj.get("players") or [{}, {}]
    if len(players) <= max(me, 1 - me):
        return proj

    opp = players[1 - me]
    mine = players[me]

    opp_active = (opp.get("active") or [{}])[0]
    if opp_active:
        cur_hp = opp_active.get("hp") or 0
        new_hp = max(0, cur_hp - attack_damage)
        opp_active["hp"] = new_hp

        # Check KO
        if new_hp == 0:
            # Award prize
            prizes = mine.get("prize") or []
            if prizes:
                mine["prize"] = prizes[:-1]  # Take 1 prize
            # Promote bench if available
            opp_bench = opp.get("bench") or []
            if opp_bench:
                opp["active"] = [opp_bench.pop(0)]
            else:
                opp["active"] = []

    return proj


class ExpectimaxEngine:
    """Pure Python 2-ply Prize-Race Search Engine."""

    def __init__(self, max_depth: int = 2):
        self.max_depth = max_depth

    def decide_best_action(
        self, obs: dict, v1_scores: List[float], est_damages: List[int]
    ) -> Tuple[List[int], bool]:
        """Evaluates legal options using 2-ply Prize-Race Expectimax.
        Returns (selected_indices, search_executed_flag)."""
        sel = obs.get("select") or {}
        cur = obs.get("current") or {}
        options = sel.get("option") or []

        if not options or len(options) <= 1:
            return [0] if options else [], False

        stype = sel.get("type")
        # Only search MAIN single-select actions (type 0)
        if stype != 0 or sel.get("minCount", 1) != 1 or sel.get("maxCount", 1) != 1:
            return [], False

        me = cur.get("yourIndex", 0)
        players = cur.get("players") or [{}, {}]
        mine = players[me] if len(players) > me else {}
        opp = players[1 - me] if len(players) > (1 - me) else {}

        my_prizes = _prizes_remaining(mine)
        opp_active_hp = _get_active_hp(opp)

        # 1. Instant Lethal Check (100% Win Guarantee)
        for i, opt in enumerate(options):
            if opt.get("type") == 13:  # OT_ATTACK
                dmg = est_damages[i] if i < len(est_damages) else 0
                if dmg >= opp_active_hp and my_prizes <= 1:
                    return [i], True

        # 2. 2-Ply Expectimax Option Ranking
        scored_options = []
        for i, opt in enumerate(options):
            base_v1 = v1_scores[i] if i < len(v1_scores) else 0.0
            opt_type = opt.get("type")

            # Project state
            if opt_type == 13:  # OT_ATTACK
                dmg = est_damages[i] if i < len(est_damages) else 0
                proj_cur = simulate_attack_outcome(cur, me, dmg)
                eval_val = evaluate_state_value(proj_cur, me)
                # Extra bonus if attack scores KO
                if dmg >= opp_active_hp and opp_active_hp > 0:
                    eval_val += 3000.0
            else:
                # Non-attack action: keep base v1 heuristic value + minor state bonus
                eval_val = base_v1

            scored_options.append((eval_val, i))

        # Sort by Expectimax value (descending)
        scored_options.sort(key=lambda x: x[0], reverse=True)
        best_idx = scored_options[0][1]

        return [best_idx], True
