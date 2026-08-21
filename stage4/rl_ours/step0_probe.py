"""STEP 0 measurement, corrected.

The hypothesis named Draconic Buster (532) as scaling off damage counters on
our own benched Cynthia's Pokemon. card_data.json refutes that: 532 is flat 260
with "Discard all Energy from this Pokemon". The scaling belongs to Raging
Curse (540) on Cynthia's Spiritomb (387), which IS in our deck (2 copies).

So this measures the real question:
  - how often was Raging Curse legal while our bench carried damage counters,
    and we declined it -- and what would it have dealt?
  - how our v1 ladder prices 540 / 531 / 532 at those same decisions
Read-only.
"""
import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
_b = io.StringIO()
with contextlib.redirect_stdout(_b), contextlib.redirect_stderr(_b):
    import deck_compare
A = deck_compare.agent_mod

CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}
RAGING_CURSE, CORKSCREW_DIVE, DRACONIC_BUSTER = 540, 531, 532
SPIRITOMB, GARCHOMP_EX = 387, 381


def is_cynthia(cid):
    return (CARDS.get(cid, {}).get("name") or "").startswith("Cynthia'")


def maxhp(cid):
    return CARDS.get(cid, {}).get("hp") or 0


def bench_counters(player):
    """Damage counters on our benched Cynthia's Pokemon (10 dmg each)."""
    n = 0
    for pk in player.get("bench") or []:
        if not pk:
            continue
        cid = pk.get("id")
        if not is_cynthia(cid):
            continue
        mx, cur = maxhp(cid), pk.get("hp")
        if cur is None or mx <= 0:
            continue
        n += max(0, int(round((mx - cur) / 10.0)))
    return n


def seat_map(sub):
    m = {}
    for f in (REPO / "scratchpad" / "s3").glob("eps_*.json"):
        for ep in json.loads(f.read_text(encoding="utf-8")).get("episodes", []):
            for a in ep.get("agents", []):
                if a.get("submissionId") == sub:
                    m[ep["id"]] = a.get("index", 0)
    return m


def scan(label, d, sub=None, pilot=""):
    A.ROLLOUT = "v1"; A.PILOT = pilot; A.DYN_DECK_TABLES = True
    A.EVAL_FIX = A.PROMOTE_RULE = A.LETHAL_PROBE = False
    A.LEARNED_VALUE = A.V3_EVAL = A.BC = False
    deck = deck_compare.read_deck(REPO / "metaC_garchomp_nasuo.csv")
    A.DECK = list(deck)
    A.TOTAL_BASIC_ENERGY = sum(
        1 for c in deck if A.CARDS.get(c, {}).get("cardType") == 5)

    smap = seat_map(sub) if sub else None
    R = Counter()
    foregone = []
    score_samples = {"540": [], "531": [], "532": []}
    for fp in sorted(Path(d).glob("*.json")):
        js = json.loads(fp.read_text(encoding="utf-8"))
        steps = js.get("steps") or []
        if smap is not None:
            eid = int(fp.stem)
            if eid not in smap:
                continue
            which = (smap[eid],)
        else:
            which = (0, 1)
        for i in range(len(steps) - 1):
            for seat in which:
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
                act = steps[i + 1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 1):
                    continue
                ci = act[0]
                if not isinstance(ci, int) or ci >= len(opts):
                    continue
                cur = obs.get("current") or {}
                me = cur.get("yourIndex") or 0
                mine = (cur.get("players") or [{}, {}])[me]
                try:
                    sc = [A._score_option(o or {}, sel, cur, me) for o in opts]
                except Exception:
                    continue
                R["main"] += 1
                by_atk = {}
                for k, o in enumerate(opts):
                    if (o or {}).get("type") == 13:
                        by_atk[(o or {}).get("attackId")] = k
                chosen_atk = (opts[ci] or {}).get("attackId") if \
                    (opts[ci] or {}).get("type") == 13 else None
                for aid, key in ((RAGING_CURSE, "540"), (CORKSCREW_DIVE, "531"),
                                 (DRACONIC_BUSTER, "532")):
                    if aid in by_atk:
                        R[f"legal_{key}"] += 1
                        score_samples[key].append(sc[by_atk[aid]])
                        if chosen_atk == aid:
                            R[f"took_{key}"] += 1
                ctr = bench_counters(mine)
                if ctr > 0:
                    R["dmgbench_decisions"] += 1
                if RAGING_CURSE in by_atk and ctr > 0:
                    R["rc_legal_with_counters"] += 1
                    if chosen_atk != RAGING_CURSE:
                        R["rc_declined_with_counters"] += 1
                        foregone.append(ctr * 10)
    print(f"\n=== {label}  (PILOT={pilot!r}) ===")
    print(f"MAIN decisions                         : {R['main']}")
    print(f"decisions with damage on our own bench : {R['dmgbench_decisions']}")
    for aid, key, nm in ((540, "540", "Raging Curse"),
                         (531, "531", "Corkscrew Dive"),
                         (532, "532", "Draconic Buster")):
        lg, tk = R[f"legal_{key}"], R[f"took_{key}"]
        s = sorted(score_samples[key])
        med = s[len(s) // 2] if s else 0
        print(f"  {nm:<16s} legal={lg:5d} taken={tk:5d} "
              f"({(tk/lg*100 if lg else 0):5.1f}%)  v1 score median={med:.0f}")
    print(f"Raging Curse legal WITH bench counters  : {R['rc_legal_with_counters']}")
    print(f"  ... and declined                     : {R['rc_declined_with_counters']}")
    if foregone:
        f = sorted(foregone)
        print(f"  ... damage foregone: median={f[len(f)//2]} "
              f"max={f[-1]} total={sum(f)}")
    return R


if __name__ == "__main__":
    scan("H1 self-play (60 games)", REPO / "scratchpad/s3/horizon_H1", pilot="garchomp")
    scan("VN ladder (25 eps, our seat, SHIP config)",
         REPO / "scratchpad/s3/vn_replays", 55003807, pilot="")
