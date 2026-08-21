"""Cross-deck: our-side Teal Ogerpon vs a NAMED opponent archetype (v1-alone).
Copied from crossdeck_kang.py; the only difference is OUR side pilots
Teal Ogerpon (metaZ_teal_ogerpon_top10.csv). Used to measure whether the
Teal Ogerpon deck-switch has ladder-favorable matchup vs Grimm."""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import deck_compare  # noqa: E402
agent_mod = deck_compare.agent_mod
make = deck_compare.make

OPP_DECKS = {
    "grimmsnarl":       "metaG_grimmsnarl_top10.csv",
    "kangaskhan":       "metaX_kangaskhan_top10.csv",
    "teal_mirror":      "metaZ_teal_ogerpon_top10.csv",
}


def make_side(deck, flags):
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)

    def wrapper(obs, _cfg):
        if obs.get("select") is None:
            return list(deck)
        agent_mod.DECK = list(deck)
        agent_mod.TOTAL_BASIC_ENERGY = n_energy
        agent_mod.PILOT = ""
        for f in ("KE1_FREE_DRAW", "KE2_ABIL_BEFORE_ATTACH", "KE3_TEAL_DANCE",
                  "KE_SUP_ATK_BEFORE_SUPPORTER", "KE_BOLT_ENGAGE",
                  "KE_WELL_ATTACH_PRIORITY", "G_ABIL_BROAD",
                  "SEQ_E1", "SEQ_E2", "SEQ_E3", "SEQ_E4",
                  "SEQ_E1B_LETHAL", "SEQ_E1C_DOOMED",
                  "TARGET_T1_BOSS_PRIZE", "TARGET_T2_SPLASH_RATIO",
                  "TARGET_T3_FEZ_TIEBREAK"):
            setattr(agent_mod, f, flags.get(f, False))
        return agent_mod.agent(obs)
    return wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opp", required=True, choices=list(OPP_DECKS))
    ap.add_argument("--games", type=int, default=200)
    args = ap.parse_args()

    our_deck = deck_compare.read_deck(REPO / "metaZ_teal_ogerpon_top10.csv")
    opp_deck = deck_compare.read_deck(REPO / OPP_DECKS[args.opp])

    out = REPO / "scratchpad" / "s3" / f"cdt_{args.opp}_v1only"
    out.mkdir(parents=True, exist_ok=True)

    agent_mod.ROLLOUT = "v1"
    agent_mod.DYN_DECK_TABLES = True
    agent_mod.EVAL_FIX = agent_mod.PROMOTE_RULE = agent_mod.LETHAL_PROBE = False
    agent_mod.CAND_INCLUDE_ATTACK = False
    agent_mod.CAND_ATK_W = 0.0
    agent_mod.CARD_R1_SEARCH_ABILITY = agent_mod.CARD_R2_BENCH_ATTACH = False
    agent_mod.CARD_R3_RAGING_CURSE = False
    agent_mod.SEARCH = False
    agent_mod.END_VETO = ""

    us = make_side(our_deck, {})
    opp = make_side(opp_deck, {})   # both sides v1-alone

    print(f"OUR side  : Teal Ogerpon (metaZ_teal_ogerpon_top10.csv), v1-alone")
    print(f"OPP side  : {args.opp} ({OPP_DECKS[args.opp]}), v1-alone")

    for g in range(args.games):
        p = out / f"g{g:03d}.json"
        if p.exists():
            continue
        our_seat = g % 2
        agents = [us, opp] if our_seat == 0 else [opp, us]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = make("cabt", debug=True)
            env.run(agents)
            js = env.toJSON()
        js["info"] = {"TeamNames": ["US", "OPP"] if our_seat == 0 else ["OPP", "US"]}
        js["_our_seat"] = our_seat
        p.write_text(json.dumps(js), encoding="utf-8")
        if (g + 1) % 25 == 0:
            print(f"  game {g+1}/{args.games}", flush=True)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
