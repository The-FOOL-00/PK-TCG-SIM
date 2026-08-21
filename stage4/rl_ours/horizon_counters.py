"""Decision-level counters per horizon arm (the capture missing last session).

Computes, from saved self-play replays, in the same definitions used for the
28 ladder games in BEHAVIORAL_GAP_DIAGNOSIS.md:
  - END-with-development-available rate
  - ENDs with bench < benchMax AND a playable Basic-searcher in hand (per game)
  - attack-when-legal uptake (per TURN, Sanjay §6n unit)
  - chosen-action-type distribution
Both seats are the same agent, so both are pooled.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
cards = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in cards.get("cards", {}).items()}
SEARCHERS = {"buddy-buddy poffin", "nest ball", "ultra ball", "hop's bag",
             "poke ball", "great ball", "pokegear 3.0"}
OT = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY", 11: "DISCARD",
      12: "RETREAT", 13: "ATTACK", 14: "END"}
DEVT = (7, 8, 9, 10)


def name_of(cid):
    return ((CARDS.get(cid) or {}).get("name") or "").lower()


def arm_counters(d):
    R = {"end": 0, "end_dev": 0, "end_searcher": 0, "chosen": Counter(),
         "own_turns": 0, "atk_legal_turns": 0, "atk_turns": 0, "games": 0}
    for fp in sorted(Path(d).glob("g*.json")):
        js = json.loads(fp.read_text(encoding="utf-8"))
        steps = js["steps"]
        R["games"] += 1
        vis = (steps[0][0].get("visualize")
               or (steps[0][0].get("observation") or {}).get("visualize")) or []
        turn_owner, atk_log = {}, defaultdict(int)
        last = 0
        for entry in vis:
            cur = entry.get("current") or {}
            t = cur.get("turn") or last
            last = max(last, t)
            for l in entry.get("logs") or []:
                ty, pi = l.get("type"), l.get("playerIndex")
                if ty == "TurnStart" and pi is not None:
                    turn_owner[t] = pi
                elif ty == "Attack" and pi is not None:
                    atk_log[(pi, t)] += 1
        for seat in (0, 1):
            own = sorted(t for t, o in turn_owner.items() if o == seat)
            R["own_turns"] += len(own)
            R["atk_turns"] += sum(1 for t in own if atk_log[(seat, t)])
            legal_turns = set()
            for i in range(len(steps) - 1):
                e = steps[i][seat]
                if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                    continue
                obs = e.get("observation") or {}
                sel = obs.get("select") or {}
                if sel.get("type") != 0:
                    continue
                opts = sel.get("option") or []
                act = steps[i + 1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 1):
                    continue
                ci = act[0]
                if not isinstance(ci, int) or ci >= len(opts):
                    continue
                types = [(o or {}).get("type") for o in opts]
                turn = (obs.get("current") or {}).get("turn") or 0
                if 13 in types:
                    legal_turns.add(turn)
                R["chosen"][OT.get(types[ci], types[ci])] += 1
                if types[ci] != 14:
                    continue
                R["end"] += 1
                if any(t in DEVT for t in types):
                    R["end_dev"] += 1
                me = ((obs.get("current") or {}).get("players") or [{}, {}])[seat]
                hand = me.get("hand") or []
                bench = me.get("bench") or []
                bmax = me.get("benchMax") or 5
                if len([b for b in bench if b]) < bmax:
                    for j, o in enumerate(opts):
                        if types[j] != 7:
                            continue
                        ix = (o or {}).get("index")
                        if isinstance(ix, int) and ix < len(hand) and hand[ix]:
                            if name_of((hand[ix] or {}).get("id")) in SEARCHERS:
                                R["end_searcher"] += 1
                                break
            R["atk_legal_turns"] += len(legal_turns & set(own))
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True, help="LABEL=dir")
    args = ap.parse_args()
    res = {}
    for spec in args.arms:
        lab, d = spec.split("=", 1)
        if not Path(d).exists():
            print(f"missing {d}")
            continue
        res[lab] = arm_counters(d)

    print(f"\n{'arm':<5s} {'games':>5s} {'ENDs':>5s} {'END+dev':>9s} "
          f"{'END+srch/g':>11s} {'ownT':>5s} {'atkLegalT':>9s} "
          f"{'atkTurns':>8s} {'atk/turn':>8s} {'atkWhenLegal':>13s}")
    print("-" * 92)
    for lab, R in res.items():
        ed = R["end_dev"] / R["end"] * 100 if R["end"] else 0
        aw = R["atk_turns"] / R["atk_legal_turns"] * 100 if R["atk_legal_turns"] else 0
        print(f"{lab:<5s} {R['games']:>5d} {R['end']:>5d} {ed:>8.1f}% "
              f"{R['end_searcher']/R['games']:>11.2f} {R['own_turns']:>5d} "
              f"{R['atk_legal_turns']:>9d} {R['atk_turns']:>8d} "
              f"{R['atk_turns']/R['own_turns']*100 if R['own_turns'] else 0:>7.1f}% "
              f"{aw:>12.1f}%")
    print("\nchosen-action distribution (% of MAIN decisions):")
    labs = list(res)
    kinds = ["PLAY", "ATTACH", "EVOLVE", "ABILITY", "ATTACK", "RETREAT", "END"]
    print(f"{'action':<10s} " + " ".join(f"{l:>9s}" for l in labs))
    for k in kinds:
        row = []
        for l in labs:
            tot = sum(res[l]["chosen"].values()) or 1
            row.append(f"{res[l]['chosen'][k]/tot*100:>8.1f}%")
        print(f"{k:<10s} " + " ".join(row))
    Path(REPO / "scratchpad/s3/horizon_counters.json").write_text(
        json.dumps({k: {**v, "chosen": dict(v["chosen"])} for k, v in res.items()}, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
