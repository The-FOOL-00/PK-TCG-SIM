"""Aggregate stats from local_eval JSONL decision logs.

Reads runs/<version>/<series>/game_*.jsonl and prints:
  - result distribution and prizes taken/lost
  - which option types / select contexts the agent picks most
  - first-attack turn number
  - decision time and fallback stats

Run:  python tools/replay_report.py            (latest series)
      python tools/replay_report.py --dir runs/<version>/<series>
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

OPTION_TYPE_NAMES = {
    0: "NUMBER", 1: "YES", 2: "NO", 3: "CARD", 4: "TOOL_CARD", 5: "ENERGY_CARD",
    6: "ENERGY", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY", 11: "DISCARD",
    12: "RETREAT", 13: "ATTACK", 14: "END", 15: "SKILL", 16: "SPECIAL_CONDITION",
}


def latest_series(root):
    dirs = [d for d in root.glob("*/*") if d.is_dir() and list(d.glob("game_*.jsonl"))]
    if not dirs:
        sys.exit(f"no JSONL logs found under {root}")
    return max(dirs, key=lambda d: d.stat().st_mtime)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=None, help="series dir with game_*.jsonl")
    args = ap.parse_args()
    series = args.dir or latest_series(REPO / "runs")

    games = {}
    for fp in sorted(series.glob("game_*.jsonl")):
        with open(fp, encoding="utf-8") as f:
            games[fp.name] = [json.loads(line) for line in f if line.strip()]
    if not games:
        sys.exit(f"no logs in {series}")

    n_dec = 0
    type_counts = Counter()
    ctx_counts = Counter()
    first_attack_turns = []
    results = Counter()
    prizes_taken = []
    prizes_lost = []
    fallbacks = 0
    ms_all = []

    for recs in games.values():
        my_moves = [r for r in recs if r.get("phase") == "move"]
        n_dec += len(my_moves)
        first_attack = None
        for r in my_moves:
            ms_all.append(r.get("ms", 0))
            if r.get("fallback"):
                fallbacks += 1
            ctx_counts[(r.get("select_type"), r.get("context"))] += 1
            for t in r.get("chosen_types") or []:
                type_counts[t] += 1
                if t == 13 and first_attack is None:
                    first_attack = r.get("turn")
        if first_attack is not None:
            first_attack_turns.append(first_attack)
        if recs:
            last = recs[-1]
            results[last.get("result")] += 1
            if last.get("my_prize") is not None:
                prizes_taken.append(6 - last["my_prize"])
                prizes_lost.append(6 - last["opp_prize"])

    print(f"series: {series}")
    print(f"games: {len(games)}   decisions: {n_dec}   fallbacks: {fallbacks}")
    print(f"results (our reward): {dict(results)}")
    if prizes_taken:
        print(f"avg prizes taken: {sum(prizes_taken) / len(prizes_taken):.2f}   "
              f"avg prizes lost: {sum(prizes_lost) / len(prizes_lost):.2f}")
    if first_attack_turns:
        print(f"first attack turn: avg {sum(first_attack_turns) / len(first_attack_turns):.1f} "
              f"min {min(first_attack_turns)} max {max(first_attack_turns)} "
              f"(in {len(first_attack_turns)}/{len(games)} games)")
    if ms_all:
        print(f"decision ms: avg {sum(ms_all) / len(ms_all):.3f}  max {max(ms_all):.3f}")
    print("chosen option types:")
    for t, k in type_counts.most_common():
        print(f"  {OPTION_TYPE_NAMES.get(t, t):18} {k:6d}  ({k / max(1, sum(type_counts.values())) * 100:.1f}%)")
    print("top select (type, context) situations:")
    for (st, ctx), k in ctx_counts.most_common(12):
        print(f"  select_type={st} context={ctx}: {k}")


if __name__ == "__main__":
    main()
