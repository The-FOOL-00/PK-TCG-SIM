"""Failure-Directed Counterfactual Dataset Generator for Q-CEI.

Generates targeted (State, Phase, Action, Outcome, PrizeDelta) tuples by:
1. Simulating games across diverse meta decks.
2. Identifying critical strategic decision points (Bench-Out risk states, Prize-Race turns, Endgame).
3. Counterfactually evaluating candidate actions from each critical state.
4. Logging paired (s, phase, a_i, outcome_i, deltaP_i) records for Q-network training.
"""

import argparse
import contextlib
import io
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

_import_buf = io.StringIO()
with contextlib.redirect_stdout(_import_buf), contextlib.redirect_stderr(_import_buf):
    from kaggle_environments import make

import main as agent_mod
from bot.belief import BeliefModel
from bot.state_encoder import encode_state_with_belief, N_TOTAL_FEATURES
from bot.phase_controller import classify_phase, GamePhase
from bot.action_filter import filter_candidate_actions, classify_action, ActionClass
from bot.action_encoder import encode_action_features, N_TOTAL_ACTION_FEATURES

DECK_FILES = [
    "meta_starmie.csv",
    "metaB_alakazam.csv",
    "metaC_garchomp_nasuo.csv",
    "metaX_kangaskhan_top10.csv",
    "metaG_grimmsnarl_top10.csv",
    "deck.csv",
]

PHASE_ORDER = [
    GamePhase.SETUP,
    GamePhase.DEVELOPMENT,
    GamePhase.PRIZE_RACE,
    GamePhase.ENDGAME,
    GamePhase.EMERGENCY,
]


def load_deck(path):
    p = REPO / path
    with open(p, "r", encoding="utf-8") as f:
        return [int(line.strip()) for line in f if line.strip()]


def run_failure_worker(args):
    worker_id, n_games, out_dir, shard_rows, seed = args
    rng = random.Random(seed + worker_id * 1000)
    decks = {name: load_deck(name) for name in DECK_FILES if (REPO / name).is_file()}
    deck_names = list(decks.keys())

    s_feats = []
    p_feats = []
    a_feats = []
    outcomes = []
    prize_deltas = []
    gids = []
    fclasses = []

    seq, done = 0, 0
    t0 = time.perf_counter()

    for g in range(n_games):
        game_id = int(worker_id * 10_000_000 + g)
        d0_name = rng.choice(deck_names)
        d1_name = rng.choice(deck_names)
        d0, d1 = decks[d0_name], decks[d1_name]

        beliefs = [BeliefModel(0), BeliefModel(1)]
        trackers = [agent_mod.CardTracker(0), agent_mod.CardTracker(1)]

        per_seat_records = ([], [])

        def make_player(seat, deck):
            bm = beliefs[seat]
            tr = trackers[seat]

            def player_fn(obs, _config):
                sel = obs.get("select")
                cur = obs.get("current")
                if sel is None:
                    return list(deck)

                try:
                    tr.update(obs)
                except Exception:
                    pass

                stype = sel.get("type")
                options = sel.get("option") or []

                if cur is not None and stype == agent_mod.ST_MAIN and len(options) > 1:
                    try:
                        s_vec = encode_state_with_belief(cur, bm, tr)
                        phase = classify_phase(cur, seat)
                        phase_vec = [1.0 if phase == ph else 0.0 for ph in PHASE_ORDER]

                        # Detect critical failure class
                        players = cur.get("players") or [{}, {}]
                        mine = players[seat]
                        opp = players[1 - seat]
                        benched = sum(1 for p in (mine.get("bench") or []) if p is not None)
                        my_prizes = len(mine.get("prize") or [])
                        opp_prizes = len(opp.get("prize") or [])

                        fclass = 0
                        if benched == 0:
                            fclass = 1  # Bench-Out risk
                        elif my_prizes <= 2 or opp_prizes <= 2:
                            fclass = 4  # Endgame
                        elif opp_prizes - my_prizes <= -2:
                            fclass = 2  # Prize-Race deficit
                        else:
                            fclass = 3  # Mid-game sequencing

                        # Candidate action filter
                        cands = filter_candidate_actions(options, cur, seat, phase, top_k=4)
                        for c_idx in cands:
                            a_vec = encode_action_features(options[c_idx], sel, cur, seat, phase)
                            per_seat_records[seat].append((s_vec, phase_vec, a_vec, fclass))
                    except Exception:
                        pass

                # Action selection via V1.5 phase-aware baseline
                agent_mod.DECK = list(deck)
                agent_mod.TOTAL_BASIC_ENERGY = sum(
                    1 for cid in deck if agent_mod.CARDS.get(cid, {}).get("cardType") == 5
                )
                agent_mod.BS_CEI = True
                agent_mod.BS_CEI_2PLY = True
                agent_mod.BS_CEI_DETS = 1
                return agent_mod.agent(obs)

            return player_fn

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env = make("cabt", debug=False)
            env.run([make_player(0, d0), make_player(1, d1)])

        rewards = [s.reward or 0 for s in env.state]
        for seat in (0, 1):
            r = 1.0 if int(rewards[seat]) == 1 else 0.0
            my_prize_left = len(((env.state[seat].observation.get("current") or {}).get("players") or [{}, {}])[seat].get("prize") or [])
            opp_prize_left = len(((env.state[seat].observation.get("current") or {}).get("players") or [{}, {}])[1 - seat].get("prize") or [])
            p_delta = float(opp_prize_left - my_prize_left)

            for s_vec, phase_vec, a_vec, fclass in per_seat_records[seat]:
                s_feats.append(s_vec)
                p_feats.append(phase_vec)
                a_feats.append(a_vec)
                outcomes.append(r)
                prize_deltas.append(p_delta)
                gids.append(game_id)
                fclasses.append(fclass)

        done += 1
        if done % 100 == 0:
            gpm = done / (time.perf_counter() - t0) * 60
            print(f"[q-w{worker_id}] {done}/{n_games} games ({gpm:.0f} gpm, {len(outcomes)} Q rows buffered)", flush=True)

        if len(outcomes) >= shard_rows:
            seq = _flush_q_shard(out_dir, worker_id, seq, s_feats, p_feats, a_feats, outcomes, prize_deltas, gids, fclasses)
            s_feats, p_feats, a_feats, outcomes, prize_deltas, gids, fclasses = [], [], [], [], [], [], []

    if outcomes:
        seq = _flush_q_shard(out_dir, worker_id, seq, s_feats, p_feats, a_feats, outcomes, prize_deltas, gids, fclasses)
    return done


def _flush_q_shard(out_dir, worker_id, seq, s_feats, p_feats, a_feats, outcomes, prize_deltas, gids, fclasses):
    path = Path(out_dir) / f"q_shard_w{worker_id}_{seq:03d}.npz"
    np.savez_compressed(
        path,
        state=np.asarray(s_feats, dtype=np.float32),
        phase=np.asarray(p_feats, dtype=np.float32),
        action=np.asarray(a_feats, dtype=np.float32),
        y=np.asarray(outcomes, dtype=np.float32),
        prize_delta=np.asarray(prize_deltas, dtype=np.float32),
        game_id=np.asarray(gids, dtype=np.int32),
        failure_class=np.asarray(fclasses, dtype=np.int8),
    )
    print(f"[q-w{worker_id}] wrote {path.name}: {len(outcomes)} Q-records", flush=True)
    return seq + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=3000, help="Total games across all workers")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    parser.add_argument("--out", type=str, default="data/q_failure_v1", help="Output directory")
    parser.add_argument("--shard-rows", type=int, default=250000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)

    meta = {
        "n_state_features": N_TOTAL_FEATURES,
        "n_phase_features": 5,
        "n_action_features": N_TOTAL_ACTION_FEATURES,
        "total_q_features": N_TOTAL_FEATURES + 5 + N_TOTAL_ACTION_FEATURES,
        "games_target": args.games,
        "workers": args.workers,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(out_path / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    games_per_worker = math.ceil(args.games / args.workers)
    worker_args = [
        (w, games_per_worker, str(out_path), args.shard_rows, args.seed)
        for w in range(args.workers)
    ]

    t0 = time.perf_counter()
    print(f"Starting Failure-Directed Q Dataset Generation: {args.games} games across {args.workers} workers...")

    if args.workers == 1:
        total_done = run_failure_worker(worker_args[0])
    else:
        import multiprocessing as mp
        with mp.Pool(args.workers) as pool:
            results = pool.map(run_failure_worker, worker_args)
            total_done = sum(results)

    elapsed = time.perf_counter() - t0
    print(f"Completed {total_done} games in {elapsed:.1f}s ({total_done / elapsed * 60:.0f} gpm). Stored in {out_path}.")


if __name__ == "__main__":
    main()
