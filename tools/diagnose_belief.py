"""E1-failure diagnosis: is the belief-search's weakness belief quality or
search budget? Runs comp-belief and mirror-exact search on the SAME searched
positions and measures where they diverge.

For each searched MAIN position (collected from real games), with identical
determinization RNG seeds per position:
  v1     : the heuristic's answer
  mirror : exact-knowledge determinized search (the 58.3% player)
  comp   : honest belief determinized search (the 49.0% player)
We report:
  - pairwise agreement (comp~mirror, comp~v1, mirror~v1)
  - override rates vs v1 (how often each search changes the heuristic answer)
  - on positions where MIRROR overrides v1 (its edge comes from these):
    how often comp makes the SAME override vs falls back to v1 vs picks a
    third option  -> "edge capture" rate
  - value separation: top1-top2 mean-value gap under each belief (a flat
    landscape = the search can't tell candidates apart = belief too vague)

Run:  python tools/diagnose_belief.py --games 40 --seed 0
"""

import argparse
import contextlib
import io
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import main  # noqa: E402
from tools import deck_compare  # noqa: E402


def collect_positions(games, seed, opp_deck_file="deck.csv"):
    """Play our v1 vs the opponent deck (v1 pilot); record every searched MAIN
    observation OUR side faces + our v1 answer. opp_deck_file=deck.csv makes it
    a mirror (original E1 diagnosis); a cross-deck file makes it honest."""
    deck = deck_compare.read_deck(REPO / "deck.csv")
    opp = deck_compare.read_deck(REPO / opp_deck_file)
    positions = []
    for g in range(games):
        stream = []

        def rec(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            main.SEARCH = False
            ans = main.agent(obs)
            sel, cur = obs.get("select") or {}, obs.get("current") or {}
            if main._searchable(obs, sel, cur):
                stream.append((json.loads(json.dumps(obs)), list(ans)))
            return ans

        def plain(obs, _cfg):
            if obs.get("select") is None:
                return list(opp)
            main.SEARCH = False
            return main.agent(obs)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run([rec, plain] if g % 2 == 0 else [plain, rec])
        positions.extend(stream)
    return positions


def search_with(obs, belief, seed, det=16, oracle_deck=None):
    """Return (answer, value_gap) for one position under a belief mode. The
    value gap is top1-value minus top2-value over the candidate set (0 if the
    search produced no usable samples)."""
    main.SEARCH = True
    main.SEARCH_BELIEF = belief
    main.SEARCH_ORACLE_DECK = oracle_deck
    main.SEARCH_DET, main.SEARCH_ROLL, main.SEARCH_TOPK = det, 2, 4
    main.SEARCH_CAP, main.GOVERNOR = 0, False
    main._TRACKERS.clear()
    main._SEARCH_RNG = random.Random(seed)

    sel, cur = obs["select"], obs["current"]
    me = cur.get("yourIndex") or 0
    tr = main.CardTracker(me)
    tr.update(obs)
    options = sel.get("option") or []
    _r, _top, scores = main._decide(obs)
    order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
    cands = order[:main.SEARCH_TOPK]

    totals = {i: 0.0 for i in cands}
    n = 0
    rng = main._SEARCH_RNG
    for _d in range(main.SEARCH_DET):
        try:
            det = main._sample_determinization(obs, tr, rng)
            root = main._sb_begin(obs["search_begin_input"], **det)
            for i in cands:
                for _rr in range(main.SEARCH_ROLL):
                    node = main._sb_step(root["searchId"], [i])
                    totals[i] += main._rollout(node, me, 400)
            n += main.SEARCH_ROLL
        except Exception:
            pass
        finally:
            main._sb_end()
    if n == 0:
        return _r, 0.0
    means = sorted((totals[i] / n for i in cands), reverse=True)
    gap = means[0] - means[1] if len(means) > 1 else 0.0
    best = max(cands, key=lambda i: (totals[i] / n, -cands.index(i)))
    return [best], gap


def run(games, seed, opp_deck_file, low_det):
    import statistics as st
    assert main._search_lib() is not None, "engine required"
    oracle_deck = deck_compare.read_deck(REPO / opp_deck_file)
    is_mirror = (opp_deck_file == "deck.csv")
    positions = collect_positions(games, seed, opp_deck_file)
    n = len(positions)
    tag = Path(opp_deck_file).stem
    print(f"collected {n} searched MAIN positions from {games} games "
          f"(our deck vs {tag}{'  [MIRROR]' if is_mirror else ''})\n")

    # belief modes compared. On a mirror match mirror==oracle, so we skip
    # oracle; on cross-deck, oracle knows the true opponent list (ceiling).
    modes = ["comp", "mirror"] + ([] if is_mirror else ["oracle"])
    agree = Counter()
    override = Counter()
    edge = Counter()          # relative to the reference belief's overrides
    ref = "oracle" if not is_mirror else "mirror"   # the "correct-belief" search
    gaps = {m: [] for m in modes}
    ans_by_mode = {m: [] for m in modes}
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        for k, (obs, v1_ans) in enumerate(positions):
            for m in modes:
                a, gp = search_with(obs, m, 7000 + k, det=16, oracle_deck=oracle_deck)
                gaps[m].append(gp)
                ans_by_mode[m].append(a)
                override[m] += (a != v1_ans)
    for k, (_obs, v1_ans) in enumerate(positions):
        r_ans = ans_by_mode[ref][k]
        c_ans = ans_by_mode["comp"][k]
        agree["comp~" + ref] += (c_ans == r_ans)
        agree["comp~v1"] += (c_ans == v1_ans)
        agree[ref + "~v1"] += (r_ans == v1_ans)
        if r_ans != v1_ans:            # the correct-belief search's edge set
            edge["total"] += 1
            if c_ans == r_ans:
                edge["comp_follows"] += 1
            elif c_ans == v1_ans:
                edge["comp_reverts_v1"] += 1
            else:
                edge["comp_third"] += 1

    # compute-cofounder check: does raising det sharpen comp's value gap?
    lowdet = {}
    if low_det:
        for det in (4, 16, 48):
            gg = []
            with contextlib.redirect_stderr(io.StringIO()):
                for k, (obs, _v1) in enumerate(positions):
                    _a, gp = search_with(obs, "comp", 9000 + k, det=det)
                    gg.append(gp)
            lowdet[det] = {"gap_mean": st.mean(gg),
                           "zero_frac": sum(1 for x in gg if x < 1e-9) / len(gg)}

    def pct(x):
        return f"{100*x/n:.0f}%"

    print(f"reference correct-belief search: {ref}")
    print("pairwise agreement:")
    for kk in (f"comp~{ref}", "comp~v1", f"{ref}~v1"):
        print(f"  {kk:14s} {pct(agree[kk])}")
    print("\noverride rate vs v1 (search changed the heuristic answer):")
    print("  " + "   ".join(f"{m} {pct(override[m])}" for m in modes))
    et = max(1, edge["total"])
    print(f"\nedge capture — on the {edge['total']} positions where {ref.upper()} "
          f"overrides v1:")
    print(f"  comp makes the same override : {100*edge['comp_follows']/et:.0f}%")
    print(f"  comp reverts to v1           : {100*edge['comp_reverts_v1']/et:.0f}%")
    print(f"  comp picks a third option    : {100*edge['comp_third']/et:.0f}%")
    print("\nvalue separation (top1-top2 mean rollout-value gap; small = "
          "candidates indistinguishable):")
    for m in modes:
        g = gaps[m]
        print(f"  {m:6s} mean {st.mean(g):.3f}  median {st.median(g):.3f}  "
              f"zero-gap {100*sum(1 for x in g if x < 1e-9)/len(g):.0f}%")
    if low_det:
        print("\ncompute-cofounder check (comp belief, value gap vs det count):")
        for det, d in lowdet.items():
            print(f"  det={det:2d}  gap_mean {d['gap_mean']:.3f}  "
                  f"zero-gap {100*d['zero_frac']:.0f}%")

    payload = {"n": n, "games": games, "opponent": tag, "mirror": is_mirror,
               "reference": ref, "agreement": dict(agree),
               "override": dict(override), "edge": dict(edge),
               "gap_mean": {m: st.mean(gaps[m]) for m in modes},
               "gap_zero_frac": {m: sum(1 for x in gaps[m] if x < 1e-9) / len(gaps[m])
                                 for m in modes},
               "lowdet": lowdet}
    out = REPO / "runs" / f"diagnose_{tag}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\njson written: {out}")
    main.SEARCH = False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--opponent", default="deck.csv",
                    help="opponent deck file (deck.csv = mirror, original E1)")
    ap.add_argument("--low-det", action="store_true",
                    help="also sweep det=4/16/48 to rule out compute cofounder")
    args = ap.parse_args()
    run(args.games, args.seed, args.opponent, args.low_det)
