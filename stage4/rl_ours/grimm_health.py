"""PART A health check for the live v1-alone Grimmsnarl submission."""
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

SUB = 55033010
GRIMM = "Marnie's Grimmsnarl ex / Munkidori"
eps = {e["id"]: e for e in json.loads(
    (REPO / "scratchpad/s3/eps_55033010.json").read_text(encoding="utf-8"))["episodes"]}
ref = sorted(int(x) for x in open(REPO / "metaG_grimmsnarl_top10.csv") if x.strip())

deck_ok = deck_bad = selfmatch = 0
energy = []
opp = collections.Counter()
wl_mirror = collections.Counter()
wl_non = collections.Counter()
reasons_loss = collections.Counter()
reasons_win = collections.Counter()
own_all, prizes_all = [], []

for fp in sorted((REPO / "scratchpad/s3/grimm_replays").glob("*.json")):
    eid = int(fp.stem)
    e = eps.get(eid)
    if not e:
        continue
    js = json.loads(fp.read_text(encoding="utf-8"))
    st = js.get("steps") or []
    if len(st) < 2:
        continue
    mine = [a.get("index", 0) for a in e["agents"] if a.get("submissionId") == SUB]
    if len(mine) > 1:
        selfmatch += 1
    for seat in mine:
        act = st[1][seat].get("action")
        if isinstance(act, list) and len(act) == 60:
            if sorted(act) == ref:
                deck_ok += 1
            else:
                deck_bad += 1
            energy.append(sum(1 for c in act if c == 7))
        o = st[1][1 - seat].get("action")
        oa = "unknown"
        if isinstance(o, list) and len(o) == 60:
            r = archetype(o)
            oa = r["label"] if r else "unknown"
        opp[oa] += 1
        rec = [a for a in e["agents"]
               if a.get("submissionId") == SUB and a.get("index", 0) == seat]
        won = bool(rec) and rec[0].get("reward") == 1
        (wl_mirror if oa == GRIMM else wl_non)["W" if won else "L"] += 1

        vis = (st[0][0].get("visualize")
               or (st[0][0].get("observation") or {}).get("visualize")) or []
        to = {}
        last = 0
        res = None
        for en in vis:
            c = en.get("current") or {}
            t = c.get("turn") or last
            last = max(last, t)
            for l in en.get("logs") or []:
                if l.get("type") == "TurnStart" and l.get("playerIndex") is not None:
                    to[t] = l["playerIndex"]
                if l.get("type") == "Result":
                    res = l.get("reason", l.get("result"))
        (reasons_win if won else reasons_loss)[str(res)] += 1
        own = [t for t, x in to.items() if x == seat]
        own_all.append(len(own))
        p0 = pl = None
        for i in range(len(st) - 1):
            en = st[i][seat]
            if not isinstance(en, dict) or en.get("status") != "ACTIVE":
                continue
            cur = (en.get("observation") or {}).get("current") or {}
            me = cur.get("yourIndex")
            ps = cur.get("players") or []
            if me is not None and me < len(ps):
                n = len(ps[me].get("prize") or [])
                if n > 0:
                    p0 = n if p0 is None else max(p0, n)
                    pl = n
        prizes_all.append((p0 - pl) if (p0 is not None and pl is not None) else 0)

tot = sum(opp.values())
print("2. DECK ON PLATFORM")
print(f"   sides where our deck == harvested Grimmsnarl list : {deck_ok}   mismatched: {deck_bad}")
print(f"   Basic (D) Energy per side                          : {sorted(set(energy))}  (expect 10)")
print(f"   self-matches (our sub on both seats)               : {selfmatch}")
print()
print(f"4. OPPONENT ARCHETYPES  (n={tot} sides)")
for k, v in opp.most_common():
    print(f"   {k[:50]:<50s} {v:3d}  {v/tot*100:5.1f}%")
m, n = wl_mirror, wl_non
nm = m["W"] + m["L"]
print()
print(f"   MIRROR rate    : {nm}/{tot} = {nm/tot*100:.1f}%")
print(f"   vs MIRROR      : {m['W']}W-{m['L']}L")
print(f"   vs NON-MIRROR  : {n['W']}W-{n['L']}L")
print()
print("5. END REASONS   (1=prizes 2=deckout 3=no-active 4=effect)")
print(f"   wins  : {dict(reasons_win)}")
print(f"   losses: {dict(reasons_loss)}")
own_all_s = sorted(own_all)
print(f"   own turns/game : mean={sum(own_all)/len(own_all):.2f} "
      f"median={own_all_s[len(own_all_s)//2]}   (self-play 7.63)")
print(f"   prizes/game    : mean={sum(prizes_all)/len(prizes_all):.2f}   (self-play 3.49)")
print()
print(f"6. PRIZE VELOCITY on ladder = {sum(prizes_all)}/{sum(own_all)} = "
      f"{sum(prizes_all)/sum(own_all):.4f}")
print(f"   self-play 0.4574 | Grimmsnarl top-10 envelope 0.5725")
