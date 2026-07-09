"""Assemble the Step 1 cross-deck gate battery into one table.

Reads runs/gate_step1_<opp>_<belief>.json (belief search vs v1+opp deck) and
runs/diagnose_<opp>.json (override-agreement + value separation), prints the
per-opponent comparison the Option-1 go/no-go decision needs.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OPPS = [("metaA_garchomp", "Garchomp ex (5E)"),
        ("metaB_alakazam", "Dudunsparce/Alakazam (3E)"),
        ("metaC_kangaskhan", "Mega Kangaskhan (16E)")]


def load(fp):
    p = REPO / "runs" / fp
    return json.loads(p.read_text()) if p.exists() else None


def ci(j):
    if not j:
        return "     (pending)      "
    lo, hi = j["wilson95"]
    return f"{j['win_rate']*100:4.1f}%  [{lo*100:4.1f},{hi*100:4.1f}]  {j['verdict']}"


print("=" * 78)
print("STEP 1 — FAIR CROSS-DECK GATES (belief-search + our deck vs v1 + opp deck)")
print("300 games each, seats alternated, 95% Wilson CI\n")
print(f"{'opponent':<28}{'comp (honest belief)':<26}{'mirror (=wrong here)':<26}")
for tag, label in OPPS:
    c = load(f"gate_step1_{tag}_comp.json")
    m = load(f"gate_step1_{tag}_mirror.json")
    print(f"{label:<28}{ci(c):<26}{ci(m):<26}")
    if c and (c["crashes"]["chal"] or c["crashes"]["inc"]):
        print(f"    !! crashes: {c['crashes']}")

print("\n" + "-" * 78)
print("DIAGNOSIS per opponent (identical positions; oracle = true-deck belief ceiling)")
for tag, label in OPPS:
    d = load(f"diagnose_{tag}.json")
    if not d:
        print(f"\n{label}: (pending)")
        continue
    print(f"\n{label}  [{d['n']} positions, ref={d['reference']}]")
    ov = d["override"]
    print("  override vs v1 : " + "  ".join(f"{k} {v*100//d['n']}%"
                                            for k, v in ov.items()))
    e = d["edge"]
    et = max(1, e.get("total", 0))
    print(f"  edge capture   : of {e.get('total',0)} {d['reference']}-overrides, "
          f"comp follows {100*e.get('comp_follows',0)//et}%  "
          f"reverts-v1 {100*e.get('comp_reverts_v1',0)//et}%  "
          f"third {100*e.get('comp_third',0)//et}%")
    zf = d["gap_zero_frac"]
    gm = d["gap_mean"]
    print("  value sep      : " + "  ".join(
        f"{m} gap {gm[m]:.3f}/zero {int(zf[m]*100)}%" for m in gm))
    if d.get("lowdet"):
        print("  det sweep      : " + "  ".join(
            f"det{k} zero {int(v['zero_frac']*100)}%" for k, v in d["lowdet"].items()))
print("=" * 78)
