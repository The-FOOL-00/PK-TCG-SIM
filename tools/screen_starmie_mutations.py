"""Screening Harness for Mega Starmie Deck Mutations (Experiment L2 / Deck Optimizer).

Evaluates 1-card and 2-card targeted mutations of S0 (meta_starmie.csv)
using the exact frozen BS-CEI V1.5c player (V0, 194-dim State+Belief, 2-Ply Minimax, 2 Belief Worlds).
"""

import json
import os
import sys
import time
from pathlib import Path
from collections import Counter
import numpy as np

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools import ab_gate, deck_compare
import main as agent_mod


# S0 Base Decklist
S0_LIST = [int(line.strip()) for line in open("meta_starmie.csv") if line.strip()]

MUTATIONS = {
    "S0_baseline": {
        "changes": "baseline S0 (17 Energy, 0 Boss, 0 Switch, 1 Max Belt)",
        "hypothesis": "Incumbent benchmark",
        "deck": S0_LIST.copy()
    },
    "S1_plus_1_boss": {
        "changes": "+1 Boss's Orders (1182), -1 Water Energy (3)",
        "hypothesis": "Target access: Allows gusting benched 2-prize EX targets",
        "remove": [3],
        "add": [1182]
    },
    "S2_plus_2_boss": {
        "changes": "+2 Boss's Orders (1182), -2 Water Energy (3)",
        "hypothesis": "High target access: 2x Boss's Orders to reliably close prize race",
        "remove": [3, 3],
        "add": [1182, 1182]
    },
    "S3_plus_1_switch": {
        "changes": "+1 Switch (1123), -1 Water Energy (3)",
        "hypothesis": "Mobility/Survival: Enables free active swap when damaged",
        "remove": [3],
        "add": [1123]
    },
    "S4_prime_catcher": {
        "changes": "+1 Prime Catcher (1088), -1 Maximum Belt (1158)",
        "hypothesis": "ACE SPEC upgrade: Gust opponent bench + switch active in 1 item",
        "remove": [1158],
        "add": [1088]
    },
    "S5_boss_and_switch": {
        "changes": "+1 Boss's Orders (1182), +1 Switch (1123), -2 Water Energy (3)",
        "hypothesis": "Target access + mobility combined",
        "remove": [3, 3],
        "add": [1182, 1123]
    },
    "S6_2boss_and_switch": {
        "changes": "+2 Boss's Orders (1182), +1 Switch (1123), -3 Water Energy (3)",
        "hypothesis": "Max target access (2x Boss) + mobility (1x Switch), 14 Energy",
        "remove": [3, 3, 3],
        "add": [1182, 1182, 1123]
    },
    "S7_prime_and_boss": {
        "changes": "+1 Prime Catcher (1088), +1 Boss's Orders (1182), -1 Max Belt (1158), -1 Energy (3)",
        "hypothesis": "Dual Gust suite (Prime Catcher + Boss's Orders)",
        "remove": [1158, 3],
        "add": [1088, 1182]
    },
    "S8_plus_mantine": {
        "changes": "+1 Mantine (720), -1 Water Energy (3)",
        "hypothesis": "Basic density: 3x Mantine to reduce bench-out losses",
        "remove": [3],
        "add": [720]
    },
    "S9_mantine_and_boss": {
        "changes": "+1 Mantine (720), +1 Boss's Orders (1182), -2 Water Energy (3)",
        "hypothesis": "Bench safety + target access combined",
        "remove": [3, 3],
        "add": [720, 1182]
    },
    "S10_full_tactical_suite": {
        "changes": "+1 Prime Catcher (1088), +1 Boss's Orders (1182), +1 Switch (1123), -1 Max Belt (1158), -2 Energy (3)",
        "hypothesis": "Complete tactical suite: Prime Catcher + Boss + Switch, 15 Energy",
        "remove": [1158, 3, 3],
        "add": [1088, 1182, 1123]
    }
}


def build_and_validate_decks(out_dir="data/decks"):
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    deck_paths = {}

    for name, spec in MUTATIONS.items():
        if "deck" in spec:
            d = spec["deck"].copy()
        else:
            d = S0_LIST.copy()
            for r in spec["remove"]:
                d.remove(r)
            for a in spec["add"]:
                d.append(a)

        # Validate
        assert len(d) == 60, f"Deck {name} has {len(d)} cards, expected 60"
        counts = Counter(d)
        for cid, c in counts.items():
            if cid != 3:  # Energy can exceed 4
                assert c <= 4, f"Deck {name} has {c}x card {cid} (exceeds 4-copy limit)"

        # Write CSV
        fpath = p / f"{name}.csv"
        fpath.write_text("\n".join(str(c) for c in d) + "\n", encoding="utf-8")
        deck_paths[name] = str(fpath)
        print(f"Validated deck {name:25s} (60 cards, {len(counts)} unique)")

    return deck_paths


def screen_candidates(deck_paths, games=100, workers=6):
    results = {}
    json_path = Path("deck_candidates.json")

    for name, fpath in deck_paths.items():
        print(f"\n========================================================")
        print(f"Screening Candidate {name} ({games} games vs Incumbent)...")
        print(f"Hypothesis: {MUTATIONS[name]['hypothesis']}")
        print(f"========================================================")

        # Build relative path for ab_gate parser
        rel_path = os.path.relpath(fpath, ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}+BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1"
        spec_i = "meta_starmie.csv"

        total = ab_gate.run_gate(
            spec_c=spec_c,
            spec_i=spec_i,
            games=games,
            workers=workers
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
            "candidate_id": name,
            "changes": MUTATIONS[name]["changes"],
            "hypothesis": MUTATIONS[name]["hypothesis"],
            "deck_path": fpath,
            "games": games,
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_out_losses": bench_out,
            "prize_losses": prize_loss,
            "deckout_losses": deckout,
            "timestamp": time.time()
        }

        results[name] = record
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        print(f"Result for {name}: {w}W / {l}L / {d}D ({p*100:.1f}%) | CI: [{lo*100:.1f}%, {hi*100:.1f}%] | Bench-Out: {bench_out}, Prize: {prize_loss}, Deckout: {deckout}")

    return results


if __name__ == "__main__":
    deck_paths = build_and_validate_decks()
    screen_candidates(deck_paths, games=100, workers=6)
