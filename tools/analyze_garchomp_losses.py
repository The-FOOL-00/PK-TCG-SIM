"""Stage 1 G1-failure analysis: WHY search+Garchomp(PILOT) loses to v2.0.0.

Replays N games (Garchomp+PILOT vs v2.0.0 old deck), separates wins/losses,
and for our Garchomp side reports the game-plan signature + tempo telemetry:
- first-attack turn, game length, whether we attacked each turn once loaded
- tempo SKIP telemetry: how often we had a loaded attack and didn't take it
- loss reason mix and the turn our attacker (Garchomp ex) came online
vs nasuo445's rank-6 numbers (first-attack 4.1, 93% attack cadence).

Run:  python tools/analyze_garchomp_losses.py --games 30
"""

import argparse
import contextlib
import io
import statistics as st
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

import main  # noqa: E402
from tools import deck_compare  # noqa: E402

GARCHOMP_EX_NAME = "Cynthia's Garchomp ex"


def name_fn():
    from cg.api import all_card_data
    cs = {c.cardId: c for c in all_card_data()}
    return lambda cid: cs[cid].name if cid in cs else f"#{cid}", cs


def run(games, mode="search"):
    name, cs = name_fn()
    gar = deck_compare.read_deck(REPO / "metaC_garchomp_nasuo.csv")
    old = deck_compare.read_deck(REPO / "deck.csv")
    ex_ids = {cid for cid in gar if cs.get(cid) and cs[cid].name == GARCHOMP_EX_NAME}

    wins = losses = 0
    loss_reasons = Counter()
    first_atk = []
    ex_online_turn = []
    skip_lines = 0
    n_dec = 0
    for g in range(games):
        seat = g % 2

        def ours(obs, _cfg):
            if obs.get("select") is None:
                return list(gar)
            main.DECK = list(gar)
            if mode == "bc":
                main.BC = "garchomp"
                main.SEARCH = False
                main.PILOT = ""
            else:
                main.BC = ""
                main.SEARCH = True
                main.SEARCH_BELIEF = "comp"
                main.PILOT = "garchomp"
            main.GOVERNOR = True
            return main.agent(obs)

        def v200(obs, _cfg):
            if obs.get("select") is None:
                return list(old)
            main.DECK = list(old)
            main.BC = ""
            main.SEARCH = True
            main.SEARCH_BELIEF = "comp"
            main.PILOT = ""
            main.GOVERNOR = True
            return main.agent(obs)

        wr = [None, None]
        wr[seat] = ours
        wr[1 - seat] = v200
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wr)
        skip_lines += buf.getvalue().count("[tempo] turn=")
        won = env.state[seat].reward == 1
        wins += won
        losses += (env.state[seat].reward == -1)

        step0 = env.steps[0][0]
        vis = step0.get("visualize") if hasattr(step0, "get") else step0.visualize
        fa = None
        exo = None
        reason = None
        for entry in vis or []:
            cur = entry.get("current") or {}
            for lg in entry.get("logs") or []:
                if lg.get("type") == "Result":
                    reason = lg.get("reason")
                if lg.get("playerIndex") != seat:
                    continue
                if lg.get("type") == "Attack" and fa is None:
                    fa = cur.get("turn")
                if lg.get("type") == "Evolve" and lg.get("cardId") in ex_ids and exo is None:
                    exo = cur.get("turn")
        if fa:
            first_atk.append(fa)
        if exo:
            ex_online_turn.append(exo)
        if not won and reason is not None:
            loss_reasons[reason] += 1

    print(f"{'BC' if mode == 'bc' else 'search+PILOT'}+Garchomp vs v2.0.0, {games} games\n")
    print(f"  record          : {wins}W / {losses}L  ({100*wins/games:.0f}% win)")
    print(f"  loss reasons    : {dict(loss_reasons)}  (1=prizes 2=deckout 3=no-active)")
    print(f"  first-attack turn: ours {st.mean(first_atk):.1f}  vs nasuo445 4.1"
          if first_atk else "  first-attack: never attacked in any game")
    print(f"  Garchomp ex online turn: {st.mean(ex_online_turn):.1f} "
          f"(in {len(ex_online_turn)}/{games} games)"
          if ex_online_turn else "  Garchomp ex: never came online")
    print(f"  tempo SKIP lines: {skip_lines} over {games} games "
          f"({skip_lines/games:.1f}/game — loaded attacks we declined)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--mode", choices=["search", "bc"], default="search")
    args = ap.parse_args()
    run(args.games, args.mode)
