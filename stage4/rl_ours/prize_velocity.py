"""Prize velocity = prizes taken per own turn, with a bootstrap CI.

Per-side extraction reuses perturn_compare's definitions: own turns from the
`visualize` TurnStart logs, prizes from players[i].prize (which holds prizes
REMAINING and is EMPTY during setup, so the baseline is the max seen).

Pooled velocity = sum(prizes) / sum(own turns), i.e. mean/mean -- the same
construction used for the reference figures in the R2_ARM.md header.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OT_ATTACK = 13


def sides(d):
    """[(own_turns, prizes_taken, first_prize_turn|None), ...] per side."""
    out = []
    for fp in sorted(Path(d).glob("*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = js.get("steps") or []
        if not steps:
            continue
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
            p0 = plast = fpt = None
            legal = set()
            for i in range(len(steps) - 1):
                e = steps[i][seat]
                if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                    continue
                obs = e.get("observation") or {}
                cur = obs.get("current") or {}
                me = cur.get("yourIndex")
                pl = cur.get("players") or []
                if me is not None and me < len(pl):
                    n = len(pl[me].get("prize") or [])
                    if n > 0:
                        p0 = n if p0 is None else max(p0, n)
                        plast = n
                        if fpt is None and n < p0:
                            fpt = cur.get("turn") or 0
                sel = obs.get("select") or {}
                if sel.get("type") == 0 and any(
                        (o or {}).get("type") == OT_ATTACK
                        for o in (sel.get("option") or [])):
                    legal.add(cur.get("turn") or 0)
            if not own:
                continue
            prizes = (p0 - plast) if (p0 is not None and plast is not None) else 0
            n_atk = sum(1 for t in own if atk_log[(seat, t)])
            out.append({"own": len(own), "prizes": prizes, "fpt": fpt,
                        "atk": n_atk, "legal": len(legal & set(own))})
    return out


def vel(rows):
    o = sum(r["own"] for r in rows)
    return (sum(r["prizes"] for r in rows) / o) if o else 0.0


def boot(a, b, n=10000, seed=12345):
    rnd = random.Random(seed)
    d = []
    for _ in range(n):
        ra = [a[rnd.randrange(len(a))] for _ in range(len(a))]
        rb = [b[rnd.randrange(len(b))] for _ in range(len(b))]
        d.append(vel(rb) - vel(ra))
    d.sort()
    return d[int(n * 0.025)], d[int(n * 0.975)]


def summarise(lab, rows):
    o = sum(r["own"] for r in rows)
    p = sum(r["prizes"] for r in rows)
    at = sum(r["atk"] for r in rows)
    lg = sum(r["legal"] for r in rows)
    f = sorted(r["fpt"] for r in rows if r["fpt"])
    print(f"\n{lab}: sides={len(rows)}")
    print(f"  own turns total={o}  mean/side={o/len(rows):.2f}")
    print(f"  prizes total={p}     mean/side={p/len(rows):.2f}")
    print(f"  PRIZE VELOCITY = {p}/{o} = {p/o:.4f}")
    print(f"  attack-share/turn      = {at}/{o} = {at/o*100:.1f}%")
    print(f"  attack-when-legal/turn = {at}/{lg} = {(at/lg*100 if lg else 0):.1f}%")
    print(f"  turn of first prize    = mean {sum(f)/len(f) if f else 0:.1f} (n={len(f)})")
    return {"own_mean": o / len(rows), "vel": p / o,
            "atk_when_legal": (at / lg if lg else 0), "atk_share": at / o,
            "prizes_mean": p / len(rows),
            "fpt": (sum(f) / len(f) if f else 0)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--out", default="scratchpad/s3/r2_arm.json")
    args = ap.parse_args()

    A = sides(REPO / args.base)
    B = sides(REPO / args.arm)
    sa = summarise("B0' (baseline)", A)
    sb = summarise("B1b' (R2 only)", B)
    d = sb["vel"] - sa["vel"]
    lo, hi = boot(A, B)
    print(f"\n{'='*60}\nPRIMARY: prize velocity")
    print(f"  B0'  = {sa['vel']:.4f}")
    print(f"  B1b' = {sb['vel']:.4f}")
    print(f"  delta = {d:+.4f}   bootstrap 95% CI [{lo:+.4f}, {hi:+.4f}]")
    print(f"\nGUARDS")
    g1 = sb["own_mean"] <= sa["own_mean"]
    print(f"  own turns not higher : B1b' {sb['own_mean']:.2f} vs B0' "
          f"{sa['own_mean']:.2f}  -> {'OK' if g1 else 'BROKEN'}")
    (REPO / args.out).write_text(json.dumps({"B0p": sa, "B1bp": sb,
                                             "delta": d, "ci": [lo, hi]},
                                            indent=1), encoding="utf-8")
    band = ("PASS" if d >= 0.030 else ("MARGINAL" if d >= 0.015 else "FAIL"))
    print(f"\n  delta band (before guards): {band}")
