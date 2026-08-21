"""BS-CEI Gate 3: Anti-Deckout Verification Suite.

Runs N games of the agent against a dedicated Stall / Mill opponent (Alakazam / Mimikyu /
Crushing Hammer / healing) to measure self-deckout rates and evaluate decision quality
in thin-deck states (deckCount <= 10).

Verifies that the BS-CEI agent does NOT blindly self-draw into deckout (the fatal flaw
of behavioral cloning).
"""

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

_import_buf = io.StringIO()
with contextlib.redirect_stdout(_import_buf), contextlib.redirect_stderr(_import_buf):
    from kaggle_environments import make

import main as agent_mod
from tools import deck_compare


def run_stall_benchmark(deck_challenger, deck_stall="metaB_alakazam.csv", games=50, bs_cei=True):
    chal_deck = deck_compare.read_deck(REPO / deck_challenger)
    stall_deck = deck_compare.read_deck(REPO / deck_stall)

    wins = 0
    losses = 0
    draws = 0
    self_deckouts = 0
    crashes = 0
    game_lengths = []

    print(f"Running Anti-Deckout Stall Benchmark: {games} games vs {deck_stall} (BS_CEI={bs_cei})...")

    for g in range(games):
        chal_seat = g % 2

        def make_chal_player():
            def player_fn(obs, _config):
                if obs.get("select") is None:
                    return list(chal_deck)
                agent_mod.DECK = list(chal_deck)
                agent_mod.BS_CEI = bs_cei
                agent_mod.EXPECTIMAX = True
                return agent_mod.agent(obs)
            return player_fn

        def make_stall_player():
            def player_fn(obs, _config):
                if obs.get("select") is None:
                    return list(stall_deck)
                agent_mod.DECK = list(stall_deck)
                agent_mod.BS_CEI = False
                agent_mod.EXPECTIMAX = False
                return agent_mod.agent(obs)
            return player_fn

        p0 = make_chal_player() if chal_seat == 0 else make_stall_player()
        p1 = make_stall_player() if chal_seat == 0 else make_chal_player()

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env = make("cabt", debug=False)
            env.run([p0, p1])

        st = env.state[chal_seat]
        r = st.reward or 0
        cur = (st.observation.get("current") or {})
        turn = cur.get("turn") or 0
        game_lengths.append(turn)

        my_deck_end = ((cur.get("players") or [{}, {}])[chal_seat].get("deckCount") or 0)

        if st.status in ("INVALID", "ERROR", "TIMEOUT"):
            crashes += 1

        if r == 1:
            wins += 1
        elif r == -1:
            losses += 1
            if my_deck_end <= 0:
                self_deckouts += 1
        else:
            draws += 1

    deckout_rate = (self_deckouts / max(1, games)) * 100.0
    win_rate = (wins / max(1, games)) * 100.0
    avg_turn = sum(game_lengths) / max(1, len(game_lengths))

    report = {
        "games": games,
        "challenger": deck_challenger,
        "stall_opponent": deck_stall,
        "bs_cei_enabled": bs_cei,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
        "self_deckouts": self_deckouts,
        "self_deckout_rate_pct": deckout_rate,
        "crashes": crashes,
        "avg_game_length_turns": avg_turn,
        "gate_3_pass": (deckout_rate <= 2.0 and crashes == 0),
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", default="meta_starmie.csv")
    parser.add_argument("--stall-deck", default="metaB_alakazam.csv")
    parser.add_argument("--games", type=int, default=50)
    parser.add_argument("--no-bs-cei", action="store_true")
    args = parser.parse_args()

    run_stall_benchmark(args.deck, args.stall_deck, args.games, bs_cei=not args.no_bs_cei)
