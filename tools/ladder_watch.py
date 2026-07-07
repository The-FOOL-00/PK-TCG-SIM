"""Ladder intelligence: track our submissions' scores + flag P0 losses.

Data sources (Kaggle API, needs ~/.kaggle/access_token):
  - `kaggle competitions submissions`  -> per-submission public score
  - `kaggle competitions leaderboard`  -> full score distribution / our rank
  - optional --scan DIR of episode replay JSONs (downloaded by meta_miner):
    finds our games by team name, reports W/L by opponent, and flags ANY
    loss where our status is INVALID/ERROR/TIMEOUT as a P0 bug.

Each run appends a timestamped row per submission to runs/ladder_history.csv
so score-over-time accumulates across invocations (Kaggle exposes only the
current score, not history — start running this daily).

Run:  python tools/ladder_watch.py [--team "TeamName"] [--scan runs/kaggle_meta/episodes]
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMP = "pokemon-tcg-ai-battle"
HISTORY = REPO / "runs" / "ladder_history.csv"
BAD_STATUSES = ("INVALID", "ERROR", "TIMEOUT")


def kaggle_cmd(*args):
    out = subprocess.run([sys.executable, "-m", "kaggle", *args],
                         capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed: {out.stderr[-400:]}")
    return out.stdout


def get_submissions():
    """Parse the submissions CLI table -> [{ref, date, description, status, score}]."""
    rows = []
    for line in kaggle_cmd("competitions", "submissions", "-c", COMP).splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2} [\d:.]+)\s+(.*)", line)
        if not m:
            continue
        ref, fname, date, rest = m.groups()
        parts = rest.split()
        score = None
        for tok in reversed(parts):
            try:
                score = float(tok)
                break
            except ValueError:
                continue
        status = next((t for t in parts if "SubmissionStatus" in t or t in
                       ("COMPLETE", "PENDING", "ERROR")), "?")
        desc = rest
        rows.append({"ref": ref, "file": fname, "date": date,
                     "status": status.split(".")[-1], "score": score, "desc": desc})
    return rows


def get_leaderboard():
    """Full leaderboard via CSV download -> [(rank, team, score)]."""
    import tempfile
    import zipfile
    with tempfile.TemporaryDirectory() as td:
        kaggle_cmd("competitions", "leaderboard", "-c", COMP, "--download", "-p", td)
        zips = list(Path(td).glob("*.zip"))
        rows = []
        if zips:
            with zipfile.ZipFile(zips[0]) as z:
                with z.open(z.namelist()[0]) as f:
                    text = f.read().decode("utf-8", "replace").splitlines()
        else:
            csvs = list(Path(td).glob("*.csv"))
            text = csvs[0].read_text(encoding="utf-8", errors="replace").splitlines()
        for i, rec in enumerate(csv.DictReader(text)):
            team = rec.get("TeamName") or rec.get("teamName") or ""
            score = rec.get("Score") or rec.get("score") or "0"
            rows.append((i + 1, team, float(score)))
    rows.sort(key=lambda r: -r[2])
    return [(i + 1, t, s) for i, (_r, t, s) in enumerate(rows)]


def scan_episodes(scan_dir, team):
    """Find our games in downloaded episode JSONs; flag P0 losses."""
    ours, p0 = [], []
    for fp in sorted(Path(scan_dir).glob("*.json")):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        teams = (d.get("info") or {}).get("TeamNames") or []
        if team not in teams:
            continue
        seat = teams.index(team)
        reward = (d.get("rewards") or [None, None])[seat]
        status = (d.get("statuses") or ["?", "?"])[seat]
        game = {"episode": d.get("id") or fp.stem, "opponent": teams[1 - seat],
                "reward": reward, "status": status}
        ours.append(game)
        if status in BAD_STATUSES:
            p0.append(game)
    return ours, p0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default=None,
                    help="our leaderboard team name (for rank + episode scan)")
    ap.add_argument("--scan", default=None,
                    help="dir of episode replay JSONs to scan for our games")
    args = ap.parse_args()

    subs = get_submissions()
    print("=== submissions ===")
    for s in subs:
        print(f"  {s['ref']}  {s['date'][:19]}  {s['status']:<9}"
              f"  score={s['score']}  {s['desc'][:60]}")

    lb = get_leaderboard()
    scores = [s for _r, _t, s in lb]
    print(f"\n=== leaderboard ({len(lb)} teams) ===")
    print(f"  top:    {scores[0]:.1f} ({lb[0][1]})")
    top20 = scores[19] if len(scores) > 19 else scores[-1]
    import statistics
    print(f"  #20:    {top20:.1f}   median: {statistics.median(scores):.1f}")
    if args.team:
        mine = [(r, t, s) for r, t, s in lb if t == args.team]
        if mine:
            r, _t, s = mine[0]
            pct = 100.0 * sum(1 for x in scores if x < s) / len(scores)
            print(f"  us:     {s:.1f}  rank {r}/{len(lb)}  (above {pct:.0f}% of teams)")
        else:
            print(f"  team {args.team!r} not found on leaderboard")
    else:
        best = max((s["score"] or 0) for s in subs) if subs else 0
        pct = 100.0 * sum(1 for x in scores if x < best) / len(scores)
        print(f"  our best submission score {best:.1f} would sit above "
              f"{pct:.0f}% of teams (pass --team for exact rank)")

    # append history
    HISTORY.parent.mkdir(exist_ok=True)
    new = not HISTORY.exists()
    with open(HISTORY, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "submission", "status", "score",
                        "lb_top", "lb_top20", "lb_median", "lb_teams"])
        for s in subs:
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), s["ref"], s["status"],
                        s["score"], scores[0], top20,
                        statistics.median(scores), len(lb)])
    print(f"\nhistory appended: {HISTORY}")

    if args.scan:
        if not args.team:
            print("--scan needs --team to identify our games", file=sys.stderr)
            return
        ours, p0 = scan_episodes(args.scan, args.team)
        wins = sum(1 for g in ours if g["reward"] == 1)
        print(f"\n=== our episodes in {args.scan}: {len(ours)} found, "
              f"{wins}W-{len(ours)-wins}L ===")
        by_opp = {}
        for g in ours:
            by_opp.setdefault(g["opponent"], []).append(g["reward"])
        for opp, rs in sorted(by_opp.items()):
            print(f"  vs {opp}: {sum(1 for r in rs if r == 1)}W-"
                  f"{sum(1 for r in rs if r != 1)}L")
        if p0:
            print(f"\n  *** P0 BUG: {len(p0)} game(s) lost by "
                  f"INVALID/ERROR/TIMEOUT: ***")
            for g in p0:
                print(f"    episode {g['episode']} vs {g['opponent']}: {g['status']}")
        else:
            print("  no INVALID/ERROR/TIMEOUT games — clean.")


if __name__ == "__main__":
    main()
