"""PHASE 2 mandatory measurement: split the can_KO cell by whether the KO is
GAME-WINNING (takes our last prize) or NON-FINAL.

If an attack takes the last prize, ending the turn costs nothing -- swing at
once. If the KO is non-final, ending the turn forfeits the rest of it. The
hypothesis is that top-10's 22% ATTACK share inside can_KO is largely the
game-winning subset.
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}
ATT = {int(k): v for k, v in CD["attacks"].items()}
GRIMM = "Marnie's Grimmsnarl ex / Munkidori"
NAME = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
        11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END"}
ACTIONS = ["PLAY", "ATTACH", "EVOLVE", "ABILITY", "RETREAT", "ATTACK", "END"]


def prizes_for_ko(cid):
    c = CARDS.get(cid) or {}
    if c.get("megaEx"):
        return 3
    if c.get("ex"):
        return 2
    return 1


def rows(dirs, teams_by_dir=None, our=False):
    out = []
    for d in dirs:
        wt = (teams_by_dir or {}).get(str(d))
        for fp in sorted(Path(d).glob("*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if len(steps) < 2:
                continue
            tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]
            for seat in (0, 1):
                if wt is not None and (seat >= len(tn) or tn[seat] not in wt):
                    continue
                act = steps[1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 60):
                    continue
                a = archetype(act)
                if not a or a["label"] != GRIMM:
                    continue
                for i in range(len(steps) - 1):
                    e = steps[i][seat]
                    if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                        continue
                    obs = e.get("observation") or {}
                    sel = obs.get("select") or {}
                    if sel.get("type") != 0:
                        continue
                    opts = sel.get("option") or []
                    if len(opts) < 2:
                        continue
                    a2 = steps[i + 1][seat].get("action")
                    if not (isinstance(a2, list) and len(a2) == 1):
                        continue
                    ci = a2[0]
                    if not isinstance(ci, int) or ci >= len(opts):
                        continue
                    cur = obs.get("current") or {}
                    me = cur.get("yourIndex") or 0
                    pl = cur.get("players") or []
                    if len(pl) < 2 or me >= len(pl):
                        continue
                    mine, opp = pl[me], pl[1 - me]
                    oa = (opp.get("active") or [None])[0]
                    if not oa or oa.get("hp") is None:
                        continue
                    best = 0.0
                    for o in opts:
                        if (o or {}).get("type") == 13:
                            best = max(best, float(
                                (ATT.get((o or {}).get("attackId")) or {}).get("damage") or 0))
                    if not (best >= (oa.get("hp") or 0) > 0):
                        continue          # not a can_KO decision
                    gain = prizes_for_ko(oa.get("id"))
                    myp = len(mine.get("prize") or [])
                    out.append((gain >= myp > 0, NAME.get((opts[ci] or {}).get("type"), "?")))
    return out


def show(label, rs):
    win = Counter(a for g, a in rs if g)
    non = Counter(a for g, a in rs if not g)
    print(f"\n=== {label} ===")
    for nm, c in (("GAME-WINNING KO (takes last prize)", win),
                  ("NON-FINAL KO", non)):
        t = sum(c.values())
        if not t:
            print(f"  {nm}: n=0")
            continue
        print(f"  {nm}: n={t}")
        print("     " + "  ".join(f"{a}={c[a]/t*100:.1f}%" for a in ACTIONS if c[a]))
    return win, non


if __name__ == "__main__":
    A = REPO / "analysis/phase2_meta_shift"
    dirs = [A / "replays_top10_jul21", A / "replays_top10_jul22",
            A / "replays_top10_jul26"]
    teams = {}
    for d, p in zip(dirs, ["profile_top10_jul21.json", "profile_top10_jul22.json",
                           "profile_top10_jul26.json"]):
        teams[str(d)] = set(json.loads((A / p).read_text(encoding="utf-8"))["teams"])
    tw, tn_ = show("TOP-10 Grimmsnarl", rows(dirs, teams))
    ow, on_ = show("OURS Grimmsnarl (D1)", rows([REPO / "scratchpad/s3/horizon_D1"]))
    tot_t = sum(tw.values()) + sum(tn_.values())
    print(f"\nshare of can_KO decisions that are GAME-WINNING:")
    print(f"  top-10 : {sum(tw.values())}/{tot_t} = {sum(tw.values())/max(1,tot_t)*100:.1f}%")
    tot_o = sum(ow.values()) + sum(on_.values())
    print(f"  ours   : {sum(ow.values())}/{tot_o} = {sum(ow.values())/max(1,tot_o)*100:.1f}%")
