"""Rigorous Paired A/B Policy Validation & Accounting Audit for Project Mew."""

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

from tools import ab_gate, deck_compare, validate_deck
from tools.meta_pool_v2 import run_meta_pool_v2
import main as agent_mod


DECKS_6 = [
    {"id": "starmie", "name": "Mega Starmie ex", "deck": "meta_starmie.csv", "type": "Water Aggro"},
    {"id": "ogerpon", "name": "Teal Mask Ogerpon ex", "deck": "metaZ_teal_ogerpon_top10.csv", "type": "Grass Mirror"},
    {"id": "dragapult", "name": "Dragapult ex", "deck": "metaZ_dragapult_top10.csv", "type": "Dragon / Spread"},
    {"id": "archaludon", "name": "Archaludon ex", "deck": "metaX_archaludon_sanjay.csv", "type": "Metal Tank"},
    {"id": "grimmsnarl", "name": "Grimmsnarl Disruption", "deck": "metaG_grimmsnarl_top10.csv", "type": "Dark Disruption"},
    {"id": "garchomp", "name": "Cynthia's Garchomp ex", "deck": "metaC_garchomp_nasuo.csv", "type": "Fighting / Power"}
]

TIERS_4 = [
    {"tier": 1, "name": "Tier 1: Greedy Heuristic", "spec": "BS_CEI=0+BC_CARD_ONLY=0"},
    {"tier": 2, "name": "Tier 2: Neural Hybrid", "spec": "BS_CEI=0+PTCG_BC_CARD_ONLY=1"},
    {"tier": 3, "name": "Tier 3: PIMC Searcher", "spec": "TEACHER=2,1,4"},
    {"tier": 4, "name": "Tier 4: Minimax V1.5c", "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"}
]


def play_paired_game(args):
    """Plays two games with the exact same seed: one for Mode A (Minimax), one for Mode B (Strong Tactical)."""
    deck_c_ids, opp_deck_ids, opp_attrs, seat_c, game_seed = args
    agent_mod = deck_compare.agent_mod

    # Mode A attrs (V1.5c Minimax)
    attrs_a = {"BS_CEI": 1, "BS_CEI_2PLY": 1, "BS_CEI_DETS": 2, "DYN_DECK_TABLES": 1}
    # Mode B attrs (Strong Tactical Heuristic)
    attrs_b = {"BS_CEI": 0, "BC_CARD_ONLY": 0}

    defaults = {name: getattr(agent_mod, name)
                for name in set(attrs_a) | set(attrs_b) | set(opp_attrs) if hasattr(agent_mod, name)}

    # Run Mode A
    wrappers_a = [None, None]
    wrappers_a[seat_c] = ab_gate.make_wrapper(deck_c_ids, attrs_a, defaults, game_seed=game_seed)
    wrappers_a[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_a = deck_compare.make("cabt", debug=True)
        env_a.run(wrappers_a)
    rew_a = env_a.state[seat_c].reward

    # Run Mode B with the EXACT SAME game seed
    wrappers_b = [None, None]
    wrappers_b[seat_c] = ab_gate.make_wrapper(deck_c_ids, attrs_b, defaults, game_seed=game_seed)
    wrappers_b[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env_b = deck_compare.make("cabt", debug=True)
        env_b.run(wrappers_b)
    rew_b = env_b.state[seat_c].reward

    return {
        "game_seed": game_seed,
        "seat": seat_c,
        "reward_a": rew_a,
        "reward_b": rew_b,
        "b_wins_a_loses": (rew_b == 1 and rew_a == -1),
        "a_wins_b_loses": (rew_a == 1 and rew_b == -1),
        "both_win": (rew_a == 1 and rew_b == 1),
        "both_lose": (rew_a == -1 and rew_b == -1)
    }


def run_paired_ab_benchmark(deck_file, games_per_cell=20, workers=6):
    deck_c_ids = deck_compare.read_deck(ROOT_DIR / deck_file)
    total_games = len(DECKS_6) * len(TIERS_4) * games_per_cell

    print(f"\n========================================================")
    print(f"Paired A/B Benchmark: Mode A (V1.5c Minimax) vs Mode B (Strong Tactical)")
    print(f"Deck: {deck_file}")
    print(f"Structure: 6 Decks x 4 Tiers x {games_per_cell} Games = {total_games} Paired Matches")
    print(f"========================================================")

    jobs = []
    for d_idx, d_info in enumerate(DECKS_6):
        opp_deck_ids = deck_compare.read_deck(ROOT_DIR / d_info["deck"])
        for t_idx, t_info in enumerate(TIERS_4):
            _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{t_info['spec']}")
            for g in range(games_per_cell):
                seat_c = g % 2
                game_seed = (d_idx * 10 + t_idx) * 10000 + g * 101 + seat_c * 17
                jobs.append((deck_c_ids, opp_deck_ids, opp_attrs, seat_c, game_seed))

    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(play_paired_game, jobs))

    wins_a = sum(1 for r in results if r["reward_a"] == 1)
    losses_a = sum(1 for r in results if r["reward_a"] == -1)
    draws_a = sum(1 for r in results if r["reward_a"] == 0)
    pa, loa, hia = ab_gate.wilson(wins_a, wins_a + losses_a)

    wins_b = sum(1 for r in results if r["reward_b"] == 1)
    losses_b = sum(1 for r in results if r["reward_b"] == -1)
    draws_b = sum(1 for r in results if r["reward_b"] == 0)
    pb, lob, hib = ab_gate.wilson(wins_b, wins_b + losses_b)

    b_over_a = sum(1 for r in results if r["b_wins_a_loses"])
    a_over_b = sum(1 for r in results if r["a_wins_b_loses"])
    both_w = sum(1 for r in results if r["both_win"])
    both_l = sum(1 for r in results if r["both_lose"])

    # McNemar's Test for paired nominal data
    # chi2 = ( |b_over_a - a_over_b| - 1 )^2 / (b_over_a + a_over_b)
    discordant = b_over_a + a_over_b
    chi2 = ((abs(b_over_a - a_over_b) - 1) ** 2 / discordant) if discordant > 0 else 0.0

    print(f"\n--- PAIRED BENCHMARK RESULTS ({len(results)} Games) ---")
    print(f"  Mode A (V1.5c Minimax):      {wins_a:3d}W / {losses_a:3d}L / {draws_a:2d}D ({pa*100:5.2f}%) | 95% CI: [{loa*100:4.1f}%, {hia*100:4.1f}%]")
    print(f"  Mode B (Strong Tactical):   {wins_b:3d}W / {losses_b:3d}L / {draws_b:2d}D ({pb*100:5.2f}%) | 95% CI: [{lob*100:4.1f}%, {hib*100:4.1f}%]")
    print(f"  Net Delta (B - A):           {((pb - pa) * 100):+5.2f} percentage points")
    print(f"  Paired Discordant Transitions: Mode B Won / Mode A Lost: {b_over_a} | Mode A Won / Mode B Lost: {a_over_b}")
    print(f"  McNemar Chi-Square Statistic: {chi2:6.2f} (p < 0.001 if > 10.83)")

    summary = {
        "deck": deck_file,
        "total_paired_games": len(results),
        "mode_a": {"wins": wins_a, "losses": losses_a, "draws": draws_a, "win_rate": float(pa), "ci": [float(loa), float(hia)]},
        "mode_b": {"wins": wins_b, "losses": losses_b, "draws": draws_b, "win_rate": float(pb), "ci": [float(lob), float(hib)]},
        "b_won_a_lost": b_over_a,
        "a_won_b_lost": a_over_b,
        "both_won": both_w,
        "both_lost": both_l,
        "mcnemar_chi2": float(chi2)
    }
    return summary


def run_strong_pool_benchmark(workers=6):
    print("\n========================================================")
    print("Extended StrongPolicyPool Benchmark (300 Paired Games across 3 Hard Families)")
    print("========================================================")

    hard_opponents = [
        ("metaX_archaludon_sanjay.csv", "TEACHER=2,1,4", "Hard PIMC Metal Tank"),
        ("meta_starmie.csv", "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2", "Minimax Water Aggro"),
        ("metaZ_dragapult_top10.csv", "TEACHER=2,1,4", "Hard PIMC Dragon Spread")
    ]

    deck_e19_ids = deck_compare.read_deck(ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv")
    jobs = []

    for h_idx, (opp_deck_file, opp_spec, desc) in enumerate(hard_opponents):
        opp_ids = deck_compare.read_deck(ROOT_DIR / opp_deck_file)
        _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{opp_spec}")
        for g in range(100):
            seat_c = g % 2
            game_seed = 888000 + h_idx * 10000 + g * 101
            jobs.append((deck_e19_ids, opp_ids, opp_attrs, seat_c, game_seed))

    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(play_paired_game, jobs))

    w_a = sum(1 for r in results if r["reward_a"] == 1)
    l_a = sum(1 for r in results if r["reward_a"] == -1)
    pa, loa, hia = ab_gate.wilson(w_a, w_a + l_a)

    w_b = sum(1 for r in results if r["reward_b"] == 1)
    l_b = sum(1 for r in results if r["reward_b"] == -1)
    pb, lob, hib = ab_gate.wilson(w_b, w_b + l_b)

    b_over_a = sum(1 for r in results if r["b_wins_a_loses"])
    a_over_b = sum(1 for r in results if r["a_wins_b_loses"])

    print(f"\n--- STRONG POLICY POOL RESULTS ({len(results)} Games) ---")
    print(f"  Mode A (V1.5c Minimax):      {w_a:3d}W / {l_a:3d}L ({pa*100:5.2f}%) | 95% CI: [{loa*100:4.1f}%, {hia*100:4.1f}%]")
    print(f"  Mode B (Strong Tactical):   {w_b:3d}W / {l_b:3d}L ({pb*100:5.2f}%) | 95% CI: [{lob*100:4.1f}%, {hib*100:4.1f}%]")
    print(f"  Net Delta (B - A):           {((pb - pa) * 100):+5.2f} percentage points")
    print(f"  Direct Swings: B won / A lost: {b_over_a} vs A won / B lost: {a_over_b}")

    return {
        "games": len(results),
        "mode_a_wr": float(pa), "mode_a_ci": [float(loa), float(hia)],
        "mode_b_wr": float(pb), "mode_b_ci": [float(lob), float(hib)],
        "b_over_a": b_over_a, "a_over_b": a_over_b
    }


if __name__ == "__main__":
    out_dir = ROOT_DIR / "runs" / "rigorous_validation"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run paired benchmark on E19 (480 games)
    e19_summary = run_paired_ab_benchmark("deck_search_ogerpon_counter/energy_neighborhood/E19.csv", games_per_cell=20, workers=6)

    # 2. Run paired benchmark on S0 (480 games)
    s0_summary = run_paired_ab_benchmark("metaZ_teal_ogerpon_top10.csv", games_per_cell=20, workers=6)

    # 3. Run StrongPolicyPool benchmark (300 games)
    strong_summary = run_strong_pool_benchmark(workers=6)

    payload = {
        "e19_benchmark_480g": e19_summary,
        "s0_benchmark_480g": s0_summary,
        "strong_pool_300g": strong_summary
    }

    (out_dir / "rigorous_validation_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\nRigorous paired validation complete. Report saved to runs/rigorous_validation/rigorous_validation_report.json")
