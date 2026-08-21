"""Ogerpon Energy Density Neighborhood Search & Calibration Tool for Project Mew."""

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


def build_energy_neighborhood():
    out_dir = ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_s0 = [int(line.strip()) for line in open(ROOT_DIR / "metaZ_teal_ogerpon_top10.csv") if line.strip()]
    assert len(base_s0) == 60

    variants = {}

    # 1. S0 (Control, 17 Energy)
    variants["S0_Control"] = (list(base_s0), "S0 Control (17 Basic Grass Energy, 2x Jumbo Ice Cream)")

    # 2. E18 (18 Energy: -1 Ice Cream, +1 Grass Energy)
    e18 = list(base_s0)
    e18.remove(1147)
    e18.append(1)
    variants["E18"] = (e18, "E18 (18 Basic Grass Energy: -1 Jumbo Ice Cream, +1 Grass Energy)")

    # 3. E19 (19 Energy: -2 Ice Cream, +2 Grass Energy)
    e19 = list(base_s0)
    e19.remove(1147)
    e19.remove(1147)
    e19.extend([1, 1])
    variants["E19"] = (e19, "E19 (19 Basic Grass Energy: -2 Jumbo Ice Cream, +2 Grass Energy)")

    # 4. E20 (20 Energy: -2 Ice Cream, -1 Harlequin, +3 Grass Energy)
    e20 = list(base_s0)
    e20.remove(1147)
    e20.remove(1147)
    e20.remove(1223) # Harlequin
    e20.extend([1, 1, 1])
    variants["E20"] = (e20, "E20 (20 Basic Grass Energy: -2 Ice Cream, -1 Harlequin, +3 Grass Energy)")

    # 5. E19_Preserve (19 Energy: -1 Harlequin, -1 N's Plan, +2 Grass Energy -> Preserves 2x Jumbo Ice Cream)
    e19_p = list(base_s0)
    e19_p.remove(1223) # Harlequin
    e19_p.remove(1221) # N's Plan
    e19_p.extend([1, 1])
    variants["E19_Preserve"] = (e19_p, "E19_Preserve (19 Energy: -1 Harlequin, -1 N's Plan, +2 Energy, Preserves Ice Cream)")

    validated = {}
    for vid, (d_list, desc) in variants.items():
        assert len(d_list) == 60
        fpath = out_dir / f"{vid}.csv"
        fpath.write_text("\n".join(str(c) for c in d_list) + "\n", encoding="utf-8")
        n_energy = sum(1 for c in d_list if c == 1)
        validated[vid] = {"path": str(fpath), "desc": desc, "deck_list": d_list, "n_energy": n_energy}
        print(f"Validated {vid:14s} ({n_energy} Basic Energy, 60 cards): {desc}")

    return validated


def compute_opening_probabilities(n_energy, n_basics=4, n_search=8, N=60, k=7):
    def hypergeom_pmf(N, M, k, x):
        return (math.comb(M, x) * math.comb(N - M, k - x)) / math.comb(N, k)

    p_basic = 1.0 - hypergeom_pmf(N, n_basics, k, 0)
    p_energy = 1.0 - hypergeom_pmf(N, n_energy, k, 0)
    p_search = 1.0 - hypergeom_pmf(N, n_search, k, 0)
    
    # Approx joint P(Basic >= 1 and Energy >= 1)
    # Using multinomial distribution of non-overlapping sets:
    p_no_basic = hypergeom_pmf(N, n_basics, k, 0)
    p_no_energy = hypergeom_pmf(N, n_energy, k, 0)
    p_neither = (math.comb(N - n_basics - n_energy, k)) / math.comb(N, k) if (N - n_basics - n_energy) >= k else 0.0
    p_both = 1.0 - p_no_basic - p_no_energy + p_neither

    return {
        "p_basic": p_basic,
        "p_energy": p_energy,
        "p_search": p_search,
        "p_basic_and_energy": p_both
    }


def run_neighborhood_screens(variants):
    out_dir = ROOT_DIR / "runs" / "energy_neighborhood"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n========================================================")
    print("PHASE 1: 120-Game Screen vs MetaPool v2 (5 Games x 24 Cells)")
    print("========================================================")

    screen_results = {}
    csv_rows = []

    for vid, info in variants.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\nScreening {vid} ({info['desc']})...")
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=5, workers=6)

        probs = compute_opening_probabilities(info["n_energy"])

        screen_results[vid] = {
            "name": vid,
            "description": info["desc"],
            "n_energy": info["n_energy"],
            "win_rate": res["overall_win_rate"],
            "wilson_ci": res["overall_wilson_ci"],
            "tier_summary": res["tier_summary"],
            "probabilities": probs
        }
        wr = res["overall_win_rate"] * 100
        lo = res["overall_wilson_ci"][0] * 100
        hi = res["overall_wilson_ci"][1] * 100
        csv_rows.append([vid, info["desc"], info["n_energy"], f"{wr:.1f}%", f"[{lo:.1f}%, {hi:.1f}%]"])

    (out_dir / "energy_screening_results.json").write_text(json.dumps(screen_results, indent=2), encoding="utf-8")
    return screen_results


def run_full_validation(top_variants):
    out_dir = ROOT_DIR / "runs" / "energy_neighborhood"

    print("\n========================================================")
    print("PHASE 2: Full 480-Game MetaPool v2 & 300g S0 Head-to-Head")
    print("========================================================")

    full_results = {}

    for vid, info in top_variants.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\nRunning 480-Game MetaPool v2 Validation for {vid}...")
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=20, workers=6)

        print(f"Running 300-Game Direct Head-to-Head: {vid} vs S0 Control...")
        h2h = ab_gate.run_gate(
            spec_c=spec_c,
            spec_i="metaZ_teal_ogerpon_top10.csv",
            games=300,
            workers=6
        )

        st = h2h["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        p, lo, hi = ab_gate.wilson(w, w + l)

        full_results[vid] = {
            "metapool_480g_wr": res["overall_win_rate"],
            "metapool_480g_ci": res["overall_wilson_ci"],
            "tier_summary": res["tier_summary"],
            "h2h_300g_wins": w,
            "h2h_300g_losses": l,
            "h2h_300g_draws": d,
            "h2h_300g_wr": float(p),
            "h2h_300g_ci": [float(lo), float(hi)],
            "h2h_wins_seat0": st["wins_seat0"],
            "h2h_wins_seat1": st["wins_seat1"],
            "bench_outs": st["reasons_lost"].get(3, 0),
            "prize_losses": st["reasons_lost"].get(1, 0),
            "deckouts": st["reasons_lost"].get(2, 0)
        }

    (out_dir / "energy_full_validation_results.json").write_text(json.dumps(full_results, indent=2), encoding="utf-8")
    return full_results


if __name__ == "__main__":
    variants = build_energy_neighborhood()
    screens = run_neighborhood_screens(variants)

    # Sort and pick top 2 non-S0 candidates for full 480g + 300g H2H
    sorted_non_s0 = sorted([(k, v) for k, v in screens.items() if k != "S0_Control"], key=lambda x: -x[1]["win_rate"])
    top_candidates = {k: variants[k] for k, _ in sorted_non_s0[:2]}
    print(f"\nPromoting Top 2 Candidates to Full 480g + 300g Validation: {list(top_candidates.keys())}")
    run_full_validation(top_candidates)
