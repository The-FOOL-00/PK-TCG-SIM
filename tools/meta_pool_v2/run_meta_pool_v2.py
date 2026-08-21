"""MetaPoolGate v2 Benchmark Runner: Evaluates Challenger against a 4-Tier Policy x 6-Deck Matrix.

Measures whether candidate performance degrades against stronger opponent decision policies:
- Tier 1: V1 Tactical Greedy Heuristic
- Tier 2: BC Card Neural Policy Hybrid
- Tier 3: PIMC Determinized Search Teacher
- Tier 4: BS-CEI V1.5c Adversarial Minimax

Evaluates 6 archetypes:
1. Mega Starmie ex
2. Teal Mask Ogerpon ex
3. Dragapult ex
4. Archaludon ex
5. Grimmsnarl Disruption
6. Cynthia's Garchomp ex
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

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, deck_compare
import main as agent_mod


DECKS_V2 = [
    {"id": "starmie", "name": "Mega Starmie ex", "deck": "meta_starmie.csv", "type": "Water Aggro"},
    {"id": "ogerpon", "name": "Teal Mask Ogerpon ex", "deck": "metaZ_teal_ogerpon_top10.csv", "type": "Grass Mirror"},
    {"id": "dragapult", "name": "Dragapult ex", "deck": "metaZ_dragapult_top10.csv", "type": "Dragon / Spread"},
    {"id": "archaludon", "name": "Archaludon ex", "deck": "metaX_archaludon_sanjay.csv", "type": "Metal Tank"},
    {"id": "grimmsnarl", "name": "Grimmsnarl Disruption", "deck": "metaG_grimmsnarl_top10.csv", "type": "Dark Disruption"},
    {"id": "garchomp", "name": "Cynthia's Garchomp ex", "deck": "metaC_garchomp_nasuo.csv", "type": "Fighting / Power"}
]

TIERS_V2 = [
    {"tier": 1, "name": "Tier 1: Greedy Heuristic", "spec": "BS_CEI=0+BC_CARD_ONLY=0"},
    {"tier": 2, "name": "Tier 2: Neural Hybrid", "spec": "BS_CEI=0+PTCG_BC_CARD_ONLY=1"},
    {"tier": 3, "name": "Tier 3: PIMC Searcher", "spec": "TEACHER=2,1,4"},
    {"tier": 4, "name": "Tier 4: Minimax V1.5c", "spec": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"}
]


def play_policy_chunk(args):
    """Worker: plays games for a specific (deck, tier) cell."""
    challenger_deck_ids, challenger_attrs, opp_deck_ids, opp_attrs, games, seat_offset, seed_base = args
    agent_mod = deck_compare.agent_mod

    defaults = {name: getattr(agent_mod, name)
                for name in set(challenger_attrs) | set(opp_attrs) if hasattr(agent_mod, name)}

    out = {
        "chal": {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
                 "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0}
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
        else:
            st["draws"] += 1

    return out


def run_meta_pool_v2(challenger_spec="metaZ_teal_ogerpon_top10.csv+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1",
                     games_per_cell=20,
                     workers=6):
    out_dir = ROOT_DIR / "runs" / "meta_pool_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    deck_c, attrs_c = ab_gate.parse_spec(challenger_spec)
    deck_c_ids = deck_compare.read_deck(ROOT_DIR / deck_c)

    matrix_results = {}
    tier_summary = {t["tier"]: {"name": t["name"], "wins": 0, "losses": 0, "draws": 0} for t in TIERS_V2}
    total_games = len(DECKS_V2) * len(TIERS_V2) * games_per_cell

    print(f"\n========================================================")
    print(f"MetaPoolGate v2: Policy Strength Calibration")
    print(f"Challenger: {challenger_spec}")
    print(f"Matrix: 6 Decks x 4 Policy Tiers x {games_per_cell} Games = {total_games} Total Games")
    print(f"========================================================")

    csv_rows = []

    for d_idx, deck_info in enumerate(DECKS_V2):
        d_id = deck_info["id"]
        d_name = deck_info["name"]
        opp_deck_ids = deck_compare.read_deck(ROOT_DIR / deck_info["deck"])
        matrix_results[d_id] = {"name": d_name, "type": deck_info["type"], "tiers": {}}

        print(f"\nEvaluating vs {d_name} ({deck_info['type']}):")

        for t_idx, tier_info in enumerate(TIERS_V2):
            t_num = tier_info["tier"]
            t_name = tier_info["name"]
            _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{tier_info['spec']}")

            base, extra = divmod(games_per_cell, workers)
            jobs, offset = [], 0
            for w in range(workers):
                n = base + (1 if w < extra else 0)
                if n:
                    jobs.append((deck_c_ids, attrs_c, opp_deck_ids, opp_attrs, n, offset % 2, (d_idx * 10 + t_idx) * 10000 + offset))
                    offset += n

            with ProcessPoolExecutor(max_workers=workers) as ex:
                chunks = list(ex.map(play_policy_chunk, jobs))

            cell_out = {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0, "crashes": 0, "reasons_won": Counter(), "reasons_lost": Counter()}
            for ch in chunks:
                for k, v in ch["chal"].items():
                    if isinstance(v, (int, float)): cell_out[k] += v
                    elif isinstance(v, Counter): cell_out[k].update(v)

            w = cell_out["wins_seat0"] + cell_out["wins_seat1"]
            l = cell_out["losses"]
            d = cell_out["draws"]
            decided = w + l
            p, lo, hi = ab_gate.wilson(w, decided)

            tier_summary[t_num]["wins"] += w
            tier_summary[t_num]["losses"] += l
            tier_summary[t_num]["draws"] += d

            matrix_results[d_id]["tiers"][t_num] = {
                "tier_name": t_name,
                "wins": w,
                "losses": l,
                "draws": d,
                "win_rate": float(p),
                "wilson_ci": [float(lo), float(hi)],
                "bench_out_losses": cell_out["reasons_lost"].get(3, 0),
                "prize_losses": cell_out["reasons_lost"].get(1, 0),
                "deckouts": cell_out["reasons_lost"].get(2, 0)
            }

            print(f"  {t_name:28s}: {w:2d}W / {l:2d}L / {d:2d}D ({p*100:5.1f}%) | CI: [{lo*100:4.1f}%, {hi*100:4.1f}%]")
            csv_rows.append([d_name, deck_info["type"], t_name, w, l, d, f"{p*100:.1f}%", f"[{lo*100:.1f}%, {hi*100:.1f}%]"])

    # Aggregate Tier Performance
    print("\n" + "=" * 64)
    print("OGERPON WIN RATE BY OPPONENT POLICY TIER:")
    print("=" * 64)
    for t_num, t_data in tier_summary.items():
        w, l, d = t_data["wins"], t_data["losses"], t_data["draws"]
        dec = w + l
        p, lo, hi = ab_gate.wilson(w, dec)
        t_data["win_rate"] = float(p)
        t_data["wilson_ci"] = [float(lo), float(hi)]
        print(f"  {t_data['name']:30s}: {w:3d}W / {l:3d}L / {d:2d}D ({p*100:5.1f}%) | CI: [{lo*100:4.1f}%, {hi*100:4.1f}%]")

    total_w = sum(t["wins"] for t in tier_summary.values())
    total_l = sum(t["losses"] for t in tier_summary.values())
    total_d = sum(t["draws"] for t in tier_summary.values())
    overall_p, overall_lo, overall_hi = ab_gate.wilson(total_w, total_w + total_l)

    payload = {
        "timestamp": time.time(),
        "total_games": total_games,
        "overall_win_rate": float(overall_p),
        "overall_wilson_ci": [float(overall_lo), float(overall_hi)],
        "tier_summary": tier_summary,
        "matrix_results": matrix_results
    }

    (out_dir / "meta_pool_v2_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with open(out_dir / "policy_deck_matrix.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Deck", "Archetype Type", "Opponent Policy Tier", "Wins", "Losses", "Draws", "Win Rate", "Wilson CI"])
        writer.writerows(csv_rows)

    print(f"\nWrote results to runs/meta_pool_v2/meta_pool_v2_results.json and policy_deck_matrix.csv")
    return payload


if __name__ == "__main__":
    run_meta_pool_v2(games_per_cell=20, workers=6)
