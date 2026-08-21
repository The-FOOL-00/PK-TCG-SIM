"""Cross-deck screen: our Kangaskhan/Raging Bolt (configurable rule flags)
vs a NAMED opponent archetype (v1-alone).

Same structure as crossdeck_test.py (which does Grimmsnarl vs opponent),
inverted -- OUR side pilots Kangaskhan/Raging Bolt (metaX_kangaskhan_top10.csv)
and can have KE1/KE2/KE12 flags applied, OPP side is v1-alone on the named
opponent deck (Grimmsnarl, mirror, etc). Seats alternate to cancel first-
player bias. Purpose: mirror self-play cannot discriminate KE1/KE2/KE12
signal because both sides get the rules; putting our Kang against a
Grimmsnarl opponent that does NOT have our rules is the closest offline
proxy to a real ladder measurement of whether the rules help.

Run: py -3.12 -X utf8 stage4/rl_ours/crossdeck_kang.py --opp grimmsnarl \\
       --our-rules ke12 --games 200
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
    "grimmsnarl":       "metaG_grimmsnarl_top10.csv",
    "kangaskhan_mirror": "metaX_kangaskhan_top10.csv",
    "fezandipiti":      "metaX_fezandipiti_top10.csv",
    "mewtwo":           "metaX_mewtwo_top10.csv",
}

RULE_SETS = {
    "none":     {},
    "ke1":      {"KE1_FREE_DRAW": True},
    "ke2":      {"KE2_ABIL_BEFORE_ATTACH": True},
    "ke3":      {"KE3_TEAL_DANCE": True},
    "ke12":     {"KE1_FREE_DRAW": True, "KE2_ABIL_BEFORE_ATTACH": True},
    "ke13":     {"KE1_FREE_DRAW": True, "KE3_TEAL_DANCE": True},
    "ke_sup":   {"KE_SUP_ATK_BEFORE_SUPPORTER": True},
    "ke1_sup":  {"KE1_FREE_DRAW": True, "KE_SUP_ATK_BEFORE_SUPPORTER": True},
    "ke_bolt":  {"KE_BOLT_ENGAGE": True},
    "ke1_bolt": {"KE1_FREE_DRAW": True, "KE_BOLT_ENGAGE": True},
    "ke_well":  {"KE_WELL_ATTACH_PRIORITY": True},
    "ke1_well": {"KE1_FREE_DRAW": True, "KE_WELL_ATTACH_PRIORITY": True},
    "ke1_well_bolt": {"KE1_FREE_DRAW": True, "KE_WELL_ATTACH_PRIORITY": True,
                       "KE_BOLT_ENGAGE": True},
    "ke1_gab":  {"KE1_FREE_DRAW": True, "G_ABIL_BROAD": True},
}

RULE_FLAG_KEYS = ("KE1_FREE_DRAW", "KE2_ABIL_BEFORE_ATTACH", "KE3_TEAL_DANCE",
                  "KE_SUP_ATK_BEFORE_SUPPORTER", "KE_BOLT_ENGAGE",
                  "KE_WELL_ATTACH_PRIORITY", "G_ABIL_BROAD",
                  "SEQ_E1", "SEQ_E2", "SEQ_E3", "SEQ_E4",
                  "SEQ_E1B_LETHAL", "SEQ_E1C_DOOMED",
                  "TARGET_T1_BOSS_PRIZE", "TARGET_T2_SPLASH_RATIO",
                  "TARGET_T3_FEZ_TIEBREAK")


def make_side(deck, flags):
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)

    def wrapper(obs, _cfg):
        if obs.get("select") is None:
            return list(deck)
        agent_mod.DECK = list(deck)
        agent_mod.TOTAL_BASIC_ENERGY = n_energy
        agent_mod.PILOT = ""
        for f in RULE_FLAG_KEYS:
            setattr(agent_mod, f, flags.get(f, False))
        return agent_mod.agent(obs)
    return wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opp", required=True, choices=list(OPP_DECKS))
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--our-rules", default="ke12", choices=list(RULE_SETS))
    args = ap.parse_args()

    our_deck = deck_compare.read_deck(REPO / "metaX_kangaskhan_top10.csv")
    opp_deck = deck_compare.read_deck(REPO / OPP_DECKS[args.opp])
    our_flags = RULE_SETS[args.our_rules]

    out = REPO / "scratchpad" / "s3" / f"cdk_{args.opp}_{args.our_rules}"
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
    opp = make_side(opp_deck, {})   # opponent always v1-alone, no rules

    print(f"OUR side  : Kangaskhan/Raging Bolt, rules={args.our_rules}")
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
                      for k in ("ke1_veto", "ke2_veto", "ke3_veto", "ke_sup_veto",
                                "ke_bolt_main", "ke_bolt_discard", "ke_well_veto",
                                "g_abil_broad_veto")}
        p.write_text(json.dumps(js), encoding="utf-8")
        if (g + 1) % 25 == 0:
            print(f"  game {g+1}/{args.games}", flush=True)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
