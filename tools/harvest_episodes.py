"""Harvest recent episodes of the current top-10 teams from the daily
episode datasets (Kaggle HTTP API, OAuth bearer from ~/.kaggle/credentials.json).

Strategy: newest day first, list the daily dataset's episode files, download
in parallel (small zips), parse TeamNames cheaply, KEEP episodes involving a
top-10 team (data/top_replays_bulk/), drop the rest. Resume-safe via a
scanned-ids ledger; stops when every team hits --quota or days are exhausted.
Writes a manifest CSV (episode, date, teams, rewards) for the filter step.

Run:  py -3.12 -X utf8 tools/harvest_episodes.py --days 4 --quota 28 --workers 6
"""

import argparse
import csv
import io
import json
import random
import sys
import time
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "top_replays_bulk"
LEDGER = OUT / "_scanned_ids.txt"
MANIFEST = OUT / "_manifest.csv"
CRED = Path.home() / ".kaggle" / "credentials.json"
BASE = "https://www.kaggle.com/api/v1"


def token():
    return json.loads(CRED.read_text())["access_token"]


def api(url, raw=False, tok=None, timeout=120):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + (tok or token())})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if raw else json.loads(data)


def list_day_files(slug):
    files, page_token = [], ""
    while True:
        url = f"{BASE}/datasets/list/kaggle/{slug}?pageSize=200"
        if page_token:
            url += f"&pageToken={page_token}"
        d = api(url)
        files += [f["name"] for f in d.get("datasetFiles") or [] if f.get("name", "").endswith(".json")]
        page_token = d.get("nextPageToken")
        if not page_token:
            break
    return files


def fetch_episode(slug, name):
    """Download one episode file; returns bytes of the JSON (unzips if needed)."""
    data = api(f"{BASE}/datasets/download/kaggle/{slug}/{name}", raw=True, timeout=180)
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            data = z.read(z.namelist()[0])
    return data


def teams_of(data):
    """Cheap parse: TeamNames + rewards without fully loading steps."""
    d = json.loads(data)
    info = d.get("info") or {}
    return (info.get("TeamNames") or ["?", "?"], d.get("rewards") or [None, None])


def run(days, quota, workers, max_scan):
    OUT.mkdir(parents=True, exist_ok=True)
    lb = list(csv.DictReader(open(REPO / "data" / "leaderboard_snapshot_2026-07-10.csv",
                                  encoding="utf-8")))
    top10 = [r["team"] for r in lb[:10]]
    print("top-10:", top10)

    counts = Counter()
    if MANIFEST.exists():
        for row in csv.DictReader(open(MANIFEST, encoding="utf-8")):
            for t in (row["team0"], row["team1"]):
                if t in top10:
                    counts[t] += 1
    scanned = set(LEDGER.read_text().split()) if LEDGER.exists() else set()
    print("resume: %d episodes already kept for top-10, %d scanned" %
          (sum(counts.values()), len(scanned)))

    manifest_f = open(MANIFEST, "a", newline="", encoding="utf-8")
    mw = csv.writer(manifest_f)
    if MANIFEST.stat().st_size == 0:
        mw.writerow(["episode", "date", "team0", "team1", "reward0", "reward1"])
    ledger_f = open(LEDGER, "a", encoding="utf-8")

    manifest_rows = list(csv.DictReader(open(REPO / "runs" / "kaggle_meta" / "manifest.csv",
                                             encoding="utf-8")))
    recent = sorted(manifest_rows, key=lambda r: r["date"])[-days:][::-1]
    t_start = time.time()
    n_scanned_run = n_kept_run = 0
    err_streak = 0

    for day in recent:
        slug, date = day["daily_dataset_slug"], day["date"]
        if all(counts[t] >= quota for t in top10):
            break
        print(f"\n== {date} ({day['episode_count']} episodes) ==")
        try:
            files = list_day_files(slug)
        except Exception as e:
            print(f"  list failed: {e!r}; skipping day", file=sys.stderr)
            continue
        todo = [f for f in files if f.split(".")[0] not in scanned]
        random.Random(0).shuffle(todo)   # unbiased sample of the day
        print(f"  {len(files)} files, {len(todo)} unscanned")

        with ThreadPoolExecutor(max_workers=workers) as ex:
            it = iter(todo)
            inflight = {}

            def submit_next():
                try:
                    name = next(it)
                except StopIteration:
                    return False
                inflight[ex.submit(fetch_episode, slug, name)] = name
                return True

            for _ in range(workers * 2):
                if not submit_next():
                    break
            while inflight:
                done = next(as_completed(list(inflight)))
                name = inflight.pop(done)
                eid = name.split(".")[0]
                try:
                    data = done.result()
                    err_streak = 0
                except Exception as e:
                    err_streak += 1
                    print(f"  fetch {name}: {e!r}", file=sys.stderr)
                    if err_streak >= 8:
                        print("  too many consecutive errors (auth expired or throttled); "
                              "stopping run", file=sys.stderr)
                        inflight.clear()
                        break
                    time.sleep(2 * err_streak)
                    submit_next()
                    continue
                n_scanned_run += 1
                scanned.add(eid)
                ledger_f.write(eid + "\n")
                try:
                    teams, rewards = teams_of(data)
                except Exception:
                    teams, rewards = ["?", "?"], [None, None]
                hit = [t for t in teams if t in top10 and counts[t] < quota * 2]
                if any(t in top10 for t in teams):
                    (OUT / name).write_bytes(data)
                    mw.writerow([eid, date, teams[0], teams[1], rewards[0], rewards[1]])
                    for t in teams:
                        if t in top10:
                            counts[t] += 1
                    n_kept_run += 1
                if n_scanned_run % 50 == 0:
                    manifest_f.flush()
                    ledger_f.flush()
                    rate = n_scanned_run / max(1e-9, time.time() - t_start)
                    print(f"  scanned {n_scanned_run} kept {n_kept_run} "
                          f"({rate:.1f} eps/s)  counts: " +
                          " ".join(f"{t.split()[0]}:{counts[t]}" for t in top10),
                          flush=True)
                if max_scan and n_scanned_run >= max_scan:
                    print("  max-scan reached for this run")
                    inflight.clear()
                    break
                if all(counts[t] >= quota for t in top10):
                    print("  all quotas met")
                    inflight.clear()
                    break
                time.sleep(0.05)   # gentle on the API
                submit_next()
        if max_scan and n_scanned_run >= max_scan:
            break

    manifest_f.close()
    ledger_f.close()
    print("\nFINAL per-team kept counts:")
    for t in top10:
        flag = "  <-- UNDER 15" if counts[t] < 15 else ""
        print(f"  {t:28s} {counts[t]:4d}{flag}")
    print(f"scanned this run: {n_scanned_run}, kept: {n_kept_run}, "
          f"wall {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--quota", type=int, default=28)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-scan", type=int, default=0, help="stop after N downloads this run")
    args = ap.parse_args()
    run(args.days, args.quota, args.workers, args.max_scan)
