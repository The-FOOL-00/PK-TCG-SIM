"""Stage 4 Stop-2 behavioral probes: C1/C2 expression tests.

Plays N games of a challenger spec vs an opponent spec (ab_gate spec syntax)
and logs per-game outcome, end reason, and final turn — the metrics that
distinguish "knows the line" from "expresses the line":

  C2 (vs Crustle stall): loss-by-deckout = self-deckout pathology;
      win-by-prizes turn distribution = the race-to-T12 line.
  C1 (vs Lucario aggro): survival = games reaching T12+, prizes conceded.

Run:
  py -3.12 -X utf8 stage4/eval/behavior_probe.py \
      --challenger stage4/deck_list0.csv+BC=list0_b+DYN_DECK_TABLES=true \
      --opponent stage4/deck_crustle_budew.csv --games 100 --workers 6 \
      --json-out stage4/runs/probe_b_vs_crustle.json
"""

import argparse
import contextlib
import io
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools import ab_gate, deck_compare  # noqa: E402

REASONS = {1: "prizes", 2: "deckout", 3: "no-active", 4: "effect"}


def play_chunk(args):
    deck_c, attrs_c, deck_o, attrs_o, n, seat_offset = args
    agent_mod = deck_compare.agent_mod
    defaults = {name: getattr(agent_mod, name)
                for name in set(attrs_c) | set(attrs_o) if hasattr(agent_mod, name)}
    games = []
    for g in range(n):
        seat_c = (seat_offset + g) % 2
        wrappers = [None, None]
        wrappers[seat_c] = ab_gate.make_wrapper(deck_c, attrs_c, defaults)
        wrappers[1 - seat_c] = ab_gate.make_wrapper(deck_o, attrs_o, defaults)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)
        ev = deck_compare.game_events(env)
        res = ev["result"] or {}
        last_turn = 0
        vis0 = env.steps[0][0].get("visualize")
        for entry in vis0 or []:
            cur = entry.get("current") or {}
            last_turn = max(last_turn, cur.get("turn") or 0)
        games.append({
            "reward": env.state[seat_c].reward,
            "status": env.state[seat_c].status,
            "reason": REASONS.get(res.get("reason"), str(res.get("reason"))),
            "turns": last_turn,
            "our_prizes": ev["kos"].get(seat_c, 0),
            "opp_prizes": ev["kos"].get(1 - seat_c, 0),
        })
    return games


def run(spec_c, spec_o, n_games, workers):
    deck_c, attrs_c = ab_gate.parse_spec(spec_c)
    deck_o, attrs_o = ab_gate.parse_spec(spec_o)
    deck_c = deck_compare.read_deck(REPO / deck_c)
    deck_o = deck_compare.read_deck(REPO / deck_o)
    if workers <= 1:
        games = play_chunk((deck_c, attrs_c, deck_o, attrs_o, n_games, 0))
    else:
        from concurrent.futures import ProcessPoolExecutor
        base, extra = divmod(n_games, workers)
        jobs, off = [], 0
        for w in range(workers):
            k = base + (1 if w < extra else 0)
            if k:
                jobs.append((deck_c, attrs_c, deck_o, attrs_o, k, off % 2))
                off += k
        with ProcessPoolExecutor(max_workers=workers) as ex:
            games = [g for ch in ex.map(play_chunk, jobs) for g in ch]
    return games


def summarize(games, label):
    wins = [g for g in games if g["reward"] == 1]
    losses = [g for g in games if g["reward"] == -1]
    crash = sum(1 for g in games if g["status"] in ("INVALID", "ERROR", "TIMEOUT"))
    wr = Counter(g["reason"] for g in wins)
    lr = Counter(g["reason"] for g in losses)
    wt = [g["turns"] for g in wins if g["turns"]]
    lt = [g["turns"] for g in losses if g["turns"]]
    out = {
        "label": label, "games": len(games),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / max(1, len(wins) + len(losses)), 3),
        "crashes": crash,
        "win_reasons": dict(wr), "loss_reasons": dict(lr),
        "win_turns_median": st.median(wt) if wt else None,
        "loss_turns_median": st.median(lt) if lt else None,
        "wins_by_T12": sum(1 for g in wins if g["turns"] and g["turns"] <= 12),
        "self_deckout_losses": lr.get("deckout", 0),
    }
    print(f"[{label}] {out['wins']}W-{out['losses']}L ({out['win_rate']*100:.0f}%)"
          f"  crashes {crash}")
    print(f"   win by {dict(wr)}  median win turn {out['win_turns_median']}"
          f"  (<=T12: {out['wins_by_T12']})")
    print(f"   loss by {dict(lr)}  median loss turn {out['loss_turns_median']}"
          f"  SELF-DECKOUTS: {out['self_deckout_losses']}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", required=True)
    ap.add_argument("--opponent", required=True)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--label", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    games = run(args.challenger, args.opponent, args.games, args.workers)
    s = summarize(games, args.label or f"{args.challenger} vs {args.opponent}")
    if args.json_out:
        p = REPO / args.json_out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"summary": s, "games": games}, indent=1),
                     encoding="utf-8")
        print("json ->", p)
