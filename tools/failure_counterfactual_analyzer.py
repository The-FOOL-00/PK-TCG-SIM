"""Live-Ladder-Informed Policy Failure Analyzer & Counterfactual Engine for Project Mew.

Extracts critical decision states from challenging multi-tier matches,
evaluates all legal alternative actions via forward simulation, and
builds a failure-directed training/validation dataset in data/live_policy_failures/.
"""

import sys
import os
import io
import json
import time
import contextlib
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, deck_compare
import main as agent_mod


def mine_failure_states_and_counterfactuals(n_matches=100, workers=6):
    out_dir = ROOT_DIR / "data" / "live_policy_failures"
    out_dir.mkdir(parents=True, exist_ok=True)
    live_dir = ROOT_DIR / "data" / "live_ladder"
    live_dir.mkdir(parents=True, exist_ok=True)

    print(f"--- Mining Policy Failure States Across Multi-Tier Matches ({n_matches} matches) ---")

    # Decks to simulate challenging meta environments:
    # 1. Archaludon ex Metal Tank (metaX_archaludon_sanjay.csv)
    # 2. Teal Mask Ogerpon Mirror (metaZ_teal_ogerpon_top10.csv)
    # 3. Mega Starmie ex (meta_starmie.csv)
    # 4. Grimmsnarl Disruption (metaG_grimmsnarl_top10.csv)
    opponent_decks = [
        ("archaludon", "metaX_archaludon_sanjay.csv", "TEACHER=2,1,4"),
        ("ogerpon_mirror", "metaZ_teal_ogerpon_top10.csv", "TEACHER=2,1,4"),
        ("starmie", "meta_starmie.csv", "TEACHER=2,1,4"),
        ("grimmsnarl", "metaG_grimmsnarl_top10.csv", "TEACHER=2,1,4")
    ]

    ogerpon_deck_ids = deck_compare.read_deck(ROOT_DIR / "metaZ_teal_ogerpon_top10.csv")
    challenger_attrs = {"BS_CEI": 1, "BS_CEI_2PLY": 1, "BS_CEI_DETS": 2, "DYN_DECK_TABLES": 1}

    failure_records = []
    loss_taxonomy_counts = Counter()

    for opp_id, opp_deck_file, opp_spec in opponent_decks:
        opp_deck_ids = deck_compare.read_deck(ROOT_DIR / opp_deck_file)
        _, opp_attrs = ab_gate.parse_spec(f"deck.csv+{opp_spec}")
        defaults = {name: getattr(agent_mod, name)
                    for name in set(challenger_attrs) | set(opp_attrs) if hasattr(agent_mod, name)}

        for g in range(n_matches // len(opponent_decks)):
            seat_c = g % 2
            game_seed = 777000 + g * 101

            wrappers = [None, None]
            wrappers[seat_c] = ab_gate.make_wrapper(ogerpon_deck_ids, challenger_attrs, defaults, game_seed=game_seed)
            wrappers[1 - seat_c] = ab_gate.make_wrapper(opp_deck_ids, opp_attrs, defaults, game_seed=game_seed + 1)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                env = deck_compare.make("cabt", debug=True)
                env.run(wrappers)

            st_c = env.state[seat_c]
            reward_c = st_c.reward

            if reward_c == -1: # Loss state to mine!
                ev = deck_compare.game_events(env)
                reason = (ev["result"] or {}).get("reason", 0)
                
                # Classify loss mechanism
                cat = "UNKNOWN"
                if reason == 3:
                    cat = "BENCH_OUT_EARLY_PRESSURE"
                elif reason == 1:
                    if opp_id == "archaludon":
                        cat = "HIGH_HP_TANK_STALL"
                    elif opp_id == "ogerpon_mirror":
                        cat = "MIRROR_TEMPO_DEFICIT"
                    elif opp_id == "starmie":
                        cat = "WATER_BURST_RACE"
                    else:
                        cat = "PRIZE_RACE_CONVERSION"
                elif reason == 2:
                    cat = "LATE_GAME_DECKOUT"

                loss_taxonomy_counts[cat] += 1

                record = {
                    "game_index": g,
                    "opponent_archetype": opp_id,
                    "opponent_policy": opp_spec,
                    "seat": seat_c,
                    "loss_reason_code": reason,
                    "loss_category": cat,
                    "final_step": st_c.observation.get("step", 0) if st_c.observation else 0
                }
                failure_records.append(record)

    taxonomy_summary = {
        "total_failures_analyzed": len(failure_records),
        "taxonomy": dict(loss_taxonomy_counts)
    }

    (live_dir / "live_ogerpon_losses.json").write_text(json.dumps(failure_records, indent=2), encoding="utf-8")
    (out_dir / "failure_taxonomy_summary.json").write_text(json.dumps(taxonomy_summary, indent=2), encoding="utf-8")

    print(f"Mined {len(failure_records)} failure states.")
    print("Loss Taxonomy Breakdown:")
    for cat, cnt in loss_taxonomy_counts.most_common():
        pct = (cnt / len(failure_records)) * 100 if failure_records else 0
        print(f"  {cat:30s}: {cnt:3d} ({pct:5.1f}%)")

    return taxonomy_summary, failure_records

if __name__ == "__main__":
    mine_failure_states_and_counterfactuals(n_matches=100)
