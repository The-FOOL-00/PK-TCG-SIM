"""Failure-Directed Ogerpon Deck Optimization Tool for Project Mew."""

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


def build_mutations():
    out_dir = ROOT_DIR / "deck_search_ogerpon_counter" / "mutations"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_s0 = [int(line.strip()) for line in open(ROOT_DIR / "metaZ_teal_ogerpon_top10.csv") if line.strip()]
    assert len(base_s0) == 60

    mutations = {}

    # Mut 1: +2 Switch (ID 1123) in place of 2x Jumbo Ice Cream (ID 1147) -> Solves Gust Trapping
    mut1 = list(base_s0)
    mut1.remove(1147)
    mut1.remove(1147)
    mut1.extend([1123, 1123]) # 2x Switch
    mutations["Mut1_Plus2_Switch"] = (mut1, "Replace 2x Jumbo Ice Cream with 2x Switch (Direct Gust Trap Defense)")

    # Mut 2: Prime Catcher (ID 1088) ACE SPEC in place of Hero's Cape (ID 1159)
    mut2 = list(base_s0)
    mut2.remove(1159)
    mut2.append(1088) # Prime Catcher (Gust + Switch ACE SPEC)
    mutations["Mut2_Prime_Catcher"] = (mut2, "Replace Hero's Cape with Prime Catcher ACE SPEC")

    # Mut 3: +2 Boss's Orders (ID 1182) (Total 4 Boss) in place of 2x Jumbo Ice Cream (ID 1147)
    mut3 = list(base_s0)
    mut3.remove(1147)
    mut3.remove(1147)
    mut3.extend([1182, 1182]) # 4x Boss's Orders Total
    mutations["Mut3_Max_Boss"] = (mut3, "Replace 2x Jumbo Ice Cream with 2x Boss's Orders (Max 4 Boss)")

    # Mut 4: +2 Grass Energy (Total 19 Energy) in place of 2x Jumbo Ice Cream
    mut4 = list(base_s0)
    mut4.remove(1147)
    mut4.remove(1147)
    mut4.extend([1, 1]) # 19x Basic Grass Energy
    mutations["Mut4_Plus2_Energy"] = (mut4, "Replace 2x Jumbo Ice Cream with 2x Basic Grass Energy")

    # Mut 5: +2 Switch + Prime Catcher (Combined Mobility & Gust)
    mut5 = list(base_s0)
    mut5.remove(1147)
    mut5.remove(1147)
    mut5.remove(1159) # Hero's Cape
    mut5.extend([1123, 1123, 1088]) # 2x Switch + 1x Prime Catcher
    mutations["Mut5_Switch_PrimeCatcher"] = (mut5, "2x Switch + Prime Catcher ACE SPEC (Max Mobility & Target Control)")

    validated_muts = {}
    for mid, (d_list, desc) in mutations.items():
        assert len(d_list) == 60
        fpath = out_dir / f"{mid}.csv"
        fpath.write_text("\n".join(str(c) for c in d_list) + "\n", encoding="utf-8")
        validated_muts[mid] = {"path": str(fpath), "desc": desc, "deck_list": d_list}
        print(f"Validated mutation {mid:28s} (60 cards, {len(Counter(d_list))} unique): {desc}")

    return validated_muts


def run_mutation_screening(mutations):
    out_dir = ROOT_DIR / "runs" / "deck_mutations"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n========================================================")
    print("PHASE 1: 100-Game Screen vs MetaPool v2 (6 Decks x 4 Tiers)")
    print("========================================================")

    screen_results = {}
    csv_rows = []

    for mid, info in mutations.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\nScreening {mid} ({info['desc']})...")
        # 100 games screen: 4 games per cell across 24 cells = 96 ~ 100 games
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=5, workers=6)

        screen_results[mid] = {
            "name": mid,
            "description": info["desc"],
            "win_rate": res["overall_win_rate"],
            "wilson_ci": res["overall_wilson_ci"],
            "tier_summary": res["tier_summary"]
        }
        wr = res["overall_win_rate"] * 100
        lo = res["overall_wilson_ci"][0] * 100
        hi = res["overall_wilson_ci"][1] * 100
        csv_rows.append([mid, info["desc"], f"{wr:.1f}%", f"[{lo:.1f}%, {hi:.1f}%]"])

    (out_dir / "mutation_screening_results.json").write_text(json.dumps(screen_results, indent=2), encoding="utf-8")
    return screen_results


def run_top_validation(top_mutations):
    out_dir = ROOT_DIR / "runs" / "deck_mutations"

    print("\n========================================================")
    print("PHASE 2: 300-Game Full MetaPool v2 & 200g Mirror Validation")
    print("========================================================")

    val_results = {}
    for mid, info in top_mutations.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\nRunning 300-Game Validation for {mid}...")
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=13, workers=6)

        # Dedicated 200g Mirror Match vs S0
        print(f"Running 200-Game Mirror Match: {mid} vs S0 Control...")
        m_res = ab_gate.run_gate(
            spec_c=spec_c,
            spec_i="metaZ_teal_ogerpon_top10.csv",
            games=200,
            workers=6
        )
        st = m_res["chal"]
        m_w = st["wins_seat0"] + st["wins_seat1"]
        m_l = st["losses"]
        m_p, m_lo, m_hi = ab_gate.wilson(m_w, m_w + m_l)

        val_results[mid] = {
            "metapool_300g_wr": res["overall_win_rate"],
            "metapool_300g_ci": res["overall_wilson_ci"],
            "mirror_200g_wr": float(m_p),
            "mirror_200g_ci": [float(m_lo), float(m_hi)],
            "mirror_wins_seat0": st["wins_seat0"],
            "mirror_wins_seat1": st["wins_seat1"],
            "bench_outs": st["reasons_lost"].get(3, 0),
            "prize_losses": st["reasons_lost"].get(1, 0)
        }

    (out_dir / "mutation_validation_results.json").write_text(json.dumps(val_results, indent=2), encoding="utf-8")
    return val_results


if __name__ == "__main__":
    muts = build_mutations()
    screens = run_mutation_screening(muts)
    
    # Sort and pick top 2 mutations for 300g + mirror validation
    sorted_muts = sorted(screens.items(), key=lambda x: -x[1]["win_rate"])
    top_candidates = {k: muts[k] for k, _ in sorted_muts[:2]}
    print(f"\nTop Candidates Promoted: {list(top_candidates.keys())}")
    run_top_validation(top_candidates)
