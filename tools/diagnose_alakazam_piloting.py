"""Phase 1B substitute: quantify HOW our agent pilots Alakazam vs Majkel1337.

Plays N games of our search agent on the (Majkel-identical) Alakazam list and
parses the transcript for the game-plan signature that distinguishes Majkel's
rank-1 piloting: game length, first-attack turn, denial plays (Enhanced Hammer
+ Boss's Orders), Rare Candy usage, energy attaches. Prints ours next to
Majkel's replay numbers so the piloting gap is explicit.

Run:  python tools/diagnose_alakazam_piloting.py --games 20 [--opp v1|search]
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

MAJKEL = {"avg_turns": 44.0, "first_attack": 4.1, "denial_per_game": 4.0,
          "rare_candy_per_game": 1.9}


def card_name():
    from cg.api import all_card_data
    cs = {c.cardId: c for c in all_card_data()}
    return lambda cid: cs[cid].name if cid in cs else f"#{cid}"


def signature_from_env(env, name, side):
    step0 = env.steps[0][0]
    vis = step0.get("visualize") if hasattr(step0, "get") else step0.visualize
    turns = 0
    first_attack = None
    denial = rc = attach = 0
    for entry in vis or []:
        cur = entry.get("current") or {}
        turns = max(turns, cur.get("turn") or 0)
        for lg in entry.get("logs") or []:
            t, pi = lg.get("type"), lg.get("playerIndex")
            if pi != side:
                continue
            if t == "Attack" and first_attack is None:
                first_attack = cur.get("turn")
            elif t == "Play":
                nm = name(lg.get("cardId"))
                if nm in ("Enhanced Hammer", "Boss’s Orders", "Boss's Orders"):
                    denial += 1
                if nm == "Rare Candy":
                    rc += 1
            elif t == "Attach":
                attach += 1
    return {"turns": turns, "first_attack": first_attack,
            "denial": denial, "rare_candy": rc, "attach": attach}


def run(games, opp):
    name = card_name()
    ala = deck_compare.read_deck(REPO / "metaB_alakazam.csv")
    sigs = []
    for g in range(games):
        seat = g % 2   # our agent's seat

        def ours(obs, _cfg):
            if obs.get("select") is None:
                return list(ala)
            main.DECK = list(ala)
            main.SEARCH = True
            main.SEARCH_BELIEF = "comp"
            main.ROLLOUT = "v1"
            main.SEARCH_CAP = 0
            main.GOVERNOR = True
            return main.agent(obs)

        def other(obs, _cfg):
            if obs.get("select") is None:
                return list(ala)
            main.DECK = list(ala)
            main.SEARCH = (opp == "search")
            main.SEARCH_BELIEF = "comp"
            main.GOVERNOR = True
            return main.agent(obs)

        wrappers = [None, None]
        wrappers[seat] = ours
        wrappers[1 - seat] = other
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run(wrappers)
        sigs.append(signature_from_env(env, name, seat))

    def agg(key, filt=None):
        vals = [s[key] for s in sigs if s[key] is not None and (filt is None or filt(s))]
        return st.mean(vals) if vals else None

    print(f"our v2.1.0 search agent piloting the Majkel-identical Alakazam list, "
          f"{games} games (opponent={opp})\n")
    print(f"{'metric':<26}{'OURS':>10}{'MAJKEL rank-1':>16}")
    rows = [
        ("avg game length (turns)", agg("turns"), MAJKEL["avg_turns"]),
        ("first-attack turn", agg("first_attack"), MAJKEL["first_attack"]),
        ("denial plays / game", agg("denial"), MAJKEL["denial_per_game"]),
        ("Rare Candy / game", agg("rare_candy"), MAJKEL["rare_candy_per_game"]),
        ("energy attaches / game", agg("attach"), None),
    ]
    for label, ours_v, maj_v in rows:
        ours_s = f"{ours_v:.1f}" if ours_v is not None else "n/a"
        maj_s = f"{maj_v:.1f}" if maj_v is not None else "-"
        print(f"{label:<26}{ours_s:>10}{maj_s:>16}")
    print(f"\nfirst-attack made in {sum(1 for s in sigs if s['first_attack'])}/{games} games")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--opp", choices=["v1", "search"], default="v1")
    args = ap.parse_args()
    run(args.games, args.opp)
