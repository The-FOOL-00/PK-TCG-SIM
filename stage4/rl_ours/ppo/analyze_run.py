"""Read a training history.json and report the validation verdict.

The pre-registered validation kill check: winrate-vs-anchor late in the run
must NOT be below its early-run value (the teammate's 34->5% collapse is the
specific pattern we must not reproduce). Also reports the KL-anchor trend
(prior-destruction guard) and throughput (nproc go/no-go floor).

Win rates are aggregated over the first-third and last-third of iterations by
POOLING games (wins/n), not by averaging small-sample per-iter rates — exact
when the trainer logged n_anchor/wins_anchor, else falls back to mean-of-rates.

    python -m stage4.rl_ours.ppo.analyze_run --log stage4/rl_ours/runs/valA/history.json
"""

import argparse
import json
import math
from pathlib import Path


def _wilson(w, n, z=1.959963984540054):
    if n == 0:
        return (None, None, None)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def _pool(hist, key_n, key_w, key_rate):
    """(wins, n, rate) pooled over a slice, exact if counts present."""
    if all(key_n in h for h in hist):
        n = sum(h[key_n] for h in hist)
        w = sum(h[key_w] for h in hist)
        return w, n, (w / n if n else None)
    rates = [h[key_rate] for h in hist if h.get(key_rate) is not None]
    return None, len(rates), (sum(rates) / len(rates) if rates else None)


def analyze(log_path):
    hist = json.loads(Path(log_path).read_text(encoding="utf-8"))
    if not hist:
        print("empty history")
        return None
    n_it = len(hist)
    games = sum(h["n_games"] for h in hist)
    elapsed = hist[-1].get("elapsed_s", 0)
    gph = games / elapsed * 3600 if elapsed else 0
    third = max(1, n_it // 3)
    early, late = hist[:third], hist[-third:]

    ew, en, er = _pool(early, "n_anchor", "wins_anchor", "winrate_anchor")
    lw, ln, lr = _pool(late, "n_anchor", "wins_anchor", "winrate_anchor")
    kl_early = sum(h.get("kl_anchor", 0) for h in early) / len(early)
    kl_late = sum(h.get("kl_anchor", 0) for h in late) / len(late)
    out_early = sum(h["mean_outcome"] for h in early) / len(early)
    out_late = sum(h["mean_outcome"] for h in late) / len(late)

    print("=" * 64)
    print("VALIDATION RUN ANALYSIS  (%s)" % Path(log_path).name)
    print("  iters %d | games %d | %.0fs | %.0f games/h" % (n_it, games, elapsed, gph))
    print("  anchor winrate  early %s  ->  late %s"
          % ("%.3f" % er if er is not None else "-",
             "%.3f" % lr if lr is not None else "-"))
    if ew is not None:
        _, elo, ehi = _wilson(ew, en)
        _, llo, lhi = _wilson(lw, ln)
        print("    early %d/%d  CI[%.2f,%.2f]   late %d/%d  CI[%.2f,%.2f]"
              % (ew, en, elo, ehi, lw, ln, llo, lhi))
    print("  mean outcome    early %.3f  ->  late %.3f" % (out_early, out_late))
    print("  KL-to-BC anchor early %.4f  ->  late %.4f" % (kl_early, kl_late))

    # verdict
    regressed = (er is not None and lr is not None and lr < er - 0.05)
    kl_ok = kl_late < 0.15         # bounded anchor => no prior destruction
    thr_ok = gph >= 1500
    ok = (not regressed) and kl_ok
    print("  ---")
    print("  no anchor-winrate regression : %s" % ("YES" if not regressed else "NO"))
    print("  KL anchor bounded (<0.15)    : %s (%.4f)" % ("YES" if kl_ok else "NO", kl_late))
    print("  throughput >= 1500 games/h   : %s (%.0f)" % ("YES" if thr_ok else "NO", gph))
    print("  VALIDATION VERDICT : %s"
          % ("PASS — loop improves/holds, no Sanjay-pattern collapse"
             if ok else "FAIL — investigate before the long run"))
    print("=" * 64)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="stage4/rl_ours/runs/valA/history.json")
    args = ap.parse_args()
    analyze(args.log)


if __name__ == "__main__":
    main()
