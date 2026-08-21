"""Behavioral Adversary Stress Test Suite for Project Mew.

Constructs 8 distinct behavioral adversary policies:
1. PRIZE_RACE_AGGRESSOR: Prioritizes fastest prize gain and lethal attacks.
2. ANTI_TEAL_DANCE: Targets energy-bearing Pokemon to disrupt acceleration.
3. BENCH_HUNTER: Aggressively gusts and attacks backup basics.
4. FIRE_PRESSURE: High-tempo Fire aggression (Gouging Fire ex).
5. TANK_AND_TRADE: 300 HP Metal tanking (Archaludon ex).
6. GUST_PRIZE_TARGETER: Opportunistic Boss's Orders dragging ex targets.
7. MIRROR_OPTIMAL: Symmetrical Ogerpon mirror with minimax search.
8. ENDGAME_SPECIALIST: Resource preservation and endgame lock.

Evaluates 100 seat-alternated games per behavioral adversary against Frozen Ogerpon S0.
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
import main as agent_mod


ADVERSARIES = [
    {
        "id": "1_prize_race_aggressor",
        "name": "Prize-Race Aggressor",
        "deck": "meta_starmie.csv",
        "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2",
        "description": "Fast Water Aggro optimizing immediate prize knockouts"
    },
    {
        "id": "2_anti_teal_dance",
        "name": "Anti-Teal-Dance Disruption",
        "deck": "metaG_grimmsnarl_top10.csv",
        "spec": "TEACHER=2,1,4",
        "description": "Crushing Hammer & energy discard targeting accelerated energy"
    },
    {
        "id": "3_bench_hunter",
        "name": "Bench Hunter",
        "deck": "metaZ_dragapult_top10.csv",
        "spec": "TEACHER=2,1,4",
        "description": "Phantom Dive spread damage sniping benched backup basics"
    },
    {
        "id": "4_fire_pressure",
        "name": "Fire / Weakness Pressure",
        "deck": "deck_search_ogerpon_counter/candidates/Counter_Gouging_Fire.csv",
        "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2",
        "description": "230 HP Fire Basic attacking for 2x Grass weakness damage"
    },
    {
        "id": "5_tank_and_trade",
        "name": "Tank-and-Trade Metal",
        "deck": "metaX_archaludon_sanjay.csv",
        "spec": "TEACHER=2,1,4",
        "description": "300 HP Metal Bridge tank forcing unfavorable 2-prize trades"
    },
    {
        "id": "6_gust_prize_targeter",
        "name": "Gust / Prize Targeter",
        "deck": "meta_starmie.csv",
        "spec": "TEACHER=2,1,4",
        "description": "Search-driven gusting dragging vulnerable benched targets"
    },
    {
        "id": "7_mirror_optimal",
        "name": "Mirror-Optimal Ogerpon",
        "deck": "metaZ_teal_ogerpon_top10.csv",
        "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1",
        "description": "Symmetrical Teal Mask Ogerpon minimax mirror"
    },
    {
        "id": "8_endgame_specialist",
        "name": "Endgame Stall Specialist",
        "deck": "meta_mewtwo_stall.csv",
        "spec": "TEACHER=2,1,4",
        "description": "Energy denial, walling, and resource preservation"
    }
]


def play_adv_chunk(args):
    """Worker: plays n games for a specific behavioral adversary."""
    challenger_deck_ids, challenger_attrs, opp_deck_ids, opp_attrs, games, seat_offset, seed_base = args
    agent_mod = deck_compare.agent_mod

    defaults = {name: getattr(agent_mod, name)
                for name in set(challenger_attrs) | set(opp_attrs) if hasattr(agent_mod, name)}

    out = {
        "chal": {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
                 "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0},
        "failures": []
    }

    for g in range(games):
        seat_c = (seat_offset + g) % 2
        game_seed = seed_base + g * 10007 + seat_offset * 101

        wrappers = [None, None]
        wrappers[seat_c] = ab_gate.make_wrapper(challenger_deck_ids, challenger_attrs, defaults, game_seed=game_seed)
        wrappers[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)

        ev = deck_compare.game_events(env)
        reason = (ev["result"] or {}).get("reason", 0)

        st = out["chal"]
        if env.state[seat_c].status in ("INVALID", "ERROR", "TIMEOUT"):
            st["crashes"] += 1
        r = env.state[seat_c].reward
        if r == 1:
            st[f"wins_seat{seat_c}"] += 1
            st["reasons_won"][reason] += 1
        elif r == -1:
            st["losses"] += 1
            st["reasons_lost"][reason] += 1
            out["failures"].append({
                "game_seed": game_seed,
                "seat": seat_c,
                "reason_code": reason,
                "final_step": env.state[seat_c].observation.get("step", 0) if env.state[seat_c].observation else 0
            })
        else:
            st["draws"] += 1

    return out


def run_behavioral_stress_test(challenger_spec="metaZ_teal_ogerpon_top10.csv+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1",
                               games_per_adv=100,
                               workers=6):
    out_dir = ROOT_DIR / "data" / "behavioral_failures"
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = ROOT_DIR / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    deck_c, attrs_c = ab_gate.parse_spec(challenger_spec)
    deck_c_ids = deck_compare.read_deck(ROOT_DIR / deck_c)

    results = []
    all_failure_states = []

    print(f"\n========================================================")
    print(f"Behavioral Adversary Stress Test (8 Behaviors x {games_per_adv}g = 800 Games)")
    print(f"Challenger: {challenger_spec}")
    print(f"========================================================")

    csv_rows = []

    for a_idx, adv in enumerate(ADVERSARIES):
        a_id = adv["id"]
        a_name = adv["name"]
        opp_deck_ids = deck_compare.read_deck(ROOT_DIR / adv["deck"])
        _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{adv['spec']}")

        print(f"\nEvaluating vs {a_name} ({adv['description']})...")

        base, extra = divmod(games_per_adv, workers)
        jobs, offset = [], 0
        for w in range(workers):
            n = base + (1 if w < extra else 0)
            if n:
                jobs.append((deck_c_ids, attrs_c, opp_deck_ids, opp_attrs, n, offset % 2, a_idx * 100000 + offset))
                offset += n

        with ProcessPoolExecutor(max_workers=workers) as ex:
            chunks = list(ex.map(play_adv_chunk, jobs))

        adv_out = {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0, "crashes": 0, "reasons_lost": Counter(), "reasons_won": Counter()}
        for ch in chunks:
            for k, v in ch["chal"].items():
                if isinstance(v, (int, float)): adv_out[k] += v
                elif isinstance(v, Counter): adv_out[k].update(v)
            for f in ch.get("failures", []):
                f["adversary_id"] = a_id
                f["adversary_name"] = a_name
                all_failure_states.append(f)

        w = adv_out["wins_seat0"] + adv_out["wins_seat1"]
        l = adv_out["losses"]
        d = adv_out["draws"]
        decided = w + l
        p, lo, hi = ab_gate.wilson(w, decided)

        bo = adv_out["reasons_lost"].get(3, 0)
        pz = adv_out["reasons_lost"].get(1, 0)
        do = adv_out["reasons_lost"].get(2, 0)

        record = {
            "adversary_id": a_id,
            "name": a_name,
            "description": adv["description"],
            "deck": adv["deck"],
            "spec": adv["spec"],
            "games": games_per_adv,
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_outs": bo,
            "prize_losses": pz,
            "deckouts": do,
            "crashes": adv_out["crashes"]
        }
        results.append(record)

        print(f"  Result for {a_name:28s}: {w:3d}W / {l:3d}L / {d:2d}D ({p*100:5.1f}%) | CI: [{lo*100:4.1f}%, {hi*100:4.1f}%] | BO: {bo:2d}, PZ: {pz:2d}, DO: {do:2d}")
        csv_rows.append([a_name, adv["description"], w, l, d, f"{p*100:.1f}%", f"[{lo*100:.1f}%, {hi*100:.1f}%]", bo, pz, do])

    total_w = sum(r["wins"] for r in results)
    total_l = sum(r["losses"] for r in results)
    total_d = sum(r["draws"] for r in results)
    overall_p, overall_lo, overall_hi = ab_gate.wilson(total_w, total_w + total_l)

    summary_payload = {
        "timestamp": time.time(),
        "total_games": len(ADVERSARIES) * games_per_adv,
        "overall_win_rate": float(overall_p),
        "overall_wilson_ci": [float(overall_lo), float(overall_hi)],
        "adversaries": results,
        "total_failure_states_mined": len(all_failure_states)
    }

    (out_dir / "behavioral_failures_dataset.json").write_text(json.dumps(all_failure_states, indent=2), encoding="utf-8")
    (runs_dir / "behavioral_adversary_results.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    with open(runs_dir / "behavioral_adversary_table.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Behavioral Adversary", "Description", "Wins", "Losses", "Draws", "Win Rate", "Wilson CI", "Bench-Outs", "Prize Losses", "Deckouts"])
        writer.writerows(csv_rows)

    print("\n" + "=" * 64)
    print(f"BEHAVIORAL STRESS TEST AGGREGATE: {total_w}W / {total_l}L / {total_d}D ({overall_p*100:.1f}%)")
    print(f"95% Wilson CI: [{overall_lo*100:.1f}%, {overall_hi*100:.1f}%]")
    print(f"Total Failure States Collected: {len(all_failure_states)}")
    print("=" * 64)

    return summary_payload


if __name__ == "__main__":
    run_behavioral_stress_test(games_per_adv=100, workers=6)
