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


def collect_positions(games, seed):
    """Play v1-vs-v1 games; record every searched MAIN observation + v1 answer."""
    deck = deck_compare.read_deck(REPO / "deck.csv")
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
                return list(deck)
            main.SEARCH = False
            return main.agent(obs)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run([rec, plain] if g % 2 == 0 else [plain, rec])
        positions.extend(stream)
    return positions


def search_with(obs, belief, seed):
    """Return (answer, value_gap) for one position under a belief mode. The
    value gap is top1-value minus top2-value over the candidate set (0 if the
    search produced no usable samples)."""
    main.SEARCH = True
    main.SEARCH_BELIEF = belief
    main.SEARCH_DET, main.SEARCH_ROLL, main.SEARCH_TOPK = 16, 2, 4
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


def run(games, seed):
    assert main._search_lib() is not None, "engine required"
    positions = collect_positions(games, seed)
    n = len(positions)
    print(f"collected {n} searched MAIN positions from {games} games\n")

    agree = Counter()
    override = Counter()
    edge = Counter()          # on mirror-overrides-v1 positions
    gaps = {"comp": [], "mirror": []}
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        for k, (obs, v1_ans) in enumerate(positions):
            m_ans, m_gap = search_with(obs, "mirror", 7000 + k)
            c_ans, c_gap = search_with(obs, "comp", 7000 + k)
            gaps["mirror"].append(m_gap)
            gaps["comp"].append(c_gap)
            agree["comp~mirror"] += (c_ans == m_ans)
            agree["comp~v1"] += (c_ans == v1_ans)
            agree["mirror~v1"] += (m_ans == v1_ans)
            override["mirror"] += (m_ans != v1_ans)
            override["comp"] += (c_ans != v1_ans)
            if m_ans != v1_ans:            # mirror's edge positions
                edge["total"] += 1
                if c_ans == m_ans:
                    edge["comp_follows"] += 1
                elif c_ans == v1_ans:
                    edge["comp_reverts_v1"] += 1
                else:
                    edge["comp_third"] += 1

    def pct(x):
        return f"{100*x/n:.0f}%"

    print("pairwise agreement:")
    for k in ("comp~mirror", "comp~v1", "mirror~v1"):
        print(f"  {k:12s} {pct(agree[k])}")
    print("\noverride rate vs v1 (search changed the heuristic answer):")
    print(f"  mirror {pct(override['mirror'])}   comp {pct(override['comp'])}")
    et = max(1, edge["total"])
    print(f"\nedge capture — on the {edge['total']} positions where MIRROR overrides v1:")
    print(f"  comp makes the same override : {100*edge['comp_follows']/et:.0f}%")
    print(f"  comp reverts to v1           : {100*edge['comp_reverts_v1']/et:.0f}%")
    print(f"  comp picks a third option    : {100*edge['comp_third']/et:.0f}%")
    import statistics as st
    print("\nvalue separation (top1-top2 mean-value gap; small = candidates "
          "indistinguishable):")
    for b in ("mirror", "comp"):
        g = gaps[b]
        print(f"  {b:6s} mean {st.mean(g):.3f}  median {st.median(g):.3f}  "
              f"zero-gap positions {100*sum(1 for x in g if x < 1e-9)/len(g):.0f}%")

    payload = {"n": n, "games": games, "agreement": dict(agree),
               "override": dict(override), "edge": dict(edge),
               "gap_mean": {b: st.mean(gaps[b]) for b in gaps},
               "gap_zero_frac": {b: sum(1 for x in gaps[b] if x < 1e-9) / len(gaps[b])
                                 for b in gaps}}
    out = REPO / "runs" / "diagnose_belief.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\njson written: {out}")
    main.SEARCH = False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run(args.games, args.seed)
