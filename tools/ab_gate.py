"""Standard A/B gate: challenger vs incumbent. Nothing ships without a PASS.

Protocol (fixed — every comparison goes through this tool):
  - >= 300 games, seats alternated every game.
  - Win rate reported with a 95% Wilson score interval (draws excluded from
    the CI, reported separately).
  - Verdict PASS only if the CI lower bound is strictly > 50% vs the incumbent.
  - Any INVALID/ERROR/TIMEOUT status is counted and reported (P0 if nonzero).

Agent specs name a deck plus optional policy flags, '+'-separated:
    deck.csv                 v1 heuristic policy, this deck
    deck.csv+v3              PTCG_V3_EVAL evaluator on
    deck.csv+NAME=VALUE      set any main.py module attribute per call
                             (forward-compat: learned value / distilled nets)

Run:  python tools/ab_gate.py --challenger deck.csv+v3 --incumbent deck.csv \
          --games 300 --workers 6 --json-out runs/gate_v3_vs_v1.json
"""

import argparse
import contextlib
import io
import json
import math
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import deck_compare  # noqa: E402  (engine import lives there)

GATE_MIN_GAMES = 300
Z95 = 1.959963984540054


def parse_spec(spec):
    """'deck.csv+v3+FOO=2' -> (deck_path, {attr: value})."""
    parts = spec.split("+")
    deck_path, attrs = parts[0], {}
    for tok in parts[1:]:
        if tok == "v3":
            attrs["V3_EVAL"] = True
        elif "=" in tok:
            name, val = tok.split("=", 1)
            for cast in (int, float):
                try:
                    val = cast(val)
                    break
                except ValueError:
                    continue
            else:
                val = {"true": True, "false": False}.get(str(val).lower(), val)
            attrs[name] = val
        else:
            raise SystemExit(f"bad spec token {tok!r} in {spec!r}")
    return deck_path, attrs


def make_wrapper(deck, attrs, defaults):
    """Same contract as deck_compare.make_wrapper, generalized to any attrs.

    `defaults` holds the module-default value for every attr EITHER side
    touches — each call resets them all first, so one side's flags can't
    leak into the other side's turns (both seats share the module).
    """
    agent_mod = deck_compare.agent_mod
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)

    def wrapper(obs, _config):
        if obs.get("select") is None:
            return list(deck)
        agent_mod.TOTAL_BASIC_ENERGY = n_energy
        for name, val in defaults.items():
            setattr(agent_mod, name, val)
        for name, val in attrs.items():
            setattr(agent_mod, name, val)
        return agent_mod.agent(obs)
    return wrapper


def play_chunk(args):
    """Worker: play n games; challenger takes seat (seat_offset+g) % 2.

    Returns tallies keyed 'chal'/'inc': wins split by the seat the winner sat
    in, loss/win reasons, crash statuses.
    """
    deck_c, attrs_c, deck_i, attrs_i, n, seat_offset = args
    agent_mod = deck_compare.agent_mod
    defaults = {name: getattr(agent_mod, name)
                for name in set(attrs_c) | set(attrs_i) if hasattr(agent_mod, name)}
    out = {
        s: {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
            "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0}
        for s in ("chal", "inc")
    }
    for g in range(n):
        seat_c = (seat_offset + g) % 2
        wrappers = [None, None]
        wrappers[seat_c] = make_wrapper(deck_c, attrs_c, defaults)
        wrappers[1 - seat_c] = make_wrapper(deck_i, attrs_i, defaults)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)
        ev = deck_compare.game_events(env)
        reason = (ev["result"] or {}).get("reason")
        for side, seat in (("chal", seat_c), ("inc", 1 - seat_c)):
            st = out[side]
            if env.state[seat].status in ("INVALID", "ERROR", "TIMEOUT"):
                st["crashes"] += 1
            r = env.state[seat].reward
            if r == 1:
                st[f"wins_seat{seat}"] += 1
                st["reasons_won"][reason] += 1
            elif r == -1:
                st["losses"] += 1
                st["reasons_lost"][reason] += 1
            else:
                st["draws"] += 1
    return out


def wilson(wins, n, z=Z95):
    """95% Wilson score interval for wins/n. Returns (p, lo, hi)."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def run_gate(spec_c, spec_i, games, workers):
    deck_c, attrs_c = parse_spec(spec_c)
    deck_i, attrs_i = parse_spec(spec_i)
    deck_c = deck_compare.read_deck(REPO / deck_c)
    deck_i = deck_compare.read_deck(REPO / deck_i)

    if workers <= 1:
        chunks = [play_chunk((deck_c, attrs_c, deck_i, attrs_i, games, 0))]
    else:
        from concurrent.futures import ProcessPoolExecutor
        base, extra = divmod(games, workers)
        # even-sized chunks with seat offsets that keep global seat balance
        jobs, offset = [], 0
        for w in range(workers):
            n = base + (1 if w < extra else 0)
            if n:
                jobs.append((deck_c, attrs_c, deck_i, attrs_i, n, offset % 2))
                offset += n
        with ProcessPoolExecutor(max_workers=workers) as ex:
            chunks = list(ex.map(play_chunk, jobs))

    total = {
        s: {"wins_seat0": 0, "wins_seat1": 0, "losses": 0, "draws": 0,
            "reasons_won": Counter(), "reasons_lost": Counter(), "crashes": 0}
        for s in ("chal", "inc")
    }
    for ch in chunks:
        for s in total:
            for k, v in ch[s].items():
                total[s][k] += v
    return total


def report(spec_c, spec_i, games, total, json_out=None, note=None):
    st = total["chal"]
    wins = st["wins_seat0"] + st["wins_seat1"]
    losses, draws = st["losses"], st["draws"]
    decided = wins + losses
    p, lo, hi = wilson(wins, decided)
    crashes = {s: total[s]["crashes"] for s in ("chal", "inc")}
    verdict = "PASS" if (lo > 0.5 and games >= GATE_MIN_GAMES) else "FAIL"

    print("=" * 64)
    print("AB GATE")
    print(f"  challenger : {spec_c}")
    print(f"  incumbent  : {spec_i}")
    print(f"  games      : {games} (seats alternated)"
          + (f"  [WARNING: below {GATE_MIN_GAMES}-game minimum]"
             if games < GATE_MIN_GAMES else ""))
    print(f"  W/L/D      : {wins}/{losses}/{draws}"
          f"   (challenger seat0 wins {st['wins_seat0']},"
          f" seat1 wins {st['wins_seat1']})")
    print(f"  win rate   : {p*100:.1f}%   95% Wilson CI [{lo*100:.1f}%, {hi*100:.1f}%]")
    print(f"  win reasons: {dict(st['reasons_won'])}  "
          f"loss reasons: {dict(st['reasons_lost'])}  "
          f"(1=prizes 2=deckout 3=no-active 4=effect)")
    print(f"  crashes    : challenger {crashes['chal']}, incumbent {crashes['inc']}"
          + ("   <-- P0: INVALID/ERROR/TIMEOUT must be zero"
             if any(crashes.values()) else ""))
    print(f"  VERDICT    : {verdict} "
          f"(CI lower bound {lo*100:.1f}% {'>' if lo > 0.5 else '<='} 50%)")
    if note:
        print(f"  note       : {note}")
    print("=" * 64)

    if json_out:
        payload = {
            "challenger": spec_c, "incumbent": spec_i, "games": games,
            "wins": wins, "losses": losses, "draws": draws,
            "wins_by_seat": [st["wins_seat0"], st["wins_seat1"]],
            "win_rate": p, "wilson95": [lo, hi], "verdict": verdict,
            "crashes": crashes,
            "reasons_won": dict(st["reasons_won"]),
            "reasons_lost": dict(st["reasons_lost"]),
        }
        Path(json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"json written: {json_out}")
    return verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", required=True, help="e.g. deck.csv+v3")
    ap.add_argument("--incumbent", required=True, help="e.g. deck.csv")
    ap.add_argument("--games", type=int, default=GATE_MIN_GAMES)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    total = run_gate(args.challenger, args.incumbent, args.games, args.workers)
    report(args.challenger, args.incumbent, args.games, total, args.json_out)


if __name__ == "__main__":
    main()
