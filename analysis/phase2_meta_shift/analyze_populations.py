"""Phase 2: population analysis for the meta-shift comparison.

Analyzes a directory of episode replays restricted to a given team list
(one population = previous or current top-10) and emits per-team and
population-level stats as JSON + a printed table:

- decks/archetypes per team (from the 60-card answer at steps[1])
- W/L per team inside the sample
- median/p90 decision time (remainingOverageTime deltas, ms)
- first-attack turn distribution, game length, end reasons
- turns 1-6 signature actions (log-type counts + most-played cards T1-3)
- Dudunsparce-engine and Crustle-stall flags per deck
- win patterns for won sides (reason, prizes, tempo), incl. vs-Crustle games

Run:
  py -3.12 -X utf8 analysis/phase2_meta_shift/analyze_populations.py \
      --dir data/top_replays_bulk --teams-lb data/leaderboard_snapshot_2026-07-10.csv \
      --label previous --out analysis/phase2_meta_shift/pop_previous.json
"""

import argparse
import csv
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import CARD_DB, archetype  # noqa: E402

REASONS = {1: "prizes", 2: "deckout", 3: "no-active", 4: "effect"}


def deck_flags(deck):
    names = {CARD_DB.get(c, {}).get("name", "") for c in deck}
    return {
        "dudunsparce": any("Dudunsparce" in n for n in names),
        "crustle_stall": any("Crustle" in n for n in names),
    }


def parse_episode(fp, wanted):
    d = json.loads(fp.read_text(encoding="utf-8"))
    teams = (d.get("info") or {}).get("TeamNames") or ["?", "?"]
    hits = [a for a in (0, 1) if teams[a] in wanted]
    if not hits:
        return None
    steps = d.get("steps") or []
    if len(steps) < 3:
        return None
    rewards = d.get("rewards") or [None, None]
    decks = [None, None]
    for a in (0, 1):
        act = steps[1][a].get("action")
        if isinstance(act, list) and len(act) == 60:
            decks[a] = act

    vis = (steps[0][0].get("visualize")
           or (steps[0][0].get("observation") or {}).get("visualize")) or []
    reason, last_turn = None, 0
    first_attack = [None, None]
    prizes = [0, 0]
    early = [defaultdict(Counter), defaultdict(Counter)]   # side -> turn -> log types
    early_cards = [Counter(), Counter()]                   # side -> cards played T1-3
    for entry in vis:
        cur = entry.get("current") or {}
        turn = cur.get("turn") or last_turn
        last_turn = max(last_turn, turn)
        for l in entry.get("logs") or []:
            t, pi = l.get("type"), l.get("playerIndex")
            if t == "Result":
                reason = l.get("reason")
            elif t == "Attack" and pi in (0, 1) and first_attack[pi] is None:
                first_attack[pi] = turn
            elif t == "MoveCard" and l.get("fromArea") == 6 and pi in (0, 1):
                prizes[pi] += 1
            if pi in (0, 1) and turn <= 6 and t in ("Play", "Evolve", "Attach",
                                                    "Attack", "Switch"):
                early[pi][turn][t] += 1
                if t == "Play" and turn <= 3:
                    nm = CARD_DB.get(l.get("cardId"), {}).get("name")
                    if nm:
                        early_cards[pi][nm] += 1

    # decision times from remainingOverageTime deltas (seconds -> ms)
    dtimes = [[], []]
    for a in (0, 1):
        prev = None
        for i in range(1, len(steps)):
            e = steps[i][a]
            if not isinstance(e, dict):
                continue
            ot = (e.get("observation") or {}).get("remainingOverageTime")
            if ot is None:
                continue
            if prev is not None and e.get("status") == "ACTIVE":
                delta = prev - ot
                if 0 <= delta < 60:
                    dtimes[a].append(delta * 1000.0)
            prev = ot

    sides = []
    for a in hits:
        sides.append({
            "team": teams[a],
            "opp_team": teams[1 - a],
            "won": rewards[a] == 1,
            "deck": decks[a],
            "opp_deck": decks[1 - a],
            "reason": REASONS.get(reason, str(reason)),
            "turns": last_turn,
            "first_attack": first_attack[a],
            "opp_first_attack": first_attack[1 - a],
            "prizes": prizes[a],
            "opp_prizes": prizes[1 - a],
            "dtimes_ms": dtimes[a],
            "early": {str(t): dict(early[a][t]) for t in sorted(early[a])},
            "early_cards": dict(early_cards[a].most_common(8)),
        })
    return sides


def run(src_dir, teams, label, out):
    files = sorted(Path(src_dir).glob("*.json"))
    files = [f for f in files if not f.name.startswith("_")]
    all_sides = []
    fails = 0
    for fp in files:
        try:
            sides = parse_episode(fp, teams)
        except Exception:
            fails += 1
            continue
        if sides:
            all_sides.extend(sides)
    print(f"[{label}] files={len(files)} parse-fails={fails} team-sides={len(all_sides)}")

    by_team = defaultdict(list)
    for s in all_sides:
        by_team[s["team"]].append(s)

    summary = {"label": label, "teams": {}, "population": {}}
    for t in teams:
        rs = by_team.get(t, [])
        if not rs:
            summary["teams"][t] = {"games": 0}
            continue
        archs = Counter()
        flags = Counter()
        for s in rs:
            a = archetype(s["deck"]) if s["deck"] else None
            if a:
                archs[a["label"]] += 1
                for k, v in deck_flags(s["deck"]).items():
                    if v:
                        flags[k] += 1
        dt = [x for s in rs for x in s["dtimes_ms"]]
        fa = [s["first_attack"] for s in rs if s["first_attack"]]
        wins = sum(1 for s in rs if s["won"])
        summary["teams"][t] = {
            "games": len(rs), "wins": wins,
            "archetypes": dict(archs.most_common()),
            "flags": dict(flags),
            "dtime_ms": {"median": round(st.median(dt), 1) if dt else None,
                         "p90": round(st.quantiles(dt, n=10)[8], 1) if len(dt) >= 10 else None,
                         "n": len(dt)},
            "first_attack": {"median": st.median(fa) if fa else None,
                             "mean": round(st.mean(fa), 2) if fa else None},
            "turns_median": st.median([s["turns"] for s in rs]),
        }

    # population-level aggregates
    win_sides = [s for s in all_sides if s["won"]]
    fa_all = [s["first_attack"] for s in all_sides if s["first_attack"]]
    summary["population"] = {
        "sides": len(all_sides),
        "wins": len(win_sides),
        "first_attack_hist": dict(Counter(fa_all)),
        "first_attack_median": st.median(fa_all) if fa_all else None,
        "end_reasons_in_wins": dict(Counter(s["reason"] for s in win_sides)),
        "win_turns_median": st.median([s["turns"] for s in win_sides]) if win_sides else None,
        "win_prizes": dict(Counter(s["prizes"] for s in win_sides)),
        "dudunsparce_sides": sum(1 for s in all_sides
                                 if s["deck"] and deck_flags(s["deck"])["dudunsparce"]),
    }

    # vs-Crustle handling (opponent plays Crustle)
    vs_crustle = [s for s in all_sides
                  if s["opp_deck"] and deck_flags(s["opp_deck"])["crustle_stall"]]
    summary["vs_crustle"] = {
        "games": len(vs_crustle),
        "wins": sum(1 for s in vs_crustle if s["won"]),
        "detail": [{
            "team": s["team"], "won": s["won"], "reason": s["reason"],
            "turns": s["turns"], "prizes": s["prizes"], "opp_prizes": s["opp_prizes"],
            "first_attack": s["first_attack"],
        } for s in vs_crustle],
    }

    Path(out).write_text(json.dumps({"summary": summary,
                                     "sides": all_sides}, indent=1),
                         encoding="utf-8")
    # console table
    print(f"{'team':28s} {'games':>5s} {'W':>3s}  {'dtime med':>9s}  "
          f"{'FA med':>6s}  archetype (top)")
    for t in teams:
        s = summary["teams"][t]
        if not s.get("games"):
            print(f"{t:28s}     0")
            continue
        arch = next(iter(s["archetypes"]), "?")
        print(f"{t:28s} {s['games']:5d} {s['wins']:3d}  "
              f"{str(s['dtime_ms']['median']):>9s}  "
              f"{str(s['first_attack']['median']):>6s}  {arch[:44]}")
    p = summary["population"]
    print(f"\npopulation: {p['sides']} sides, {p['wins']} wins, "
          f"FA median {p['first_attack_median']}, "
          f"dudunsparce sides {p['dudunsparce_sides']}")
    vc = summary["vs_crustle"]
    print(f"vs Crustle: {vc['games']} games, {vc['wins']} wins")
    print(f"saved -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--teams-lb", required=True,
                    help="leaderboard CSV; top-10 taken as the population")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    lb = list(csv.DictReader(open(args.teams_lb, encoding="utf-8-sig")))
    if "team" not in lb[0]:
        lb.sort(key=lambda r: -float(r.get("Score") or 0))
        lb = [{"team": r["TeamName"]} for r in lb]
    teams = [r["team"] for r in lb[:10]]
    print("population:", teams)
    run(args.dir, teams, args.label, args.out)
