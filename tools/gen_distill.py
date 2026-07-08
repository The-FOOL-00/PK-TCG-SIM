"""Generate search-distillation training data — Phase 2c, cycle 1.

Plays teacher-guided self-play: BOTH seats run the determinized-MC teacher
(tools/searcher.py) at the signed-off (det=16, roll=2, topk=4) config,
deck.csv both sides. At every decision the teacher actually SEARCHED
(MAIN-phase, single-select, >1 option) we log, from the acting player's
perspective:

    state    170-dim main.encode_state vector
    options  one 41-dim main.encode_option row PER option (all options of
             the decision, not just the searched top-k candidates)
    label    the option index the teacher chose (0-based, within the
             decision's full option list)

Non-searched decisions are pure v1 and are not logged (the student keeps v1
for those phases at inference).

Known caveat (accepted for cycle 1, see EXPERIMENT_LOG.md): teacher
determinizations assume the opponent's 60-card list is OUR deck list — exact
in mirror self-play, an information leak vs ladder conditions.

Output: .npz shards under --out (gitignored), each holding
    state      float32 [D, 170]  encode_state per searched decision
    n_options  int16   [D]       options in that decision
    label      int16   [D]       teacher-chosen option index
    turn       int16   [D]
    game_id    int32   [D]       unique per game (shared by both seats' rows)
    opt_x      float32 [sum(n_options), 41]  option rows, concatenated in
               decision order (reconstruct offsets via cumsum of n_options)
plus meta.json (schema, feature name maps, teacher config, AGENT_VERSION).

Run:  python tools/gen_distill.py --decisions 500000 --workers 8 \
          --out data/distill_c1
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

TEACHER_CFG = {"det": 16, "roll": 2, "topk": 4, "cap": 400}
SHARD_DECISIONS_DEFAULT = 40_000  # ~28 MB state + ~66 MB opt_x raw per shard


def _flush(out_dir, worker_id, seq, buf):
    import numpy as np
    path = Path(out_dir) / f"shard_w{worker_id}_{seq:03d}.npz"
    np.savez_compressed(
        path,
        state=np.asarray(buf["state"], dtype=np.float32),
        n_options=np.asarray(buf["n_options"], dtype=np.int16),
        label=np.asarray(buf["label"], dtype=np.int16),
        turn=np.asarray(buf["turn"], dtype=np.int16),
        game_id=np.asarray(buf["game_id"], dtype=np.int32),
        opt_x=np.concatenate(buf["opt_rows"], axis=0),
    )
    print(f"[w{worker_id}] wrote {path.name}: {len(buf['label'])} decisions",
          flush=True)
    for v in buf.values():
        v.clear()
    return seq + 1


def run_worker(args):
    worker_id, n_decisions, out_dir, shard_decisions = args
    import numpy as np
    sio = io.StringIO()
    with contextlib.redirect_stdout(sio), contextlib.redirect_stderr(sio):
        from kaggle_environments import make
    import main as agent_mod
    from tools import searcher

    deck = agent_mod.DECK
    buf = {"state": [], "n_options": [], "label": [], "turn": [],
           "game_id": [], "opt_rows": []}
    seq, games, logged = 0, 0, 0
    stats_total = {"decisions": 0, "searched": 0, "changed": 0}
    # one teacher per seat: separate cg.dll search arenas, distinct rng streams
    teachers = [searcher.Teacher(deck, seed=worker_id * 2 + s, **TEACHER_CFG)
                for s in (0, 1)]
    t0 = time.perf_counter()

    def make_seat(seat, game_id):
        teacher = teachers[seat]

        def wrapper(obs, _config=None):
            if obs.get("select") is None:
                return list(deck)
            ans, searched, _cands = teacher.choose(obs)
            if searched:
                try:
                    cur = obs["current"]
                    buf["state"].append(
                        np.asarray(agent_mod.encode_state(cur), np.float32))
                    rows = np.asarray(
                        agent_mod.encode_options(obs["select"], cur), np.float32)
                    buf["opt_rows"].append(rows)
                    buf["n_options"].append(len(rows))
                    buf["label"].append(ans[0])
                    buf["turn"].append(cur.get("turn") or 0)
                    buf["game_id"].append(game_id)
                except Exception:
                    # logging must never kill the game; drop arrays in sync
                    n = min(len(buf[k]) for k in buf)
                    for k in buf:
                        del buf[k][n:]
            return ans
        return wrapper

    while logged < n_decisions:
        game_id = worker_id * 10_000_000 + games
        before = len(buf["label"])
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            env = make("cabt", debug=False)
            env.run([make_seat(0, game_id), make_seat(1, game_id)])
        logged += len(buf["label"]) - before
        games += 1
        if games % 20 == 0:
            dt = time.perf_counter() - t0
            print(f"[w{worker_id}] {games} games, {logged}/{n_decisions} "
                  f"decisions ({logged/dt:.1f} dec/s)", flush=True)
        if len(buf["label"]) >= shard_decisions:
            seq = _flush(out_dir, worker_id, seq, buf)
    if buf["label"]:
        seq = _flush(out_dir, worker_id, seq, buf)
    for t in teachers:
        for k in stats_total:
            stats_total[k] += t.stats[k]
    print(f"[w{worker_id}] DONE: {games} games, {logged} decisions, "
          f"teacher stats {stats_total}", flush=True)
    return games, logged, stats_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", type=int, default=500_000,
                    help="total searched decisions to log across all workers")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="data/distill_c1")
    ap.add_argument("--shard-decisions", type=int,
                    default=SHARD_DECISIONS_DEFAULT)
    args = ap.parse_args()

    import main as agent_mod
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "agent_version": agent_mod.AGENT_VERSION,
        "phase": "2c cycle 1 — search distillation data",
        "policy": "teacher-guided self-play BOTH seats (tools/searcher.py), "
                  "deck.csv both sides, V3_EVAL/LEARNED_VALUE off",
        "teacher": TEACHER_CFG,
        "caveat": "determinizations assume opponent runs our deck list — "
                  "exact only in the mirror (accepted for cycle 1)",
        "logged": "only decisions the teacher searched (MAIN single-select, "
                  ">1 option); label = teacher-chosen option index over the "
                  "FULL option list",
        "n_state_features": agent_mod.N_STATE_FEATURES,
        "n_option_features": agent_mod.N_OPTION_FEATURES,
        "state_feature_names": agent_mod.state_feature_names(),
        "option_feature_names": agent_mod.option_feature_names(),
        "arrays": {"state": "float32 [D,170]", "n_options": "int16 [D]",
                   "label": "int16 [D]", "turn": "int16 [D]",
                   "game_id": "int32 [D]",
                   "opt_x": "float32 [sum(n_options),41], decision order; "
                            "offsets = cumsum(n_options)"},
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "decisions_requested": args.decisions,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2),
                                       encoding="utf-8")

    base, extra = divmod(args.decisions, args.workers)
    jobs = [(w, base + (1 if w < extra else 0), str(out_dir),
             args.shard_decisions)
            for w in range(args.workers) if base + (1 if w < extra else 0) > 0]
    t0 = time.perf_counter()
    if args.workers <= 1:
        results = [run_worker(jobs[0])]
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(run_worker, jobs))
    dt = time.perf_counter() - t0
    games = sum(r[0] for r in results)
    logged = sum(r[1] for r in results)
    stats = {k: sum(r[2][k] for r in results)
             for k in ("decisions", "searched", "changed")}
    pct = 100.0 * stats["changed"] / max(1, stats["searched"])
    print(f"DONE: {games} games, {logged} decisions in {dt/3600:.2f} h "
          f"({logged/dt:.1f} dec/s) -> {out_dir}", flush=True)
    print(f"teacher totals: {stats} (override rate {pct:.0f}% of searched)",
          flush=True)


if __name__ == "__main__":
    main()
