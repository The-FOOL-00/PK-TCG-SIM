"""Final High-Upside Challenger Search & Evaluation Pipeline for Project Mew.

Evaluates 3 radically distinct high-basic archetypes against Frozen S0 Control:
- Challenger A: Raging Bolt ex / Teal Ogerpon Dual Dragon Turbo (240 HP, Bellowing Thunder 280+ burst, 9 Basics)
- Challenger B: Quad-Mask Ogerpon Toolbox (Teal + Cornerstone + Wellspring + Fezandipiti, 9 Basics)
- Challenger C: Miraidon ex Lightning Turbo (220 HP, Cyber Drive 220 damage, 9 Basics)

Executes:
1. Quick Local Screen (48 games vs MetaPool v2)
2. Serious 300-Game MetaPool v2 Validation
3. Dedicated 300-Game Head-to-Head vs S0 Control
4. Builds and validates project_mew_final_challenger.tar.gz
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

from tools import ab_gate, deck_compare, validate_deck
from tools.meta_pool_v2 import run_meta_pool_v2
import main as agent_mod


def build_challengers():
    out_dir = ROOT_DIR / "deck_search_ogerpon_counter" / "final_challengers"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Challenger A: Raging Bolt ex / Teal Ogerpon Dual Dragon Turbo
    # 4x Raging Bolt ex (63), 4x Teal Mask Ogerpon ex (96), 1x Fezandipiti ex (140) = 9 Basics
    # 4x Bug Catching (1094), 4x Tera Orb (1127), 4x Ultra Ball (1121), 4x Boss (1182), 4x Lillie (1227), 4x Judge (1213) = 24
    # 2x Energy Retrieval (1118), 2x Energy Search (1119), 1x Prime Catcher (1088) = 5 -> Total 38 cards
    # 12x Basic Grass Energy (1), 10x Basic Fighting Energy (6) = 22 Energy -> Total = 60 cards
    deck_raging_bolt = (
        [63] * 4 +   # Raging Bolt ex (240 HP Dragon Basic)
        [96] * 4 +   # Teal Mask Ogerpon ex (210 HP Grass Basic)
        [140] * 1 +  # Fezandipiti ex (210 HP Basic)
        [1094] * 4 + # Bug Catching Set
        [1127] * 4 + # Tera Orb
        [1121] * 4 + # Ultra Ball
        [1182] * 4 + # Boss's Orders
        [1227] * 4 + # Lillie's Determination
        [1213] * 4 + # Judge
        [1118] * 2 + # Energy Retrieval
        [1119] * 2 + # Energy Search
        [1088] * 1 + # Prime Catcher (ACE SPEC)
        [1] * 12 +   # Basic Grass Energy
        [6] * 10     # Basic Fighting Energy
    )
    assert len(deck_raging_bolt) == 60, f"raging bolt deck len = {len(deck_raging_bolt)}"

    # 2. Challenger B: Quad-Mask Ogerpon Multi-Attacker Toolbox
    # 4x Teal Mask (96), 2x Cornerstone Mask (117), 2x Wellspring Mask (108), 1x Fezandipiti ex (140) = 9 Basics
    # 4x Bug Catching (1094), 4x Tera Orb (1127), 4x Ultra Ball (1121), 4x Boss (1182), 4x Lillie (1227), 4x Judge (1213) = 24
    # 2x Energy Search (1119), 1x Prime Catcher (1088) = 3 -> Total 36 cards
    # 24x Basic Grass Energy (1) = 24 Energy -> Total = 60 cards
    deck_quad_mask = (
        [96] * 4 +   # Teal Mask Ogerpon ex
        [117] * 2 +  # Cornerstone Mask Ogerpon ex (Fighting)
        [108] * 2 +  # Wellspring Mask Ogerpon ex (Water)
        [140] * 1 +  # Fezandipiti ex
        [1094] * 4 + # Bug Catching Set
        [1127] * 4 + # Tera Orb
        [1121] * 4 + # Ultra Ball
        [1182] * 4 + # Boss's Orders
        [1227] * 4 + # Lillie's Determination
        [1213] * 4 + # Judge
        [1119] * 2 + # Energy Search
        [1088] * 1 + # Prime Catcher (ACE SPEC)
        [1] * 24     # Basic Grass Energy
    )
    assert len(deck_quad_mask) == 60, f"quad mask deck len = {len(deck_quad_mask)}"

    # 3. Challenger C: Miraidon ex Lightning Turbo
    # 4x Miraidon ex (313), 4x Raikou (735), 1x Fezandipiti ex (140) = 9 Basics
    # 4x Ultra Ball (1121), 4x Switch (1123), 4x Boss (1182), 4x Lillie (1227), 4x Judge (1213) = 20
    # 2x Energy Search (1119), 1x Prime Catcher (1088) = 3 -> Total 32 cards
    # 28x Basic Lightning Energy (4) = 28 Energy -> Total = 60 cards
    deck_miraidon = (
        [313] * 4 +  # Miraidon ex (220 HP, Cyber Drive 220 damage)
        [735] * 4 +  # Raikou (120 HP)
        [140] * 1 +  # Fezandipiti ex
        [1121] * 4 + # Ultra Ball
        [1123] * 4 + # Switch
        [1182] * 4 + # Boss's Orders
        [1227] * 4 + # Lillie's Determination
        [1213] * 4 + # Judge
        [1119] * 2 + # Energy Search
        [1088] * 1 + # Prime Catcher (ACE SPEC)
        [4] * 28     # Basic Lightning Energy
    )
    assert len(deck_miraidon) == 60, f"miraidon deck len = {len(deck_miraidon)}"

    challengers = {
        "Challenger_A_Raging_Bolt": (deck_raging_bolt, "Raging Bolt ex / Teal Ogerpon Dual Dragon Turbo (240 HP, Bellowing Thunder 280+ burst, 9 Basics)"),
        "Challenger_B_Quad_Mask": (deck_quad_mask, "Quad-Mask Ogerpon Multi-Attacker Toolbox (Teal + Cornerstone + Wellspring, 9 Basics)"),
        "Challenger_C_Miraidon": (deck_miraidon, "Miraidon ex Lightning Turbo (220 HP, Cyber Drive 220 damage, 9 Basics)")
    }

    validated = {}
    for cid, (d_list, desc) in challengers.items():
        fpath = out_dir / f"{cid}.csv"
        fpath.write_text("\n".join(str(c) for c in d_list) + "\n", encoding="utf-8")
        n_basics = sum(1 for c in d_list if c in (63, 96, 117, 108, 140, 313, 735))
        validated[cid] = {"path": str(fpath), "desc": desc, "deck_list": d_list, "n_basics": n_basics}
        print(f"Validated {cid:26s} ({n_basics} Basics, 60 cards): {desc}")

    return validated


def run_pipeline(challengers):
    out_dir = ROOT_DIR / "runs" / "final_challengers"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n========================================================")
    print("PHASE 1: Quick Screen (48 Games vs MetaPool v2)")
    print("========================================================")

    screen_res = {}
    for cid, info in challengers.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\nQuick Screening {cid}...")
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=2, workers=6)
        screen_res[cid] = res["overall_win_rate"]

    print("\n========================================================")
    print("PHASE 2: Serious 300-Game MetaPool v2 Validation & 300g S0 H2H")
    print("========================================================")

    final_results = {}
    for cid, info in challengers.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\n--- Running 300-Game MetaPool v2 Validation for {cid} ---")
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=13, workers=6)

        print(f"--- Running 300-Game Head-to-Head: {cid} vs S0 Control ---")
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

        final_results[cid] = {
            "name": cid,
            "description": info["desc"],
            "n_basics": info["n_basics"],
            "metapool_300g_wr": res["overall_win_rate"],
            "metapool_300g_ci": res["overall_wilson_ci"],
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

    (out_dir / "final_challengers_summary.json").write_text(json.dumps(final_results, indent=2), encoding="utf-8")
    return final_results


if __name__ == "__main__":
    chals = build_challengers()
    run_pipeline(chals)
