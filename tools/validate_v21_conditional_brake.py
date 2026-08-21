"""V2.1 Outcome-Conditional Tactical Safety Brake Validation Suite for Project Mew."""

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

BENCHMARK_OPPONENTS = [
    {"name": "Teal Ogerpon Mirror", "deck": "metaZ_teal_ogerpon_top10.csv", "spec": "BS_CEI=0+BC_CARD_ONLY=0", "games": 100},
    {"name": "Mega Starmie Water Aggro", "deck": "meta_starmie.csv", "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2", "games": 100},
    {"name": "Archaludon Metal Tank", "deck": "metaX_archaludon_sanjay.csv", "spec": "TEACHER=2,1,4", "games": 100}
]

def play_v21_paired_game(args):
    deck_e19_ids, opp_deck_ids, opp_attrs, seat_c, game_seed = args
    agent_mod = deck_compare.agent_mod

    # Mode A: V1 (Unbraked Strong Tactical)
    attrs_v1 = {"BS_CEI": 0, "BC_CARD_ONLY": 0, "ENABLE_TACTICAL_BRAKE": 0}
    # Mode B: V2 (Broad Safety Brake)
    attrs_v2 = {"BS_CEI": 0, "BC_CARD_ONLY": 0, "ENABLE_TACTICAL_BRAKE": 1}
    # Mode C: V2.1 (Outcome-Conditional Brake)
    attrs_v21 = {"BS_CEI": 0, "BC_CARD_ONLY": 0, "ENABLE_TACTICAL_BRAKE": 2}

    defaults = {name: getattr(agent_mod, name)
                for name in set(attrs_v1) | set(attrs_v2) | set(attrs_v21) | set(opp_attrs) if hasattr(agent_mod, name)}

    # 1. Run V1
    w_v1 = [None, None]
    w_v1[seat_c] = ab_gate.make_wrapper(deck_e19_ids, attrs_v1, defaults, game_seed=game_seed)
    w_v1[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_v1 = deck_compare.make("cabt", debug=True)
        env_v1.run(w_v1)
    rew_v1 = env_v1.state[seat_c].reward

    # 2. Run V2
    w_v2 = [None, None]
    w_v2[seat_c] = ab_gate.make_wrapper(deck_e19_ids, attrs_v2, defaults, game_seed=game_seed)
    w_v2[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_v2 = deck_compare.make("cabt", debug=True)
        env_v2.run(w_v2)
    rew_v2 = env_v2.state[seat_c].reward

    # 3. Run V2.1
    w_v21 = [None, None]
    w_v21[seat_c] = ab_gate.make_wrapper(deck_e19_ids, attrs_v21, defaults, game_seed=game_seed)
    w_v21[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_v21 = deck_compare.make("cabt", debug=True)
        env_v21.run(w_v21)
    rew_v21 = env_v21.state[seat_c].reward

    return {
        "game_seed": game_seed,
        "seat": seat_c,
        "reward_v1": rew_v1,
        "reward_v2": rew_v2,
        "reward_v21": rew_v21,
        "v21_wins_v2_loses": (rew_v21 == 1 and rew_v2 == -1),
        "v2_wins_v21_loses": (rew_v2 == 1 and rew_v21 == -1),
        "v21_wins_v1_loses": (rew_v21 == 1 and rew_v1 == -1),
        "v1_wins_v21_loses": (rew_v1 == 1 and rew_v21 == -1)
    }

def run_v21_paired_validation(workers=6):
    out_dir = ROOT_DIR / "runs" / "v21_validation"
    out_dir.mkdir(parents=True, exist_ok=True)

    deck_e19_ids = deck_compare.read_deck(ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv")

    print("\n========================================================")
    print("RUNNING V2.1 CONDITIONAL BRAKE PAIRED VALIDATION (300 Matches)")
    print("========================================================")

    jobs = []
    for opp_idx, opp in enumerate(BENCHMARK_OPPONENTS):
        opp_ids = deck_compare.read_deck(ROOT_DIR / opp["deck"])
        _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{opp['spec']}")
        for g in range(opp["games"]):
            seat_c = g % 2
            game_seed = 666000 + opp_idx * 10000 + g * 101
            jobs.append((deck_e19_ids, opp_ids, opp_attrs, seat_c, game_seed))

    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(play_v21_paired_game, jobs))

    w_v1 = sum(1 for r in results if r["reward_v1"] == 1)
    l_v1 = sum(1 for r in results if r["reward_v1"] == -1)
    pv1, lov1, hiv1 = ab_gate.wilson(w_v1, w_v1 + l_v1)

    w_v2 = sum(1 for r in results if r["reward_v2"] == 1)
    l_v2 = sum(1 for r in results if r["reward_v2"] == -1)
    pv2, lov2, hiv2 = ab_gate.wilson(w_v2, w_v2 + l_v2)

    w_v21 = sum(1 for r in results if r["reward_v21"] == 1)
    l_v21 = sum(1 for r in results if r["reward_v21"] == -1)
    pv21, lov21, hiv21 = ab_gate.wilson(w_v21, w_v21 + l_v21)

    v21_over_v2 = sum(1 for r in results if r["v21_wins_v2_loses"])
    v2_over_v21 = sum(1 for r in results if r["v2_wins_v21_loses"])
    v21_over_v1 = sum(1 for r in results if r["v21_wins_v1_loses"])
    v1_over_v21 = sum(1 for r in results if r["v1_wins_v21_loses"])

    print(f"\n--- V2.1 PAIRED VALIDATION RESULTS (300 Games) ---")
    print(f"  V1 (Strong Tactical Baseline):     {w_v1:3d}W / {l_v1:3d}L ({pv1*100:5.2f}%) | 95% CI: [{lov1*100:4.1f}%, {hiv1*100:4.1f}%]")
    print(f"  V2 (Broad Safety Brake):          {w_v2:3d}W / {l_v2:3d}L ({pv2*100:5.2f}%) | 95% CI: [{lov2*100:4.1f}%, {hiv2*100:4.1f}%]")
    print(f"  V2.1 (Outcome-Conditional Brake): {w_v21:3d}W / {l_v21:3d}L ({pv21*100:5.2f}%) | 95% CI: [{lov21*100:4.1f}%, {hiv21*100:4.1f}%]")
    print(f"  Net Delta V2.1 vs V2:             {((pv21 - pv2)*100):+5.2f} percentage points")
    print(f"  Net Delta V2.1 vs V1:             {((pv21 - pv1)*100):+5.2f} percentage points")
    print(f"  Direct Swings: V2.1 won / V2 lost: {v21_over_v2} vs V2 won / V2.1 lost: {v2_over_v21}")

    summary = {
        "games": len(results),
        "v1": {"wins": w_v1, "losses": l_v1, "wr": float(pv1), "ci": [float(lov1), float(hiv1)]},
        "v2": {"wins": w_v2, "losses": l_v2, "wr": float(pv2), "ci": [float(lov2), float(hiv2)]},
        "v21": {"wins": w_v21, "losses": l_v21, "wr": float(pv21), "ci": [float(lov21), float(hiv21)]},
        "v21_over_v2": v21_over_v2, "v2_over_v21": v2_over_v21,
        "v21_over_v1": v21_over_v1, "v1_over_v21": v1_over_v21
    }

    (out_dir / "v21_validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

if __name__ == "__main__":
    run_v21_paired_validation(workers=6)
