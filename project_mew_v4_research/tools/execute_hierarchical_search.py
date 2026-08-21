"""PROJECT MEW — HIGH-PERFORMANCE HIERARCHICAL HYBRID SEARCH RUNNER.

Optimized for 12-core CPU with real-time checkpointing and progressive family evaluation.
"""

import sys
import os
import io
import json
import math
import time
import hashlib
from pathlib import Path
from collections import defaultdict, Counter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, deck_compare
from tools.meta_pool_v2 import run_meta_pool_v2
from project_mew_v4_research.tools.run_hybrid_search import (
    verify_control_freeze,
    build_mechanism_library,
    build_compatibility_graph,
    generate_hybrid_candidates,
    RESEARCH_DIR,
    CANDIDATES_DIR,
    REPORTS_DIR,
    DATA_DIR
)

NUM_WORKERS = 10


def run_hierarchical_search():
    print("===================================================================", flush=True)
    print("PROJECT MEW — HYBRID ANTI-E19 / GLOBAL META BREAKTHROUGH SEARCH", flush=True)
    print("===================================================================", flush=True)
    
    # 1. Verify Control Freeze
    freeze_rec = verify_control_freeze()
    
    # 2. Build Library and Compatibility Graph
    lib = build_mechanism_library()
    cg = build_compatibility_graph(lib)
    
    # 3. Generate all 224 legal candidates
    candidates = generate_hybrid_candidates()
    ogerpon_spec = "metaZ_teal_ogerpon_top10.csv"
    
    # -----------------------------------------------------------------------
    # STEP 1A: FAST SCREEN (30 games each) with Real-Time Checkpointing
    # -----------------------------------------------------------------------
    stage1a_file = REPORTS_DIR / "stage1a_fast_screen.json"
    stage1a_results = {}
    if stage1a_file.exists():
        try:
            stage1a_results = json.loads(stage1a_file.read_text(encoding="utf-8"))
            print(f"Loaded {len(stage1a_results)} existing Stage 1A results from disk.", flush=True)
        except Exception:
            stage1a_results = {}
            
    # Stratified ordering: alternate families so all 9 families get screened early
    by_family = defaultdict(list)
    for cid, info in candidates.items():
        by_family[info["family"]].append(cid)
        
    ordered_cids = []
    max_len = max(len(v) for v in by_family.values())
    for i in range(max_len):
        for fam in sorted(by_family.keys()):
            if i < len(by_family[fam]):
                ordered_cids.append(by_family[fam][i])

    print(f"\nExecuting Stage 1A Fast Screen (30g each, {NUM_WORKERS} workers) across {len(ordered_cids)} candidates...", flush=True)
    t0_1a = time.time()
    
    for idx, cid in enumerate(ordered_cids):
        if cid in stage1a_results:
            continue
            
        info = candidates[cid]
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}"
        
        res = ab_gate.run_gate(spec_c=spec_c, spec_i=ogerpon_spec, games=30, workers=NUM_WORKERS)
        st = res["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        dec = w + l
        p, lo, hi = ab_gate.wilson(w, dec) if dec > 0 else (0.0, 0.0, 0.0)
        
        entry = {
            "name": cid,
            "family": info["family"],
            "p1": info["p1"],
            "p2": info["p2"],
            "ace": info["ace"],
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_outs": st["reasons_lost"].get(3, 0),
            "prize_losses": st["reasons_lost"].get(1, 0),
            "deckouts": st["reasons_lost"].get(2, 0),
            "crashes": st["crashes"]
        }
        stage1a_results[cid] = entry
        
        # Checkpoint to disk after every evaluation
        stage1a_file.write_text(json.dumps(stage1a_results, indent=2), encoding="utf-8")
        
        done_count = len(stage1a_results)
        if done_count % 10 == 0 or done_count == len(ordered_cids) or p >= 0.45:
            el = time.time() - t0_1a
            gps = (done_count * 30) / max(1.0, el)
            print(f"  [{done_count:3d}/{len(ordered_cids):3d}] {cid:48s} | WR vs E19: {p*100:5.1f}% [{lo*100:4.1f}%, {hi*100:4.1f}%] (W:{w:2d} L:{l:2d}) | {gps:.1f} g/s", flush=True)

    print(f"\nStage 1A Complete ({len(stage1a_results)} candidates screened in {time.time()-t0_1a:.1f}s).", flush=True)

    # Sort candidates by Stage 1A performance
    sorted_1a = sorted(stage1a_results.values(), key=lambda x: x["win_rate"], reverse=True)
    print("\n--- TOP 20 CANDIDATES FROM STAGE 1A FAST SCREEN ---", flush=True)
    for i, c in enumerate(sorted_1a[:20], 1):
        print(f"  {i:2d}. {c['name']:48s} | WR vs E19: {c['win_rate']*100:5.1f}% | Family: {c['family']}", flush=True)

    # -----------------------------------------------------------------------
    # STEP 1B: DEEP SCREEN (100 games each for top candidates across diverse families)
    # -----------------------------------------------------------------------
    family_best = defaultdict(list)
    for c in sorted_1a:
        family_best[c["family"]].append(c)
        
    top_screen_cids = set()
    # Take top 3 from each family + overall top 15
    for f, c_list in family_best.items():
        for c in c_list[:3]:
            top_screen_cids.add(c["name"])
    for c in sorted_1a[:15]:
        top_screen_cids.add(c["name"])
        
    print(f"\nSelected {len(top_screen_cids)} structurally diverse candidates for Stage 1B Deep Screen (100g each)...", flush=True)
    stage1b_file = REPORTS_DIR / "stage1b_deep_screen.json"
    stage1b_results = {}
    if stage1b_file.exists():
        try:
            stage1b_results = json.loads(stage1b_file.read_text(encoding="utf-8"))
            print(f"Loaded {len(stage1b_results)} existing Stage 1B results.", flush=True)
        except Exception:
            stage1b_results = {}

    t0_1b = time.time()
    for idx, cid in enumerate(sorted(list(top_screen_cids))):
        if cid in stage1b_results:
            continue
            
        info = candidates[cid]
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}"
        
        res = ab_gate.run_gate(spec_c=spec_c, spec_i=ogerpon_spec, games=100, workers=NUM_WORKERS)
        st = res["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        dec = w + l
        p, lo, hi = ab_gate.wilson(w, dec) if dec > 0 else (0.0, 0.0, 0.0)
        
        entry = {
            "name": cid,
            "family": info["family"],
            "p1": info["p1"],
            "p2": info["p2"],
            "ace": info["ace"],
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_outs": st["reasons_lost"].get(3, 0),
            "prize_losses": st["reasons_lost"].get(1, 0),
            "deckouts": st["reasons_lost"].get(2, 0),
            "crashes": st["crashes"]
        }
        stage1b_results[cid] = entry
        stage1b_file.write_text(json.dumps(stage1b_results, indent=2), encoding="utf-8")
        print(f"  [{len(stage1b_results):2d}/{len(top_screen_cids):2d}] {cid:48s} | WR: {p*100:5.1f}% [{lo*100:4.1f}%, {hi*100:4.1f}%] (W:{w:2d} L:{l:2d})", flush=True)

    print(f"\nStage 1B Complete ({len(stage1b_results)} candidates deep screened in {time.time()-t0_1b:.1f}s).", flush=True)

    # -----------------------------------------------------------------------
    # STEP 2: BROAD METAPOOL EVALUATION (480g across 6 archetypes x 4 tiers)
    # -----------------------------------------------------------------------
    sorted_1b = sorted(stage1b_results.values(), key=lambda x: x["win_rate"], reverse=True)
    print("\n--- TOP 10 CANDIDATES FROM STAGE 1B DEEP SCREEN (100g vs E19) ---", flush=True)
    for i, c in enumerate(sorted_1b[:10], 1):
        print(f"  {i:2d}. {c['name']:48s} | WR vs E19: {c['win_rate']*100:5.1f}% | CI: [{c['wilson_ci'][0]*100:.1f}%, {c['wilson_ci'][1]*100:.1f}%] | Family: {c['family']}", flush=True)

    # Select top 6 candidates across top families + E19 control
    metapool_cids = [c["name"] for c in sorted_1b[:6]]
    if "CONTROL_E19_OGERPON" not in metapool_cids:
        metapool_cids.append("CONTROL_E19_OGERPON")
    
    stage2_file = REPORTS_DIR / "stage2_broad_meta_results.json"
    stage2_results = {}
    if stage2_file.exists():
        try:
            stage2_results = json.loads(stage2_file.read_text(encoding="utf-8"))
            print(f"Loaded {len(stage2_results)} existing Stage 2 MetaPool results.", flush=True)
        except Exception:
            stage2_results = {}

    print(f"\nExecuting Stage 2 Broad MetaPool v2 across {len(metapool_cids)} candidates...", flush=True)
    t0_2 = time.time()
    
    for cid in metapool_cids:
        if cid in stage2_results:
            continue
            
        if cid == "CONTROL_E19_OGERPON":
            spec_c = "metaZ_teal_ogerpon_top10.csv"
            family = "Control"
        else:
            info = candidates[cid]
            rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
            spec_c = f"{rel_path}"
            family = info["family"]
            
        print(f"\nEvaluating {cid} across MetaPool v2 (480 games, 6 decks x 4 tiers)...", flush=True)
        t_start = time.time()
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=20, workers=NUM_WORKERS)
        el = time.time() - t_start
        
        stage2_results[cid] = {
            "name": cid,
            "family": family,
            "overall_win_rate": res["overall_win_rate"],
            "overall_wilson_ci": res["overall_wilson_ci"],
            "matrix_results": res["matrix_results"],
            "tier_summary": res["tier_summary"],
            "eval_time_sec": round(el, 1)
        }
        stage2_file.write_text(json.dumps(stage2_results, indent=2), encoding="utf-8")
        print(f"  -> MetaPool WR: {res['overall_win_rate']*100:.2f}% | CI: [{res['overall_wilson_ci'][0]*100:.1f}%, {res['overall_wilson_ci'][1]*100:.1f}%] ({el:.1f}s)", flush=True)

    print(f"\nStage 2 Broad Meta Evaluation Complete in {time.time()-t0_2:.1f}s.", flush=True)

    # -----------------------------------------------------------------------
    # STEP 3 & 4: 300g H2H BENCHMARK & INDEPENDENT REPLICATION
    # -----------------------------------------------------------------------
    top_contenders = [c["name"] for c in sorted_1b[:4]]
    stage3_file = REPORTS_DIR / "stage3_replication_results.json"
    stage3_results = {}
    if stage3_file.exists():
        try:
            stage3_results = json.loads(stage3_file.read_text(encoding="utf-8"))
            print(f"Loaded {len(stage3_results)} existing Stage 3 Replication results.", flush=True)
        except Exception:
            stage3_results = {}

    print(f"\nExecuting Stage 3 & 4: Dedicated 300g H2H + 300g Independent Replication on Top 4 Contenders...", flush=True)
    t0_3 = time.time()
    
    for cid in top_contenders:
        if cid in stage3_results:
            continue
            
        info = candidates[cid]
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}"
        
        print(f"\n[Run 1] 300g Head-to-Head vs V4 + E19: {cid}...", flush=True)
        r1 = ab_gate.run_gate(spec_c=spec_c, spec_i=ogerpon_spec, games=300, workers=NUM_WORKERS)
        st1 = r1["chal"]
        w1 = st1["wins_seat0"] + st1["wins_seat1"]
        l1 = st1["losses"]
        d1 = st1["draws"]
        p1, lo1, hi1 = ab_gate.wilson(w1, w1 + l1)
        print(f"  Run 1 WR: {p1*100:5.1f}% [{lo1*100:4.1f}%, {hi1*100:4.1f}%] (W:{w1} L:{l1} D:{d1})", flush=True)
        
        print(f"[Run 2] 300g INDEPENDENT REPLICATION (New Game Sequence): {cid}...", flush=True)
        r2 = ab_gate.run_gate(spec_c=spec_c, spec_i=ogerpon_spec, games=300, workers=NUM_WORKERS)
        st2 = r2["chal"]
        w2 = st2["wins_seat0"] + st2["wins_seat1"]
        l2 = st2["losses"]
        d2 = st2["draws"]
        p2, lo2, hi2 = ab_gate.wilson(w2, w2 + l2)
        print(f"  Run 2 WR: {p2*100:5.1f}% [{lo2*100:4.1f}%, {hi2*100:4.1f}%] (W:{w2} L:{l2} D:{d2})", flush=True)
        
        stage3_results[cid] = {
            "name": cid,
            "family": info["family"],
            "run1": {"wins": w1, "losses": l1, "draws": d1, "wr": float(p1), "ci": [float(lo1), float(hi1)]},
            "run2": {"wins": w2, "losses": l2, "draws": d2, "wr": float(p2), "ci": [float(lo2), float(hi2)]},
            "replicated": bool(p1 >= 0.55 and p2 >= 0.55)
        }
        stage3_file.write_text(json.dumps(stage3_results, indent=2), encoding="utf-8")

    print(f"\nStage 3 & 4 Replications complete in {time.time()-t0_3:.1f}s.", flush=True)
    print("\n===================================================================", flush=True)
    print("ALL EXPERIMENTAL STAGES COMPLETED SUCCESSFULLY", flush=True)
    print("===================================================================", flush=True)
    return stage1a_results, stage1b_results, stage2_results, stage3_results


if __name__ == "__main__":
    run_hierarchical_search()
