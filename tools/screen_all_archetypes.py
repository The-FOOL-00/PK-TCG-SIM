"""Screening Runner for All 8 Candidate Archetypes (Experiment L3).

Runs 100 seat-alternated games per candidate deck against the baseline incumbent
using the frozen BS-CEI V1.5c player (V0, 194-dim State+Belief, 2-Ply Minimax, 2 Belief Worlds).
"""

import json
import os
import sys
import time
from pathlib import Path
import csv

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools import ab_gate


def run_archetype_screening(games=100, workers=6):
    candidates_dir = Path("deck_search/candidates")
    out_dir = Path("deck_search")
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        ("Starmie_S0", "meta_starmie.csv", "Mega Starmie ex Fast Aggro (Control S0)"),
        ("Alakazam_Psychic", "deck_search/candidates/Alakazam_Psychic.csv", "Alakazam ex / Dudunsparce Psychic Control"),
        ("Grimmsnarl_Dark", "deck_search/candidates/Grimmsnarl_Dark.csv", "Grimmsnarl / Dark / Non-EX Disruption"),
        ("Mewtwo_Stall", "deck_search/candidates/Mewtwo_Stall.csv", "Mewtwo ex / Energy Denial / Stall"),
        ("Dragapult_Spread", "deck_search/candidates/Dragapult_Spread.csv", "Dragapult ex Phantom Dive Bench Spread"),
        ("Archaludon_Metal", "deck_search/candidates/Archaludon_Metal.csv", "Archaludon ex Metal Bridge High-HP Tank"),
        ("Ogerpon_Grass", "deck_search/candidates/Ogerpon_Grass.csv", "Teal Mask Ogerpon ex Teal Dance Acceleration"),
        ("Bellibolt_Lightning", "deck_search/candidates/Bellibolt_Lightning.csv", "Iono's Bellibolt ex Lightning Tempo"),
    ]

    results = []
    csv_rows = []

    for name, deck_path, desc in candidates:
        print(f"\n========================================================")
        print(f"Screening Archetype: {name} ({games} games vs Incumbent)...")
        print(f"Description: {desc}")
        print(f"========================================================")

        rel_path = os.path.relpath(deck_path, ROOT_DIR).replace("\\", "/")
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
            "archetype": name,
            "description": desc,
            "deck_path": deck_path,
            "games": games,
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_out_losses": bench_out,
            "prize_losses": prize_loss,
            "deckout_losses": deckout
        }
        results.append(record)

        csv_rows.append([
            name, f"{p*100:.1f}%", f"[{lo*100:.1f}%, {hi*100:.1f}%]",
            w, l, d, bench_out, prize_loss, deckout
        ])

        (out_dir / "screening_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Result for {name}: {w}W / {l}L / {d}D ({p*100:.1f}%) | CI: [{lo*100:.1f}%, {hi*100:.1f}%] | Bench-Out: {bench_out}, Prize: {prize_loss}, Deckout: {deckout}")

    # Write CSV
    with open(out_dir / "screening_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Candidate", "Win Rate", "Wilson CI", "Wins", "Losses", "Draws", "Bench-Out", "Prize Loss", "Deckout"])
        writer.writerows(csv_rows)

    print(f"\nWrote deck_search/screening_results.csv and deck_search/screening_results.json")
    return results


if __name__ == "__main__":
    run_archetype_screening(games=100, workers=6)
