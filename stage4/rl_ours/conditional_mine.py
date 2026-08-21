"""PHASE 1 — mine CONDITIONAL rules: "in state X, top-10 do Y at rate Z".

Prior mining reported unconditional rates. This records the full state context
of every MAIN decision and partitions on it, so the output is a set of
state -> action-distribution cells that can be compared pilot-to-pilot.

Comparison is deck-matched: top-10 GRIMMSNARL sides vs OUR Grimmsnarl sides
(the D1 self-play arm). Same 60 cards, different pilot.

Everything is computed from the seat's own observation, so every feature is
available to the agent at decision time.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}
ATT = {int(k): v for k, v in CD["attacks"].items()}
GRIMM = "Marnie's Grimmsnarl ex / Munkidori"

OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY = 7, 8, 9, 10
OT_RETREAT, OT_ATTACK, OT_END = 12, 13, 14
NAME = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
        11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END"}
ACTIONS = ["PLAY", "ATTACH", "EVOLVE", "ABILITY", "RETREAT", "ATTACK", "END"]


def card(cid):
    return CARDS.get(cid) or {}


def best_printed(cid):
    """Max printed damage across a Pokemon's attacks (observable threat proxy)."""
    b = 0
    for aid in card(cid).get("attacks") or []:
        b = max(b, float((ATT.get(aid) or {}).get("damage") or 0))
    return b


def cheapest_cost(cid):
    c = None
    for aid in card(cid).get("attacks") or []:
        n = len((ATT.get(aid) or {}).get("energies") or [])
        c = n if c is None else min(c, n)
    return c if c is not None else 99


def active_of(p):
    a = p.get("active") or []
    return a[0] if a and a[0] else None


def features(obs, opts):
    """State context for one MAIN decision, from the seat's own observation."""
    cur = obs.get("current") or {}
    me = cur.get("yourIndex") or 0
    pl = cur.get("players") or []
    if len(pl) < 2 or me >= len(pl):
        return None
    mine, opp = pl[me], pl[1 - me]
    my_act, op_act = active_of(mine), active_of(opp)
    turn = cur.get("turn") or 0

    my_pr = len(mine.get("prize") or [])
    op_pr = len(opp.get("prize") or [])

    # our best legal attack damage this decision (printed, from the menu)
    best_atk = 0.0
    for o in opts:
        if (o or {}).get("type") == OT_ATTACK:
            best_atk = max(best_atk, float(
                (ATT.get((o or {}).get("attackId")) or {}).get("damage") or 0))
    can_ko = bool(op_act and op_act.get("hp") is not None
                  and best_atk >= (op_act.get("hp") or 0) > 0)

    # can the opponent's active KO ours next turn (printed-damage proxy)?
    threat = best_printed(op_act.get("id")) if op_act else 0
    ko_able = bool(my_act and my_act.get("hp") is not None
                   and threat >= (my_act.get("hp") or 0) > 0)

    my_bench = len([b for b in (mine.get("bench") or []) if b])
    op_bench = len([b for b in (opp.get("bench") or []) if b])
    e_on = len((my_act or {}).get("energies") or []) if my_act else 0
    need = cheapest_cost((my_act or {}).get("id")) if my_act else 99
    powered = e_on >= need

    return {
        "turn": turn,
        "turn_b": ("T1" if turn <= 1 else "T2" if turn == 2 else "T3" if turn == 3
                   else "T4-6" if turn <= 6 else "T7+"),
        "my_pr": my_pr, "op_pr": op_pr,
        "race": ("AHEAD" if my_pr < op_pr else "BEHIND" if my_pr > op_pr else "EVEN"),
        "opp_close": op_pr <= 2,
        "we_close": my_pr <= 2,
        "can_ko": can_ko,
        "ko_able": ko_able,
        "my_bench": my_bench, "op_bench": op_bench,
        "bench_low": my_bench <= 1,
        "powered": powered,
        "hand": len(mine.get("hand") or []),
        "supporter_done": bool(cur.get("supporterPlayed")),
        "atk_legal": best_atk > 0,
    }


def side_rows(fp, want_team=None, want_arch=GRIMM, seat_filter=None):
    """Yield (features, chosen_action) for each MAIN decision of matching sides."""
    try:
        js = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return
    steps = js.get("steps") or []
    if len(steps) < 2:
        return
    tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]
    for seat in (0, 1):
        if seat_filter is not None and seat != seat_filter:
            continue
        if want_team is not None and (seat >= len(tn) or tn[seat] not in want_team):
            continue
        if want_arch is not None:
            act = steps[1][seat].get("action")
            if not (isinstance(act, list) and len(act) == 60):
                continue
            a = archetype(act)
            if not a or a["label"] != want_arch:
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
            act2 = steps[i + 1][seat].get("action")
            if not (isinstance(act2, list) and len(act2) == 1):
                continue
            ci = act2[0]
            if not isinstance(ci, int) or ci >= len(opts):
                continue
            f = features(obs, opts)
            if f is None:
                continue
            f["_menu"] = {NAME.get((o or {}).get("type")) for o in opts}
            yield f, NAME.get((opts[ci] or {}).get("type"), "?")


def collect(dirs, want_team_by_dir=None, seat_filter=None):
    rows = []
    for d in dirs:
        wt = (want_team_by_dir or {}).get(str(d))
        for fp in sorted(Path(d).glob("*.json")):
            for f, a in side_rows(fp, wt, GRIMM, seat_filter):
                rows.append((f, a))
    return rows


# ---- partition definitions: (name, predicate) --------------------------------
def cells(f):
    """Every partition cell this decision belongs to."""
    out = [
        ("turn=%s" % f["turn_b"], True),
        ("race=%s" % f["race"], True),
        ("can_KO", f["can_ko"]),
        ("no_KO_available", not f["can_ko"] and f["atk_legal"]),
        ("our_active_KOable", f["ko_able"]),
        ("safe_active", not f["ko_able"]),
        ("opp_le2_prizes", f["opp_close"]),
        ("we_le2_prizes", f["we_close"]),
        ("bench<=1", f["bench_low"]),
        ("bench>=3", f["my_bench"] >= 3),
        ("attacker_powered", f["powered"]),
        ("attacker_not_powered", not f["powered"]),
        ("supporter_done", f["supporter_done"]),
        ("supporter_pending", not f["supporter_done"]),
        ("hand>=6", f["hand"] >= 6),
        ("hand<=3", f["hand"] <= 3),
        # conjunctions -- the interesting ones
        ("can_KO & race=%s" % f["race"], f["can_ko"]),
        ("KOable & attacker_powered", f["ko_able"] and f["powered"]),
        ("KOable & not_powered", f["ko_able"] and not f["powered"]),
        ("turn=%s & bench<=1" % f["turn_b"], f["bench_low"]),
        ("turn=%s & powered" % f["turn_b"], f["powered"]),
        ("opp_le2 & can_KO", f["opp_close"] and f["can_ko"]),
        ("opp_le2 & no_KO", f["opp_close"] and not f["can_ko"]),
        ("atk_legal & supporter_done", f["atk_legal"] and f["supporter_done"]),
        ("atk_legal & supporter_pending", f["atk_legal"] and not f["supporter_done"]),
    ]
    return [n for n, ok in out if ok]


def dist(counter):
    t = sum(counter.values()) or 1
    return {a: counter[a] / t for a in ACTIONS}


def tvd(p, q):
    return 0.5 * sum(abs(p[a] - q[a]) for a in ACTIONS)


if __name__ == "__main__":
    A = REPO / "analysis/phase2_meta_shift"
    top_dirs = [A / "replays_top10_jul21", A / "replays_top10_jul22",
                A / "replays_top10_jul26"]
    teams = {}
    for d, prof in zip(top_dirs, ["profile_top10_jul21.json",
                                  "profile_top10_jul22.json",
                                  "profile_top10_jul26.json"]):
        teams[str(d)] = set(json.loads((A / prof).read_text(encoding="utf-8"))["teams"])

    them = collect(top_dirs, teams)
    us = collect([REPO / "scratchpad/s3/horizon_D1"], None)
    print("top-10 Grimmsnarl MAIN decisions : %d" % len(them))
    print("our     Grimmsnarl MAIN decisions : %d" % len(us))

    TC, UC = defaultdict(Counter), defaultdict(Counter)
    tg = ug = 0
    for f, a in them:
        tg += 1
        for c in cells(f):
            TC[c][a] += 1
    for f, a in us:
        ug += 1
        for c in cells(f):
            UC[c][a] += 1

    rows = []
    for c, tc in TC.items():
        nt, nu = sum(tc.values()), sum(UC[c].values())
        if nt < 30 or nu < 30:
            continue
        p, q = dist(tc), dist(UC[c])
        d = tvd(p, q)
        freq = nt / tg
        rows.append({"cell": c, "n_them": nt, "n_us": nu, "tvd": d,
                     "freq": freq, "leverage": freq * d,
                     "them": p, "us": q})
    rows.sort(key=lambda r: -r["leverage"])
    (REPO / "scratchpad/s3/conditional_cells.json").write_text(
        json.dumps({"n_them": tg, "n_us": ug, "rows": rows}, indent=1),
        encoding="utf-8")

    print("\ncells with n>=30 on BOTH sides: %d" % len(rows))
    print("\n%-34s %6s %6s %6s %7s %8s" % ("cell", "n_them", "n_us", "TVD", "freq", "leverage"))
    for r in rows[:25]:
        print("%-34s %6d %6d %6.3f %6.1f%% %8.4f"
              % (r["cell"][:34], r["n_them"], r["n_us"], r["tvd"],
                 r["freq"] * 100, r["leverage"]))
    print("\n-> scratchpad/s3/conditional_cells.json")
