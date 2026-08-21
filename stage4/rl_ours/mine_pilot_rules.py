"""STEP 1 -- mine decision rules from top-10 Cynthia's Garchomp sides.

Restricts to sides whose deck is the Cynthia's Garchomp line, so the rules are
archetype-matched to the deck we pilot. Emits counters only; every reported
rule carries n so the n>=20 floor can be applied.

Also runs the identical extraction over OUR sides (H1 self-play, VN ladder) so
each rule is a like-for-like comparison.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}

GIBLE, GABITE, GARCHOMP = 379, 380, 381
ROSELIA, ROSERADE, SPIRITOMB = 341, 342, 387
POWER_WEIGHT = 1173
CORKSCREW_DIVE, DRACONIC_BUSTER, RAGING_CURSE = 531, 532, 540
CYNTHIA_LINE = {GIBLE, GABITE, GARCHOMP, ROSELIA, ROSERADE, SPIRITOMB}

OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY = 7, 8, 9, 10
OT_RETREAT, OT_ATTACK, OT_END = 12, 13, 14
OT_NAME = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
           12: "RETREAT", 13: "ATTACK", 14: "END"}
AREA_ACTIVE, AREA_BENCH = 4, 5


def nm(cid):
    return (CARDS.get(cid, {}).get("name") or "?")


def side_is_garchomp(steps, seat):
    """True if this seat's board/hand ever shows the Cynthia's Garchomp line."""
    seen = set()
    for i in range(min(len(steps), 40)):
        e = steps[i][seat]
        if not isinstance(e, dict):
            continue
        cur = (e.get("observation") or {}).get("current") or {}
        pl = (cur.get("players") or [{}, {}])
        me = cur.get("yourIndex")
        if me is None or me >= len(pl):
            continue
        p = pl[me]
        for c in (p.get("hand") or []):
            if c:
                seen.add(c.get("id"))
        for pk in (p.get("active") or []) + (p.get("bench") or []):
            if pk:
                seen.add(pk.get("id"))
    return len(seen & CYNTHIA_LINE) >= 2


def mine(d, label, limit_seat=None, only_garchomp=True, teams=None):
    R = Counter()
    first_evo, first_atk = [], []
    t13_bench = []
    R_by_turn = defaultdict(Counter)
    for fp in sorted(Path(d).glob("*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = js.get("steps") or []
        if not steps:
            continue
        tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]
        seats = (limit_seat,) if limit_seat is not None else (0, 1)
        for seat in seats:
            if seat >= len(steps[0]):
                continue
            if teams is not None:
                if seat >= len(tn) or tn[seat] not in teams:
                    continue
            if only_garchomp and not side_is_garchomp(steps, seat):
                continue
            R["sides"] += 1
            evo_turn = atk_turn = None
            bench_t3 = None
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
                act = steps[i + 1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 1):
                    continue
                ci = act[0]
                if not isinstance(ci, int) or ci >= len(opts):
                    continue
                cur = obs.get("current") or {}
                me = cur.get("yourIndex") or 0
                mine_p = (cur.get("players") or [{}, {}])[me]
                turn = cur.get("turn") or 0
                types = [(o or {}).get("type") for o in opts]
                ch = opts[ci] or {}
                ct = ch.get("type")
                R["decisions"] += 1
                R_by_turn[min(turn, 12)][OT_NAME.get(ct, ct)] += 1

                # --- ability availability / uptake (Champion's Call) ---
                if OT_ABILITY in types:
                    R["ability_avail"] += 1
                    if ct == OT_ABILITY:
                        R["ability_taken"] += 1
                # --- evolve availability / uptake ---
                if OT_EVOLVE in types:
                    R["evolve_avail"] += 1
                    if ct == OT_EVOLVE:
                        R["evolve_taken"] += 1
                        if evo_turn is None:
                            evo_turn = turn
                # --- attack availability / uptake, and which attack ---
                atk_ids = {(o or {}).get("attackId") for o in opts
                           if (o or {}).get("type") == OT_ATTACK}
                if atk_ids:
                    R["attack_avail"] += 1
                    if ct == OT_ATTACK:
                        R["attack_taken"] += 1
                        if atk_turn is None:
                            atk_turn = turn
                if CORKSCREW_DIVE in atk_ids and DRACONIC_BUSTER in atk_ids:
                    R["both_atks"] += 1
                    if ct == OT_ATTACK:
                        if ch.get("attackId") == DRACONIC_BUSTER:
                            R["chose_buster"] += 1
                        elif ch.get("attackId") == CORKSCREW_DIVE:
                            R["chose_dive"] += 1
                for aid, key in ((CORKSCREW_DIVE, "dive"),
                                 (DRACONIC_BUSTER, "buster"),
                                 (RAGING_CURSE, "curse")):
                    if aid in atk_ids:
                        R[f"{key}_avail"] += 1
                        if ct == OT_ATTACK and ch.get("attackId") == aid:
                            R[f"{key}_taken"] += 1
                # --- energy attach target ---
                if ct == OT_ATTACH:
                    R["attach"] += 1
                    R["attach_active" if ch.get("inPlayArea") == AREA_ACTIVE
                      else "attach_bench"] += 1
                # --- retreat ---
                if OT_RETREAT in types:
                    R["retreat_avail"] += 1
                    if ct == OT_RETREAT:
                        R["retreat_taken"] += 1
                # --- Power Weight play ---
                pw_avail = False
                hand = mine_p.get("hand") or []
                for j, o in enumerate(opts):
                    if types[j] in (OT_PLAY, OT_ATTACH):
                        ix = (o or {}).get("index")
                        if isinstance(ix, int) and ix < len(hand) and hand[ix]:
                            if (hand[ix] or {}).get("id") == POWER_WEIGHT:
                                pw_avail = True
                if pw_avail:
                    R["pw_avail"] += 1
                    ix = ch.get("index")
                    if isinstance(ix, int) and ix < len(hand) and hand[ix] \
                            and (hand[ix] or {}).get("id") == POWER_WEIGHT:
                        R["pw_played"] += 1
                # --- END with development on the menu ---
                if ct == OT_END:
                    R["end"] += 1
                    if any(t in (OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY)
                           for t in types):
                        R["end_with_dev"] += 1
                # --- turn<=3 bench size ---
                if turn == 3 and bench_t3 is None:
                    bench_t3 = len([b for b in (mine_p.get("bench") or []) if b])
            if evo_turn:
                first_evo.append(evo_turn)
            if atk_turn:
                first_atk.append(atk_turn)
            if bench_t3 is not None:
                t13_bench.append(bench_t3)

    def med(v):
        return sorted(v)[len(v) // 2] if v else 0

    def rate(a, b):
        return f"{R[a]}/{R[b]} = {R[a]/R[b]*100:5.1f}%" if R[b] else "n=0"

    print(f"\n{'='*70}\n{label}\n{'='*70}")
    print(f"sides={R['sides']}  MAIN decisions={R['decisions']}")
    print(f"  ABILITY   taken when available : {rate('ability_taken','ability_avail')}")
    print(f"  EVOLVE    taken when available : {rate('evolve_taken','evolve_avail')}")
    print(f"  ATTACK    taken when available : {rate('attack_taken','attack_avail')}")
    print(f"  RETREAT   taken when available : {rate('retreat_taken','retreat_avail')}")
    print(f"  PowerWeight played when in hand: {rate('pw_played','pw_avail')}")
    print(f"  END with development available : {rate('end_with_dev','end')}")
    print(f"  Corkscrew Dive  taken/avail    : {rate('dive_taken','dive_avail')}")
    print(f"  Draconic Buster taken/avail    : {rate('buster_taken','buster_avail')}")
    print(f"  Raging Curse    taken/avail    : {rate('curse_taken','curse_avail')}")
    if R["both_atks"]:
        print(f"  BOTH attacks legal (n={R['both_atks']}): "
              f"Buster {R['chose_buster']} / Dive {R['chose_dive']} / "
              f"neither {R['both_atks']-R['chose_buster']-R['chose_dive']}")
    print(f"  ATTACH target  active/bench    : {R['attach_active']}/{R['attach_bench']}")
    print(f"  first evolution turn (median)  : {med(first_evo)}  (n={len(first_evo)})")
    print(f"  first attack turn    (median)  : {med(first_atk)}  (n={len(first_atk)})")
    print(f"  bench size at T3     (median)  : {med(t13_bench)}  (n={len(t13_bench)})")
    print("  action mix by turn (PLAY/ATTACH/EVOLVE/ABILITY/ATTACK/END):")
    for t in sorted(R_by_turn):
        c = R_by_turn[t]
        tot = sum(c.values()) or 1
        print(f"    T{t:<3d} n={tot:<5d} "
              + " ".join(f"{k}={c[k]/tot*100:4.1f}%" for k in
                         ("PLAY", "ATTACH", "EVOLVE", "ABILITY", "ATTACK", "END")))
    return R


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True, help="LABEL=dir[:seat]")
    ap.add_argument("--all-sides", action="store_true",
                    help="do not filter to Cynthia's Garchomp sides")
    ap.add_argument("--teams", nargs="*", default=None,
                    help="restrict to these info.TeamNames entries")
    args = ap.parse_args()
    teams = set(args.teams) if args.teams else None
    for spec in args.dirs:
        lab, d = spec.split("=", 1)
        seat = None
        if ":" in d:
            d, s = d.rsplit(":", 1)
            seat = int(s)
        mine(REPO / d, lab, seat, not args.all_sides, teams)
