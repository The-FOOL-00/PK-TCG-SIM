"""Gate 1 metrics: P1 (contested zero-discrimination) and P2 (contested
signal-bearing agreement), plus the simulated chance floor for P2 and the
leaf-branch audit. Same contested definition as PIMC_DIAGNOSTIC.md."""

import argparse
import json
import random
import statistics as st
from pathlib import Path

CONTESTED_MARGIN = 0.10


def chance_floor(rows, trials=4000, seed=7):
    """Expected P2 if votes were uniform-random over the candidates, using the
    ACTUAL (n_cands, n_dets_strict) distribution of the arm."""
    rng = random.Random(seed)
    vals = []
    pool = [(r["n_cands"], r["n_dets_strict"]) for r in rows if r["n_dets_strict"] > 0]
    if not pool:
        return None
    for _ in range(trials):
        c, d = pool[rng.randrange(len(pool))]
        counts = [0] * max(1, c)
        for _ in range(d):
            counts[rng.randrange(max(1, c))] += 1
        vals.append(max(counts) / d)
    return st.mean(vals)


def metrics(path, label):
    d = json.loads(Path(path).read_text())
    dec = d["decisions"]
    C = [r for r in dec if r["n_legal"] >= 3 and r["margin"] < CONTESTED_MARGIN]
    zero = [r for r in C if r["n_dets_strict"] == 0]
    sb = [r["agreement_strict"] for r in C if r["agreement_strict"] is not None]
    L = d.get("leaf") or {}
    tot = (L.get("n_terminal", 0) + L.get("n_cap", 0)) or 1
    g = d.get("games") or []
    per = [x["time_seat0"] for x in g] + [x["time_seat1"] for x in g]
    per.sort()
    p95 = per[min(len(per) - 1, int(0.95 * len(per)))] if per else 0.0
    wins0 = sum(1 for x in g if x["winner"] == 0)
    return {
        "label": label,
        "cfg": d.get("config", {}),
        "games": len(g),
        "decisions": len(dec),
        "contested": len(C),
        "P1_zero_discrimination": len(zero) / len(C) if C else None,
        "P2_agreement_median": st.median(sb) if sb else None,
        "P2_chance_floor": chance_floor(C),
        "spread_mean": st.mean(r["mean_spread"] for r in C) if C else None,
        "alltied_mean": st.mean(r["all_tied_frac"] for r in C) if C else None,
        "S1_zero_all": sum(1 for r in dec if r["n_dets_strict"] == 0) / len(dec) if dec else None,
        "terminal_pct": L.get("n_terminal", 0) / tot,
        "cap_pct": L.get("n_cap", 0) / tot,
        "leaf_min": L.get("min"), "leaf_max": L.get("max"),
        "p95_s": p95, "p95_pct_bank": p95 / 600 * 100,
        "seat0_winrate": wins0 / len(g) if g else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True,
                    help="label=path pairs")
    args = ap.parse_args()
    rows = []
    for spec in args.runs:
        label, path = spec.split("=", 1)
        if not Path(path).exists():
            print(f"  (missing: {path})")
            continue
        rows.append(metrics(path, label))

    print(f"\n{'arm':<22s} {'games':>5s} {'contst':>6s} {'P1 zero-disc':>13s} "
          f"{'P2 agree':>9s} {'chance':>7s} {'spread':>7s} {'term%':>6s} "
          f"{'p95 %bank':>10s}")
    print("-" * 96)
    for r in rows:
        print(f"{r['label']:<22s} {r['games']:>5d} {r['contested']:>6d} "
              f"{r['P1_zero_discrimination']*100:>12.1f}% "
              f"{r['P2_agreement_median']:>9.3f} "
              f"{(r['P2_chance_floor'] or 0):>7.3f} "
              f"{r['spread_mean']:>7.3f} {r['terminal_pct']*100:>5.1f}% "
              f"{r['p95_pct_bank']:>9.1f}%")
    print(f"\n{'arm':<22s} {'P2 raw':>8s} {'chance':>8s} {'P2-chance':>10s}  "
          f"(P2 is only comparable across arms as excess over ITS OWN chance floor)")
    for r in rows:
        ch = r["P2_chance_floor"] or 0
        print(f"{r['label']:<22s} {r['P2_agreement_median']:>8.4f} {ch:>8.4f} "
              f"{r['P2_agreement_median'] - ch:>+10.4f}")
    print()
    for r in rows:
        lo = "n/a" if r["leaf_min"] is None else f"{r['leaf_min']:.4f}"
        hi = "n/a" if r["leaf_max"] is None else f"{r['leaf_max']:.4f}"
        print(f"{r['label']}: cfg={r['cfg']} leaf_range=[{lo},{hi}] "
              f"all-tied={r['alltied_mean']:.3f} "
              f"S1(all-dec zero)={r['S1_zero_all']*100:.1f}% "
              f"seat0_wr={r['seat0_winrate']*100:.1f}%")


if __name__ == "__main__":
    main()
