"""Stop 2b diagnostic: N-selection data for the draw-brake.

Replays the failing matchup (BC-v2 variant b vs v1-piloted Budew Crustle)
with a per-decision recorder on our seat: (turn, own deckCount, prizes
remaining both sides, selection type, chosen option type + card). Deck
consumption is attributed to the PREVIOUS chosen action via deckCount deltas
between consecutive decisions — an empirical "which MAIN actions shrink our
deck" table, plus the self-deckout trajectory histogram that picks N.

Run:  py -3.12 -X utf8 stage4/eval/brake_diag.py --games 100 --workers 6 \
          --json-out stage4/runs/brake_diag_b_vs_crustle.json
"""

import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools import ab_gate, deck_compare  # noqa: E402

REASONS = {1: "prizes", 2: "deckout", 3: "no-active", 4: "effect"}
CHAL = "stage4/deck_list0.csv+BC=list0_b+DYN_DECK_TABLES=true"
OPP = "stage4/deck_crustle_budew.csv"


def recording_wrapper(inner, rec):
    agent_mod = deck_compare.agent_mod

    def wrapper(obs, config):
        action = inner(obs, config)
        try:
            sel = obs.get("select")
            cur = obs.get("current")
            if sel is not None and cur is not None:
                me = cur.get("yourIndex")
                players = cur.get("players") or []
                mine = players[me] if me is not None and me < len(players) else {}
                theirs = players[1 - me] if me is not None else {}
                row = {
                    "turn": cur.get("turn"),
                    "deck": mine.get("deckCount"),
                    "my_prizes_left": len(mine.get("prize") or []),
                    "opp_prizes_left": len(theirs.get("prize") or []),
                    "stype": sel.get("type"),
                    "n_opt": len(sel.get("option") or []),
                    "chosen": None, "opt_type": None, "card": None,
                }
                if isinstance(action, list) and action \
                        and isinstance(action[0], int) \
                        and action[0] < row["n_opt"]:
                    row["chosen"] = action[0]
                    opt = sel["option"][action[0]]
                    row["opt_type"] = opt.get("type")
                    cid = None
                    try:
                        if opt.get("type") == 7:
                            cid = agent_mod._hand_card_id(cur, me, opt.get("index"))
                        else:
                            cid = agent_mod._option_card_id(opt, sel, cur, me)
                    except Exception:
                        pass
                    if cid is None and opt.get("type") == 10:
                        # ability: attribute to the ability's Pokemon if resolvable
                        try:
                            pk = agent_mod._pokemon_at(
                                cur, me, opt.get("inPlayArea"), opt.get("inPlayIndex"), me)
                            cid = (pk or {}).get("id")
                        except Exception:
                            pass
                    row["card"] = cid
                rec.append(row)
        except Exception:
            pass
        return action

    return wrapper


def play_chunk(args):
    n, seat_offset = args
    deck_c, attrs_c = ab_gate.parse_spec(CHAL)
    deck_o, attrs_o = ab_gate.parse_spec(OPP)
    deck_c = deck_compare.read_deck(REPO / deck_c)
    deck_o = deck_compare.read_deck(REPO / deck_o)
    agent_mod = deck_compare.agent_mod
    defaults = {name: getattr(agent_mod, name)
                for name in set(attrs_c) | set(attrs_o) if hasattr(agent_mod, name)}
    games = []
    for g in range(n):
        seat_c = (seat_offset + g) % 2
        rec = []
        wrappers = [None, None]
        wrappers[seat_c] = recording_wrapper(
            ab_gate.make_wrapper(deck_c, attrs_c, defaults), rec)
        wrappers[1 - seat_c] = ab_gate.make_wrapper(deck_o, attrs_o, defaults)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)
        ev = deck_compare.game_events(env)
        res = ev["result"] or {}
        games.append({
            "reward": env.state[seat_c].reward,
            "reason": REASONS.get(res.get("reason"), str(res.get("reason"))),
            "decisions": rec,
        })
    return games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--json-out", default="stage4/runs/brake_diag_b_vs_crustle.json")
    args = ap.parse_args()

    if args.workers <= 1:
        games = play_chunk((args.games, 0))
    else:
        from concurrent.futures import ProcessPoolExecutor
        base, extra = divmod(args.games, args.workers)
        jobs, off = [], 0
        for w in range(args.workers):
            k = base + (1 if w < extra else 0)
            if k:
                jobs.append((k, off % 2))
                off += k
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            games = [g for ch in ex.map(play_chunk, jobs) for g in ch]

    out = REPO / args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(games), encoding="utf-8")
    w = sum(1 for g in games if g["reward"] == 1)
    sd = sum(1 for g in games if g["reward"] == -1 and g["reason"] == "deckout")
    print(f"{len(games)} games: {w}W, self-deckouts {sd}  -> {out}")


if __name__ == "__main__":
    main()
