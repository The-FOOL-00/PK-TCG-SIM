"""Grimm mining v2 — includes jul31 snapshot AND compares to POST-bundle
behavior (horizon_T1T2 = v1+E1+E2+T1+T2). Finds cells where the shipped
bundle still doesn't close the top-10 gap → candidate cells for a NEW rule."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conditional_mine import features, cells, NAME, ACTIONS, dist, tvd, GRIMM  # noqa
from meta_miner import archetype  # noqa: E402


def top10_rows(dirs):
    """Grimm sides from top-10 teams (all snapshots, uses profile for team filter)."""
    A = REPO / "analysis/phase2_meta_shift"
    teams_by_dir = {}
    for d, prof in [(dirs[0], "profile_top10_jul21.json"),
                    (dirs[1], "profile_top10_jul22.json"),
                    (dirs[2], "profile_top10_jul26.json"),
                    (dirs[3], "profile_top10_jul31.json")]:
        try:
            teams_by_dir[str(d)] = set(json.loads(
                (A / prof).read_text(encoding="utf-8"))["teams"])
        except Exception:
            teams_by_dir[str(d)] = set()

    rows = []
    for d in dirs:
        allowed_teams = teams_by_dir.get(str(d), set())
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
                if seat >= len(tn) or tn[seat] not in allowed_teams:
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


def our_rows(bundle_dir):
    """Our Grimm play with shipped bundle (E1+E2+T1+T2) enabled. Games are
    mirror Grimm vs Grimm — both sides pilot Grimm identically, so read
    from BOTH seats (each provides a full sample of our-side decisions)."""
    rows = []
    for fp in sorted(Path(bundle_dir).glob("g*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = js.get("steps") or []
        if len(steps) < 2:
            continue
        for seat in (0, 1):
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


if __name__ == "__main__":
    A = REPO / "analysis/phase2_meta_shift"
    top_dirs = [A / "replays_top10_jul21", A / "replays_top10_jul22",
                A / "replays_top10_jul26", A / "replays_top10_jul31"]
    them = top10_rows(top_dirs)
    us = our_rows(REPO / "scratchpad/s3/horizon_T1T2")
    print(f"top-10 Grimm decisions (4 snapshots): {len(them)}")
    print(f"our T1T2 (shipped bundle) decisions:  {len(us)}")

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
    out = REPO / "scratchpad/s3/grimm_cells_v2.json"
    out.write_text(json.dumps({"n_them": tg, "n_us": ug, "rows": rows}, indent=1),
                    encoding="utf-8")

    print(f"\ncells with n>=30 both sides: {len(rows)}")
    print(f"\n{'cell':<34s} {'nT':>6s} {'nU':>6s} {'TVD':>6s} {'freq':>7s} {'lev':>7s}")
    for r in rows[:25]:
        print(f"{r['cell'][:34]:<34s} {r['n_them']:>6d} {r['n_us']:>6d} "
              f"{r['tvd']:>6.3f} {r['freq']*100:>6.1f}% {r['leverage']:>7.4f}")
    print(f"\n-> {out}")
