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
    """Fetch submissions via direct Kaggle HTTP API using OAuth bearer token."""
    cred_p = Path.home() / ".kaggle" / "credentials.json"
    if not cred_p.exists():
        return []
    try:
        import urllib.request
        tok = json.loads(cred_p.read_text(encoding="utf-8")).get("access_token")
        if not tok:
            return []
        url = f"https://www.kaggle.com/api/v1/competitions/submissions/list/{COMP}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = []
        for s in data:
            ref = str(s.get("ref", s.get("id", "")))
            fname = str(s.get("fileName", s.get("description", "")))
            date = str(s.get("date", s.get("submittedDate", "")))
            status = str(s.get("status", s.get("submissionStatus", "")))
            score_val = s.get("publicScore", s.get("score"))
            score = float(score_val) if score_val is not None else None
            rows.append({"ref": ref, "file": fname, "date": date, "status": status, "score": score, "desc": fname})
        return rows
    except Exception as e:
        sys.stderr.write(f"[ladder_watch] Warning: Direct API submission fetch failed ({e})\n")
        return []


def get_leaderboard():
    """Full leaderboard via CSV download -> [(rank, team, score)]."""
    import tempfile
    import zipfile
    try:
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
                if not csvs:
                    return []
                text = csvs[0].read_text(encoding="utf-8", errors="replace").splitlines()
            for i, rec in enumerate(csv.DictReader(text)):
                team = rec.get("TeamName") or rec.get("teamName") or ""
                score = rec.get("Score") or rec.get("score") or "0"
                rows.append((i + 1, team, float(score)))
        rows.sort(key=lambda r: -r[2])
        return [(i + 1, t, s) for i, (_r, t, s) in enumerate(rows)]
    except Exception:
        return []


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
    ap.add_argument("--team", default=None, help="our leaderboard team name")
    ap.add_argument("--scan", default=None, help="dir of episode replay JSONs")
    ap.add_argument("--all", action="store_true", help="Show all historical submissions")
    args = ap.parse_args()

    subs = get_submissions()
    display_subs = subs if args.all else subs[:2]
    print("=== Active Pair Submissions (Kaggle Top 2) ===" if not args.all else "=== All Historical Submissions ===")
    for s in display_subs:
        print(f"  ID: {s['ref']:<10} Date: {s['date'][:19]}  Status: {s['status']:<9} Score/Elo: {s['score']}  {s['desc'][:50]}")

    lb = get_leaderboard()
    scores = [s for _r, _t, s in lb]
    print(f"\n=== leaderboard ({len(lb)} teams) ===")
    if scores:
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
    else:
        print("  (Leaderboard data currently unavailable)")

    # append history
    HISTORY.parent.mkdir(exist_ok=True)
    new = not HISTORY.exists()
    with open(HISTORY, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "submission", "status", "score",
                        "lb_top", "lb_top20", "lb_median", "lb_teams"])
        lb_top = scores[0] if scores else 0.0
        lb_top20 = top20 if scores else 0.0
        lb_med = statistics.median(scores) if scores else 0.0
        for s in subs:
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), s["ref"], s["status"],
                        s["score"], lb_top, lb_top20,
                        lb_med, len(lb)])
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
