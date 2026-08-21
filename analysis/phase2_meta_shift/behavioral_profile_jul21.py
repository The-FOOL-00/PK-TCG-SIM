"""Phase B (2026-07-21): per-TURN behavioral profile of a replay population.

Emits, per team, the metrics comparable to the teammate's §6n table
(SANJAY CONTEXT doc), from the fields this replay schema actually carries:
  - decision speed (remainingOverageTime deltas, ms; median)
  - hand size at the START of own turns 3/4/5 (his: 7.9/9.3/10.3 top vs
    6.1/6.5/7.0 his agent — measured on his Alakazam 300+HP subset)
  - extra draws per own turn (Draw logs beyond the turn draw) = the
    draw-ability-engine usage proxy; there is NO Ability log type in this
    schema, so ability-use-when-legal is NOT directly measurable here
  - first-evolution turn, first-attack turn
  - attacks per own turn (share of own turns containing an Attack)
  - archetype, W/L, end reasons

UNIT: per TURN (own turns), per his §6m unit-of-analysis rule.

Run:
  py -3.12 -X utf8 analysis/phase2_meta_shift/behavioral_profile_jul21.py \
      --dir analysis/phase2_meta_shift/replays_top10_jul21 \
      --teams-lb analysis/phase2_meta_shift/leaderboard_2026-07-21.csv \
      --out analysis/phase2_meta_shift/profile_top10_jul21.json
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
    turn_owner = {}                    # turn -> playerIndex (from TurnStart)
    hand_at_turn_start = [dict(), dict()]   # side -> turn -> handCount
    draws = [defaultdict(int), defaultdict(int)]     # side -> turn -> Draw count
    evolves = [defaultdict(int), defaultdict(int)]
    attacks = [defaultdict(int), defaultdict(int)]
    attaches = [defaultdict(int), defaultdict(int)]
    first_attack = [None, None]
    first_evolve = [None, None]
    prizes = [0, 0]

    for entry in vis:
        cur = entry.get("current") or {}
        turn = cur.get("turn") or last_turn
        last_turn = max(last_turn, turn)
        players = cur.get("players") or [{}, {}]
        for l in entry.get("logs") or []:
            t, pi = l.get("type"), l.get("playerIndex")
            if t == "Result":
                reason = l.get("reason")
            elif t == "TurnStart" and pi in (0, 1):
                turn_owner[turn] = pi
                hc = (players[pi] or {}).get("handCount")
                if hc is not None and turn not in hand_at_turn_start[pi]:
                    hand_at_turn_start[pi][turn] = hc
            elif t == "Draw" and pi in (0, 1) and turn > 0:
                draws[pi][turn] += 1
            elif t == "Evolve" and pi in (0, 1):
                evolves[pi][turn] += 1
                if first_evolve[pi] is None:
                    first_evolve[pi] = turn
            elif t == "Attack" and pi in (0, 1):
                attacks[pi][turn] += 1
                if first_attack[pi] is None:
                    first_attack[pi] = turn
            elif t == "Attach" and pi in (0, 1):
                attaches[pi][turn] += 1
            elif t == "MoveCard" and l.get("fromArea") == 6 and pi in (0, 1):
                prizes[pi] += 1

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
        own_turns = sorted(t for t, o in turn_owner.items() if o == a)
        n_own = len(own_turns)
        extra_draws = [max(0, draws[a][t] - 1) for t in own_turns]
        sides.append({
            "team": teams[a],
            "opp_team": teams[1 - a],
            "won": rewards[a] == 1,
            "deck": decks[a],
            "opp_deck": decks[1 - a],
            "reason": REASONS.get(reason, str(reason)),
            "turns": last_turn,
            "n_own_turns": n_own,
            "first_attack": first_attack[a],
            "first_evolve": first_evolve[a],
            "prizes": prizes[a],
            "opp_prizes": prizes[1 - a],
            "dtime_med": round(st.median(dtimes[a]), 1) if dtimes[a] else None,
            "hand_T3": hand_at_turn_start[a].get(own_turns[1]) if n_own > 1 else None,
            "hand_T5": hand_at_turn_start[a].get(own_turns[2]) if n_own > 2 else None,
            "hand_T7": hand_at_turn_start[a].get(own_turns[3]) if n_own > 3 else None,
            "extra_draws_per_turn": round(sum(extra_draws) / n_own, 2) if n_own else None,
            "attack_turn_share": round(sum(1 for t in own_turns if attacks[a][t]) / n_own, 2) if n_own else None,
            "evolves_total": sum(evolves[a].values()),
        })
    return sides


def agg(vals):
    vals = [v for v in vals if v is not None]
    return round(st.mean(vals), 2) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--teams-lb", required=True)
    ap.add_argument("--teams", nargs="*", help="explicit team list (overrides lb)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.teams:
        teams = args.teams
    else:
        lb = list(csv.DictReader(open(args.teams_lb, encoding="utf-8-sig")))
        teams = [r["TeamName"] for r in lb[:10]]
    print("population:", teams)

    all_sides = []
    fails = 0
    for fp in sorted(Path(args.dir).glob("*.json")):
        if fp.name.startswith("_"):
            continue
        try:
            sides = parse_episode(fp, set(teams))
        except Exception:
            fails += 1
            continue
        if sides:
            all_sides.extend(sides)
    print(f"files parsed, fails={fails}, sides={len(all_sides)}")

    by_team = defaultdict(list)
    for s in all_sides:
        by_team[s["team"]].append(s)

    out = {"teams": {}, "sides": all_sides}
    hdr = (f"{'team':26s} {'n':>3s} {'W%':>4s} {'dtime':>6s} {'FA':>4s} {'FE':>4s} "
           f"{'hT3':>4s} {'hT5':>4s} {'hT7':>4s} {'xDr/t':>5s} {'atk/t':>5s}  archetype")
    print("\n" + hdr)
    for t in teams:
        rs = by_team.get(t, [])
        if not rs:
            print(f"{t:26s}   0")
            continue
        archs = Counter()
        for s in rs:
            a = archetype(s["deck"]) if s["deck"] else None
            if a:
                archs[a["label"]] += 1
        wr = sum(1 for s in rs if s["won"]) / len(rs)
        row = {
            "games": len(rs),
            "winrate": round(wr, 2),
            "archetypes": dict(archs.most_common()),
            "dtime_med": agg([s["dtime_med"] for s in rs]),
            "first_attack": agg([s["first_attack"] for s in rs]),
            "first_evolve": agg([s["first_evolve"] for s in rs]),
            "hand_T3": agg([s["hand_T3"] for s in rs]),
            "hand_T5": agg([s["hand_T5"] for s in rs]),
            "hand_T7": agg([s["hand_T7"] for s in rs]),
            "extra_draws_per_turn": agg([s["extra_draws_per_turn"] for s in rs]),
            "attack_turn_share": agg([s["attack_turn_share"] for s in rs]),
            "end_reasons_wins": dict(Counter(s["reason"] for s in rs if s["won"])),
        }
        out["teams"][t] = row
        arch = next(iter(row["archetypes"]), "?")
        print(f"{t:26s} {row['games']:3d} {row['winrate']*100:4.0f} "
              f"{str(row['dtime_med']):>6s} {str(row['first_attack']):>4s} "
              f"{str(row['first_evolve']):>4s} {str(row['hand_T3']):>4s} "
              f"{str(row['hand_T5']):>4s} {str(row['hand_T7']):>4s} "
              f"{str(row['extra_draws_per_turn']):>5s} "
              f"{str(row['attack_turn_share']):>5s}  {arch[:40]}")

    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nsaved -> {args.out}")


if __name__ == "__main__":
    main()
