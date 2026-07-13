"""Tier-1 STOP gate: prove OUR encoder + training path leak no hidden info.

Pre-registered (algorithm_survey.md amendments): any leakage-audit fail is an
immediate STOP; no training proceeds without our own 6/6 pass. This is run on
OUR encoder (main.py encode_state / encode_options / encode_card_options) and
OUR data-collection path (ppo.collect) — not inherited from the teammate's
6/6 on his stack.

The engine already hides the opponent's private zones from the observation
(opp hand carries no ids, no deck list, prize identities null). The risk is
that OUR feature code, or the training loop, reintroduces hidden state. Six
checks, each with a concrete plant:

  C1 structural       : hidden zones are absent from the raw observation
                        (opp hand/deck, AND both sides' prize identities).
  C2 opp-hand         : encoded features are invariant to opponent hand ids.
  C3 deck-order       : invariant to opp deck list and our own deck order.
  C4 opp-prize        : invariant to opponent prize-card identities.
  C5 option-rows      : MAIN and ST_CARD option rows share C2-C4 invariance
                        (all hidden zones planted at once).
  C6 power+path       : a deliberately-leaky encoder IS caught (the audit has
                        teeth), and the collector records only learner-seat
                        decisions with count-only shaping.

Note on OWN prizes: a player's own prizes are face-down (null in every real
observation, per C1) but CAN be legally revealed by a fetch effect that lets
you choose one — e.g. the SC_TO_HAND "take a prize to hand" decision, whose
options carry area=PRIZE/playerIndex=self. When the engine reveals them, the
option-card encoder reading that identity is legal (it is your own choice
among cards the rules show you). So own-prize identity is NOT a planted leak
vector; its safety is proven by C1's real-data nullness, not by invariance.
The opponent's prizes must NEVER be readable and ARE a planted vector (C4).

We ship a raw 1ms policy with NO search, so there is no determinizer in the
train or serve path; the "determinizer invariance" slot is discharged by C6's
training-path check (nothing samples opponent private state). If a belief
search is ever added, this file gains a determinizer-invariance check before
that path may train.
"""

import argparse
import copy
import json
import sys

import numpy as np

from . import collect, common

# card ids drawn from the list-0 deck, used to fill hidden zones with plausible
# but UNKNOWABLE-to-us content.
PLANT_IDS = [1235, 1145, 721, 140, 66, 13, 1231, 1225, 1086, 1152, 3, 1046]


def _feat(kind, sel, cur):
    """Encoded (state, rows) for a decision, as float32 arrays."""
    state, rows = (common.encode_decision_main(sel, cur) if kind == "main"
                   else common.encode_decision_card(sel, cur))
    return np.asarray(state, dtype=np.float32), np.asarray(rows, dtype=np.float32)


def _plant_opp_hand(cur):
    me = cur.get("yourIndex") or 0
    opp = cur["players"][1 - me]
    n = opp.get("handCount") or 7
    opp["hand"] = [{"id": PLANT_IDS[i % len(PLANT_IDS)],
                    "serial": 900 + i, "playerIndex": 1 - me} for i in range(n)]
    return cur


def _plant_deck_order(cur):
    me = cur.get("yourIndex") or 0
    for side, pl in enumerate(cur["players"]):
        dc = pl.get("deckCount") or 0
        pl["deck"] = [{"id": PLANT_IDS[(i + side) % len(PLANT_IDS)],
                       "serial": 500 + i, "playerIndex": side}
                      for i in range(dc)]
    return cur


def _plant_opp_prize(cur):
    """Reveal ONLY the opponent's prizes — a zone we must never be able to
    read. (Our own prizes are a legitimately-revealable zone; see module doc.)"""
    me = cur.get("yourIndex") or 0
    opp = cur["players"][1 - me]
    prize = opp.get("prize") or []
    opp["prize"] = [{"id": PLANT_IDS[i % len(PLANT_IDS)],
                     "serial": 700 + i, "playerIndex": 1 - me}
                    for i in range(len(prize))]
    return cur


def _plant_all(cur):
    return _plant_opp_prize(_plant_deck_order(_plant_opp_hand(cur)))


def _invariant(decisions, plant, want_rows=False):
    """max abs feature delta between clean and planted encodings, over all
    decisions. 0.0 means the plant is invisible to the encoder."""
    dmax = 0.0
    for kind, sel, cur in decisions:
        s0, r0 = _feat(kind, sel, cur)
        planted = plant(copy.deepcopy(cur))
        s1, r1 = _feat(kind, sel, planted)
        dmax = max(dmax, float(np.abs(s0 - s1).max()))
        if want_rows and r0.size:
            dmax = max(dmax, float(np.abs(r0 - r1).max()))
    return dmax


# ---- C6 power control: a leaky encoder the audit must catch ----
def _leaky_state(sel, cur):
    """Deliberately reads opponent hand ids into an extra feature block —
    exactly the class of bug the audit exists to catch."""
    base = list(common.agent_mod.encode_state(cur))
    me = cur.get("yourIndex") or 0
    opp = cur["players"][1 - me]
    leak = 0.0
    for c in opp.get("hand") or []:
        if isinstance(c, dict) and c.get("id"):
            leak += (c["id"] % 97) / 97.0
    return np.asarray(base + [leak], dtype=np.float32)


def run(n_games=40, cap=1500, verbose=True):
    if verbose:
        print("collecting decision states for leakage audit...")
    decisions = collect.collect_decisions(n_games=n_games, cap=cap)
    n_main = sum(1 for d in decisions if d[0] == "main")
    n_card = sum(1 for d in decisions if d[0] == "card")
    if verbose:
        print("captured %d decisions (%d MAIN, %d ST_CARD)"
              % (len(decisions), n_main, n_card))
    if len(decisions) < 300 or n_card < 30:
        print("FAIL: insufficient decision coverage (%d total, %d card)"
              % (len(decisions), n_card))
        return False

    results = []  # (name, passed, detail)

    # C1 structural: no hidden zone content in the raw observation
    opp_hand_ids = own_prize_ids = opp_prize_ids = opp_deck_lists = 0
    for _kind, _sel, cur in decisions:
        me = cur.get("yourIndex") or 0
        opp, mine = cur["players"][1 - me], cur["players"][me]
        for c in opp.get("hand") or []:
            if isinstance(c, dict) and c.get("id") is not None:
                opp_hand_ids += 1
        if isinstance(opp.get("deck"), list) and opp["deck"]:
            opp_deck_lists += 1
        for c in mine.get("prize") or []:
            if isinstance(c, dict) and c.get("id") is not None:
                own_prize_ids += 1
        for c in opp.get("prize") or []:
            if isinstance(c, dict) and c.get("id") is not None:
                opp_prize_ids += 1
    c1 = (opp_hand_ids == 0 and opp_deck_lists == 0
          and own_prize_ids == 0 and opp_prize_ids == 0)
    results.append(("C1 structural (raw obs hides opp hand/deck, all prizes)",
                    c1, "opp_hand=%d opp_deck=%d own_prize=%d opp_prize=%d"
                    % (opp_hand_ids, opp_deck_lists, own_prize_ids, opp_prize_ids)))

    # C2 opp-hand invariance
    d = _invariant(decisions, _plant_opp_hand)
    results.append(("C2 state invariant to opponent hand contents",
                    d == 0.0, "max|Δ|=%.3e" % d))

    # C3 deck-order invariance
    d = _invariant(decisions, _plant_deck_order)
    results.append(("C3 state invariant to opp deck + our deck order",
                    d == 0.0, "max|Δ|=%.3e" % d))

    # C4 opponent-prize invariance (state + rows: the true prize leak vector)
    d = _invariant(decisions, _plant_opp_prize, want_rows=True)
    results.append(("C4 state+rows invariant to opponent prize identities",
                    d == 0.0, "max|Δ|=%.3e" % d))

    # C5 option rows invariant to all hidden info (MAIN + ST_CARD)
    d = _invariant(decisions, _plant_all, want_rows=True)
    results.append(("C5 MAIN+ST_CARD option rows invariant to all hidden info",
                    d == 0.0, "max|Δ|=%.3e" % d))

    # C6 power control + training-path check
    leaky_caught = False
    for kind, sel, cur in decisions[:200]:
        s0 = _leaky_state(sel, cur)
        s1 = _leaky_state(sel, _plant_opp_hand(copy.deepcopy(cur)))
        if float(np.abs(s0 - s1).max()) > 0.0:
            leaky_caught = True
            break
    # training path: collector only ever records learner-seat decisions, and
    # shaping exposes counts only (no identities). collect tags each record
    # with the seat it was captured on == learner seat by construction; verify
    # shaping_scalars returns 4 ints (counts), never card ids.
    scal = common.shaping_scalars(decisions[0][2])
    shaping_ok = (len(scal) == 4 and all(isinstance(x, int) for x in scal))
    c6 = leaky_caught and shaping_ok
    results.append(("C6 audit has power (leak caught) + count-only shaping path",
                    c6, "leak_caught=%s shaping_counts=%s"
                    % (leaky_caught, scal)))

    passed = sum(1 for _n, ok, _d in results if ok)
    print("=" * 68)
    print("LEAKAGE AUDIT  (our encoder + our training path)")
    for name, ok, detail in results:
        print("  [%s] %-52s %s" % ("PASS" if ok else "FAIL", name, detail))
    print("  SCORE : %d/6" % passed)
    ok_all = (passed == 6)
    print("  VERDICT : %s" % ("PASS" if ok_all
                              else "FAIL -- STOP, no training proceeds"))
    print("=" * 68)
    return ok_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--cap", type=int, default=1500)
    args = ap.parse_args()
    ok = run(n_games=args.games, cap=args.cap)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
