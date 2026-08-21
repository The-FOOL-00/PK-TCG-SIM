"""MetaPool Report Generator & Sensitivity Analysis Tool."""

import sys
import os
import json
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def generate_report():
    runs_dir = ROOT_DIR / "runs"
    f1 = runs_dir / "meta_pool_v1_300.json"
    f2 = runs_dir / "meta_pool_v1_300_replicate.json"

    if not f1.exists() or not f2.exists():
        print("MetaPool run files not found yet.")
        return

    r1 = json.loads(f1.read_text(encoding="utf-8"))
    r2 = json.loads(f2.read_text(encoding="utf-8"))

    # Compile Matchup Comparison Table
    matchup_rows = []
    for aid in r1["matchup_breakdown"]:
        m1 = r1["matchup_breakdown"][aid]
        m2 = r2["matchup_breakdown"][aid]

        matchup_rows.append({
            "archetype_id": aid,
            "name": m1["name"],
            "type": m1["type"],
            "r1_wins": m1["wins"],
            "r1_losses": m1["losses"],
            "r1_draws": m1["draws"],
            "r1_wr": m1["win_rate"],
            "r2_wins": m2["wins"],
            "r2_losses": m2["losses"],
            "r2_draws": m2["draws"],
            "r2_wr": m2["win_rate"],
            "combined_wr": (m1["wins"] + m2["wins"]) / (m1["wins"] + m1["losses"] + m2["wins"] + m2["losses"])
        })

    # Sensitivity Analyses:
    # A. Water/Grass-heavy (Starmie 40%, Ogerpon 40%, Others 20%)
    wr_starmie = matchup_rows[0]["combined_wr"]
    wr_ogerpon = matchup_rows[1]["combined_wr"]
    wr_others = sum(row["combined_wr"] for row in matchup_rows[2:]) / 4.0

    sens_water_grass = 0.40 * wr_starmie + 0.40 * wr_ogerpon + 0.20 * wr_others
    sens_balanced = sum(row["combined_wr"] for row in matchup_rows) / 6.0
    sens_stage2 = 0.40 * matchup_rows[2]["combined_wr"] + 0.40 * matchup_rows[5]["combined_wr"] + 0.20 * wr_starmie
    sens_disruption = 0.50 * matchup_rows[4]["combined_wr"] + 0.50 * matchup_rows[3]["combined_wr"]

    sensitivity_summary = {
        "balanced_meta_v1": sens_balanced,
        "water_grass_heavy": sens_water_grass,
        "stage2_setup_heavy": sens_stage2,
        "tank_disruption_heavy": sens_disruption
    }

    report_payload = {
        "run1_overall_wr": r1["overall_win_rate"],
        "run1_wilson_ci": r1["overall_wilson_ci"],
        "run2_overall_wr": r2["overall_win_rate"],
        "run2_wilson_ci": r2["overall_wilson_ci"],
        "replicate_delta": abs(r1["overall_win_rate"] - r2["overall_win_rate"]),
        "matchup_details": matchup_rows,
        "sensitivity": sensitivity_summary
    }

    (runs_dir / "meta_pool_report.json").write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    # Write CSV
    with open(runs_dir / "meta_pool_matchups.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Archetype", "Type", "Run1 W/L/D", "Run1 WR", "Run2 W/L/D", "Run2 WR", "Combined WR"])
        for r in matchup_rows:
            writer.writerow([
                r["name"], r["type"],
                f"{r['r1_wins']}/{r['r1_losses']}/{r['r1_draws']}", f"{r['r1_wr']*100:.1f}%",
                f"{r['r2_wins']}/{r['r2_losses']}/{r['r2_draws']}", f"{r['r2_wr']*100:.1f}%",
                f"{r['combined_wr']*100:.1f}%"
            ])

    print("MetaPool report and CSV generated successfully.")
    return report_payload

if __name__ == "__main__":
    generate_report()
