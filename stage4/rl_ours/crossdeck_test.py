"""Cross-deck self-play: OUR Grimmsnarl (configurable rule flags) vs a NAMED
opponent archetype deck (v1-alone), both piloted by the same main.py.

Mirror self-play (horizon_test.py) can never test matchup-specific behaviour:
the opponent is always our own deck. This harness is the only way, short of
real ladder, to measure our policy against an actual different board -- the
opponent side is v1-alone (a generic, not top-10-calibre, pilot of that deck),
so it is a proxy for "a reasonably played opponent", not a claim about real
ladder opposition strength.

Run: py -3.12 -X utf8 stage4/rl_ours/crossdeck_test.py --opp kangaskhan --games 100
"""
import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import deck_compare  # noqa: E402
agent_mod = deck_compare.agent_mod
make = deck_compare.make

OPP_DECKS = {
    "kangaskhan": "metaX_kangaskhan_top10.csv",
    "fezandipiti": "metaX_fezandipiti_top10.csv",
    "mewtwo": "metaX_mewtwo_top10.csv",
    "grimmsnarl_mirror": "metaG_grimmsnarl_top10.csv",
}

OUR_FLAGS = {"SEQ_E1": True, "SEQ_E2": True,
             "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True}
OUR_FLAGS_T3 = dict(OUR_FLAGS, TARGET_T3_FEZ_TIEBREAK=True)
OUR_V1ONLY_FLAGS = {}  # no rules, for the AR-v1-style baseline read


def make_side(deck, flags):
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)

    def wrapper(obs, _cfg):
        if obs.get("select") is None:
            return list(deck)
        agent_mod.DECK = list(deck)
        agent_mod.TOTAL_BASIC_ENERGY = n_energy
        agent_mod.PILOT = ""
        for f in ("SEQ_E1", "SEQ_E2", "SEQ_E3", "SEQ_E4", "SEQ_E1B_LETHAL",
                  "SEQ_E1C_DOOMED", "TARGET_T1_BOSS_PRIZE", "TARGET_T2_SPLASH_RATIO",
                  "TARGET_T3_FEZ_TIEBREAK"):
            setattr(agent_mod, f, flags.get(f, False))
        return agent_mod.agent(obs)
    return wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opp", required=True, choices=list(OPP_DECKS))
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--our-rules", default="full", choices=["full", "none", "full_t3"])
    args = ap.parse_args()

    our_deck = deck_compare.read_deck(REPO / "metaG_grimmsnarl_top10.csv")
    opp_deck = deck_compare.read_deck(REPO / OPP_DECKS[args.opp])
    our_flags = {"full": OUR_FLAGS, "none": OUR_V1ONLY_FLAGS,
                 "full_t3": OUR_FLAGS_T3}[args.our_rules]

    out = REPO / "scratchpad" / "s3" / f"crossdeck_{args.opp}_{args.our_rules}"
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

    us = make_side(our_deck, our_flags)
    opp = make_side(opp_deck, {})   # opponent always v1-alone

    print(f"OUR side  : Grimmsnarl, rules={args.our_rules}")
    print(f"OPP side  : {args.opp} ({OPP_DECKS[args.opp]}), v1-alone")

    for g in range(args.games):
        p = out / f"g{g:03d}.json"
        if p.exists():
            continue
        our_seat = g % 2   # alternate to cancel first-player bias
        agents = [us, opp] if our_seat == 0 else [opp, us]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = make("cabt", debug=True)
            env.run(agents)
            js = env.toJSON()
        js["info"] = {"TeamNames": ["US", "OPP"] if our_seat == 0 else ["OPP", "US"]}
        js["_our_seat"] = our_seat
        js["_seq"] = {k: agent_mod.STATS.get(k, 0)
                      for k in ("e1_veto", "e2_veto", "e3_veto", "t1_fired", "t2_fired", "t3_fired")}
        p.write_text(json.dumps(js), encoding="utf-8")
        if (g + 1) % 20 == 0:
            print(f"  game {g+1}/{args.games}", flush=True)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
