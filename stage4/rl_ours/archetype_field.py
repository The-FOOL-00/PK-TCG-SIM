"""Per-archetype prize-velocity envelopes + field position, from the jul26 harvest.

Envelope: pooled `total prizes / total own turns` over that archetype's
top-10 sides -- exactly the construction used for Grimmsnarl's 0.5725.

Field position: win rate vs the pooled field, and head-to-head vs Grimmsnarl,
counted over ALL sides whose deck is recoverable (not only top-10 pilots), so
the head-to-head cells have usable n.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

DIR = REPO / "analysis/phase2_meta_shift/replays_top10_jul26"
TOP10 = set(json.loads(
    (REPO / "analysis/phase2_meta_shift/profile_top10_jul26.json")
    .read_text(encoding="utf-8"))["teams"])
GRIMM = "Marnie's Grimmsnarl ex / Munkidori"


def scan():
    env = defaultdict(lambda: {"own": 0, "prizes": 0, "sides": 0})
    wl = defaultdict(lambda: Counter())          # arch -> W/L vs pooled field
    h2h = defaultdict(lambda: Counter())         # (arch, opp_arch) -> W/L
    seats = Counter()
    for fp in sorted(DIR.glob("*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = js.get("steps") or []
        if len(steps) < 2:
            continue
        tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]
        rewards = js.get("rewards") or [None, None]
        arch = [None, None]
        for a in (0, 1):
            act = steps[1][a].get("action")
            if isinstance(act, list) and len(act) == 60:
                r = archetype(act)
                arch[a] = r["label"] if r else None

        vis = (steps[0][0].get("visualize")
               or (steps[0][0].get("observation") or {}).get("visualize")) or []
        turn_owner = {}
        last = 0
        for e in vis:
            c = e.get("current") or {}
            t = c.get("turn") or last
            last = max(last, t)
            for l in e.get("logs") or []:
                if l.get("type") == "TurnStart" and l.get("playerIndex") is not None:
                    turn_owner[t] = l["playerIndex"]

        for a in (0, 1):
            A, O = arch[a], arch[1 - a]
            if not A:
                continue
            won = rewards[a] == 1
            lost = rewards[a] == -1
            if won or lost:
                wl[A]["W" if won else "L"] += 1
                if O:
                    h2h[(A, O)]["W" if won else "L"] += 1
            if tn[a] in TOP10:
                seats[A] += 1
                own = [t for t, o in turn_owner.items() if o == a]
                if not own:
                    continue
                p0 = pl = None
                for i in range(len(steps) - 1):
                    e = steps[i][a]
                    if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                        continue
                    cur = (e.get("observation") or {}).get("current") or {}
                    me = cur.get("yourIndex")
                    ps = cur.get("players") or []
                    if me is not None and me < len(ps):
                        n = len(ps[me].get("prize") or [])
                        if n > 0:
                            p0 = n if p0 is None else max(p0, n)
                            pl = n
                env[A]["own"] += len(own)
                env[A]["sides"] += 1
                if p0 is not None and pl is not None:
                    env[A]["prizes"] += p0 - pl
    return env, wl, h2h, seats


if __name__ == "__main__":
    env, wl, h2h, seats = scan()
    tot_seats = sum(seats.values())
    print("=== PER-ARCHETYPE ENVELOPE (top-10 sides only) ===")
    print(f"{'archetype':<48s}{'sides':>6s}{'own':>7s}{'prizes':>7s}{'ENVELOPE':>10s}")
    out = {}
    for lab, v in sorted(env.items(), key=lambda kv: -kv[1]["sides"]):
        e = v["prizes"] / v["own"] if v["own"] else 0
        out[lab] = {"envelope": e, "sides": v["sides"], "own": v["own"],
                    "prizes": v["prizes"], "seat_share": seats[lab] / tot_seats}
        print(f"{lab[:48]:<48s}{v['sides']:>6d}{v['own']:>7d}{v['prizes']:>7d}{e:>10.4f}")

    print("\n=== FIELD POSITION (all recoverable sides) ===")
    print(f"{'archetype':<48s}{'seat share':>11s}{'W':>5s}{'L':>5s}{'n':>5s}{'WR vs field':>12s}")
    for lab in out:
        c = wl[lab]
        n = c["W"] + c["L"]
        wr = c["W"] / n * 100 if n else 0
        out[lab].update({"W": c["W"], "L": c["L"], "n": n, "wr": wr})
        flag = "" if n >= 60 else "   <-- n<60 NOT QUOTABLE"
        print(f"{lab[:48]:<48s}{out[lab]['seat_share']*100:>10.1f}%"
              f"{c['W']:>5d}{c['L']:>5d}{n:>5d}{wr:>11.1f}%{flag}")

    print("\n=== HEAD-TO-HEAD vs Grimmsnarl (both directions) ===")
    for lab in out:
        if lab == GRIMM:
            continue
        f = h2h[(lab, GRIMM)]
        r = h2h[(GRIMM, lab)]
        nf, nr = f["W"] + f["L"], r["W"] + r["L"]
        comb = nf + nr
        out[lab].update({"vs_grimm_W": f["W"], "vs_grimm_L": f["L"], "vs_grimm_n": nf,
                         "grimm_vs_W": r["W"], "grimm_vs_L": r["L"], "grimm_vs_n": nr})
        flag = "" if comb >= 60 else "   <-- combined n<60 NOT QUOTABLE"
        print(f"  {lab[:44]:<44s} as-us {f['W']}W-{f['L']}L (n={nf})"
              f"   Grimm-side {r['W']}W-{r['L']}L (n={nr})   combined n={comb}{flag}")
    (REPO / "scratchpad/s3/archetype_field.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print("\n-> scratchpad/s3/archetype_field.json")
