"""Comprehensive V1 vs V2 Live Replay Analysis & Difference Engine for Project Mew."""

import sys
import os
import io
import json
import math
from pathlib import Path
from collections import defaultdict, Counter

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate

def run_v1_v2_forensics():
    v1_file = ROOT_DIR / "data" / "live_complete_history" / "live_match_history.json"
    v2_file = ROOT_DIR / "data" / "live_replays" / "V2" / "v2_match_history.json"

    v1_matches = json.loads(v1_file.read_text(encoding="utf-8"))
    v2_matches = json.loads(v2_file.read_text(encoding="utf-8"))

    print("========================================================")
    print("COMPREHENSIVE V1 vs V2 LIVE REPLAY FORENSICS")
    print(f"Loaded: {len(v1_matches)} V1 matches + {len(v2_matches)} V2 matches.")
    print("========================================================")

    # 1. Opponent Rating Stats (Mean, Median, p25, p75, Min, Max)
    def calc_stats(ratings):
        s = sorted(ratings)
        n = len(s)
        mean = sum(s) / n
        med = s[n // 2]
        p25 = s[n // 4]
        p75 = s[(3 * n) // 4]
        return {"mean": mean, "med": med, "p25": p25, "p75": p75, "min": s[0], "max": s[-1]}

    v1_ratings = [m["opponent_rating"] for m in v1_matches]
    v2_ratings = [m["opponent_rating"] for m in v2_matches]

    v1_early_r = [m["opponent_rating"] for m in v1_matches[:25]]
    v1_late_r = [m["opponent_rating"] for m in v1_matches[75:]]
    v2_early_r = [m["opponent_rating"] for m in v2_matches[:15]]
    v2_late_r = [m["opponent_rating"] for m in v2_matches[30:]]

    print("\n--- OPPONENT RATING DISTRIBUTIONS ---")
    print(f"V1 Overall ({len(v1_ratings)}g):  Mean={calc_stats(v1_ratings)['mean']:.1f}, Med={calc_stats(v1_ratings)['med']:.1f}, Range=[{calc_stats(v1_ratings)['min']:.1f}, {calc_stats(v1_ratings)['max']:.1f}]")
    print(f"  V1 Early (1-25): Mean={calc_stats(v1_early_r)['mean']:.1f}, Med={calc_stats(v1_early_r)['med']:.1f}")
    print(f"  V1 Late (76-120): Mean={calc_stats(v1_late_r)['mean']:.1f}, Med={calc_stats(v1_late_r)['med']:.1f}")
    print(f"V2 Overall ({len(v2_ratings)}g):  Mean={calc_stats(v2_ratings)['mean']:.1f}, Med={calc_stats(v2_ratings)['med']:.1f}, Range=[{calc_stats(v2_ratings)['min']:.1f}, {calc_stats(v2_ratings)['max']:.1f}]")
    print(f"  V2 Early (1-15): Mean={calc_stats(v2_early_r)['mean']:.1f}, Med={calc_stats(v2_early_r)['med']:.1f}")
    print(f"  V2 Late (31-60): Mean={calc_stats(v2_late_r)['mean']:.1f}, Med={calc_stats(v2_late_r)['med']:.1f}")

    # 2. Matchup Matrix Comparison (V1 vs V2 by Archetype)
    archs = sorted(list(set(m["opponent_archetype"] for m in v1_matches + v2_matches)))
    
    matrix = {}
    print("\n--- V1 vs V2 MATCHUP MATRIX ---")
    print(f"{'Archetype':24s} | {'V1 Games':9s} | {'V1 WR':7s} | {'V2 Games':9s} | {'V2 WR':7s} | {'Delta':7s}")
    print("-" * 75)

    for arch in archs:
        v1_sub = [m for m in v1_matches if m["opponent_archetype"] == arch]
        v2_sub = [m for m in v2_matches if m["opponent_archetype"] == arch]

        v1_w = sum(1 for m in v1_sub if m["result"] == "WIN")
        v1_n = len(v1_sub)
        v1_wr = (v1_w / v1_n) if v1_n > 0 else 0.0

        v2_w = sum(1 for m in v2_sub if m["result"] == "WIN")
        v2_n = len(v2_sub)
        v2_wr = (v2_w / v2_n) if v2_n > 0 else 0.0

        delta = (v2_wr - v1_wr) * 100.0 if (v1_n > 0 and v2_n > 0) else 0.0
        matrix[arch] = {
            "v1_games": v1_n, "v1_wins": v1_w, "v1_wr": v1_wr,
            "v2_games": v2_n, "v2_wins": v2_w, "v2_wr": v2_wr,
            "delta_pct": delta
        }
        print(f"{arch:24s} | {v1_n:9d} | {v1_wr*100:6.1f}% | {v2_n:9d} | {v2_wr*100:6.1f}% | {delta:+6.1f}%")

    # 3. Loss Taxonomy Comparison
    v1_losses = [m for m in v1_matches if m["result"] == "LOSS"]
    v2_losses = [m for m in v2_matches if m["result"] == "LOSS"]

    v1_tax = Counter(m["loss_category"] for m in v1_losses)
    v2_tax = Counter(m["loss_category"] for m in v2_losses)

    print("\n--- LOSS TAXONOMY COMPARISON ---")
    all_cats = sorted(list(set(list(v1_tax.keys()) + list(v2_tax.keys()))))
    for cat in all_cats:
        c1 = v1_tax.get(cat, 0)
        c2 = v2_tax.get(cat, 0)
        print(f"  {cat:26s} | V1: {c1:2d} ({c1/len(v1_losses)*100:4.1f}%) | V2: {c2:2d} ({c2/len(v2_losses)*100:4.1f}%)")

    # 4. Safety Brake Activation Analysis
    brake_counts = Counter(m.get("brake_activation_status", "IRRELEVANT") for m in v2_matches if m["result"] == "LOSS")
    print(f"\nV2 Safety Brake Status in Losses: {dict(brake_counts)}")

    # 5. Save comprehensive results
    out_dir = ROOT_DIR / "runs" / "v1_v2_forensics"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "v1_total_games": len(v1_matches),
        "v1_wins": sum(1 for m in v1_matches if m["result"] == "WIN"),
        "v1_losses": len(v1_losses),
        "v1_overall_wr": sum(1 for m in v1_matches if m["result"] == "WIN") / len(v1_matches),
        "v2_total_games": len(v2_matches),
        "v2_wins": sum(1 for m in v2_matches if m["result"] == "WIN"),
        "v2_losses": len(v2_losses),
        "v2_overall_wr": sum(1 for m in v2_matches if m["result"] == "WIN") / len(v2_matches),
        "rating_stats": {
            "v1_overall": calc_stats(v1_ratings),
            "v1_early": calc_stats(v1_early_r),
            "v1_late": calc_stats(v1_late_r),
            "v2_overall": calc_stats(v2_ratings),
            "v2_early": calc_stats(v2_early_r),
            "v2_late": calc_stats(v2_late_r)
        },
        "matchup_matrix": matrix,
        "v1_loss_taxonomy": dict(v1_tax),
        "v2_loss_taxonomy": dict(v2_tax),
        "v2_brake_status": dict(brake_counts)
    }

    (out_dir / "v1_v2_forensics_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    run_v1_v2_forensics()
