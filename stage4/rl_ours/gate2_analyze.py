"""Gate 2 factorial analysis.

P1  = contested zero-discrimination rate (band <= 20%).
P2' = median signal-bearing agreement MINUS that arm's OWN simulated chance
      floor. Raw modal shares are never compared across arms (Gate 1 defect:
      the floor moves with strict-det count, 0.694 @ ~1.5 dets vs ~0.42 @ 16).

Bootstrap 95% CI on P2' by resampling contested decisions; the chance floor is
recomputed inside each bootstrap replicate from that replicate's own
(n_cands, n_dets_strict) distribution, so the CI covers floor uncertainty too.
"""

import argparse
import json
import random
import statistics as st
from pathlib import Path

CONTESTED_MARGIN = 0.10
MIN_STRICT_DECISIONS = 200      # below this the floor sim is unreliable -> INCONCLUSIVE


def _floor(pool, rng, trials):
    if not pool:
        return None
    tot = 0.0
    for _ in range(trials):
        c, dd = pool[rng.randrange(len(pool))]
        counts = [0] * max(1, c)
        for _ in range(dd):
            counts[rng.randrange(max(1, c))] += 1
        tot += max(counts) / dd
    return tot / trials


def excess(rows, rng, trials=600):
    sb = [r["agreement_strict"] for r in rows if r["agreement_strict"] is not None]
    pool = [(r["n_cands"], r["n_dets_strict"]) for r in rows if r["n_dets_strict"] > 0]
    if not sb or not pool:
        return None, None, None
    raw = st.median(sb)
    fl = _floor(pool, rng, trials)
    return raw, fl, raw - fl


def arm(path, label, boot=400, seed=11):
    d = json.loads(Path(path).read_text())
    dec = d["decisions"]
    C = [r for r in dec if r["n_legal"] >= 3 and r["margin"] < CONTESTED_MARGIN]
    zero = sum(1 for r in C if r["n_dets_strict"] == 0)
    n_strict = sum(1 for r in C if r["n_dets_strict"] > 0)
    rng = random.Random(seed)
    raw, fl, exc = excess(C, rng)
    # bootstrap
    cis = []
    if n_strict >= MIN_STRICT_DECISIONS:
        for _ in range(boot):
            samp = [C[rng.randrange(len(C))] for _ in range(len(C))]
            _r, _f, e = excess(samp, rng, trials=300)
            if e is not None:
                cis.append(e)
        cis.sort()
    lo = cis[int(0.025 * len(cis))] if cis else None
    hi = cis[int(0.975 * len(cis))] if cis else None
    g = d.get("games") or []
    per = sorted([x["time_seat0"] for x in g] + [x["time_seat1"] for x in g])
    return {
        "label": label, "cfg": d.get("config", {}),
        "games": len(g), "contested": len(C), "n_strict_decisions": n_strict,
        "P1": zero / len(C) if C else None,
        "raw": raw, "floor": fl, "P2p": exc, "ci": (lo, hi),
        "mean_dets": st.mean(r["n_dets"] for r in dec) if dec else None,
        "p95_pct": per[min(len(per) - 1, int(0.95 * len(per)))] / 600 * 100 if per else None,
        "inconclusive": n_strict < MIN_STRICT_DECISIONS,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="label=path")
    args = ap.parse_args()
    arms = {}
    for spec in args.runs:
        label, path = spec.split("=", 1)
        if not Path(path).exists():
            print(f"  MISSING: {path}")
            continue
        arms[label] = arm(path, label)

    print(f"\n{'arm':<6s} {'games':>5s} {'contst':>6s} {'P1':>7s} {'raw P2':>7s} "
          f"{'floor':>7s} {'P2-prime':>9s} {'boot 95% CI':>20s} {'dets':>5s} {'p95%':>6s}")
    print("-" * 100)
    for k in sorted(arms):
        r = arms[k]
        ci = f"[{r['ci'][0]:+.4f},{r['ci'][1]:+.4f}]" if r["ci"][0] is not None else "INCONCLUSIVE"
        print(f"{k:<6s} {r['games']:>5d} {r['contested']:>6d} {r['P1']*100:>6.1f}% "
              f"{r['raw']:>7.4f} {r['floor']:>7.4f} {r['P2p']:>+9.4f} {ci:>20s} "
              f"{r['mean_dets']:>5.1f} {r['p95_pct']:>5.1f}%")

    def g(k, f):
        return arms[k][f] if k in arms else None
    if all(k in arms for k in ("A1", "A2", "A3", "A4")):
        print("\nFACTORIAL (leaf: terminal->graded ; prior: uniform->archetype)")
        for f, name in (("P1", "P1 zero-disc"), ("P2p", "P2-prime")):
            a1, a2, a3, a4 = (arms["A1"][f], arms["A2"][f], arms["A3"][f], arms["A4"][f])
            leaf = ((a2 + a4) / 2) - ((a1 + a3) / 2)
            prior = ((a3 + a4) / 2) - ((a1 + a2) / 2)
            inter = (a4 - a3) - (a2 - a1)
            print(f"  {name:<14s} main(leaf)={leaf:+.4f}  main(prior)={prior:+.4f}  "
                  f"interaction={inter:+.4f}")
            print(f"                 cells: A1={a1:+.4f} A2={a2:+.4f} A3={a3:+.4f} A4={a4:+.4f}")
    if "A4" in arms and "A5" in arms:
        c4, c5 = arms["A4"]["ci"], arms["A5"]["ci"]
        if c4[0] is None or c5[0] is None:
            print("\nA4 vs A5 separation: INCONCLUSIVE (a CI could not be computed)")
        else:
            sep = c4[0] > c5[1]
            print(f"\nA4 vs A5 separation: A4 CI [{c4[0]:+.4f},{c4[1]:+.4f}]  "
                  f"A5 CI [{c5[0]:+.4f},{c5[1]:+.4f}]  -> "
                  f"{'NON-OVERLAPPING (separates)' if sep else 'OVERLAPPING (does NOT separate)'}")


if __name__ == "__main__":
    main()
