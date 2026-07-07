"""A/B compare two deck lists with the SAME agent policy on both sides.

The agent's policy logic is untouched: each wrapper only overrides the answer
to the deck-selection call (obs["select"] is None), which is the one place
decks enter the game (verified: configuration decks are ignored by cabt).

Per side it reports: win rate, game-end reason distribution (from the
'visualize' transcript: reason 1=prizes 2=deckout 3=no-active 4=effect),
mulligan rate, Hammer-lanche damage stats, KOs and energy attaches per game.

Run:  python tools/deck_compare.py --deck-a deck_v2.csv --deck-b deck.csv --games 50
      python tools/deck_compare.py --deck-a deck.csv --deck-b deck.csv --games 50   (baseline)
"""

import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
    from kaggle_environments import make

import main as agent_mod

HAMMER_LANCHE_ID = 1046
BASIC_WATER_ID = 3


def read_deck(path):
    with open(path, "r") as f:
        return [int(line.strip()) for line in f if line.strip()]


def make_wrapper(deck, v3=False):
    # TOTAL_BASIC_ENERGY feeds the Hammer-lanche deck-density estimate; it is
    # baked from deck.csv at import, so re-point it at THIS side's deck per
    # call (both seats share the module). Harness fairness fix, not policy.
    # V3_EVAL likewise toggles the evaluator policy for THIS side only.
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)

    def wrapper(obs, _config):
        if obs.get("select") is None:
            return list(deck)
        agent_mod.TOTAL_BASIC_ENERGY = n_energy
        agent_mod.V3_EVAL = v3
        return agent_mod.agent(obs)
    return wrapper


def game_events(env):
    """Parse the full-game transcript from steps[0][0].visualize.

    Log 'type' values are string enum names in the visualize stream.
    Returns per-player event tallies plus the game-end Result log.
    """
    step0 = env.steps[0][0]
    vis = step0.get("visualize") if hasattr(step0, "get") else step0.visualize
    ev = {
        "result": None,          # {'result': winner index or 2=draw, 'reason': 1..4}
        "mulligans": Counter(),  # playerIndex -> count of no-Basic redraws
        "hammer_dmg": {0: [], 1: []},   # damage dealt per Hammer-lanche use
        "kos": Counter(),        # playerIndex -> opposing KOs (their prize takes)
        "energy_attach": Counter(),     # playerIndex -> basic water attaches
        "attacks": {0: Counter(), 1: Counter()},
    }
    pending_hammer = None  # (playerIndex,) waiting for the HpChange that follows
    for entry in vis or []:
        for l in entry.get("logs") or []:
            t = l.get("type")
            pi = l.get("playerIndex")
            if t == "Result":
                ev["result"] = {"result": l.get("result"), "reason": l.get("reason")}
            elif t == "HasBasicPokemon" and l.get("hasBasicPokemon") is False:
                ev["mulligans"][pi] += 1
            elif t == "Attack":
                ev["attacks"][pi][l.get("attackId")] += 1
                pending_hammer = pi if l.get("attackId") == HAMMER_LANCHE_ID else None
            elif t == "HpChange":
                v = l.get("value") or 0
                if pending_hammer is not None and pi != pending_hammer and v < 0:
                    ev["hammer_dmg"][pending_hammer].append(-v)
                    pending_hammer = None
            elif t == "Attach" and l.get("cardId") == BASIC_WATER_ID:
                ev["energy_attach"][pi] += 1
            elif t == "MoveCard" and l.get("toArea") == 2 and l.get("fromArea") == 6:
                # prize card to hand = the mover KO'd an opposing Pokemon
                ev["kos"][pi] += 1
    return ev


def run_compare(deck_a, deck_b, games, label_a="A", label_b="B", v3_a=False, v3_b=False):
    stats = {
        s: {"wins": 0, "losses": 0, "draws": 0, "reasons_won": Counter(),
            "reasons_lost": Counter(), "mulligans": 0, "hammer_dmg": [],
            "kos": 0, "energy_attach": 0, "crashes": 0}
        for s in (label_a, label_b)
    }
    turns = []
    for g in range(games):
        seat_a = g % 2  # alternate seats
        if seat_a == 0:
            agents = [make_wrapper(deck_a, v3_a), make_wrapper(deck_b, v3_b)]
        else:
            agents = [make_wrapper(deck_b, v3_b), make_wrapper(deck_a, v3_a)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = make("cabt", debug=True)
            env.run(agents)
        if "Traceback" in buf.getvalue():
            print(buf.getvalue()[-2000:], file=sys.stderr)

        rewards = [s.reward for s in env.state]
        statuses = [s.status for s in env.state]
        ev = game_events(env)
        seat_of = {label_a: seat_a, label_b: 1 - seat_a}
        for label, seat in seat_of.items():
            st = stats[label]
            if statuses[seat] in ("INVALID", "ERROR", "TIMEOUT"):
                st["crashes"] += 1
            r = rewards[seat]
            reason = (ev["result"] or {}).get("reason")
            if r == 1:
                st["wins"] += 1
                st["reasons_won"][reason] += 1
            elif r == -1:
                st["losses"] += 1
                st["reasons_lost"][reason] += 1
            else:
                st["draws"] += 1
            st["mulligans"] += ev["mulligans"].get(seat, 0)
            st["hammer_dmg"].extend(ev["hammer_dmg"][seat])
            st["kos"] += ev["kos"].get(seat, 0)
            st["energy_attach"] += ev["energy_attach"].get(seat, 0)
        last_turn = 0
        vis0 = env.steps[0][0].get("visualize")
        if vis0:
            for entry in vis0:
                cur = entry.get("current") or {}
                last_turn = max(last_turn, cur.get("turn") or 0)
        turns.append(last_turn)
    return stats, turns


def print_report(stats, turns, games, label_a, label_b):
    print(f"games: {games}   avg turns: {sum(turns)/len(turns):.1f}")
    for label in (label_a, label_b):
        st = stats[label]
        n = st["wins"] + st["losses"] + st["draws"]
        hd = st["hammer_dmg"]
        print(f"--- {label} ---")
        print(f"  W/L/D          : {st['wins']}/{st['losses']}/{st['draws']}"
              f"  (win rate {st['wins']/max(1,n)*100:.0f}%)  crashes: {st['crashes']}")
        print(f"  win reasons    : {dict(st['reasons_won'])}")
        print(f"  loss reasons   : {dict(st['reasons_lost'])}   "
              f"(1=prizes 2=deckout 3=no-active 4=effect)")
        print(f"  reason-3 losses: {st['reasons_lost'].get(3,0)}/{games} games "
              f"({st['reasons_lost'].get(3,0)/games*100:.0f}%)")
        print(f"  mulligans      : {st['mulligans']} total ({st['mulligans']/games:.2f}/game)")
        print(f"  KOs (prizes)   : {st['kos']} ({st['kos']/games:.2f}/game)")
        print(f"  energy attaches: {st['energy_attach']} ({st['energy_attach']/games:.2f}/game)")
        if hd:
            print(f"  Hammer-lanche  : {len(hd)} uses, dmg avg {sum(hd)/len(hd):.0f} "
                  f"min {min(hd)} max {max(hd)}")
        else:
            print(f"  Hammer-lanche  : 0 uses")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck-a", default="deck.csv")
    ap.add_argument("--deck-b", default="deck.csv")
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--v3-a", action="store_true", help="side A uses the v3 evaluator policy")
    ap.add_argument("--v3-b", action="store_true", help="side B uses the v3 evaluator policy")
    args = ap.parse_args()

    deck_a = read_deck(REPO / args.deck_a)
    deck_b = read_deck(REPO / args.deck_b)
    la = args.deck_a + ("+v3" if args.v3_a else "")
    lb = args.deck_b + ("+v3" if args.v3_b else "")
    if la == lb:
        la, lb = f"{la}(A)", f"{lb}(B)"
    print(f"deck A = {la} ({len(deck_a)} cards)   deck B = {lb} ({len(deck_b)} cards)")
    print(f"agent = {agent_mod.AGENT_VERSION} on BOTH sides; seats alternate each game")
    stats, turns = run_compare(deck_a, deck_b, args.games, la, lb,
                               v3_a=args.v3_a, v3_b=args.v3_b)
    print_report(stats, turns, args.games, la, lb)
    if args.json_out:
        out = {k: {kk: (dict(vv) if isinstance(vv, Counter) else vv)
                   for kk, vv in v.items()} for k, v in stats.items()}
        Path(args.json_out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"json written: {args.json_out}")


if __name__ == "__main__":
    main()
