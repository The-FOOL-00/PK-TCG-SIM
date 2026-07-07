"""Generate self-play training data for the learned value model (Phase 1a).

Plays v1-policy self-play (current best; deck.csv both sides) and logs, at
EVERY decision point, the 170-dim state feature vector from the acting
player's perspective (main.encode_state — the same encoder inference will
use), plus that player's final game outcome (+1/-1/0), the turn number, and
a globally unique game id (for grouping / by-game splits).

Output: .npz shards under --out (gitignored), each holding
    x        float32 [N, 170]   encode_state vectors
    y        int8    [N]        outcome for the acting player (+1/-1/0)
    turn     int16   [N]        turn number at the decision
    game_id  int32   [N]        unique per game (shared by both players' rows)
plus meta.json (schema, feature index map, AGENT_VERSION) in the same dir.

Run:  python tools/gen_selfplay.py --games 50000 --workers 8 --out data/selfplay_v1
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

SHARD_ROWS_DEFAULT = 500_000  # ~340 MB of float32 x per shard, < 500 MB cap


def _flush(out_dir, worker_id, seq, feats, outs, turns, gids):
    import numpy as np
    path = Path(out_dir) / f"shard_w{worker_id}_{seq:03d}.npz"
    np.savez_compressed(
        path,
        x=np.asarray(feats, dtype=np.float32),
        y=np.asarray(outs, dtype=np.int8),
        turn=np.asarray(turns, dtype=np.int16),
        game_id=np.asarray(gids, dtype=np.int32),
    )
    print(f"[w{worker_id}] wrote {path.name}: {len(outs)} rows", flush=True)
    return seq + 1


def run_worker(args):
    worker_id, n_games, out_dir, shard_rows = args
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        from kaggle_environments import make
    import main as agent_mod

    feats, outs, turns, gids = [], [], [], []
    seq, done = 0, 0
    t0 = time.perf_counter()
    for g in range(n_games):
        game_id = worker_id * 10_000_000 + g
        per_seat = ([], [])  # (features, turn) rows awaiting the outcome

        def make_seat(seat):
            rows = per_seat[seat]

            def wrapper(obs, _config):
                cur = obs.get("current")
                if cur is not None and obs.get("select") is not None:
                    try:
                        rows.append((agent_mod.encode_state(cur),
                                     cur.get("turn") or 0))
                    except Exception:
                        pass  # never let logging kill the game
                return agent_mod.agent(obs)
            return wrapper

        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            env = make("cabt", debug=False)
            env.run([make_seat(0), make_seat(1)])

        for seat in (0, 1):
            outcome = int(env.state[seat].reward or 0)
            for vec, turn in per_seat[seat]:
                feats.append(vec)
                outs.append(outcome)
                turns.append(turn)
                gids.append(game_id)
        done += 1
        if done % 200 == 0:
            gpm = done / (time.perf_counter() - t0) * 60
            print(f"[w{worker_id}] {done}/{n_games} games "
                  f"({gpm:.0f} games/min, {len(outs)} rows buffered)", flush=True)
        if len(outs) >= shard_rows:
            seq = _flush(out_dir, worker_id, seq, feats, outs, turns, gids)
            feats, outs, turns, gids = [], [], [], []
    if outs:
        seq = _flush(out_dir, worker_id, seq, feats, outs, turns, gids)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=50_000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="data/selfplay_v1")
    ap.add_argument("--shard-rows", type=int, default=SHARD_ROWS_DEFAULT)
    args = ap.parse_args()

    import main as agent_mod
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "agent_version": agent_mod.AGENT_VERSION,
        "policy": "v1 heuristic self-play, deck.csv both sides, V3_EVAL off",
        "n_features": agent_mod.N_STATE_FEATURES,
        "feature_names": agent_mod.state_feature_names(),
        "outcome": "+1 win / -1 loss / 0 draw for the acting player, "
                   "assigned to every decision of that player's game",
        "arrays": {"x": "float32 [N,170]", "y": "int8 [N]",
                   "turn": "int16 [N]", "game_id": "int32 [N]"},
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "games_requested": args.games,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    base, extra = divmod(args.games, args.workers)
    jobs = [(w, base + (1 if w < extra else 0), str(out_dir), args.shard_rows)
            for w in range(args.workers) if base + (1 if w < extra else 0) > 0]
    t0 = time.perf_counter()
    if args.workers <= 1:
        total = run_worker(jobs[0])
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            total = sum(ex.map(run_worker, jobs))
    dt = time.perf_counter() - t0
    print(f"DONE: {total} games in {dt/60:.1f} min "
          f"({total/dt*60:.0f} games/min) -> {out_dir}", flush=True)


if __name__ == "__main__":
    main()
