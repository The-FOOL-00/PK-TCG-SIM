"""Phase 3 quantifications:
(a) nasuo445 per-opponent-archetype record, previous vs current samples
(b) Crustle-matchup coverage inside the BC training harvest (win sides only,
    the extraction filter) — did BC ever see anti-stall play?
(c) Lucario sightings among top-10 opponents + their leaderboard mu
    (Sanjay strand check)
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import CARD_DB, archetype  # noqa: E402

P2 = REPO / "analysis" / "phase2_meta_shift"
prev = json.loads((P2 / "pop_previous.json").read_text(encoding="utf-8"))
cur = json.loads((P2 / "pop_current.json").read_text(encoding="utf-8"))


def nasuo_by_opp(pop, label):
    rec = defaultdict(lambda: [0, 0])
    for s in pop["sides"]:
        if s["team"] != "nasuo445":
            continue
        a = archetype(s["opp_deck"]) if s["opp_deck"] else None
        k = a["label"] if a else "?"
        rec[k][0 if s["won"] else 1] += 1
    print(f"\nnasuo445 vs opponent archetype ({label}):")
    for k, (w, l) in sorted(rec.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {k[:44]:44s} {w}W-{l}L")


nasuo_by_opp(prev, "previous sample, 145 sides")
nasuo_by_opp(cur, "current sample, 43 sides")

# (b) BC harvest coverage: winning nasuo sides (what extraction kept)
win_opp = Counter()
crustle_win_sides = 0
nasuo_win = 0
for s in prev["sides"]:
    if s["team"] != "nasuo445" or not s["won"]:
        continue
    nasuo_win += 1
    if s["opp_deck"] and any("Crustle" in CARD_DB.get(c, {}).get("name", "")
                             for c in s["opp_deck"]):
        crustle_win_sides += 1
print(f"\nBC-training proxy (nasuo winning sides in prev harvest): {nasuo_win}")
print(f"  of which vs Crustle decks: {crustle_win_sides} "
      f"({100*crustle_win_sides/max(1,nasuo_win):.0f}%)")
# how do those Crustle wins end?
cw = Counter()
for s in prev["sides"]:
    if s["team"] == "nasuo445" and s["won"] and s["opp_deck"] and any(
            "Crustle" in CARD_DB.get(c, {}).get("name", "") for c in s["opp_deck"]):
        cw[s["reason"]] += 1
print(f"  those wins end by: {dict(cw)}")

# (c) Lucario opponents of current top-10 + their LB mu
lb = {}
for r in csv.DictReader(open(P2 / "leaderboard_2026-07-12.csv", encoding="utf-8-sig")):
    try:
        lb[r["TeamName"]] = float(r["Score"])
    except ValueError:
        pass
luc = Counter()
for s in cur["sides"]:
    if s["opp_deck"] and any("Lucario" in CARD_DB.get(c, {}).get("name", "")
                             for c in s["opp_deck"]):
        luc[s["opp_team"]] += 1
print("\nLucario opponents seen by current top-10 (team, games, LB mu):")
if not luc:
    print("  none in 883 sides")
for t, n in luc.most_common():
    print(f"  {t[:30]:30s} {n:3d}  mu={lb.get(t, '?')}")
top_lucario = max((lb.get(t, 0) for t in luc), default=0)
print(f"highest-mu Lucario team seen: {top_lucario}")

# bonus: nasuo mu-trend context — win rate by population already known
