"""Discrepancy Investigation Tool: Audits local simulation environment,
engine versions, seed handling, and opponent policy mechanisms.
"""

import sys
import os
import json
import hashlib
from pathlib import Path
from collections import Counter
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

import kaggle_environments
from tools import build_submission, validate_deck, ab_gate

def audit_environment():
    out_dir = ROOT_DIR / "tools" / "discrepancy_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    audit_data = {}

    # 1. SDK and Engine Versions
    audit_data["kaggle_environments_version"] = getattr(kaggle_environments, "__version__", "unknown")
    
    # Check cabt environment specification
    try:
        from kaggle_environments import make
        env = make("cabt")
        audit_data["cabt_env_name"] = env.name
        audit_data["cabt_specification"] = env.specification
    except Exception as e:
        audit_data["cabt_env_error"] = str(e)

    # 2. Engine Card DB vs Local card_data.json
    cards_db, attacks_db = build_submission.load_engine_card_db()
    audit_data["engine_cards_count"] = len(cards_db)
    audit_data["engine_attacks_count"] = len(attacks_db)

    # Check Teal Mask Ogerpon ex in engine DB
    ogerpon_engine = cards_db.get(96)
    if ogerpon_engine:
        audit_data["ogerpon_engine"] = {
            "name": str(ogerpon_engine.name),
            "hp": int(ogerpon_engine.hp),
            "cardType": int(ogerpon_engine.cardType),
            "energyType": int(ogerpon_engine.energyType),
            "retreatCost": int(ogerpon_engine.retreatCost)
        }

    # 3. Audit Local Opponent Policy in ab_gate.py
    # In ab_gate.py: How is incumbent policy defined?
    # When spec_i is "meta_starmie.csv", what policy does it use?
    deck_i, attrs_i = ab_gate.parse_spec("meta_starmie.csv")
    audit_data["incumbent_parsed_attrs"] = attrs_i
    # Note: attrs_i is empty dict -> uses default policy in main.py for seat 1!

    # 4. Audit Randomness & Seed Reset
    audit_data["seed_handling"] = {
        "engine_run_seeds": "Passed via env.run() or default random",
        "state_caching_risk": "Check if CardTracker or global variables leak across matches"
    }

    report_path = out_dir / "audit_report.json"
    report_path.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")
    print("Environment audit complete. Report written to tools/discrepancy_audit/audit_report.json")
    return audit_data

if __name__ == "__main__":
    audit_environment()
