"""Local evaluation harness for the PTCG agent.

Runs N games of our agent vs itself and/or the built-in baseline agents via
kaggle_environments make("cabt"). Decks are supplied by each agent's answer
to the deck-selection call (verified: configuration={"decks": ...} is ignored
by the cabt interpreter).

Outputs per series:
  - W/L/D, average game length (turns), decision time avg/max/p99
  - fallback-exception count (must be 0) and crash (INVALID/ERROR) count
  - runs/<AGENT_VERSION>/<timestamp>-<opponent>/game_NNN.jsonl decision logs
  - replay JSON for game 1 (env.toJSON()); HTML render only if non-empty

Run:  python tools/local_eval.py --games 30 --opponent all
"""

import argparse
import contextlib
import datetime
import io
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

_import_buf = io.StringIO()
try:
    with contextlib.redirect_stdout(_import_buf), contextlib.redirect_stderr(_import_buf):
        from kaggle_environments import make
except Exception:
    print(_import_buf.getvalue(), file=sys.stderr)
    raise

import main as agent_mod


def _percentile(sorted_values, pct):
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(round(pct / 100.0 * (len(sorted_values) - 1))))
    return sorted_values[idx]


def run_series(games, opponent, tag=None, out_root=None):
    """Play `games` games vs `opponent` ('self', 'random' or 'first')."""
    out_root = Path(out_root) if out_root else REPO / "runs"
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = tag or ts
    out_dir = out_root / agent_mod.AGENT_VERSION / f"{label}-vs-{opponent}"
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []

    def wrapper(obs, _config):
        action = agent_mod.agent(obs)
        rec = dict(agent_mod.LAST_INFO)
        records.append(rec)
        return action

    wins = losses = draws = crashes = 0
    fallbacks_before = agent_mod.STATS["fallbacks"]
    turns_per_game = []
    all_ms = []
    prizes_taken = []
    prizes_lost = []
    t_series = time.perf_counter()

    for g in range(games):
        our_seat = 0 if opponent == "self" else g % 2
        if opponent == "self":
            agents = [wrapper, wrapper]
        else:
            agents = [wrapper, opponent] if our_seat == 0 else [opponent, wrapper]

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = make("cabt", debug=True)
            game_start = len(records)
            env.run(agents)
        noise = buf.getvalue()
        if "Traceback" in noise:
            print(noise, file=sys.stderr)

        game_records = records[game_start:]
        statuses = [s.status for s in env.state]
        rewards = [s.reward for s in env.state]
        if statuses[our_seat] in ("INVALID", "ERROR", "TIMEOUT") or (
                opponent == "self" and any(st in ("INVALID", "ERROR", "TIMEOUT") for st in statuses)):
            crashes += 1
        r = rewards[our_seat]
        if r == 1:
            wins += 1
        elif r == -1:
            losses += 1
        else:
            draws += 1

        move_turns = [rec["turn"] for rec in game_records if rec.get("turn")]
        turns_per_game.append(max(move_turns) if move_turns else 0)
        all_ms.extend(rec["ms"] for rec in game_records if "ms" in rec)
        end_recs = [rec for rec in game_records if rec.get("my_prize") is not None]
        if end_recs:
            last = end_recs[-1]
            prizes_taken.append(6 - last["my_prize"])   # we take OUR prizes on opposing KOs
            prizes_lost.append(6 - last["opp_prize"])

        log_path = out_dir / f"game_{g:03d}.jsonl"
        with open(log_path, "w", encoding="utf-8") as f:
            for rec in game_records:
                rec2 = dict(rec)
                rec2["game"] = g
                rec2["opponent"] = opponent
                rec2["result"] = int(r) if r is not None else None
                f.write(json.dumps(rec2) + "\n")

        if g == 0:
            try:
                (out_dir / "replay_game000.json").write_text(env.toJSON() if isinstance(
                    env.toJSON(), str) else json.dumps(env.toJSON()), encoding="utf-8")
            except Exception as e:
                print(f"replay save failed: {e}", file=sys.stderr)
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    html = env.render(mode="html")
                if html and len(html) > 100:
                    (out_dir / "replay_game000.html").write_text(html, encoding="utf-8")
            except Exception:
                pass

    wall = time.perf_counter() - t_series
    fallbacks = agent_mod.STATS["fallbacks"] - fallbacks_before
    ms_sorted = sorted(all_ms)
    summary = {
        "opponent": opponent,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crashes": crashes,
        "fallbacks": fallbacks,
        "avg_turns": round(sum(turns_per_game) / len(turns_per_game), 1) if turns_per_game else 0,
        "decisions": len(all_ms),
        "avg_ms": round(sum(all_ms) / len(all_ms), 3) if all_ms else 0,
        "max_ms": round(max(all_ms), 3) if all_ms else 0,
        "p99_ms": round(_percentile(ms_sorted, 99), 3),
        "avg_prizes_taken": round(sum(prizes_taken) / len(prizes_taken), 2) if prizes_taken else None,
        "avg_prizes_lost": round(sum(prizes_lost) / len(prizes_lost), 2) if prizes_lost else None,
        "wall_s": round(wall, 1),
        "log_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def print_summary(s):
    print(f"--- vs {s['opponent']} ({s['games']} games) ---")
    print(f"  W/L/D             : {s['wins']}/{s['losses']}/{s['draws']}"
          f"  (win rate {s['wins'] / s['games'] * 100:.0f}%)")
    print(f"  crashes           : {s['crashes']}   fallbacks: {s['fallbacks']}")
    print(f"  avg game length   : {s['avg_turns']} turns")
    print(f"  decision time (ms): avg {s['avg_ms']}  p99 {s['p99_ms']}  max {s['max_ms']}"
          f"  over {s['decisions']} decisions")
    print(f"  prizes taken/lost : {s['avg_prizes_taken']} / {s['avg_prizes_lost']}")
    print(f"  wall time         : {s['wall_s']}s   logs: {s['log_dir']}")


def main():
    ap = argparse.ArgumentParser(description="Local eval for the PTCG agent")
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--opponent", choices=["self", "random", "first", "all"], default="all")
    args = ap.parse_args()

    opponents = ["self", "random"] if args.opponent == "all" else [args.opponent]
    print(f"agent version: {agent_mod.AGENT_VERSION}")
    exit_code = 0
    for opp in opponents:
        s = run_series(args.games, opp)
        print_summary(s)
        if s["crashes"] or s["fallbacks"]:
            exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
