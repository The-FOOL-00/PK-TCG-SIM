"""Stage 4 data prep: census of list-0 across all harvested replay pools.

list-0 = the consensus Alakazam engine list shared by Majkel1337 and Yushin
Ito (metaB_alakazam.csv + 7-card update). This script:
1. reconstructs list-0 from the current-top10 pool (majority exact list of
   Yushin's Alakazam-family sides, cross-checked byte-identical vs Majkel's),
2. writes stage4/deck_list0.csv,
3. censuses every replay pool for sides playing exactly list-0: team, W/L,
   opponent archetype class (Crustle stall / fast aggro / engine mirror),
   date span -> the real harvestable volume per pilot,
4. copies list-0 episodes into stage4/data/replays_list0/ for extraction.
"""

import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import CARD_DB, archetype  # noqa: E402

POOLS = {
    "current(07-10..11)": REPO / "analysis/phase2_meta_shift/replays_current_top10",
    "bulk(07-06..09)": REPO / "data/top_replays_bulk",
}
DEST = REPO / "stage4" / "data" / "replays_list0"
DECK_OUT = REPO / "stage4" / "deck_list0.csv"

# -- step 1: reconstruct list-0 from current pool --------------------------
per_list = defaultdict(Counter)          # deck-key -> Counter(team)
src = POOLS["current(07-10..11)"]
for fp in sorted(src.glob("*.json")):
    if fp.name.startswith("_"):
        continue
    d = json.loads(fp.read_text(encoding="utf-8"))
    teams = d["info"]["TeamNames"]
    for a in (0, 1):
        if teams[a] not in ("Majkel1337", "Yushin Ito"):
            continue
        act = d["steps"][1][a].get("action")
        if isinstance(act, list) and len(act) == 60:
            per_list[tuple(sorted(act))][teams[a]] += 1

shared = [k for k, c in per_list.items() if len(c) == 2]
assert len(shared) == 1, f"expected exactly one shared list, got {len(shared)}"
LIST0 = Counter(shared[0])
DECK_OUT.parent.mkdir(parents=True, exist_ok=True)
DECK_OUT.write_text("\n".join(str(c) for c in shared[0]) + "\n", encoding="utf-8")
print(f"list-0 written -> {DECK_OUT}  ({sum(LIST0.values())} cards, "
      f"{len(LIST0)} distinct)")
arch = archetype(list(shared[0]))
print(f"archetype label: {arch['label']}")

# -- steps 2-4: census + copy ----------------------------------------------
def opp_class(deck):
    if not deck:
        return "?"
    names = {CARD_DB.get(c, {}).get("name", "") for c in deck}
    if any("Crustle" in n for n in names):
        return "crustle"
    if any(n in ("Mega Lucario ex", "Archaludon ex") for n in names):
        return "aggro"
    if Counter(deck) == LIST0:
        return "mirror(list-0)"
    if any("Alakazam" in n for n in names):
        return "alakazam-family"
    return "other"


DEST.mkdir(parents=True, exist_ok=True)
stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # pool -> team -> [W, L]
oppc = defaultdict(lambda: Counter())                     # team -> class counter (wins only)
copied = 0
for pool, src in POOLS.items():
    for fp in sorted(src.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        teams = (d.get("info") or {}).get("TeamNames") or ["?", "?"]
        steps = d.get("steps") or []
        if len(steps) < 3:
            continue
        keep = False
        for a in (0, 1):
            act = steps[1][a].get("action")
            if not (isinstance(act, list) and Counter(act) == LIST0):
                continue
            keep = True
            won = (d.get("rewards") or [None, None])[a] == 1
            stats[pool][teams[a]][0 if won else 1] += 1
            if won:
                oppc[teams[a]][opp_class(steps[1][1 - a].get("action"))] += 1
        if keep:
            dst = DEST / fp.name
            if not dst.exists():
                shutil.copy2(fp, dst)
                copied += 1

print(f"\nepisodes copied to {DEST}: {copied}")
for pool, teams_d in stats.items():
    print(f"\n[{pool}] list-0 sides:")
    for t, (w, l) in sorted(teams_d.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {t[:26]:26s} {w}W-{l}L")
print("\nwin-side opponent classes per pilot (C1/C2 coverage):")
for t, c in oppc.items():
    print(f"  {t[:26]:26s} {dict(c.most_common())}")
