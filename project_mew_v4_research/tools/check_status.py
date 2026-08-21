import json
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
s1a = REPORTS_DIR / "stage1a_fast_screen.json"
s1b = REPORTS_DIR / "stage1b_deep_screen.json"
s2 = REPORTS_DIR / "stage2_broad_meta_results.json"
s3 = REPORTS_DIR / "stage3_replication_results.json"

if s1a.exists():
    d = json.loads(s1a.read_text(encoding="utf-8"))
    print(f"Stage 1A Screened: {len(d)} / 224 candidates")
    top = sorted(d.values(), key=lambda x: x["win_rate"], reverse=True)[:10]
    print("\n--- TOP 10 IN STAGE 1A ---")
    for i, c in enumerate(top, 1):
        print(f"  {i:2d}. {c['name']:48s}: {c['win_rate']*100:5.1f}% [{c['wilson_ci'][0]*100:4.1f}%, {c['wilson_ci'][1]*100:4.1f}%] (W:{c['wins']:2d} L:{c['losses']:2d}) Fam:{c['family']}")

if s1b.exists():
    d = json.loads(s1b.read_text(encoding="utf-8"))
    print(f"\nStage 1B Deep Screened: {len(d)} candidates")
    top = sorted(d.values(), key=lambda x: x["win_rate"], reverse=True)[:10]
    for i, c in enumerate(top, 1):
        print(f"  {i:2d}. {c['name']:48s}: {c['win_rate']*100:5.1f}% [{c['wilson_ci'][0]*100:4.1f}%, {c['wilson_ci'][1]*100:4.1f}%] Fam:{c['family']}")

if s2.exists():
    d = json.loads(s2.read_text(encoding="utf-8"))
    print(f"\nStage 2 MetaPool Evaluated: {len(d)} decks")
    for name, r in d.items():
        print(f"  {name:40s}: MetaPool WR = {r['overall_win_rate']*100:5.2f}% [{r['overall_wilson_ci'][0]*100:4.1f}%, {r['overall_wilson_ci'][1]*100:4.1f}%]")

if s3.exists():
    d = json.loads(s3.read_text(encoding="utf-8"))
    print(f"\nStage 3 Replications: {len(d)} decks")
    for name, r in d.items():
        print(f"  {name:40s}: Run1={r['run1']['wr']*100:.1f}% Run2={r['run2']['wr']*100:.1f}% Replicated={r['replicated']}")
