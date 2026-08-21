"""Comprehensive Archetype Search V2 Harness for Project Mew.

Evaluates 12-15 distinct legal archetypes against the frozen baseline
under the exact frozen BS-CEI V1.5c player (V0, 194-dim State+Belief, 2-Ply Minimax, 2 Belief Worlds).
Directly benchmarks against the 70.9% Teal Mask Ogerpon ex Champion.
"""

import json
import os
import sys
import time
import csv
from pathlib import Path
from collections import Counter
from kaggle_environments import make

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, validate_deck, build_submission
import main as agent_mod


ARCHETYPES_TO_EVALUATE = {
    "Ogerpon_S0_Control": {
        "path": "metaZ_teal_ogerpon_top10.csv",
        "name": "Teal Mask Ogerpon ex",
        "family": "Grass Acceleration (FROZEN CHAMPION)",
        "win_con": "Teal Dance self-acceleration + heavy basic damage"
    },
    "Starmie_S0_Aggro": {
        "path": "meta_starmie.csv",
        "name": "Mega Starmie ex",
        "family": "Water Aggro",
        "win_con": "Turn 2 Stage-1 burst attack (130 dmg)"
    },
    "Alakazam_Psychic": {
        "path": "metaB_alakazam.csv",
        "name": "Alakazam ex / Dudunsparce",
        "family": "Psychic Control",
        "win_con": "Hand attachment scaling + Dudunsparce draw engine"
    },
    "Grimmsnarl_Dark": {
        "path": "metaG_grimmsnarl_top10.csv",
        "name": "Grimmsnarl Disruption",
        "family": "Dark Disruption / Single-Prize",
        "win_con": "Energy discard & 1-prize trading economics"
    },
    "Mewtwo_Stall": {
        "path": "meta_mewtwo_stall.csv",
        "name": "Mewtwo ex Stall",
        "family": "Energy Denial / Stall",
        "win_con": "Energy denial, walling, and deckout pressure"
    },
    "Dragapult_Spread": {
        "path": "metaZ_dragapult_top10.csv",
        "name": "Dragapult ex",
        "family": "Dragon / Spread Damage",
        "win_con": "Phantom Dive 200 active + 60 bench spread"
    },
    "Archaludon_Metal": {
        "path": "metaX_archaludon_sanjay.csv",
        "name": "Archaludon ex",
        "family": "Metal High-HP Tank",
        "win_con": "300 HP Metal Bridge tanking & energy recovery"
    },
    "Fezandipiti_Revenge": {
        "path": "metaX_fezandipiti_top10.csv",
        "name": "Fezandipiti ex",
        "family": "Psychic Revenge Draw",
        "win_con": "Flip the Script 3-card draw upon knockout"
    },
    "Garchomp_Fighting": {
        "path": "metaC_garchomp_nasuo.csv",
        "name": "Cynthia's Garchomp ex",
        "family": "Fighting / Power Setup",
        "win_con": "Dragon/Fighting heavy single-hit KOs"
    },
    "Kangaskhan_Tank": {
        "path": "metaX_kangaskhan_top10.csv",
        "name": "Mega Kangaskhan ex",
        "family": "Colorless Tank",
        "win_con": "High HP single-energy early setup"
    },
    "Bellibolt_Lightning": {
        "path": "deck_search/candidates/Bellibolt_Lightning.csv",
        "name": "Iono's Bellibolt ex",
        "family": "Lightning Tempo",
        "win_con": "Iono's synergy & lightning tempo attacks"
    },
    "Junlee_Garchomp_Turbo": {
        "path": "junlee789_garchomp.csv",
        "name": "Junlee Garchomp Turbo",
        "family": "Fighting Turbo Setup",
        "win_con": "Fast Fighting acceleration & burst"
    },
    "Dark_Gengar_Hybrid": {
        "path": "deck_v2.csv",
        "name": "Dark Gengar Hybrid",
        "family": "Dark / Psychic Hybrid",
        "win_con": "Shadow attack disruption & damage placement"
    }
}


def run_full_search_v2():
    out_dir = Path("deck_search_v2")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Build Archetype Inventory
    inventory = {}
    for aid, spec in ARCHETYPES_TO_EVALUATE.items():
        fpath = ROOT_DIR / spec["path"]
        assert fpath.exists(), f"File {fpath} not found"
        deck_ids = [int(line.strip()) for line in fpath.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(deck_ids) == 60, f"Deck {aid} has {len(deck_ids)} cards"
        counts = Counter(deck_ids)
        inventory[aid] = {
            "id": aid,
            "name": spec["name"],
            "family": spec["family"],
            "win_con": spec["win_con"],
            "path": spec["path"],
            "cards_count": len(deck_ids),
            "unique_cards": len(counts)
        }
    
    (out_dir / "archetype_inventory_v2.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"--- Archetype Inventory V2 ({len(inventory)} archetypes) ---")
    for aid, info in inventory.items():
        print(f"  {aid:25s}: {info['family']:35s} | {info['win_con']}")

    # 2. 10-Game Sanity per Candidate
    print("\n--- Running 10-Game Sanity on All Archetypes ---")
    for aid, spec in ARCHETYPES_TO_EVALUATE.items():
        deck_ids = [int(line.strip()) for line in (ROOT_DIR / spec["path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
        wins, crashes = 0, 0
        for g in range(10):
            def p0(obs, _config):
                if obs.get("select") is None: return list(deck_ids)
                agent_mod.DECK = list(deck_ids)
                agent_mod.BS_CEI = True
                agent_mod.BS_CEI_2PLY = True
                agent_mod.BS_CEI_DETS = 2
                agent_mod.DYN_DECK_TABLES = True
                return agent_mod.agent(obs)
            def p1(obs, _config):
                if obs.get("select") is None: return list(deck_ids)
                agent_mod.DECK = list(deck_ids)
                agent_mod.BS_CEI = False
                return agent_mod.agent(obs)
            env = make("cabt", debug=False)
            env.run([p0, p1])
            st0 = env.state[0]
            if st0.status in ("INVALID", "ERROR", "TIMEOUT"): crashes += 1
            if (st0.reward or 0) == 1: wins += 1
        print(f"  {aid:25s}: {wins}/10 wins, {crashes} crashes -> {'PASS' if crashes == 0 else 'FAIL'}")

    # 3. 100-Game Screening vs Incumbent
    print("\n--- Running 100-Game Fast Screening on All Archetypes ---")
    screening_results = []
    for aid, spec in ARCHETYPES_TO_EVALUATE.items():
        print(f"\nScreening Archetype {aid} ({spec['name']})...")
        spec_c = f"{spec['path']}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"
        spec_i = "meta_starmie.csv"

        total = ab_gate.run_gate(
            spec_c=spec_c,
            spec_i=spec_i,
            games=100,
            workers=6
        )

        st = total["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        decided = w + l
        p, lo, hi = ab_gate.wilson(w, decided)

        l_reasons = st["reasons_lost"]
        bench_out = l_reasons.get(3, 0)
        prize_loss = l_reasons.get(1, 0)
        deckout = l_reasons.get(2, 0)

        record = {
            "archetype_id": aid,
            "name": spec["name"],
            "family": spec["family"],
            "path": spec["path"],
            "games": 100,
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_out_losses": bench_out,
            "prize_losses": prize_loss,
            "deckout_losses": deckout
        }
        screening_results.append(record)
        print(f"Result for {aid:22s}: {w}W / {l}L / {d}D ({p*100:.1f}%) | CI: [{lo*100:.1f}%, {hi*100:.1f}%] | Bench-Out: {bench_out}, Prize: {prize_loss}, Deckout: {deckout}")

    (out_dir / "screening_results_v2.json").write_text(json.dumps(screening_results, indent=2), encoding="utf-8")
    print(f"\nWrote deck_search_v2/screening_results_v2.json")
    return screening_results


if __name__ == "__main__":
    run_full_search_v2()
