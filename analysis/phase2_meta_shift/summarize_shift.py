"""Phase 2: cross-population diff numbers for the report .mds.

Reads pop_previous.json / pop_current.json (from analyze_populations.py) and
prints: FA histograms, decision-time table, early-turn play signatures,
per-team vs-Crustle records with win reasons, engine share, nasuo deck drift
vs metaC_garchomp_nasuo.csv, and Lucario/Hariyama presence (Sanjay overlap).
"""

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import CARD_DB  # noqa: E402

prev = json.loads((HERE / "pop_previous.json").read_text(encoding="utf-8"))
cur = json.loads((HERE / "pop_current.json").read_text(encoding="utf-8"))


def fa_hist(pop):
    c = Counter()
    for s in pop["sides"]:
        if s["first_attack"]:
            c[min(s["first_attack"], 10)] += 1
    n = sum(c.values())
    return {t: round(100 * c[t] / n, 1) for t in sorted(c)}


def early_sig(pop):
    """Population-level: median Play/Attach/Evolve counts on turns 1-6 of won
    sides + top cards played T1-3."""
    per_turn = defaultdict(lambda: defaultdict(list))
    cards = Counter()
    for s in pop["sides"]:
        if not s["won"]:
            continue
        for t_str, d in s["early"].items():
            for typ, n in d.items():
                per_turn[int(t_str)][typ].append(n)
        for nm, n in s["early_cards"].items():
            cards[nm] += n
    out = {}
    for t in sorted(per_turn):
        out[t] = {typ: round(st.mean(v), 2) for typ, v in sorted(per_turn[t].items())}
    return out, cards.most_common(12)


def crustle_table(pop):
    """Per-team record vs Crustle opponents + how wins end."""
    rows = defaultdict(lambda: {"w": 0, "l": 0, "win_reasons": Counter(),
                                "win_turns": [], "loss_reasons": Counter()})
    for s in pop["sides"]:
        opp = s.get("opp_deck")
        if not opp:
            continue
        if not any("Crustle" in CARD_DB.get(c, {}).get("name", "") for c in opp):
            continue
        r = rows[s["team"]]
        if s["won"]:
            r["w"] += 1
            r["win_reasons"][s["reason"]] += 1
            r["win_turns"].append(s["turns"])
        else:
            r["l"] += 1
            r["loss_reasons"][s["reason"]] += 1
    return rows


def own_crustle(pop):
    return {t: d for t, d in pop["summary"]["teams"].items()
            if d.get("games") and d.get("flags", {}).get("crustle_stall")}


for label, pop in (("PREVIOUS", prev), ("CURRENT", cur)):
    print(f"\n================ {label} ================")
    print("first-attack % by turn:", fa_hist(pop))
    sig, cards = early_sig(pop)
    print("early-turn action means (won sides):")
    for t, d in sig.items():
        print(f"  T{t}: {d}")
    print("top cards played T1-3 (won sides):")
    for nm, n in cards:
        print(f"  {n:5d}  {nm}")
    p = pop["summary"]["population"]
    print("wins end by:", p["end_reasons_in_wins"], " win turns median:",
          p["win_turns_median"])
    print("dudunsparce share:", p["dudunsparce_sides"], "/", p["sides"])
    print("\nvs-Crustle per team:")
    for t, r in sorted(crustle_table(pop).items(), key=lambda kv: -(kv[1]["w"] + kv[1]["l"])):
        tot = r["w"] + r["l"]
        wt = f"{st.median(r['win_turns']):.0f}" if r["win_turns"] else "-"
        print(f"  {t[:26]:26s} {r['w']:3d}W-{r['l']:3d}L ({100*r['w']/tot:3.0f}%)  "
              f"win by {dict(r['win_reasons'])}  loss by {dict(r['loss_reasons'])}  "
              f"win-turns med {wt}")
    print("Crustle-deck pilots in this top-10:", list(own_crustle(pop)))

# nasuo deck drift
want = Counter(int(x) for x in open(REPO / "metaC_garchomp_nasuo.csv") if x.strip())
drift = Counter()
for s in cur["sides"]:
    if s["team"] == "nasuo445" and s["deck"]:
        drift[Counter(s["deck"]) == want] += 1
print("\nnasuo445 current deck == our metaC list:", dict(drift))
if False in drift:
    # show the diff of the most common variant
    variants = Counter()
    for s in cur["sides"]:
        if s["team"] == "nasuo445" and s["deck"] and Counter(s["deck"]) != want:
            variants[tuple(sorted(s["deck"]))] += 1
    v = Counter(dict(zip(*[iter(sum(([c, n] for c, n in
        Counter(list(variants.most_common(1)[0][0])).items()), []))] * 2)))
    v = Counter(list(variants.most_common(1)[0][0]))
    gone = want - v
    added = v - want
    def nm(c):
        return CARD_DB.get(c, {}).get("name", str(c))
    print("  removed:", {nm(c): n for c, n in gone.items()})
    print("  added:  ", {nm(c): n for c, n in added.items()})

# Lucario/Hariyama (Sanjay overlap) in both top-10 populations
for label, pop in (("previous", prev), ("current", cur)):
    luc = sum(1 for s in pop["sides"] if s["deck"] and any(
        "Lucario" in CARD_DB.get(c, {}).get("name", "") for c in s["deck"]))
    print(f"{label} top-10 sides playing any Lucario deck: {luc}")

# nasuo W-rate then vs now
for label, pop in (("previous", prev), ("current", cur)):
    d = pop["summary"]["teams"].get("nasuo445", {})
    if d.get("games"):
        print(f"nasuo445 {label}: {d['wins']}/{d['games']} "
              f"({100*d['wins']/d['games']:.0f}%)")
