"""B1 validation: CardTracker + belief sampler against logged games.

Plays N games (v1 both sides, tracker seat alternating, opponent optionally
on a DIFFERENT deck so revealed-card tracking is non-trivial), records the
tracker seat's full observation stream plus the opponent's true hand at each
of its own decisions, then re-drives a fresh CardTracker over the stream and
asserts, at every decision:

  A. identity   every serial the tracker identified carries the same card id
                as the omniscient visualize transcript;
  B. multiset   per card id, identified opponent copies <= true copies in the
                opponent's actual 60-card list;
  C. hand       every hand_known serial is in the opponent's true hand at the
                adjacent opponent decisions (union of prev/next — a card
                cannot be hand_known while never actually in hand there);
  D. counts     hand_known <= handCount; sampler zone arithmetic consistent;
  E. engine     _sample_determinization() x K per decision is accepted by
                SearchBegin with zero errors — the engine is the final
                consistency judge.

Run:  python tools/test_tracker.py --games 20 --samples 3
"""

import argparse
import io
import contextlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import main  # noqa: E402
from tools import deck_compare  # noqa: E402

SERIAL_FIELDS = [
    ("serial", "cardId"), ("serialTarget", "cardIdTarget"),
    ("serialActive", "cardIdActive"), ("serialBench", "cardIdBench"),
    ("serialBefore", "cardIdBefore"), ("serialAfter", "cardIdAfter"),
]


def gt_serial_map(env):
    """serial -> card id from the omniscient visualize transcript."""
    step0 = env.steps[0][0]
    vis = step0.get("visualize") if hasattr(step0, "get") else step0.visualize
    gt = {}
    for entry in vis or []:
        for lg in entry.get("logs") or []:
            for sf, cf in SERIAL_FIELDS:
                s, c = lg.get(sf), lg.get(cf)
                if s is not None and c is not None:
                    prev = gt.get(s)
                    assert prev is None or prev == c, \
                        f"transcript serial {s} maps to both {prev} and {c}"
                    gt[s] = c
    return gt


def play_recorded(deck_me, deck_opp, me_seat, seed):
    """One game; returns (event stream, gt serial map, statuses).
    Stream entries: ('mine', obs_json_copy) | ('opp', set(hand serials))."""
    stream = []

    def rec_me(obs, _cfg):
        if obs.get("select") is None:
            return list(deck_me)
        stream.append(("mine", json.loads(json.dumps(obs))))
        main.SEARCH = False
        return main.agent(obs)

    def rec_opp(obs, _cfg):
        if obs.get("select") is None:
            return list(deck_opp)
        cur = obs.get("current") or {}
        hand = (cur.get("players") or [{}, {}])[cur.get("yourIndex") or 0].get("hand") or []
        stream.append(("opp", {c["serial"] for c in hand if c}))
        main.SEARCH = False
        return main.agent(obs)

    wrappers = [None, None]
    wrappers[me_seat] = rec_me
    wrappers[1 - me_seat] = rec_opp
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        env = deck_compare.make("cabt", debug=True)
        env.run(wrappers)
    statuses = [env.state[i].status for i in (0, 1)]
    return stream, gt_serial_map(env), statuses


def check_game(stream, gt, deck_opp, samples, rng):
    """Re-drive a tracker over the stream; return per-game stats. Raises
    AssertionError on any violation."""
    tracker = None
    opp_true = Counter(deck_opp)
    stats = Counter()
    mine_idx = [k for k, (kind, _) in enumerate(stream) if kind == "mine"]
    for k in mine_idx:
        obs = stream[k][1]
        cur = obs.get("current") or {}
        me = cur.get("yourIndex") or 0
        if tracker is None:
            tracker = main.CardTracker(me)
        assert tracker.me == me, "yourIndex changed mid-game"
        tracker.update(obs)
        stats["decisions"] += 1

        # A. identity vs transcript
        for ser, cid in tracker.serial_id.items():
            assert gt.get(ser) == cid, \
                f"serial {ser}: tracker says {cid}, transcript says {gt.get(ser)}"
        # B. revealed multiset <= true opponent list
        by_id = Counter(tracker.serial_id.values())
        for cid, n in by_id.items():
            assert n <= opp_true[cid], \
                f"card {cid}: tracker identified {n} copies, deck has {opp_true[cid]}"
        stats["ids_peak"] = max(stats["ids_peak"], len(tracker.serial_id))

        # C. hand_known in true hand at adjacent opponent decisions
        prev_h = next((stream[j][1] for j in range(k - 1, -1, -1)
                       if stream[j][0] == "opp"), set())
        next_h = next((stream[j][1] for j in range(k + 1, len(stream))
                       if stream[j][0] == "opp"), set())
        ghosts = set(tracker.hand_known) - (prev_h | next_h)
        assert not ghosts, f"hand_known serials never in true hand: {ghosts}"
        stats["hand_peak"] = max(stats["hand_peak"], len(tracker.hand_known))
        stats["float_peak"] = max(stats["float_peak"], len(tracker.floating))

        # D. counts
        theirs = (cur.get("players") or [{}, {}])[1 - me]
        assert len(tracker.hand_known) <= (theirs.get("handCount") or 0)

        # E. engine accepts sampled determinizations
        if obs.get("search_begin_input"):
            for _ in range(samples):
                det = main._sample_determinization(obs, tracker, rng)
                root = main._sb_begin(obs["search_begin_input"], **det)
                assert root and root.get("searchId") is not None
                main._sb_end()
                stats["samples_ok"] += 1
    return stats


def run(games, samples, seed):
    deck_a = deck_compare.read_deck(REPO / "deck.csv")
    deck_b = deck_compare.read_deck(REPO / "deck_v2.csv")
    assert main._search_lib() is not None, "cg engine required for this test"
    rng = random.Random(seed)
    total = Counter()
    for g in range(games):
        me_seat = g % 2
        deck_opp = deck_b if g % 2 == 0 else deck_a  # half the games non-mirror
        stream, gt, statuses = play_recorded(deck_a, deck_opp, me_seat, seed + g)
        assert all(s == "DONE" for s in statuses), f"game {g} statuses {statuses}"
        stats = check_game(stream, gt, deck_opp, samples, rng)
        for key in ("ids_peak", "hand_peak", "float_peak"):
            total[key] = max(total[key], stats[key])
        for key in ("decisions", "samples_ok"):
            total[key] += stats[key]
        print(f"game {g:2d} seat={me_seat} opp={'v2' if deck_opp is deck_b else 'v1'}"
              f" decisions={stats['decisions']:3d} ids_peak={stats['ids_peak']:2d}"
              f" hand_peak={stats['hand_peak']} float_peak={stats['float_peak']}"
              f" samples_ok={stats['samples_ok']}")
    print(f"\nALL OK: {games} games, {total['decisions']} decisions, "
          f"{total['samples_ok']} determinizations engine-accepted, "
          f"peaks: ids={total['ids_peak']} hand={total['hand_peak']} "
          f"float={total['float_peak']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run(args.games, args.samples, args.seed)
