"""Generate BS-CEI balanced self-play training data with hard-state oversampling.

Runs multi-process CABT games across diverse meta decks and policy configurations:
- Mega Starmie ex (Aggro)
- Alakazam (Control / Stall)
- Cynthia's Garchomp ex (Setup Midrange)
- Mega Kangaskhan ex (Energy Acceleration)
- Marnie's Grimmsnarl ex (Disruption)
- Abomasnow (Baseline)

Logs 194-dim state + belief feature vectors, game outcome (+1/-1/0), prize delta,
deckout indicator, turn number, and game ID.

Deliberately oversamples hard states (thin deck <= 10, endgame prizes <= 2,
prize deficit, long stall turns) to eliminate the BC self-deckout failure mode.
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
from collections import Counter
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

DECK_FILES = [
    "meta_starmie.csv",
    "metaB_alakazam.csv",
    "metaC_garchomp_nasuo.csv",
    "metaX_kangaskhan_top10.csv",
    "metaG_grimmsnarl_top10.csv",
    "deck.csv",
]


def load_deck(path):
    p = REPO / path
    with open(p, "r", encoding="utf-8") as f:
        return [int(line.strip()) for line in f if line.strip()]


def run_worker(args):
    worker_id, n_games, out_dir, shard_rows, seed = args
    rng = random.Random(seed + worker_id * 1000)
    decks = {name: load_deck(name) for name in DECK_FILES if (REPO / name).is_file()}
    deck_names = list(decks.keys())

    feats = []
    outs = []
    prize_deltas = []
    deckouts = []
    turns = []
    gids = []
    hard_flags = []

    seq, done = 0, 0
    t0 = time.perf_counter()

    for g in range(n_games):
        game_id = int(worker_id * 10_000_000 + g)
        deck0_name = rng.choice(deck_names)
        deck1_name = rng.choice(deck_names)
        deck0, deck1 = decks[deck0_name], decks[deck1_name]

        # Policy variations: Heuristic, Expectimax, or Defensive/Stall
        policy_mode0 = rng.choice(["expectimax", "v1", "v1", "stall" if "alakazam" in deck0_name else "v1"])
        policy_mode1 = rng.choice(["expectimax", "v1", "v1", "stall" if "alakazam" in deck1_name else "v1"])

        beliefs = [BeliefModel(0), BeliefModel(1)]
        trackers = [agent_mod.CardTracker(0), agent_mod.CardTracker(1)]

        per_seat_records = ([], [])

        def make_player(seat, deck, policy_mode):
            bm = beliefs[seat]
            tr = trackers[seat]

            def player_fn(obs, _config):
                sel = obs.get("select")
                cur = obs.get("current")
                if sel is None:
                    return list(deck)

                # Update belief & tracker
                try:
                    tr.update(obs)
                except Exception:
                    pass

                if cur is not None:
                    try:
                        vec = encode_state_with_belief(cur, bm, tr)
                        turn_num = cur.get("turn") or 0
                        mine = (cur.get("players") or [{}, {}])[seat]
                        opp = (cur.get("players") or [{}, {}])[1 - seat]
                        my_deck = mine.get("deckCount") or 0
                        my_prizes = len(mine.get("prize") or [])
                        opp_prizes = len(opp.get("prize") or [])

                        # Classify if this is a critical hard-state
                        is_hard = bool(
                            my_deck <= 10
                            or (my_prizes <= 2 and opp_prizes <= 2)
                            or (opp_prizes - my_prizes <= -2)
                            or turn_num >= 15
                        )
                        per_seat_records[seat].append((vec, turn_num, is_hard))
                    except Exception:
                        pass

                # Execute action based on policy mode
                agent_mod.DECK = list(deck)
                agent_mod.TOTAL_BASIC_ENERGY = sum(
                    1 for cid in deck if agent_mod.CARDS.get(cid, {}).get("cardType") == 5
                )
                agent_mod.EXPECTIMAX = (policy_mode == "expectimax")
                return agent_mod.agent(obs)

            return player_fn

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env = make("cabt", debug=False)
            env.run([make_player(0, deck0, policy_mode0), make_player(1, deck1, policy_mode1)])

        # Process end of game labels
        rewards = [s.reward or 0 for s in env.state]
        for seat in (0, 1):
            r = int(rewards[seat])
            opp_r = int(rewards[1 - seat])
            my_prize_left = len(((env.state[seat].observation.get("current") or {}).get("players") or [{}, {}])[seat].get("prize") or [])
            opp_prize_left = len(((env.state[seat].observation.get("current") or {}).get("players") or [{}, {}])[1 - seat].get("prize") or [])
            p_delta = float(opp_prize_left - my_prize_left)
            # Check deckout loss
            my_deck_end = ((env.state[seat].observation.get("current") or {}).get("players") or [{}, {}])[seat].get("deckCount") or 0
            is_deckout = 1 if (r == -1 and my_deck_end <= 0) else 0

            for vec, turn_num, is_hard in per_seat_records[seat]:
                feats.append(vec)
                outs.append(r)
                prize_deltas.append(p_delta)
                deckouts.append(is_deckout)
                turns.append(turn_num)
                gids.append(game_id)
                hard_flags.append(is_hard)

        done += 1
        if done % 100 == 0:
            gpm = done / (time.perf_counter() - t0) * 60
            print(f"[w{worker_id}] {done}/{n_games} games ({gpm:.0f} games/min, {len(outs)} rows buffered)", flush=True)

        if len(outs) >= shard_rows:
            seq = _flush_shard(out_dir, worker_id, seq, feats, outs, prize_deltas, deckouts, turns, gids, hard_flags)
            feats, outs, prize_deltas, deckouts, turns, gids, hard_flags = [], [], [], [], [], [], []

    if outs:
        seq = _flush_shard(out_dir, worker_id, seq, feats, outs, prize_deltas, deckouts, turns, gids, hard_flags)
    return done


def _flush_shard(out_dir, worker_id, seq, feats, outs, prize_deltas, deckouts, turns, gids, hard_flags):
    path = Path(out_dir) / f"shard_w{worker_id}_{seq:03d}.npz"
    np.savez_compressed(
        path,
        x=np.asarray(feats, dtype=np.float32),
        y=np.asarray(outs, dtype=np.int8),
        prize_delta=np.asarray(prize_deltas, dtype=np.float32),
        deckout=np.asarray(deckouts, dtype=np.int8),
        turn=np.asarray(turns, dtype=np.int16),
        game_id=np.asarray(gids, dtype=np.int32),
        hard=np.asarray(hard_flags, dtype=bool),
    )
    print(f"[w{worker_id}] wrote {path.name}: {len(outs)} rows ({sum(hard_flags)} hard)", flush=True)
    return seq + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=5000, help="Total games across all workers")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--out", type=str, default="data/bs_cei_v1", help="Output directory for .npz shards")
    parser.add_argument("--shard-rows", type=int, default=250000, help="Rows per shard file")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)

    meta = {
        "n_features": N_TOTAL_FEATURES,
        "games_target": args.games,
        "workers": args.workers,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_pool": DECK_FILES,
    }
    with open(out_path / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    games_per_worker = math.ceil(args.games / args.workers)
    worker_args = [
        (w, games_per_worker, str(out_path), args.shard_rows, args.seed)
        for w in range(args.workers)
    ]

    t0 = time.perf_counter()
    print(f"Starting BS-CEI balanced data generation: {args.games} games across {args.workers} workers...")

    if args.workers == 1:
        total_done = run_worker(worker_args[0])
    else:
        import multiprocessing as mp
        with mp.Pool(args.workers) as pool:
            results = pool.map(run_worker, worker_args)
            total_done = sum(results)

    elapsed = time.perf_counter() - t0
    print(f"Completed {total_done} games in {elapsed:.1f}s ({total_done / elapsed * 60:.0f} games/min). Data stored in {out_path}.")


if __name__ == "__main__":
    main()
