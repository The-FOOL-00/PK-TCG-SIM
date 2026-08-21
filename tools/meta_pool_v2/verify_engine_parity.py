"""Engine Version & Opponent Policy Inventory Tool for MetaPoolGate v2."""

import sys
import os
import json
import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

import kaggle_environments
from tools import build_submission, ab_gate

def audit_engine_and_policies():
    out_dir = ROOT_DIR / "tools" / "meta_pool_v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Engine & SDK Audit
    kg_ver = getattr(kaggle_environments, "__version__", "unknown")
    
    # Locate cabt DLL
    cg_dll_path = ROOT_DIR / "sample_submission" / "sample_submission" / "cg" / "cg.dll"
    has_dll = cg_dll_path.exists()
    dll_sha256 = hashlib.sha256(cg_dll_path.read_bytes()).hexdigest() if has_dll else "NOT_FOUND"

    engine_info = {
        "installed_kaggle_environments_version": kg_ver,
        "competition_docs_reference_version": "1.14.10",
        "version_relationship": "kaggle-environments package updates periodically on Kaggle, but CABT environment specification remains 1.0.0",
        "cabt_dll_path": str(cg_dll_path),
        "cabt_dll_sha256": dll_sha256,
        "engine_specification_version": "1.0.0"
    }

    # 2. Opponent Policy Inventory across 4 Tiers
    policies = {
        "TIER_1_HEURISTIC": {
            "tier": 1,
            "name": "V1 Tactical Heuristic",
            "spec_flag": "BS_CEI=0+BC_CARD_ONLY=0",
            "type": "Rule-based tactical greedy heuristic",
            "source": "main.py v1 heuristic policy (878 historical baseline)",
            "description": "Evaluates candidate actions using rule-based scoring without tree search"
        },
        "TIER_2_NEURAL_HYBRID": {
            "tier": 2,
            "name": "BC Card-Head Neural Hybrid",
            "spec_flag": "BS_CEI=0+PTCG_BC_CARD_ONLY=1",
            "type": "Neural policy card selection + heuristic execution",
            "source": "main.py BC neural policy weights (policy_weights.npz)",
            "description": "Uses behavioral cloning neural net for card search + tactical heuristics"
        },
        "TIER_3_SEARCH_TEACHER": {
            "tier": 3,
            "name": "PIMC Determinized Searcher",
            "spec_flag": "TEACHER=2,1,4",
            "type": "Flat Monte Carlo tree search with rollout simulations",
            "source": "tools/searcher.py forward simulation teacher",
            "description": "Simulates 2 determinized worlds with top-4 action lookahead"
        },
        "TIER_4_ADVERSARIAL_MINIMAX": {
            "tier": 4,
            "name": "BS-CEI V1.5c Minimax",
            "spec_flag": "BS_CEI=1+BS_CEI_2PLY=1+BS_CEI_DETS=2+DYN_DECK_TABLES=1",
            "type": "2-Ply Pure Adversarial Minimax with 2 Hidden Belief Worlds",
            "source": "bot/counterfactual_v15.py + V0 leaf evaluator",
            "description": "Full adversarial minimax search with learned win-value model"
        }
    }

    (data_dir / "opponent_policy_inventory.json").write_text(json.dumps(policies, indent=2), encoding="utf-8")
    (out_dir / "engine_audit.json").write_text(json.dumps(engine_info, indent=2), encoding="utf-8")
    
    print("Engine audit & Opponent Policy Inventory complete.")
    print(f"  kaggle-environments: {kg_ver} (CABT spec v1.0.0)")
    print(f"  Opponent Policy Tiers: {len(policies)} tiers registered.")
    return engine_info, policies

if __name__ == "__main__":
    audit_engine_and_policies()
