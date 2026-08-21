"""Evening Jul-22 top-10 harvest — unauth path (bearer expired).

Current top-10 read from the live leaderboard page (browser), TeamIds mapped
via the morning full-CSV (TeamIds stable, ranks stale). Submission IDs are
discovered UNAUTHENTICATED by scanning episodes of known submissions:
episode.agents[] carries teamId + submissionId for BOTH sides, and top-ladder
matchmaking pairs similar-mu teams, so the current top-10 all appear as
opponents within one or two hops of any known top submission.

Chain:
  known submissionIds (morning meta + ours)
    -> api/i/competitions.EpisodeService/ListEpisodes {"submissionId": N}  (unauth)
    -> index agents by teamId -> newest submissionId per target team
    -> ListEpisodes per target submission -> latest QUOTA episodes
    -> replay CDN kaggleusercontent.com/episodes/{id}.json               (unauth)

Run: py -3.12 -X utf8 analysis/phase2_meta_shift/harvest_jul22_evening.py
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DEST = HERE / "replays_top10_jul22"
META = DEST / "_episodes_meta.json"
QUOTA = 30
CDN_WORKERS = 6
HDRS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

# Current top-10, read from the live leaderboard page 2026-07-22 evening.
# label -> (teamId from morning full CSV, current rank, current score)
TARGETS = {
    "Luca":            (16448747, 1, 1211.6),
    "Yudai Ueno":      (16418623, 2, 1147.8),
    "Eduardo Rocha de Andrade": (16461850, 3, 1129.5),
    "Majkel1337":      (16374395, 4, 1122.7),
    "kashiwashira":    (16385372, 5, 1120.4),
    "junlee789":       (16422150, 6, 1119.6),
    "LumenLiquidity":  (16381624, 7, 1115.6),
    "Yushin Ito":      (16381823, 8, 1115.5),
    "Rmy":             (16425135, 9, 1112.9),
    "Budew":           (16371434, 10, 1112.7),
}

# Seed scan set: morning top-10 submissions + our own two (all verified live today)
SEED_SUBMISSIONS = [
    54861775,  # Oshbocker (morning #1)
    54840044,  # THIRD PTCG Club
    54773249,  # Yushin Ito
    54838518,  # LumenLiquidity
    54775633,  # junlee789
    54863439,  # GUOHAOYANG
    54846143,  # __Taichicchi__
    54826859,  # jiatu.l
    54863641,  # ポケカ前線
    54831269,  # 齐乐
    54855847,  # Project Mew v7
    54863817,  # Project Mew v8
]


def list_episodes(submission_id):
    r = requests.post(
        "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
        json={"submissionId": submission_id}, headers=HDRS, timeout=90)
    r.raise_for_status()
    return r.json()


def main():
    DEST.mkdir(exist_ok=True)
    target_ids = {tid: label for label, (tid, _r, _s) in TARGETS.items()}

    # -- discovery: teamId -> {submissionId: newest endTime seen} ------------
    team_subs = {}          # teamId -> {subId: latest endTime}
    scanned = set()
    frontier = list(SEED_SUBMISSIONS)
    for hop in range(2):
        nxt = []
        for sid in frontier:
            if sid in scanned:
                continue
            scanned.add(sid)
            try:
                d = list_episodes(sid)
            except Exception as e:
                print(f"  scan {sid}: {e!r}")
                continue
            for ep in d.get("episodes") or []:
                for ag in ep.get("agents") or []:
                    tid, sub = ag.get("teamId"), ag.get("submissionId")
                    if tid in target_ids and sub:
                        cur = team_subs.setdefault(tid, {})
                        et = ep.get("endTime") or ""
                        if et > cur.get(sub, ""):
                            cur[sub] = et
            time.sleep(0.4)
        # after hop 0: for each target, tentatively queue its newest sub for hop 1
        missing = [t for t in target_ids if t not in team_subs]
        print(f"hop {hop}: found {len(team_subs)}/10 targets, missing: "
              f"{[target_ids[t] for t in missing]}")
        if not missing:
            break
        # expand: scan the newest submission of every FOUND target (their
        # opponents include the missing teams at adjacent ranks)
        for tid, subs in team_subs.items():
            newest = max(subs, key=subs.get)
            if newest not in scanned:
                nxt.append(newest)
        frontier = nxt

    # newest submission per target team
    chosen = {}
    for tid, subs in team_subs.items():
        newest = max(subs, key=subs.get)
        chosen[target_ids[tid]] = newest
    print("\nchosen submissions:")
    for label, (tid, rank, score) in TARGETS.items():
        print(f"  #{rank:<2d} {label:<28s} teamId={tid} sub={chosen.get(label, 'NOT FOUND')}")

    # -- per-target episode listing ------------------------------------------
    meta = {"targets": {l: {"teamId": t[0], "rank": t[1], "score": t[2],
                            "submissionId": chosen.get(l)} for l, t in TARGETS.items()},
            "episodes": {}}
    ep_owner = {}
    for label, sub in chosen.items():
        try:
            d = list_episodes(sub)
        except Exception as e:
            print(f"  {label}: {e!r}")
            continue
        eps = [e for e in (d.get("episodes") or []) if e.get("state") == "COMPLETED"]
        eps.sort(key=lambda e: e.get("endTime") or "", reverse=True)
        for e in eps[:QUOTA]:
            eid = e.get("id")
            if eid and eid not in ep_owner:
                ep_owner[eid] = label
                meta["episodes"][str(eid)] = e
        print(f"  {label}: {len(eps)} completed episodes, kept {min(QUOTA, len(eps))}")
        time.sleep(0.4)

    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    todo = [e for e in ep_owner if not (DEST / f"{e}.json").exists()]
    print(f"\n{len(ep_owner)} unique episodes, {len(todo)} to fetch")

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
                print(f"  {eid}: {e!r}")
            if (ok + miss) % 50 == 0:
                print(f"  {ok} fetched, {miss} failed", flush=True)
    print(f"done: {ok} fetched, {miss} failed -> {DEST}")


if __name__ == "__main__":
    main()
