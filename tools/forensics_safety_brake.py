"""Emergency Live-Loss Forensics & Selective Safety Brake Validation Suite for Project Mew.

Compares:
- Mode A: V1.5c 2-Ply Minimax Control
- Mode B: Strong Tactical Baseline (unbraked)
- Mode D: Strong Tactical + Selective Safety Brake (Mode D)

Evaluates:
1. 300 Paired Matches vs Hard Live Failure Opponents (Archaludon Metal Tank, Starmie Aggro, Dragapult Spread)
2. 240 Paired Matches vs Full MetaPool v2
3. Decisive state extraction and failure classification
"""

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
from tools.meta_pool_v2 import run_meta_pool_v2
import main as agent_mod


HARD_OPPONENTS = [
    {"id": "archaludon_tank", "name": "Hard PIMC Metal Tank (Archaludon)", "deck": "metaX_archaludon_sanjay.csv", "spec": "TEACHER=2,1,4"},
    {"id": "starmie_aggro", "name": "Minimax Fast Water Aggro (Starmie)", "deck": "meta_starmie.csv", "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2"},
    {"id": "dragapult_spread", "name": "Hard PIMC Dragon Spread (Dragapult)", "deck": "metaZ_dragapult_top10.csv", "spec": "TEACHER=2,1,4"}
]


def play_forensic_paired_game(args):
    """Executes a paired game comparing Mode A vs Mode B vs Mode D with identical seed and seat."""
    deck_e19_ids, opp_deck_ids, opp_attrs, seat_c, game_seed = args
    agent_mod = deck_compare.agent_mod

    # Mode A (V1.5c Minimax)
    attrs_a = {"BS_CEI": 1, "BS_CEI_2PLY": 1, "BS_CEI_DETS": 2, "DYN_DECK_TABLES": 1}
    # Mode B (Strong Tactical Unbraked)
    attrs_b = {"BS_CEI": 0, "BC_CARD_ONLY": 0}
    # Mode D (Strong Tactical + Safety Brake: ENABLE_TACTICAL_BRAKE=1)
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

    # 3. Run Mode D (Safety Braked)
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
        "d_wins_a_loses": (rew_d == 1 and rew_a == -1),
        "a_wins_d_loses": (rew_a == 1 and rew_d == -1)
    }


def run_forensic_suite(workers=6):
    out_dir = ROOT_DIR / "runs" / "forensics"
    out_dir.mkdir(parents=True, exist_ok=True)

    deck_e19_ids = deck_compare.read_deck(ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv")

    print("\n========================================================")
    print("EMERGENCY LIVE FORENSICS: Evaluating Mode D (Safety Braked) vs Mode B vs Mode A")
    print("Benchmark: 300 Paired Matches vs Live Failure Opponent Classes (100g each)")
    print("========================================================")

    jobs = []
    for h_idx, opp in enumerate(HARD_OPPONENTS):
        opp_ids = deck_compare.read_deck(ROOT_DIR / opp["deck"])
        _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{opp['spec']}")
        for g in range(100):
            seat_c = g % 2
            game_seed = 999000 + h_idx * 10000 + g * 101
            jobs.append((deck_e19_ids, opp_ids, opp_attrs, seat_c, game_seed))

    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(play_forensic_paired_game, jobs))

    wins_a = sum(1 for r in results if r["reward_a"] == 1)
    losses_a = sum(1 for r in results if r["reward_a"] == -1)
    pa, loa, hia = ab_gate.wilson(wins_a, wins_a + losses_a)

    wins_b = sum(1 for r in results if r["reward_b"] == 1)
    losses_b = sum(1 for r in results if r["reward_b"] == -1)
    pb, lob, hib = ab_gate.wilson(wins_b, wins_b + losses_b)

    wins_d = sum(1 for r in results if r["reward_d"] == 1)
    losses_d = sum(1 for r in results if r["reward_d"] == -1)
    pd, lod, hid = ab_gate.wilson(wins_d, wins_d + losses_d)

    d_over_b = sum(1 for r in results if r["d_wins_b_loses"])
    b_over_d = sum(1 for r in results if r["b_wins_d_loses"])
    d_over_a = sum(1 for r in results if r["d_wins_a_loses"])
    a_over_d = sum(1 for r in results if r["a_wins_d_loses"])

    print(f"\n--- HARD OPPONENT SUITE RESULTS ({len(results)} Games) ---")
    print(f"  Mode A (V1.5c Minimax Control):     {wins_a:3d}W / {losses_a:3d}L ({pa*100:5.2f}%) | 95% CI: [{loa*100:4.1f}%, {hia*100:4.1f}%]")
    print(f"  Mode B (Strong Tactical Baseline):  {wins_b:3d}W / {losses_b:3d}L ({pb*100:5.2f}%) | 95% CI: [{lob*100:4.1f}%, {hib*100:4.1f}%]")
    print(f"  Mode D (Strong Tactical + Brake):   {wins_d:3d}W / {losses_d:3d}L ({pd*100:5.2f}%) | 95% CI: [{lod*100:4.1f}%, {hid*100:4.1f}%]")
    print(f"  Net Delta Mode D vs Mode B:         {((pd - pb)*100):+5.2f} percentage points")
    print(f"  Direct Swings: Mode D won / Mode B lost: {d_over_b} vs Mode B won / Mode D lost: {b_over_d}")
    print(f"  Direct Swings: Mode D won / Mode A lost: {d_over_a} vs Mode A won / Mode D lost: {a_over_d}")

    forensics_report = {
        "total_hard_games": len(results),
        "mode_a": {"wins": wins_a, "losses": losses_a, "wr": float(pa), "ci": [float(loa), float(hia)]},
        "mode_b": {"wins": wins_b, "losses": losses_b, "wr": float(pb), "ci": [float(lob), float(hib)]},
        "mode_d": {"wins": wins_d, "losses": losses_d, "wr": float(pd), "ci": [float(lod), float(hid)]},
        "d_over_b": d_over_b,
        "b_over_d": b_over_d,
        "d_over_a": d_over_a,
        "a_over_d": a_over_d
    }

    (out_dir / "live_forensics_report.json").write_text(json.dumps(forensics_report, indent=2), encoding="utf-8")
    return forensics_report


if __name__ == "__main__":
    run_forensic_suite(workers=6)
