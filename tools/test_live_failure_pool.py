"""LiveFailurePool Benchmark (300 Paired Games) matching Window D Opponent Population."""

import sys
import os
import io
import json
import math
import time
import csv
import contextlib
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, deck_compare

# Exact Window D Matchup Distribution:
# 1. 120 games vs Teal Ogerpon Mirror (Mirror-Optimal Policy)
# 2. 105 games vs Mega Starmie (Water Aggro Minimax)
# 3. 75 games vs Archaludon Metal Tank (Hard PIMC Tank)
# Total = 300 Paired Games

WINDOW_D_OPPONENTS = [
    {"name": "Ogerpon Mirror Optimal", "deck": "metaZ_teal_ogerpon_top10.csv", "spec": "BS_CEI=0+BC_CARD_ONLY=0", "games": 120},
    {"name": "Mega Starmie Minimax", "deck": "meta_starmie.csv", "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2", "games": 105},
    {"name": "Archaludon PIMC Tank", "deck": "metaX_archaludon_sanjay.csv", "spec": "TEACHER=2,1,4", "games": 75}
]


def play_failure_pool_game(args):
    deck_e19_ids, opp_deck_ids, opp_attrs, seat_c, game_seed = args
    agent_mod = deck_compare.agent_mod

    # Mode A: V1.5c Minimax Control
    attrs_a = {"BS_CEI": 1, "BS_CEI_2PLY": 1, "BS_CEI_DETS": 2, "DYN_DECK_TABLES": 1}
    # Mode B: Current Strong Tactical (Unbraked)
    attrs_b = {"BS_CEI": 0, "BC_CARD_ONLY": 0}
    # Mode D: Strong Tactical v2 (Enhanced Gust + Retaliation Brake)
    attrs_d = {"BS_CEI": 0, "BC_CARD_ONLY": 0, "ENABLE_TACTICAL_BRAKE": 1}

    defaults = {name: getattr(agent_mod, name)
                for name in set(attrs_a) | set(attrs_b) | set(attrs_d) | set(opp_attrs) if hasattr(agent_mod, name)}

    # 1. Run Mode A
    w_a = [None, None]
    w_a[seat_c] = ab_gate.make_wrapper(deck_e19_ids, attrs_a, defaults, game_seed=game_seed)
    w_a[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_a = deck_compare.make("cabt", debug=True)
        env_a.run(w_a)
    rew_a = env_a.state[seat_c].reward

    # 2. Run Mode B
    w_b = [None, None]
    w_b[seat_c] = ab_gate.make_wrapper(deck_e19_ids, attrs_b, defaults, game_seed=game_seed)
    w_b[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_b = deck_compare.make("cabt", debug=True)
        env_b.run(w_b)
    rew_b = env_b.state[seat_c].reward

    # 3. Run Mode D
    w_d = [None, None]
    w_d[seat_c] = ab_gate.make_wrapper(deck_e19_ids, attrs_d, defaults, game_seed=game_seed)
    w_d[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_d = deck_compare.make("cabt", debug=True)
        env_d.run(w_d)
    rew_d = env_d.state[seat_c].reward

    return {
        "game_seed": game_seed,
        "seat": seat_c,
        "reward_a": rew_a,
        "reward_b": rew_b,
        "reward_d": rew_d,
        "d_wins_b_loses": (rew_d == 1 and rew_b == -1),
        "b_wins_d_loses": (rew_b == 1 and rew_d == -1),
        "b_wins_a_loses": (rew_b == 1 and rew_a == -1),
        "a_wins_b_loses": (rew_a == 1 and rew_b == -1)
    }


def run_live_failure_pool(workers=6):
    out_dir = ROOT_DIR / "runs" / "live_failure_pool"
    out_dir.mkdir(parents=True, exist_ok=True)

    deck_e19_ids = deck_compare.read_deck(ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv")

    print("\n========================================================")
    print("RUNNING LIVE FAILURE POOL (300 Paired Games across Window D Matchups)")
    print("========================================================")

    jobs = []
    for opp_idx, opp in enumerate(WINDOW_D_OPPONENTS):
        opp_ids = deck_compare.read_deck(ROOT_DIR / opp["deck"])
        _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{opp['spec']}")
        for g in range(opp["games"]):
            seat_c = g % 2
            game_seed = 777000 + opp_idx * 10000 + g * 101
            jobs.append((deck_e19_ids, opp_ids, opp_attrs, seat_c, game_seed))

    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(play_failure_pool_game, jobs))

    wins_a = sum(1 for r in results if r["reward_a"] == 1)
    losses_a = sum(1 for r in results if r["reward_a"] == -1)
    pa, loa, hia = ab_gate.wilson(wins_a, wins_a + losses_a)

    wins_b = sum(1 for r in results if r["reward_b"] == 1)
    losses_b = sum(1 for r in results if r["reward_b"] == -1)
    pb, lob, hib = ab_gate.wilson(wins_b, wins_b + losses_b)

    wins_d = sum(1 for r in results if r["reward_d"] == 1)
    losses_d = sum(1 for r in results if r["reward_d"] == -1)
    pd, lod, hid = ab_gate.wilson(wins_d, wins_d + losses_d)

    print(f"\n--- LIVE FAILURE POOL (WINDOW D MATCHUPS) RESULTS (300 Games) ---")
    print(f"  Mode A (V1.5c Minimax Control):     {wins_a:3d}W / {losses_a:3d}L ({pa*100:5.2f}%) | 95% CI: [{loa*100:4.1f}%, {hia*100:4.1f}%]")
    print(f"  Mode B (Current Strong Tactical):   {wins_b:3d}W / {losses_b:3d}L ({pb*100:5.2f}%) | 95% CI: [{lob*100:4.1f}%, {hib*100:4.1f}%]")
    print(f"  Mode D (Strong Tactical v2 Fix):    {wins_d:3d}W / {losses_d:3d}L ({pd*100:5.2f}%) | 95% CI: [{lod*100:4.1f}%, {hid*100:4.1f}%]")
    print(f"  Delta Mode B over Mode A:           {((pb - pa)*100):+5.2f} percentage points")
    print(f"  Delta Mode D over Mode B:           {((pd - pb)*100):+5.2f} percentage points")

    summary = {
        "games": len(results),
        "mode_a": {"wins": wins_a, "losses": losses_a, "wr": float(pa), "ci": [float(loa), float(hia)]},
        "mode_b": {"wins": wins_b, "losses": losses_b, "wr": float(pb), "ci": [float(lob), float(hib)]},
        "mode_d": {"wins": wins_d, "losses": losses_d, "wr": float(pd), "ci": [float(lod), float(hid)]}
    }

    (out_dir / "live_failure_pool_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    run_live_failure_pool(workers=6)
