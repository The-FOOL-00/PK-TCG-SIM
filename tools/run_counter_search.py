"""Targeted Ogerpon Counter Search & MetaPool v2 Validation Tool."""

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


def build_weakness_map():
    out_dir = ROOT_DIR / "deck_search_ogerpon_counter" / "weakness_map"
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    weakness_map = {
        "FIRE_WEAKNESS": {
            "mechanism": "Teal Mask Ogerpon ex is Grass-type, taking 2x weakness damage from Fire attacks.",
            "impact": "110+ Fire base damage deals 220+ damage, scoring instant 1-hit KOs on 210 HP Ogerpon.",
            "counter_family": "Fire Basic Aggro (Gouging Fire ex / Hearthflame Ogerpon ex)",
            "confidence": "HIGH"
        },
        "SAFEGUARD_ANTI_EX_IMMUNITY": {
            "mechanism": "Ogerpon is exclusively a 2-prize Pokemon ex; Mimikyu/Miltank block all damage from ex Pokemon.",
            "impact": "Ogerpon cannot damage Safeguard single-prize walls, forcing pass-turns and stall deckouts.",
            "counter_family": "Single-Prize Anti-EX Wall (Mimikyu / Miltank / Crushing Hammer)",
            "confidence": "HIGH"
        },
        "HIGH_HP_METAL_RESISTANCE": {
            "mechanism": "Archaludon ex possesses 300 HP and Metal energy recovery, requiring 3+ attacks to breach.",
            "impact": "Absorbs multiple Ogerpon hits while trading 2-prize knockouts.",
            "counter_family": "Metal High-HP Tank (Archaludon ex)",
            "confidence": "MEDIUM"
        }
    }

    (data_dir / "ogerpon_weakness_map.json").write_text(json.dumps(weakness_map, indent=2), encoding="utf-8")
    (out_dir / "ogerpon_weakness_map.json").write_text(json.dumps(weakness_map, indent=2), encoding="utf-8")
    print("Ogerpon Weakness Map built.")
    return weakness_map


def build_counter_decks():
    c_dir = ROOT_DIR / "deck_search_ogerpon_counter" / "candidates"
    c_dir.mkdir(parents=True, exist_ok=True)

    # 1. Gouging Fire ex Aggro
    # 4x Gouging Fire ex (46), 2x Hearthflame Ogerpon (99), 2x Chi-Yu (719), 4x Ultra Ball (1121), 4x Switch (1123),
    # 4x Boss's Orders (1182), 4x Lillie (1227), 4x Waitress (1235), 2x Cyrano (1205), 1x Prime Catcher (1088), 18x Fire Energy (2)
    deck_gouging = (
        [46] * 4 +   # Gouging Fire ex (Basic, 230 HP)
        [99] * 2 +   # Hearthflame Mask Ogerpon ex (Basic, 210 HP)
        [719] * 2 +  # Chi-Yu (Basic, 110 HP)
        [1121] * 4 + # Ultra Ball
        [1123] * 4 + # Switch
        [1182] * 4 + # Boss's Orders
        [1227] * 4 + # Lillie's Determination
        [1235] * 4 + # Waitress
        [1205] * 2 + # Cyrano
        [1088] * 1 + # Prime Catcher (ACE SPEC)
        [2] * 29     # Basic Fire Energy (Total = 60 cards)
    )
    # Adjust count to exactly 60: 4+2+2+4+4+4+4+4+2+1 = 31 trainers/pokes -> 29 energy = 60 cards.
    assert len(deck_gouging) == 60

    # 2. Hearthflame Mask Ogerpon Fire Turbo
    deck_hearthflame = (
        [99] * 4 +   # Hearthflame Mask Ogerpon ex (Basic, 210 HP)
        [719] * 2 +  # Chi-Yu (Basic, 110 HP)
        [1127] * 4 + # Tera Orb
        [1094] * 4 + # Bug Catching Set
        [1123] * 4 + # Switch
        [1182] * 4 + # Boss's Orders
        [1227] * 4 + # Lillie's Determination
        [1235] * 4 + # Waitress
        [1159] * 1 + # Hero's Cape (ACE SPEC)
        [2] * 29     # Basic Fire Energy
    )
    assert len(deck_hearthflame) == 60

    # 3. Safeguard Anti-EX Wall
    deck_safeguard = (
        [767] * 4 +  # Mimikyu (Safeguard, Basic 70 HP)
        [703] * 4 +  # Miltank (Miracle Body, Basic 120 HP)
        [1120] * 4 + # Crushing Hammer
        [1121] * 4 + # Ultra Ball
        [1123] * 4 + # Switch
        [1182] * 4 + # Boss's Orders
        [1213] * 4 + # Judge
        [1227] * 4 + # Lillie's Determination
        [1159] * 1 + # Hero's Cape (ACE SPEC)
        [5] * 27     # Basic Psychic Energy
    )
    assert len(deck_safeguard) == 60

    # 4. Archaludon ex Metal Tank (Existing legal deck)
    deck_archaludon = [int(line.strip()) for line in open(ROOT_DIR / "metaX_archaludon_sanjay.csv") if line.strip()]
    assert len(deck_archaludon) == 60

    candidate_files = {
        "Counter_Gouging_Fire": (deck_gouging, "Gouging Fire ex Basic Fire Aggro (2x Weakness Exploiter)"),
        "Counter_Hearthflame_Ogerpon": (deck_hearthflame, "Hearthflame Mask Ogerpon ex Fire Turbo"),
        "Counter_Safeguard_Anti_EX": (deck_safeguard, "Mimikyu / Miltank Safeguard Anti-EX Wall"),
        "Counter_Archaludon_Metal": (deck_archaludon, "Archaludon ex 300 HP Metal Bridge Tank")
    }

    validated_paths = {}
    for cid, (d_list, desc) in candidate_files.items():
        fpath = c_dir / f"{cid}.csv"
        fpath.write_text("\n".join(str(c) for c in d_list) + "\n", encoding="utf-8")
        validated_paths[cid] = {"path": str(fpath), "desc": desc, "deck_list": d_list}
        print(f"Validated counter candidate {cid:30s} (60 cards, {len(Counter(d_list))} unique)")

    return validated_paths


def run_counter_evaluations(candidates):
    out_dir = ROOT_DIR / "deck_search_ogerpon_counter"
    h2h_results = {}
    screen_results = {}

    print("\n========================================================")
    print("PHASE 1: Dedicated 300-Game Head-to-Head vs Frozen Ogerpon")
    print("========================================================")

    ogerpon_spec = "metaZ_teal_ogerpon_top10.csv"

    for cid, info in candidates.items():
        print(f"\nRunning 300g Head-to-Head: {cid} vs Frozen Ogerpon S0...")
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"
        spec_i = ogerpon_spec

        total = ab_gate.run_gate(
            spec_c=spec_c,
            spec_i=spec_i,
            games=300,
            workers=6
        )

        st = total["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        decided = w + l
        p, lo, hi = ab_gate.wilson(w, decided)

        h2h_results[cid] = {
            "name": cid,
            "description": info["desc"],
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate_vs_ogerpon": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_outs": st["reasons_lost"].get(3, 0),
            "prize_losses": st["reasons_lost"].get(1, 0),
            "deckouts": st["reasons_lost"].get(2, 0)
        }

        print(f"  H2H Result vs Ogerpon: {w:3d}W / {l:3d}L / {d:2d}D ({p*100:5.1f}%) | CI: [{lo*100:4.1f}%, {hi*100:4.1f}%]")

    (out_dir / "ogerpon_h2h_results.json").write_text(json.dumps(h2h_results, indent=2), encoding="utf-8")

    print("\n========================================================")
    print("PHASE 2: MetaPool v2 Validation across 6 Decks x 4 Tiers")
    print("========================================================")

    metapool_results = {}
    for cid, info in candidates.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"

        print(f"\nEvaluating {cid} across MetaPool v2 (480 games)...")
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=20, workers=6)
        metapool_results[cid] = {
            "overall_win_rate": res["overall_win_rate"],
            "overall_wilson_ci": res["overall_wilson_ci"],
            "tier_summary": res["tier_summary"]
        }

    (out_dir / "meta_pool_counter_results.json").write_text(json.dumps(metapool_results, indent=2), encoding="utf-8")
    print("\nAll Counter evaluations complete.")
    return h2h_results, metapool_results


if __name__ == "__main__":
    build_weakness_map()
    candidates = build_counter_decks()
    run_counter_evaluations(candidates)
