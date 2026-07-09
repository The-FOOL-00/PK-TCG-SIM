"""Phase D stress test: the governor must make timeouts structurally impossible.

50 games, search seat at TRIPLED cost (SEARCH_DET = 3x the ship config's 16),
terminal rollouts, governor ON, seats alternated, vs plain v1. Per game we
record the search seat's own decision time (sum over its agent calls — the
quantity Kaggle's 600 s overage meters). Hard requirements:

  - zero games with own-time > 400 s
  - p99 decision time < 3.5 s

Run:  python tools/stress_governor.py --games 50 --workers 6
"""

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import deck_compare  # noqa: E402


def play_chunk(args):
    n, seat_offset, det = args
    import main
    deck = deck_compare.read_deck(REPO / "deck.csv")
    games = []
    for g in range(n):
        seat = (seat_offset + g) % 2
        dec_times = []

        def searcher(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            main.SEARCH = True
            main.SEARCH_DET = det
            main.SEARCH_ROLL, main.SEARCH_TOPK, main.SEARCH_CAP = 2, 4, 0
            main.GOVERNOR = True
            t0 = time.perf_counter()
            ans = main.agent(obs)
            dec_times.append(time.perf_counter() - t0)
            return ans

        def plain(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            main.SEARCH = False
            return main.agent(obs)

        wrappers = [None, None]
        wrappers[seat] = searcher
        wrappers[1 - seat] = plain
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)
        sticky = "heuristic-only for the rest" in buf.getvalue()
        games.append({
            "own_time": sum(dec_times),
            "n_dec": len(dec_times),
            "max_dec": max(dec_times) if dec_times else 0.0,
            "dec_times": dec_times,
            "status": [env.state[i].status for i in (0, 1)],
            "sticky": sticky,
        })
    return games


def main_run(games, workers, det):
    from concurrent.futures import ProcessPoolExecutor
    base, extra = divmod(games, workers)
    jobs, off = [], 0
    for w in range(workers):
        n = base + (1 if w < extra else 0)
        if n:
            jobs.append((n, off % 2, det))
            off += n
    t0 = time.time()
    if workers <= 1:
        chunks = [play_chunk(jobs[0])]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            chunks = list(ex.map(play_chunk, jobs))
    allg = [g for ch in chunks for g in ch]
    times = sorted(g["own_time"] for g in allg)
    all_dec = sorted(t for g in allg for t in g["dec_times"])
    crashes = sum(1 for g in allg
                  for s in g["status"] if s in ("INVALID", "ERROR", "TIMEOUT"))

    def pct(v, p):
        return v[min(len(v) - 1, int(p / 100 * len(v)))] if v else 0.0

    print("=" * 64)
    print(f"GOVERNOR STRESS: {len(allg)} games, det={det} (3x ship config), "
          f"terminal rollouts, wall {time.time()-t0:.0f}s")
    print(f"  own-time/game : mean {sum(times)/len(times):6.1f}s  p50 {pct(times,50):6.1f}s  "
          f"p90 {pct(times,90):6.1f}s  max {times[-1]:6.1f}s")
    print(f"  decision time : p50 {pct(all_dec,50)*1000:6.0f}ms  p90 {pct(all_dec,90)*1000:6.0f}ms  "
          f"p99 {pct(all_dec,99)*1000:6.0f}ms  max {all_dec[-1]*1000:6.0f}ms  (n={len(all_dec)})")
    print(f"  sticky games  : {sum(1 for g in allg if g['sticky'])}   crashes: {crashes}")
    ok_time = times[-1] < 400.0
    ok_p99 = pct(all_dec, 99) < 3.5
    print(f"  REQUIREMENTS  : max own-time < 400s: {'PASS' if ok_time else 'FAIL'}   "
          f"p99 decision < 3.5s: {'PASS' if ok_p99 else 'FAIL'}   "
          f"crashes==0: {'PASS' if crashes == 0 else 'FAIL'}")
    print("=" * 64)
    payload = {"games": len(allg), "det": det,
               "own_time": {"mean": sum(times) / len(times), "p50": pct(times, 50),
                            "p90": pct(times, 90), "max": times[-1]},
               "decision_ms": {"p50": pct(all_dec, 50) * 1000, "p90": pct(all_dec, 90) * 1000,
                               "p99": pct(all_dec, 99) * 1000, "max": all_dec[-1] * 1000,
                               "n": len(all_dec)},
               "sticky_games": sum(1 for g in allg if g["sticky"]),
               "crashes": crashes, "pass": bool(ok_time and ok_p99 and crashes == 0)}
    out = REPO / "runs" / "stress_governor.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"json written: {out}")
    if not (ok_time and ok_p99 and crashes == 0):
        raise SystemExit("STRESS FAIL")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--det", type=int, default=48)
    args = ap.parse_args()
    main_run(args.games, args.workers, args.det)
