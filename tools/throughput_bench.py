"""Measure self-play throughput (games/minute) for RL planning (WS3).

Plays v1-policy self-play games via kaggle_environments make("cabt") and
reports games/minute single-process and with N worker processes.

Run:  python tools/throughput_bench.py --games 20 --workers 1 2 4 8
"""

import argparse
import contextlib
import io
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def play_games(n):
    """Worker: play n self-play games, return elapsed seconds."""
    sys.path.insert(0, str(REPO))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        from kaggle_environments import make
    import main as agent_mod

    def wrapper(obs, _config):
        return agent_mod.agent(obs)

    t0 = time.perf_counter()
    for _ in range(n):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env = make("cabt", debug=False)
            env.run([wrapper, wrapper])
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20, help="games per worker")
    ap.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4])
    args = ap.parse_args()

    print(f"cpu_count: {os.cpu_count()}")
    # warm-up (imports, DLL load) so the measurement is steady-state
    play_games(2)

    for w in args.workers:
        if w == 1:
            elapsed = play_games(args.games)
            total = args.games
        else:
            from concurrent.futures import ProcessPoolExecutor
            t0 = time.perf_counter()
            with ProcessPoolExecutor(max_workers=w) as ex:
                list(ex.map(play_games, [args.games] * w))
            elapsed = time.perf_counter() - t0
            total = args.games * w
        gpm = total / elapsed * 60.0
        print(f"workers={w}: {total} games in {elapsed:.1f}s -> {gpm:.0f} games/min "
              f"({gpm / 60:.2f} games/s)", flush=True)


if __name__ == "__main__":
    main()
