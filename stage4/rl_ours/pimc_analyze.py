"""Analyze the PIMC diagnostic raw capture into the report tables."""

import argparse
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

EVAL_RANGE = 1.0        # _rollout returns [0,1]
CONTESTED_MARGIN = 0.10 * EVAL_RANGE


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, c - hw, c + hw


def hist(vals, edges):
    out = Counter()
    for v in vals:
        for lo, hi in edges:
            if lo <= v <= hi:
                out[(lo, hi)] += 1
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    args = ap.parse_args()
    d = json.loads(Path(args.raw).read_text())
    dec, games = d["decisions"], d["games"]

    print(f"corpus: {len(dec)} searched decisions over {len(games)} games\n")

    contested = [r for r in dec if r["n_legal"] >= 3 and r["margin"] < CONTESTED_MARGIN]
    forced = [r for r in dec if r not in contested]
    # cheaper split (identity compare above is O(n^2)); recompute properly:
    contested = [r for r in dec if r["n_legal"] >= 3 and r["margin"] < CONTESTED_MARGIN]
    forced = [r for r in dec
              if not (r["n_legal"] >= 3 and r["margin"] < CONTESTED_MARGIN)]

    print("=" * 72)
    print("D1  STRATEGY FUSION INCIDENCE")
    print("=" * 72)
    for label, rows in (("ALL", dec), ("CONTESTED", contested), ("FORCED/near", forced)):
        if not rows:
            print(f"{label}: none")
            continue
        naive = [r["agreement"] for r in rows]
        strictrows = [r for r in rows if r["agreement_strict"] is not None]
        strict = [r["agreement_strict"] for r in strictrows]
        tied = [r["all_tied_frac"] for r in rows]
        sfrac = [r["n_dets_strict"] / r["n_dets"] for r in rows]
        print(f"\n--- {label}  (n={len(rows)}, {len(rows)/len(dec)*100:.1f}% of decisions)")
        print(f"  naive agreement (ties broken by index) : median {st.median(naive):.3f}  "
              f"mean {st.mean(naive):.3f}")
        print(f"  frac of dets with a STRICT argmax      : median {st.median(sfrac):.3f}  "
              f"mean {st.mean(sfrac):.3f}")
        print(f"  frac of dets where ALL cands tie       : mean {st.mean(tied):.3f}")
        if strict:
            print(f"  *** SIGNAL-BEARING agreement (strict) : median {st.median(strict):.3f}  "
                  f"mean {st.mean(strict):.3f}   [n={len(strict)} decisions with >=1 strict det]")
            edges = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 0.999), (0.999, 1.0)]
            h = hist(strict, edges)
            print("      distribution:")
            for lo, hi in edges:
                c = h[(lo, hi)]
                bar = "#" * int(40 * c / max(1, len(strict)))
                print(f"        [{lo:.2f},{hi:.2f}] {c:4d} {c/len(strict)*100:5.1f}% {bar}")
        else:
            print("  *** no decision had any strict determinization")
        mv = [r["distinct_votes_strict"] for r in strictrows]
        if mv:
            print(f"  distinct actions voted for (strict dets): mean {st.mean(mv):.2f}  "
                  f"max {max(mv)}")

    print("\n--- agreement vs TURN (contested only) ---")
    byturn = defaultdict(list)
    for r in contested:
        if r["agreement_strict"] is not None:
            byturn[r["turn"] // 4 * 4].append(r["agreement_strict"])
    print(f"  {'turns':<10s} {'n':>5s} {'median strict agreement':>24s}")
    for t in sorted(byturn):
        v = byturn[t]
        if len(v) >= 5:
            print(f"  {f'{t}-{t+3}':<10s} {len(v):>5d} {st.median(v):>24.3f}")

    print("\n" + "=" * 72)
    print("D2  DISAMBIGUATION FACTOR (opponent-hand belief)")
    print("=" * 72)
    byturn = defaultdict(list)
    for r in dec:
        byturn[r["turn"] // 2 * 2].append(r)
    print(f"  {'turn':<8s} {'n':>5s} {'handCt':>7s} {'known':>7s} {'known%':>7s} "
          f"{'entropy':>8s} {'perplex':>8s}")
    for t in sorted(byturn):
        rows = byturn[t]
        if len(rows) < 10:
            continue
        hc = st.mean(r["opp_hand_count"] for r in rows)
        kn = st.mean(r["opp_hand_known"] for r in rows)
        ent = st.mean(r["opp_hand_entropy_bits"] for r in rows)
        pp = st.mean(r["opp_hand_perplexity"] for r in rows)
        print(f"  {t:<8d} {len(rows):>5d} {hc:>7.2f} {kn:>7.2f} "
              f"{(kn/hc*100 if hc else 0):>6.1f}% {ent:>8.2f} {pp:>8.1f}")

    ptl = [t for g in games for t in g["prize_turns"]]
    if ptl:
        ptl.sort()
        q1, med, q3 = (ptl[len(ptl)//4], ptl[len(ptl)//2], ptl[3*len(ptl)//4])
        print(f"\n  prize-take (game-deciding) events: n={len(ptl)}  "
              f"turn q1={q1} median={med} q3={q3}")
        print(f"  => GAME-DECIDING TURN RANGE (IQR): turns {q1}-{q3}")

    print("\n" + "=" * 72)
    print("D4  TIME BUDGET AUDIT (600 s per player per match)")
    print("=" * 72)
    per = [g["time_seat0"] for g in games] + [g["time_seat1"] for g in games]
    per.sort()
    pct = [x / 600.0 * 100 for x in per]
    def q(v, f):
        return v[min(len(v) - 1, int(f * len(v)))]
    print(f"  player-matches sampled: {len(per)}")
    print(f"  seconds/player/match : min {per[0]:.1f}  q1 {q(per,.25):.1f}  "
          f"median {q(per,.5):.1f}  q3 {q(per,.75):.1f}  p95 {q(per,.95):.1f}  max {per[-1]:.1f}")
    print(f"  as % of 600 s bank   : min {pct[0]:.1f}%  q1 {q(pct,.25):.1f}%  "
          f"median {q(pct,.5):.1f}%  q3 {q(pct,.75):.1f}%  p95 {q(pct,.95):.1f}%  "
          f"max {pct[-1]:.1f}%")
    edges = [(0, 5), (5, 10), (10, 20), (20, 40), (40, 70), (70, 100), (100, 1e9)]
    h = hist(pct, edges)
    print("  distribution across player-matches:")
    for lo, hi in edges:
        c = h[(lo, hi)]
        lab = f"{lo}-{hi}%" if hi < 1e9 else ">100% (TIMEOUT)"
        bar = "#" * int(40 * c / max(1, len(pct)))
        print(f"    {lab:<16s} {c:4d} {c/len(pct)*100:5.1f}% {bar}")
    tl = [g["turns"] for g in games]
    print(f"  game length: median {st.median(tl):.0f} turns, max {max(tl)}")
    print(f"  headroom at p95: {100 - q(pct,.95):.1f} points of the bank unused")


if __name__ == "__main__":
    main()
