"""Prize velocity etc. for OUR side only, from crossdeck_test.py output.
Respects per-game _our_seat (alternated to cancel first-player bias)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OT_ATTACK = 13


def side_stats(d):
    out = []
    for fp in sorted(Path(d).glob("g*.json")):
        js = json.loads(fp.read_text(encoding="utf-8"))
        steps = js.get("steps") or []
        seat = js.get("_our_seat", 0)
        if len(steps) < 2:
            continue
        vis = (steps[0][0].get("visualize")
               or (steps[0][0].get("observation") or {}).get("visualize")) or []
        turn_owner, atk_log = {}, defaultdict(int)
        last = 0
        for e in vis:
            c = e.get("current") or {}
            t = c.get("turn") or last
            last = max(last, t)
            for l in e.get("logs") or []:
                if l.get("type") == "TurnStart" and l.get("playerIndex") is not None:
                    turn_owner[t] = l["playerIndex"]
                elif l.get("type") == "Attack" and l.get("playerIndex") is not None:
                    atk_log[(l["playerIndex"], t)] += 1
        own = sorted(t for t, o in turn_owner.items() if o == seat)
        legal = set()
        p0 = plast = None
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
            sel = obs.get("select") or {}
            if sel.get("type") == 0 and any(
                    (o or {}).get("type") == OT_ATTACK for o in (sel.get("option") or [])):
                legal.add(cur.get("turn") or 0)
        n_atk = sum(1 for t in own if atk_log[(seat, t)])
        prizes = (p0 - plast) if (p0 is not None and plast is not None) else 0
        out.append({"own": len(own), "atk": n_atk, "legal": len(legal & set(own)),
                    "prizes": prizes})
    return out


if __name__ == "__main__":
    for d in sys.argv[1:]:
        rows = side_stats(Path(d))
        o = sum(r["own"] for r in rows)
        p = sum(r["prizes"] for r in rows)
        at = sum(r["atk"] for r in rows)
        lg = sum(r["legal"] for r in rows)
        print(f"{d:<55s} n={len(rows):3d}  velocity={p/max(1,o):.4f}  "
              f"ownT={o/max(1,len(rows)):.2f}  atkWL={at/max(1,lg)*100:5.1f}%  "
              f"prizes/g={p/max(1,len(rows)):.2f}")
