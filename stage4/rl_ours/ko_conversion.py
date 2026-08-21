"""Damage-to-KO conversion: how much of the damage we deal becomes a knockout.

The gap this measures is the one writeup S8 described but mis-diagnosed --
"identical damage dealt and identical attack count, fewer knockouts" is a
CONVERSION gap, decided at the damage-target slot, not a stat mismatch.

Method. `HpChange` logs in the replay `visualize` stream carry the engine
`serial` (unique per match), the owning `playerIndex`, and a signed `value`
(negative = damage, positive = heal/counter-removal). Running that per serial
gives each Pokemon's damage track; a serial whose running total ever reaches
its card's printed `hp` was knocked out.

  stranded share = 1 - (damage that landed on KO'd Pokemon / total damage dealt)

Damage on a KO'd Pokemon is credited only up to its HP -- overkill past the
lethal point is not "converted", it is just unavoidable granularity.

Both seats are the same agent in these mirror runs, so sides are pooled.

Usage:  python stage4/rl_ours/ko_conversion.py LABEL=dir [LABEL=dir ...]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CARDS = {int(k): v
         for k, v in json.loads(
             (REPO / "card_data.json").read_text(encoding="utf-8"))["cards"].items()}


def arm_conversion(d):
    dmg_total = dmg_converted = kos = struck = games = 0
    for fp in sorted(Path(d).glob("g*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        vis = (js["steps"][0][0].get("visualize")
               or (js["steps"][0][0].get("observation") or {}).get("visualize")) or []
        games += 1
        run, hp, koed = defaultdict(int), {}, set()
        for entry in vis:
            for l in entry.get("logs") or []:
                if l.get("type") != "HpChange":
                    continue
                s = l.get("serial")
                if s is None:
                    continue
                hp.setdefault(s, (CARDS.get(l.get("cardId")) or {}).get("hp") or 0)
                # value is negative for damage, positive for heal
                run[s] = max(0, run[s] - (l.get("value") or 0))
                if hp[s] and run[s] >= hp[s]:
                    koed.add(s)
        for s, dealt in run.items():
            h = hp.get(s) or 0
            if not h or dealt <= 0:
                continue
            struck += 1
            if s in koed:
                dmg_total += min(dealt, h)   # overkill is not credited either way
                dmg_converted += h
            else:
                dmg_total += dealt
        kos += len(koed)
    return {"games": games, "dmg": dmg_total, "converted": dmg_converted,
            "kos": kos, "struck": struck,
            "stranded": 1 - (dmg_converted / dmg_total) if dmg_total else 0.0,
            "dmg_per_ko": dmg_total / kos if kos else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+", help="LABEL=dir")
    args = ap.parse_args()
    print(f"{'arm':<14}{'games':>6}{'damage':>10}{'KOs':>7}"
          f"{'struck':>8}{'STRANDED':>10}{'dmg/KO':>9}")
    print("-" * 64)
    for a in args.arms:
        lab, _, d = a.partition("=")
        r = arm_conversion(d)
        print(f"{lab:<14}{r['games']:>6}{r['dmg']:>10}{r['kos']:>7}"
              f"{r['struck']:>8}{r['stranded'] * 100:>9.1f}%{r['dmg_per_ko']:>9.1f}")


if __name__ == "__main__":
    main()
