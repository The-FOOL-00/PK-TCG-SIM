"""Phase 2 (2026-07-31): fresh top-10 replay harvest, per user direction to
check for a new archetype/development path before committing to a bigger
engineering investment.

Chain (identical to harvest_jul21.py / harvest_jul22_evening.py):
  leaderboard CSV (TeamId) -> ListTeamPublicSubmissions -> ListSubmissionEpisodes
  -> replay CDN kaggleusercontent.com/episodes/{id}.json

Auth: bearer from ~/.kaggle/credentials.json (refreshed via kagglesdk this
session). CDN fetches are unauthenticated.

Run: py -3.12 -X utf8 analysis/phase2_meta_shift/harvest_jul31.py
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
LB = HERE / "leaderboard_2026-07-31.csv"
DEST = HERE / "replays_top10_jul31"
META = DEST / "_episodes_meta.json"
QUOTA = 30          # episodes per team (latest first)
CDN_WORKERS = 6


def token():
    return json.loads((Path.home() / ".kaggle" / "credentials.json").read_text())["access_token"]


def api(method, body, tok):
    r = requests.post(
        f"https://api.kaggle.com/v1/competitions.CompetitionApiService/{method}",
        json=body, headers={"Authorization": "Bearer " + tok}, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    import csv
    tok = token()
    DEST.mkdir(exist_ok=True)
    rows = list(csv.DictReader(open(LB, encoding="utf-8-sig")))
    top10 = [(int(r["TeamId"]), r["TeamName"]) for r in rows[:10]]
    print("top-10:", [t[1] for t in top10])

    meta = {"teams": {}, "episodes": {}}
    ep_team = {}          # eid -> team name (first claimer)
    for team_id, name in top10:
        subs = api("ListTeamPublicSubmissions", {"teamId": team_id}, tok).get("submissions") or []
        subs.sort(key=lambda s: s.get("dateSubmitted") or "", reverse=True)
        meta["teams"][name] = {"teamId": team_id, "submissions": subs}
        eps = []
        for s in subs:
            try:
                r = api("ListSubmissionEpisodes", {"submissionId": s["id"]}, tok)
            except Exception as e:
                print(f"  {name} sub {s['id']}: {e!r}", file=sys.stderr)
                continue
            got = r.get("episodes") or []
            eps.extend(got)
            print(f"  {name} sub {s['id']} (score {s.get('publicScore')}): {len(got)} episodes")
            if len(eps) >= QUOTA:
                break
            time.sleep(0.5)
        eps.sort(key=lambda e: e.get("endTime") or e.get("createTime") or "", reverse=True)
        keep = eps[:QUOTA]
        for e in keep:
            eid = e.get("id")
            if eid and eid not in ep_team:
                ep_team[eid] = name
                meta["episodes"][str(eid)] = e
        time.sleep(0.5)

    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    todo = [e for e in ep_team if not (DEST / f"{e}.json").exists()]
    print(f"\n{len(ep_team)} unique episodes, {len(todo)} to fetch")

    def fetch(eid):
        r = requests.get(f"https://www.kaggleusercontent.com/episodes/{eid}.json",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=180)
        r.raise_for_status()
        return r.content

    ok = miss = 0
    with ThreadPoolExecutor(max_workers=CDN_WORKERS) as ex:
        futs = {ex.submit(fetch, e): e for e in todo}
        for fut in as_completed(futs):
            eid = futs[fut]
            try:
                (DEST / f"{eid}.json").write_bytes(fut.result())
                ok += 1
            except Exception as e:
                miss += 1
                print(f"  {eid}: {e!r}", file=sys.stderr)
            if (ok + miss) % 25 == 0:
                print(f"  {ok} fetched, {miss} failed", flush=True)
    print(f"done: {ok} fetched, {miss} failed -> {DEST}")


if __name__ == "__main__":
    main()
