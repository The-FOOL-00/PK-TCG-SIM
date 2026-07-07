"""Hill-climb the v3 evaluator weights: v3 policy vs v1 policy, same deck.

One round = evaluate the current config plus x0.5 / x2 for each tuned weight
(one at a time), N games each. Move to the best neighbor if it beats the
center; stop after --rounds or when the center is best. Finish with a
--confirm-games run of the winner.

Run:  python tools/tune_v3.py --games 100 --rounds 2 --confirm-games 200
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import deck_compare
import main as agent_mod

TUNED = ["V3_W_ACTIVE", "V3_W_ATTACKER_ENERGY", "V3_W_PRIZE", "V3_W_KO_THREAT"]


def set_config(cfg):
    for k, v in cfg.items():
        setattr(agent_mod, k, v)


def win_rate(cfg, deck, games):
    set_config(cfg)
    stats, _turns = deck_compare.run_compare(deck, deck, games, "v3", "v1",
                                             v3_a=True, v3_b=False)
    st = stats["v3"]
    if st["crashes"]:
        print(f"  WARNING: {st['crashes']} crashes with {cfg}", flush=True)
    return st["wins"] / max(1, st["wins"] + st["losses"] + st["draws"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--confirm-games", type=int, default=200)
    ap.add_argument("--deck", default="deck.csv")
    ap.add_argument("--json-out", default="runs/tune_v3.json")
    args = ap.parse_args()

    deck = deck_compare.read_deck(REPO / args.deck)
    center = {k: getattr(agent_mod, k) for k in TUNED}
    history = []

    wr_center = win_rate(center, deck, args.games)
    print(f"center {center} -> {wr_center:.1%}", flush=True)
    history.append({"config": dict(center), "games": args.games, "win_rate": wr_center})

    for r in range(args.rounds):
        best_cfg, best_wr = center, wr_center
        for k in TUNED:
            for mult in (0.5, 2.0):
                cfg = dict(center)
                cfg[k] = center[k] * mult
                wr = win_rate(cfg, deck, args.games)
                print(f"round {r+1}: {k} x{mult} ({cfg[k]:g}) -> {wr:.1%}", flush=True)
                history.append({"config": dict(cfg), "games": args.games, "win_rate": wr})
                if wr > best_wr:
                    best_cfg, best_wr = cfg, wr
        if best_cfg is center:
            print(f"round {r+1}: center is best ({best_wr:.1%}), stopping", flush=True)
            break
        center, wr_center = best_cfg, best_wr
        print(f"round {r+1}: moved to {center} ({wr_center:.1%})", flush=True)

    wr_final = win_rate(center, deck, args.confirm_games)
    print(f"CONFIRM {args.confirm_games} games: {center} -> {wr_final:.1%}", flush=True)
    history.append({"config": dict(center), "games": args.confirm_games,
                    "win_rate": wr_final, "confirm": True})
    Path(REPO / args.json_out).write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"history written: {args.json_out}", flush=True)


if __name__ == "__main__":
    main()
