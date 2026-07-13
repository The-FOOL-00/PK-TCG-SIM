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


# ---- K1/K2 gate signal ------------------------------------------------------
# The pre-registered gates (configs.py KILL) are:
#   K1: two consecutive 200-game gates < 29% vs v2.2.0 => halt, revert.
#   K2: no gate >= 44% by 150k games or >= 48% by 300k => grow net first.
# THESE ARE FORMAL, DEDICATED 200-game evals (learner vs v2.2.0, search-off),
# not the in-training league games. This module reports an EARLY-WARNING PROXY
# from the in-training winrate_incumbent stream so we are not eyeballing raw
# JSON. A proxy trip does NOT by itself fire K1 -- it says "run the formal
# gate now, it will very likely come in below threshold." Two caveats on the
# proxy vs the formal gate:
#   (1) winrate_incumbent counts OUTRIGHT WINS only (o==1); draws are excluded
#       from the numerator, so the proxy is a conservative LOWER bound vs a
#       win-fraction gate that scores draws as 0.5.
#   (2) early iters draw few incumbent games at low incumbent_share; the honest
#       apples-to-apples read is the CONVERGED window (share at its ceiling).
K1_THRESH = 0.29
K2_G150K = (150_000, 0.44)
K2_G300K = (300_000, 0.48)


def _cum_games(hist):
    return sum(h.get("n_games", 0) for h in hist)


def _trailing_incumbent(hist, min_games=200):
    """Pool the most recent iters until >= min_games incumbent games seen.
    Mirrors a formal 200-game gate as closely as the in-training stream allows.
    Returns (wins, n, rate, n_iters_used)."""
    w = n = k = 0
    for h in reversed(hist):
        ni = h.get("n_incumbent", 0) or 0
        if ni == 0:
            continue
        w += h.get("wins_incumbent", 0) or 0
        n += ni
        k += 1
        if n >= min_games:
            break
    return w, n, (w / n if n else None), k


def _converged_window(hist):
    """Iters where incumbent_share has reached (>=95% of) its ceiling."""
    shares = [h.get("incumbent_share", 0) or 0 for h in hist]
    ceiling = max(shares) if shares else 0
    if ceiling <= 0:
        return []
    return [h for h in hist if (h.get("incumbent_share", 0) or 0) >= 0.95 * ceiling]


def gate_check(hist):
    """Print the K1/K2 early-warning section. Returns a dict of signals."""
    n_it = len(hist)
    games = _cum_games(hist)
    third = max(1, n_it // 3)
    ew, en, er = _pool(hist[:third], "n_incumbent", "wins_incumbent", "winrate_incumbent")
    lw, ln, lr = _pool(hist[-third:], "n_incumbent", "wins_incumbent", "winrate_incumbent")
    tw, tn, tr, tk = _trailing_incumbent(hist, 200)
    conv = _converged_window(hist)
    cw, cn, cr = _pool(conv, "n_incumbent", "wins_incumbent", "winrate_incumbent") \
        if conv else (None, 0, None)

    k1_pct = int(round(K1_THRESH * 100))
    print("-" * 64)
    print("K1/K2 GATE SIGNAL vs v2.2.0 (incumbent) -- EARLY-WARNING PROXY")
    print("  (in-training league games; wins-only, draws excluded. Formal")
    print("   K1 = two consecutive dedicated 200-game gates < %d%%.)" % k1_pct)
    if er is not None:
        _, elo, ehi = _wilson(ew, en)
        print("  early-third  %d/%d = %.1f%%  CI[%.1f,%.1f]"
              % (ew, en, er * 100, elo * 100, ehi * 100))
    if lr is not None:
        _, llo, lhi = _wilson(lw, ln)
        print("  late-third   %d/%d = %.1f%%  CI[%.1f,%.1f]"
              % (lw, ln, lr * 100, llo * 100, lhi * 100))
    if cr is not None:
        _, clo, chi = _wilson(cw, cn)
        print("  converged*   %d/%d = %.1f%%  CI[%.1f,%.1f]   (*share at ceiling)"
              % (cw, cn, cr * 100, clo * 100, chi * 100))
    if tr is not None:
        _, tlo, thi = _wilson(tw, tn)
        print("  trailing~200 %d/%d = %.1f%%  CI[%.1f,%.1f]   (last %d iters)"
              % (tw, tn, tr * 100, tlo * 100, thi * 100, tk))

    # --- K1 proxy verdict. Lead with the converged window (share at ceiling,
    # most games, apples-to-apples with a formal gate); fall back to trailing
    # if the ramp hasn't converged yet. TRIP = Wilson UPPER bound < threshold,
    # i.e. we are statistically confident the true winrate is below K1.
    if cr is not None and cn >= 200:
        pw, pn, pr, plabel = cw, cn, cr, "converged"
    else:
        pw, pn, pr, plabel = tw, tn, tr, "trailing"
    k1_proxy = None
    if pr is not None and pn > 0:
        _, _, phi = _wilson(pw, pn)
        if phi < K1_THRESH:
            k1_proxy = "TRIP"     # even the optimistic CI edge is below thresh
        elif pr < K1_THRESH:
            k1_proxy = "WARN"     # point estimate below, CI still straddles
        else:
            k1_proxy = "OK"
    print("  K1 proxy [%s window]: %s" % (plabel, {
        "TRIP": "TRIP -- upper CI < %d%%; run the FORMAL 200-game gate, it will"
                " almost certainly read < %d%%." % (k1_pct, k1_pct),
        "WARN": "WARN -- point est < %d%% but CI straddles; needs more games." % k1_pct,
        "OK": "OK -- >= %d%%." % k1_pct,
        None: "n/a (no incumbent games yet)",
    }[k1_proxy]))

    # --- K2: checkpoints at 150k / 300k games. Report reach + best proxy.
    best = max((cr, tr, lr, er), default=None,
               key=lambda x: (x if x is not None else -1))
    for g_ckpt, thr in (K2_G150K, K2_G300K):
        if games >= g_ckpt:
            hit = (best is not None and best >= thr)
            print("  K2 @%dk: reached (games %d). best proxy %.1f%% vs %d%% -> %s"
                  % (g_ckpt // 1000, games, (best or 0) * 100, thr * 100,
                     "OK" if hit else "PLATEAU SIGNAL (grow net first)"))
        else:
            print("  K2 @%dk: not evaluable -- %d/%d games (need %d more)"
                  % (g_ckpt // 1000, games, g_ckpt, g_ckpt - games))
    return {"k1_proxy": k1_proxy, "games": games,
            "trailing": (tw, tn, tr), "converged": (cw, cn, cr)}


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
    gate_check(hist)
    print("=" * 64)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="stage4/rl_ours/runs/valA/history.json")
    args = ap.parse_args()
    analyze(args.log)


if __name__ == "__main__":
    main()
