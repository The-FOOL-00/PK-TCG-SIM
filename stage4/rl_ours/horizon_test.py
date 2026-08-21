"""Horizon-harm test: H1 cap=400 / H2 cap=16 / H3 v1-alone.

Plays self-play games per arm and saves each as a replay-shaped JSON so the
SAME profiler used for the top-10 table (behavioral_profile_jul21.py) can be
run on the output — guaranteeing unit match with the field.

Decision-level counters (the capture that was missing last session) are
computed from the saved replays by horizon_counters.py.

Run: py -3.12 -X utf8 stage4/rl_ours/horizon_test.py --arm H2 --games 60
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

ARMS = {
    "H1": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": ""},   # cap=400 baseline
    "H2": {"SEARCH": True, "SEARCH_CAP": 16, "END_VETO": ""},  # graded leaf (reverted)
    "H3": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": ""},  # v1 alone
    "VN": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "narrow"},
    "VB": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "broad"},
    # Candidate-set factorial (2026-07-26). END_VETO stays OFF in all four --
    # it is a separate variable and did not convert on ladder.
    "CI":  {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "",
            "CAND_INCLUDE_ATTACK": True},                       # A-INCLUDE
    "CW":  {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "",
            "CAND_ATK_W": 2200.0},                              # A-WEIGHT
    "CIW": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "",
            "CAND_INCLUDE_ATTACK": True, "CAND_ATK_W": 2200.0},  # both
    # Card-knowledge arms (PILOT_KNOWLEDGE.md). PILOT="" in all four -- that is
    # the ship config; every earlier arm used "garchomp", which no bundle bakes.
    # B2C is the search-without-rules control: without it, B2 vs B0 would
    # conflate the search layer with the rules.
    "B0":  {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "B1":  {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "CARD_R1_SEARCH_ABILITY": True, "CARD_R2_BENCH_ATTACH": True,
            "CARD_R3_RAGING_CURSE": True},
    # single-rule ablations of B1 (v1-alone is ~free to run, so attribute)
    "B1a": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "CARD_R1_SEARCH_ABILITY": True},
    "B1b": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "CARD_R2_BENCH_ATTACH": True},
    "B1c": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "CARD_R3_RAGING_CURSE": True},
    # R2_ARM.md pre-registered pair, 100 games, fresh dirs (R1/R3 stay off)
    "B0p":  {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "B1bp": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
             "CARD_R2_BENCH_ATTACH": True},
    # DECK_SWITCH.md: same generic agent, two decks. DECK is set via --deck.
    "D0": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "D1": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "D2": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "D3": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    # DECK_SWEEP.md: v1-alone across every buildable top-10 archetype
    "SW_KANG": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "SW_FEZ":  {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "SW_MEW":  {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    # CONDITIONAL_BUILD.md screen: C0 -> C1(E1) -> C2(+E2) -> C3(+E3) -> C4(+E4)
    "C0": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "C1": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True},
    "C2": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True, "SEQ_E2": True},
    "C3": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True, "SEQ_E2": True, "SEQ_E3": True},
    "C4": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True, "SEQ_E2": True, "SEQ_E3": True, "SEQ_E4": True},
    # C2 dropped, so E3 is screened on a clean base (E1+E3, no E2) per brief
    "C3B": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "SEQ_E1": True, "SEQ_E3": True},
    # MATCHUP_MINING.md target-selection fixes, screened on top of C2 (E1+E2)
    "T1":   {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
             "SEQ_E1": True, "SEQ_E2": True, "TARGET_T1_BOSS_PRIZE": True},
    "T1T2": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
             "SEQ_E1": True, "SEQ_E2": True,
             "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True},
    "T2":   {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
             "SEQ_E1": True, "SEQ_E2": True, "TARGET_T2_SPLASH_RATIO": True},
    # ARCHALUDON_TEST.md: same policy, Sanjay's deck, isolate the deck variable
    "AR_V1":   {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "AR_FULL": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                "SEQ_E1": True, "SEQ_E2": True,
                "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True},
    "AR_E1_ONLY": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                   "SEQ_E1": True},
    "AR_T1_ONLY": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                   "TARGET_T1_BOSS_PRIZE": True},
    "B2C": {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "B2":  {"SEARCH": True, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "CARD_R1_SEARCH_ABILITY": True, "CARD_R2_BENCH_ATTACH": True,
            "CARD_R3_RAGING_CURSE": True},
    # ENDVETO_ON_CURRENT.md: END_VETO=narrow was only ever measured on the
    # retired search+Garchomp stack. Never tested with SEARCH=False (v1-alone)
    # or on top of the shipped E1+E2+T1+T2 build. Testing both here.
    "T1T2_EV": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "narrow", "PILOT": "",
                "SEQ_E1": True, "SEQ_E2": True,
                "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True},
    "C0_EV":   {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "narrow", "PILOT": ""},
    # KANGASKHAN_E1.md: Phase 1 for the new build target (ROSTER_DIFF_JUL31.md).
    # K0 = v1-alone baseline piloting Kangaskhan/Raging Bolt (use --deck
    # metaX_kangaskhan_top10.csv). K1 = + SEQ_E1 (mined "can_KO" cell showed
    # top-10 sequences Mega Kangaskhan's free Run-Errand-draw before its
    # purely-terminal attack; known risk carried over from ARCHALUDON_TEST:
    # Raging Bolt's Burst Roar is a hybrid attack+refresh effect like
    # Cinderace's Turbo Flare, so E1 may misfire there).
    "K0": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "K1": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True},
    # KE1: native-mined free-draw-ability veto for Kangaskhan.
    "KE1": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "KE1_FREE_DRAW": True},
    "KE2": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
            "KE2_ABIL_BEFORE_ATTACH": True},
    "KE12": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
             "KE1_FREE_DRAW": True, "KE2_ABIL_BEFORE_ATTACH": True},
    # G_ABIL_BROAD (G_ABIL_BROAD_SCREEN.md): on top of shipped Grimm bundle
    # (E1+E2+T1+T2), extends E2's ability-first substitution to fire on any
    # non-OT_ABILITY chosen action, not just OT_ATTACK.
    "T1T2_GAB": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                 "SEQ_E1": True, "SEQ_E2": True,
                 "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True,
                 "G_ABIL_BROAD": True},
    # Dragapult deck-switch test (DECK_SWITCH.md methodology). DZ = v1-alone on
    # Dragapult/Munkidori — measure envelope closure to decide if the deck
    # itself is a better ship-target than the currently-shipped Grimm bundle.
    "DZ": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    # TEMPO_E1.md (2026-08-02): the shipped Grimm bundle has never been measured
    # against the field's per-TURN envelope, which FINAL_PATH_JUL21 durable
    # fact 5 names as THE target -- E1/E2 were adopted on mirror prize velocity
    # instead, and the only envelope reads we hold (BEHAVIORAL_GAP_DIAGNOSIS
    # atk/t 0.18, FA 7.91; FINAL_PATH live row atk/t 0.24, FA 6.1) are both from
    # the retired search+Garchomp stack. E1 substitutes a free action for a
    # terminal one, so it structurally delays the first attack; this pair
    # isolates that cost on the build we actually ship.
    # Run both with --deck metaG_grimmsnarl_top10.csv.
    "TE_FULL": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                "SEQ_E1": True, "SEQ_E2": True,
                "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True},
    "TE_NOE1": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                "SEQ_E2": True,
                "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True},
    # OGERPON_SCREEN.md (2026-08-02). DECK_SWITCH's 2x2 shows the deck axis is
    # ~10x the policy axis; Ogerpon is the only archetype in the Jul-31 census
    # with a better field W% than Grimmsnarl that does NOT fail closure (80.9%
    # vs 79.9%) -- but its 80.9% came from the second harness and has never been
    # measured against Grimmsnarl on one instrument. ZO_SHIP carries E1+E2 only:
    # T1/T2 are Grimmsnarl-specific, so a switch forfeits them.
    # ZG_* use --deck metaG_grimmsnarl_top10.csv, ZO_* use metaZ_teal_ogerpon_top10.csv.
    "ZG_V1":   {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "ZO_V1":   {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": ""},
    "ZG_SHIP": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                "SEQ_E1": True, "SEQ_E2": True,
                "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True},
    "ZO_SHIP": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
                "SEQ_E1": True, "SEQ_E2": True},
    # T4_KO_CONVERT.md: shipped build + lethal-target substitution in the
    # damage-target scorer. Comparator is ZG_SHIP (already run, 300 games).
    "T4": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True, "SEQ_E2": True,
           "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True,
           "TARGET_T4_LETHAL": True},
    # FETCH_MINE.md: shipped build + F1 energy-first fetch. Comparator ZG_SHIP.
    "F1": {"SEARCH": False, "SEARCH_CAP": 0, "END_VETO": "", "PILOT": "",
           "SEQ_E1": True, "SEQ_E2": True,
           "TARGET_T1_BOSS_PRIZE": True, "TARGET_T2_SPLASH_RATIO": True,
           "FETCH_F1_ENERGY_FIRST": True},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=list(ARMS))
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--deck", default="metaC_garchomp_nasuo.csv")
    args = ap.parse_args()

    cfg = ARMS[args.arm]
    agent_mod.ROLLOUT = "v1"
    # PILOT defaults to "garchomp" for the historic arms; the card-knowledge
    # arms set it to "" so they measure the configuration that actually ships.
    agent_mod.PILOT = cfg.get("PILOT", "garchomp")
    agent_mod.DYN_DECK_TABLES = True
    agent_mod.EVAL_FIX = False
    agent_mod.PROMOTE_RULE = False
    agent_mod.LETHAL_PROBE = False
    agent_mod.SEARCH = cfg["SEARCH"]
    agent_mod.SEARCH_CAP = cfg["SEARCH_CAP"]
    agent_mod.END_VETO = cfg.get("END_VETO", "")
    # candidate-set arms: explicit on every arm so a stale module-level default
    # can never leak across arms
    agent_mod.CAND_INCLUDE_ATTACK = cfg.get("CAND_INCLUDE_ATTACK", False)
    agent_mod.CAND_ATK_W = cfg.get("CAND_ATK_W", 0.0)
    for _f in ("SEQ_E1", "SEQ_E2", "SEQ_E3", "SEQ_E4",
               "SEQ_E1B_LETHAL", "SEQ_E1C_DOOMED",
               "TARGET_T1_BOSS_PRIZE", "TARGET_T2_SPLASH_RATIO",
               "TARGET_T3_FEZ_TIEBREAK", "TARGET_T4_LETHAL",
               "FETCH_F1_ENERGY_FIRST",
               "KE1_FREE_DRAW", "KE2_ABIL_BEFORE_ATTACH",
               "G_ABIL_BROAD"):
        setattr(agent_mod, _f, cfg.get(_f, False))
    agent_mod.CARD_R1_SEARCH_ABILITY = cfg.get("CARD_R1_SEARCH_ABILITY", False)
    agent_mod.CARD_R2_BENCH_ATTACH = cfg.get("CARD_R2_BENCH_ATTACH", False)
    agent_mod.CARD_R3_RAGING_CURSE = cfg.get("CARD_R3_RAGING_CURSE", False)
    if cfg["SEARCH"]:
        agent_mod._search_lib()
        agent_mod._pool()
    print(f"arm {args.arm}: SEARCH={agent_mod.SEARCH} SEARCH_CAP={agent_mod.SEARCH_CAP} "
          f"END_VETO={agent_mod.END_VETO!r} "
          f"CAND_INCLUDE_ATTACK={agent_mod.CAND_INCLUDE_ATTACK} "
          f"CAND_ATK_W={agent_mod.CAND_ATK_W} "
          f"CAND_ATK_MIN_DMG={agent_mod.CAND_ATK_MIN_DMG} "
          f"PILOT={agent_mod.PILOT!r} "
          f"R1={agent_mod.CARD_R1_SEARCH_ABILITY} "
          f"R2={agent_mod.CARD_R2_BENCH_ATTACH} "
          f"R3={agent_mod.CARD_R3_RAGING_CURSE} "
          f"T1={agent_mod.TARGET_T1_BOSS_PRIZE} "
          f"T2={agent_mod.TARGET_T2_SPLASH_RATIO} "
          f"T4={agent_mod.TARGET_T4_LETHAL} "
          f"F1={agent_mod.FETCH_F1_ENERGY_FIRST}", flush=True)

    deck = deck_compare.read_deck(REPO / args.deck)
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)
    out = REPO / "scratchpad" / "s3" / f"horizon_{args.arm}"
    out.mkdir(parents=True, exist_ok=True)

    def wrapper(timing, seat):
        def w(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            agent_mod.DECK = list(deck)
            agent_mod.TOTAL_BASIC_ENERGY = n_energy
            t = time.perf_counter()
            try:
                return agent_mod.agent(obs)
            finally:
                timing[seat] += time.perf_counter() - t
        return w

    for g in range(args.games):
        p = out / f"g{g:03d}.json"
        if p.exists():
            continue
        timing = {0: 0.0, 1: 0.0}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = make("cabt", debug=True)
            env.run([wrapper(timing, 0), wrapper(timing, 1)])
            js = env.toJSON()
        # profiler expects info.TeamNames; both seats are the same agent here
        js["info"] = {"TeamNames": ["ARM", "ARM"]}
        js["_timing"] = timing
        # mechanism telemetry (CONDITIONAL_BUILD.md amendment 1): a rule that
        # did not fire has not been tested.
        js["_seq"] = {k: agent_mod.STATS.get(k, 0)
                      for k in ("e1_veto", "e2_veto", "e3_veto")}
        js["_seq"]["turns"] = agent_mod._SEQ.get("turns", 0)
        js["_seq"]["ceiling_turns"] = agent_mod._SEQ.get("ceiling_turns", 0)
        # T1/T2 (MATCHUP_MINING.md): option-level scoring counts, not
        # decision-level vetoes -- _score_card is called once per candidate
        # option, so these count "option evaluations under the new formula".
        js["_seq"]["t1_fired"] = agent_mod.STATS.get("t1_fired", 0)
        js["_seq"]["t2_fired"] = agent_mod.STATS.get("t2_fired", 0)
        js["_seq"]["t4_fired"] = agent_mod.STATS.get("t4_fired", 0)
        js["_seq"]["f1_fired"] = agent_mod.STATS.get("f1_fired", 0)
        js["_seq"]["ke1_veto"] = agent_mod.STATS.get("ke1_veto", 0)
        js["_seq"]["ke2_veto"] = agent_mod.STATS.get("ke2_veto", 0)
        js["_seq"]["g_abil_broad_veto"] = agent_mod.STATS.get("g_abil_broad_veto", 0)
        p.write_text(json.dumps(js), encoding="utf-8")
        print(f"  {args.arm} game {g+1}/{args.games} "
              f"t0={timing[0]:.1f}s t1={timing[1]:.1f}s", flush=True)
    print(f"{args.arm} done -> {out}")


if __name__ == "__main__":
    main()
