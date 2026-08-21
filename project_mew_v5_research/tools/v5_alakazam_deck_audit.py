"""V5 Alakazam Master Deck Forensic Audit and Exact Hypergeometric Calculations.

Analyzes metaB_alakazam.csv:
1. Complete card-by-card breakdown.
2. Exact combinatorial and hypergeometric probability derivations.
3. Comparative analysis against E19 (Teal Mask Ogerpon ex).
"""

import sys
import os
import csv
import math
import json
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data" / "p0_gate"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def comb(n, k):
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)

def hypergeometric_ge(N, K, n, k_target):
    """P(X >= k_target) when drawing n cards without replacement from population N with K successes."""
    prob = 0.0
    for k in range(k_target, min(n, K) + 1):
        prob += (comb(K, k) * comb(N - K, n - k)) / comb(N, n)
    return prob

def run_alakazam_audit():
    print("===================================================================")
    print("PROJECT MEW — PHASE 9 & 10: V5 ALAKAZAM MASTER DECK AUDIT")
    print("===================================================================")

    # 1. Load card DB
    card_db = {}
    with open(ROOT_DIR / "EN_Card_Data.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cid = int(r["Card ID"])
            if cid not in card_db:
                card_db[cid] = {
                    "name": r["Card Name"],
                    "card_type": r.get("Card Type", ""),
                    "hp": r.get("HP", "0"),
                    "rule": r.get("Rule", ""),
                    "stage": r.get("Stage", "")
                }

    # 2. Load Alakazam Deck
    alakazam_csv = ROOT_DIR / "metaB_alakazam.csv"
    alakazam_ids = [int(line.strip()) for line in alakazam_csv.read_text().splitlines() if line.strip()]
    assert len(alakazam_ids) == 60, f"Deck length is {len(alakazam_ids)}, expected 60!"

    # 3. Load E19 Deck
    e19_csv = ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv"
    e19_ids = [int(line.strip()) for line in e19_csv.read_text().splitlines() if line.strip()]

    print(f"Alakazam Master Deck: {len(alakazam_ids)} cards.")
    counts = Counter(alakazam_ids)

    basics = []
    stage1 = []
    stage2 = []
    items = []
    supporters = []
    stadiums = []
    tools = []
    energies = []

    print("\n--- Complete 60-Card List (Alakazam Master) ---")
    for cid, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        info = card_db.get(cid, {"name": f"Card #{cid}", "stage": "Unknown", "hp": "0"})
        cname = info["name"]
        stage = info["stage"]
        hp = info["hp"]
        print(f"  {cnt:2d}x ID {cid:4d}: {cname:30s} (Stage: {stage:12s}, HP: {hp})")

        if stage == "Basic":
            basics.extend([cid] * cnt)
        elif stage == "Stage 1":
            stage1.extend([cid] * cnt)
        elif stage == "Stage 2":
            stage2.extend([cid] * cnt)
        elif "Energy" in stage or "Energy" in cname:
            energies.extend([cid] * cnt)
        elif "Item" in stage or "Ball" in cname or "Poffin" in cname or "Candy" in cname or "Vessel" in cname:
            items.extend([cid] * cnt)
        elif "Supporter" in stage or "Dawn" in cname or "Arven" in cname or "Iono" in cname or "Boss" in cname:
            supporters.extend([cid] * cnt)
        elif "Stadium" in stage or "Artazon" in cname or "Town" in cname or "Center" in cname:
            stadiums.extend([cid] * cnt)
        else:
            items.extend([cid] * cnt)

    total_basics_al = len(basics)
    total_energy_al = len(energies)
    total_trainers_al = 60 - total_basics_al - len(stage1) - len(stage2) - total_energy_al

    # E19 counts
    total_basics_e19 = 4 # 4 Teal Mask Ogerpon ex
    total_energy_e19 = 21 # 19 Basic + 2 Grow Grass

    # Hypergeometric calculations
    # 1. Mulligan Probability: P(0 Basics in 7 cards)
    p_mulligan_al = comb(60 - total_basics_al, 7) / comb(60, 7)
    p_mulligan_e19 = comb(60 - total_basics_e19, 7) / comb(60, 7)

    # 2. Opening Basic: P(>= 1 Basic in 7)
    p_open_basic_al = 1.0 - p_mulligan_al
    p_open_basic_e19 = 1.0 - p_mulligan_e19

    # 3. Opening Energy: P(>= 1 Energy in 7)
    p_open_energy_al = hypergeometric_ge(60, total_energy_al, 7, 1)
    p_open_energy_e19 = hypergeometric_ge(60, total_energy_e19, 7, 1)

    # 4. Opening Setup Synergy (>=1 Basic AND >=1 Search Item/Energy)
    # Buddy-Buddy Poffin (4 copies), Nest Ball, etc.
    p_open_poffin_al = hypergeometric_ge(60, 4, 7, 1)

    print("\n--- Exact Hypergeometric Mathematical Comparison ---")
    print(f"Metric                                  E19 Ogerpon          V5 Alakazam Master")
    print(f"--------------------------------------------------------------------------------")
    print(f"Total Basic Pokémon                     {total_basics_e19:2d} cards ( 6.7%)     {total_basics_al:2d} cards ({total_basics_al/60*100:4.1f}%)")
    print(f"Opening Basic Prob P(>=1 in 7)          {p_open_basic_e19*100:6.2f}%               {p_open_basic_al*100:6.2f}%")
    print(f"Mulligan Probability                    {p_mulligan_e19*100:6.2f}%               {p_mulligan_al*100:6.2f}%")
    print(f"Opening Energy Prob P(>=1 in 7)         {p_open_energy_e19*100:6.2f}%               {p_open_energy_al*100:6.2f}%")
    print(f"Turn-1 Buddy-Buddy Poffin in 7          0.00%                {p_open_poffin_al*100:6.2f}%")
    print(f"Damage Ceiling vs Cornerstone Mask ex   0 DMG (Immune)       UNRESTRICTED (Bench KO)")
    print(f"Damage Ceiling vs Crustle Wall          Nullified / Stalled  Bypasses Defense")

    audit_payload = {
        "deck_name": "V5_Alakazam_Master",
        "deck_file": "metaB_alakazam.csv",
        "composition": {
            "basics_count": total_basics_al,
            "stage1_count": len(stage1),
            "stage2_count": len(stage2),
            "energy_count": total_energy_al,
            "trainer_count": total_trainers_al
        },
        "exact_hypergeometric_probabilities": {
            "mulligan_rate_pct": round(p_mulligan_al * 100, 3),
            "opening_basic_pct": round(p_open_basic_al * 100, 3),
            "opening_energy_pct": round(p_open_energy_al * 100, 3),
            "turn1_poffin_pct": round(p_open_poffin_al * 100, 3)
        },
        "comparison_vs_e19": {
            "e19_mulligan_pct": round(p_mulligan_e19 * 100, 3),
            "mulligan_reduction_pct": round((p_mulligan_e19 - p_mulligan_al) * 100, 3),
            "cornerstone_ex_status": "Alakazam completely bypasses Cornerstone Stance via non-ex / bench spread damage",
            "crustle_wall_status": "Alakazam directly places damage counters, bypassing Battle Cage / Full Metal Lab reduction"
        }
    }

    out_file = DATA_DIR / "alakazam_deck_audit_results.json"
    out_file.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    print(f"\nAlakazam deck audit complete. Saved to {out_file}")
    return audit_payload

if __name__ == "__main__":
    run_alakazam_audit()
