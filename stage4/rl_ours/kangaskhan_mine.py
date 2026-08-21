"""PHASE 1 for Kangaskhan/Raging Bolt ex -- same method as conditional_mine.py
(which found E1/E2 for Grimmsnarl), applied to the new build target chosen
from ROSTER_DIFF_JUL31.md: top-10's Kangaskhan/Raging Bolt pilots (4 snapshots
now confirming the archetype's edge over Grimmsnarl) vs OUR OWN generic
v1-alone piloting of the same decklist (the "OPP" side of crossdeck_test.py's
kangaskhan-matchup runs, which already exist from this session's crossdeck
work) -- this is the identical "top-10 vs us, same deck" comparison shape
that originally surfaced E1/E2, just retargeted.

Reuses features()/cells()/NAME/ACTIONS/dist/tvd from conditional_mine.py
unchanged -- state features are deck-agnostic (turn/race/KO/bench/power),
same reasoning as the original script.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from meta_miner import archetype  # noqa: E402
from conditional_mine import features, cells, NAME, ACTIONS, dist, tvd  # noqa: E402

KANG = "Mega Kangaskhan ex / Raging Bolt ex"


def top10_rows(dirs):
    """Top-10 Kangaskhan/Raging Bolt pilots -- want_arch filter alone finds
    them, no team-name restriction needed (mirrors matchup_mine.py's approach)."""
    rows = []
    for d in dirs:
        for fp in sorted(Path(d).glob("*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if len(steps) < 2:
                continue
            for seat in (0, 1):
                act = steps[1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 60):
                    continue
                a = archetype(act)
                if not a or a["label"] != KANG:
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
                    rows.append((f, NAME.get((opts[ci] or {}).get("type"), "?")))
    return rows


def our_rows(dirs):
    """Our own v1-alone piloting of the same decklist -- the OPP seat of
    crossdeck_test.py's kangaskhan-matchup output (`_our_seat` marks US;
    OPP = 1 - _our_seat)."""
    rows = []
    for d in dirs:
        for fp in sorted(Path(d).glob("g*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if len(steps) < 2:
                continue
            opp_seat = 1 - js.get("_our_seat", 0)
            for i in range(len(steps) - 1):
                e = steps[i][opp_seat]
                if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                    continue
                obs = e.get("observation") or {}
                sel = obs.get("select") or {}
                if sel.get("type") != 0:
                    continue
                opts = sel.get("option") or []
                if len(opts) < 2:
                    continue
                act2 = steps[i + 1][opp_seat].get("action")
                if not (isinstance(act2, list) and len(act2) == 1):
                    continue
                ci = act2[0]
                if not isinstance(ci, int) or ci >= len(opts):
                    continue
                f = features(obs, opts)
                if f is None:
                    continue
                rows.append((f, NAME.get((opts[ci] or {}).get("type"), "?")))
    return rows


if __name__ == "__main__":
    A = REPO / "analysis/phase2_meta_shift"
    top_dirs = [A / "replays_top10_jul26", A / "replays_top10_jul31"]
    our_dirs = [REPO / "scratchpad/s3/crossdeck_kangaskhan_full",
                REPO / "scratchpad/s3/crossdeck_kangaskhan_full_t3"]

    them = top10_rows(top_dirs)
    us = our_rows(our_dirs)
    print("top-10 Kangaskhan/RagingBolt MAIN decisions : %d" % len(them))
    print("our     Kangaskhan/RagingBolt MAIN decisions : %d" % len(us))

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
        if nt < 20 or nu < 20:      # lower bar than Grimmsnarl's n>=30 -- smaller corpus
            continue
        p, q = dist(tc), dist(UC[c])
        d = tvd(p, q)
        freq = nt / tg
        rows.append({"cell": c, "n_them": nt, "n_us": nu, "tvd": d,
                     "freq": freq, "leverage": freq * d,
                     "them": p, "us": q})
    rows.sort(key=lambda r: -r["leverage"])
    (REPO / "scratchpad/s3/kangaskhan_conditional_cells.json").write_text(
        json.dumps({"n_them": tg, "n_us": ug, "rows": rows}, indent=1),
        encoding="utf-8")

    print("\ncells with n>=20 on BOTH sides: %d" % len(rows))
    print("\n%-34s %6s %6s %6s %7s %8s" % ("cell", "n_them", "n_us", "TVD", "freq", "leverage"))
    for r in rows[:25]:
        print("%-34s %6d %6d %6.3f %6.1f%% %8.4f"
              % (r["cell"][:34], r["n_them"], r["n_us"], r["tvd"],
                 r["freq"] * 100, r["leverage"]))
    print("\n-> scratchpad/s3/kangaskhan_conditional_cells.json")
