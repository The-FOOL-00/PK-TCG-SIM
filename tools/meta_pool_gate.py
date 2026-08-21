"""MetaPoolGate v1: Multi-Archetype Balanced Evaluation Benchmark for Project Mew.

Evaluates a candidate agent across 6 balanced opponent archetypes:
1. Mega Starmie ex (Water Aggro)
2. Teal Mask Ogerpon ex (Grass Mirror)
3. Dragapult ex (Dragon / Spread Damage)
4. Archaludon ex (Metal High-HP Tank)
5. Grimmsnarl (Dark Disruption / Single-Prize)
6. Cynthia's Garchomp ex (Fighting / Power Setup)

50 games per archetype = 300 total games per run.
Seats strictly alternated (25 seat 0, 25 seat 1 per archetype).
Independent seeds per game with zero cross-game state persistence.
"""

import sys
import os
import io
import json
import math
import time
import contextlib
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, deck_compare
import main as agent_mod


META_POOL_V1 = [
    {
        "id": "starmie",
        "name": "Mega Starmie ex",
        "deck": "meta_starmie.csv",
        "type": "Water Aggro",
        "games": 50
    },
    {
        "id": "ogerpon_mirror",
        "name": "Teal Mask Ogerpon ex",
        "deck": "metaZ_teal_ogerpon_top10.csv",
        "type": "Grass Mirror",
        "games": 50
    },
    {
        "id": "dragapult",
        "name": "Dragapult ex",
        "deck": "metaZ_dragapult_top10.csv",
        "type": "Dragon / Spread",
        "games": 50
    },
    {
        "id": "archaludon",
        "name": "Archaludon ex",
        "deck": "metaX_archaludon_sanjay.csv",
        "type": "Metal Tank",
        "games": 50
    },
    {
        "id": "grimmsnarl",
        "name": "Grimmsnarl Disruption",
        "deck": "metaG_grimmsnarl_top10.csv",
        "type": "Dark Disruption",
        "games": 50
    },
    {
        "id": "garchomp",
        "name": "Cynthia's Garchomp ex",
        "deck": "metaC_garchomp_nasuo.csv",
        "type": "Fighting / Power",
        "games": 50
    }
]


def play_meta_chunk(args):
    """Worker: plays games for a specific archetype chunk."""
    challenger_deck, challenger_attrs, opp_deck, opp_attrs, games, seat_offset, seed_base = args
    agent_mod = deck_compare.agent_mod

    defaults = {name: getattr(agent_mod, name)
                for name in set(challenger_attrs) | set(opp_attrs) if hasattr(agent_mod, name)}

    out = {
        "chal": {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
                 "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0, "latencies": []},
        "inc": {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
                "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0}
    }

    for g in range(games):
        seat_c = (seat_offset + g) % 2
        game_seed = seed_base + g * 10007 + seat_offset * 101

        wrappers = [None, None]
        wrappers[seat_c] = ab_gate.make_wrapper(challenger_deck, challenger_attrs, defaults, game_seed=game_seed)
        wrappers[1 - seat_c] = ab_gate.make_wrapper(opp_deck, opp_attrs, defaults, game_seed=game_seed + 1)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)

        ev = deck_compare.game_events(env)
        reason = (ev["result"] or {}).get("reason", 0)

        for side, seat in (("chal", seat_c), ("inc", 1 - seat_c)):
            st = out[side]
            if env.state[seat].status in ("INVALID", "ERROR", "TIMEOUT"):
                st["crashes"] += 1
            r = env.state[seat].reward
            if r == 1:
                st[f"wins_seat{seat}"] += 1
                st["reasons_won"][reason] += 1
            elif r == -1:
                st["losses"] += 1
                st["reasons_lost"][reason] += 1
            else:
                st["draws"] += 1

    return out


def run_meta_pool(challenger_spec="metaZ_teal_ogerpon_top10.csv+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1",
                  seed_offset=0,
                  workers=6):
    deck_c, attrs_c = ab_gate.parse_spec(challenger_spec)
    deck_c_ids = deck_compare.read_deck(ROOT_DIR / deck_c)

    pool_results = {}
    total_wins = 0
    total_losses = 0
    total_draws = 0
    total_bench_outs = 0
    total_prize_losses = 0
    total_deckouts = 0
    total_crashes = 0

    print(f"\n========================================================")
    print(f"MetaPoolGate v1 Benchmark (Seed Offset: {seed_offset})")
    print(f"Challenger: {challenger_spec}")
    print(f"Pool: 6 Archetypes x 50 Games = 300 Total Games")
    print(f"========================================================")

    for arch in META_POOL_V1:
        arch_name = arch["name"]
        arch_deck_path = ROOT_DIR / arch["deck"]
        opp_deck_ids = deck_compare.read_deck(arch_deck_path)
        opp_attrs = {}

        games = arch["games"]
        base, extra = divmod(games, workers)
        jobs, offset = [], 0
        for w in range(workers):
            n = base + (1 if w < extra else 0)
            if n:
                jobs.append((deck_c_ids, attrs_c, opp_deck_ids, opp_attrs, n, offset % 2, seed_offset * 500000 + offset))
                offset += n

        with ProcessPoolExecutor(max_workers=workers) as ex:
            chunks = list(ex.map(play_meta_chunk, jobs))

        arch_out = {
            "wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
            "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0
        }
        for ch in chunks:
            for k, v in ch["chal"].items():
                if isinstance(v, (int, float)):
                    arch_out[k] += v
                elif isinstance(v, Counter):
                    arch_out[k].update(v)

        w = arch_out["wins_seat0"] + arch_out["wins_seat1"]
        l = arch_out["losses"]
        d = arch_out["draws"]
        decided = w + l
        p, lo, hi = ab_gate.wilson(w, decided)

        bench_out = arch_out["reasons_lost"].get(3, 0)
        prize_loss = arch_out["reasons_lost"].get(1, 0)
        deckout = arch_out["reasons_lost"].get(2, 0)

        total_wins += w
        total_losses += l
        total_draws += d
        total_bench_outs += bench_out
        total_prize_losses += prize_loss
        total_deckouts += deckout
        total_crashes += arch_out["crashes"]

        pool_results[arch["id"]] = {
            "name": arch["name"],
            "type": arch["type"],
            "deck": arch["deck"],
            "games": games,
            "wins": w,
            "wins_seat0": arch_out["wins_seat0"],
            "wins_seat1": arch_out["wins_seat1"],
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_out_losses": bench_out,
            "prize_losses": prize_loss,
            "deckout_losses": deckout,
            "crashes": arch_out["crashes"]
        }

        print(f"  {arch_name:25s} ({arch['type']:18s}): {w:2d}W / {l:2d}L / {d:2d}D ({p*100:5.1f}%) | CI: [{lo*100:4.1f}%, {hi*100:4.1f}%] | BO: {bench_out:2d}, PZ: {prize_loss:2d}, DO: {deckout:2d}")

    total_decided = total_wins + total_losses
    overall_p, overall_lo, overall_hi = ab_gate.wilson(total_wins, total_decided)

    full_report = {
        "timestamp": time.time(),
        "seed_offset": seed_offset,
        "challenger_spec": challenger_spec,
        "total_games": len(META_POOL_V1) * 50,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_draws": total_draws,
        "overall_win_rate": float(overall_p),
        "overall_wilson_ci": [float(overall_lo), float(overall_hi)],
        "total_bench_out_losses": total_bench_outs,
        "total_prize_losses": total_prize_losses,
        "total_deckouts": total_deckouts,
        "total_crashes": total_crashes,
        "matchup_breakdown": pool_results
    }

    print("=" * 64)
    print(f"METAPOOL V1 OVERALL RESULT: {total_wins}W / {total_losses}L / {total_draws}D ({overall_p*100:.1f}%)")
    print(f"95% Wilson CI: [{overall_lo*100:.1f}%, {overall_hi*100:.1f}%]")
    print(f"Loss Profile: Bench-Out {total_bench_outs}, Prize Loss {total_prize_losses}, Deckouts {total_deckouts}, Crashes {total_crashes}")
    print("=" * 64)

    return full_report


if __name__ == "__main__":
    out_dir = ROOT_DIR / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run 1: Primary Balanced 300g Evaluation
    res1 = run_meta_pool(seed_offset=1, workers=6)
    (out_dir / "meta_pool_v1_300.json").write_text(json.dumps(res1, indent=2), encoding="utf-8")

    # Run 2: Replicate Check (Independent Seed Offset)
    res2 = run_meta_pool(seed_offset=2, workers=6)
    (out_dir / "meta_pool_v1_300_replicate.json").write_text(json.dumps(res2, indent=2), encoding="utf-8")
