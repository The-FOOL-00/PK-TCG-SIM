"""Automated capacity-limited-vs-still-climbing verdict for any run's history.json.

Encodes the exact diagnostic we applied by hand to run1 (83.5k games -> flat
27.1% -> capacity-limited) and run2_local (24k games -> flat but too few
converged iters -> inconclusive), so it can be re-run standalone against any
run (run1/run2/run2_local/run3) without re-describing the methodology.

    python -m stage4.rl_ours.ppo.verdict --log stage4/rl_ours/runs/run2/history.json

What it does, all automatic:
  1. Auto-detects the CONVERGED window (incumbent_share at its ceiling), so the
     winrate_incumbent reads are NOT diluted by the low-share ramp-up iters.
  2. Pools winrate_incumbent vs v2.2.0 over converged first/second halves and the
     freshest tail, each with a Wilson 95% CI. Flat = CIs overlap; climbing =
     2nd-half lower bound clears 1st-half upper bound; declining = the reverse.
  3. Trends mean_outcome, vf (critic), kl_anchor over early/mid/late thirds.
     vf "plateaued" = late >= 0.9*early (didn't keep dropping). kl "asymptoted"
     = the late increment is <= half the early increment (leveled off).
  4. Emits ONE recommendation from the pre-registered decision logic:
       climbing winrate                         -> CONTINUE (improving)
       flat + vf plateaued + kl asymptoted      -> CAPACITY-LIMITED (grow net)
       flat but vf/kl still moving              -> CONTINUE (not yet conclusive)
       declining winrate                        -> REGRESSION (investigate)
     Gated by a minimum converged sample: below CONV_GAMES_MIN games the
     capacity call is only "directional", not high-confidence.
"""

import argparse
import json
import math
from pathlib import Path

# pre-registered gate thresholds (configs.py KILL)
K1_THRESH = 0.29
K2_150K = (150_000, 0.44)
K2_300K = (300_000, 0.48)
# a capacity-limited call needs at least this many converged (full-share) games
# to be high-confidence (run1 had ~25.8k and was conclusive; run2_local ~5k was
# not). Below this the plateau read is "directional only".
CONV_GAMES_MIN = 15_000
# critic is "still learning" if late-third vf dropped more than this (relative).
VF_LEARNING_DROP = 0.15


def wilson(w, n, z=1.959963984540054):
    if not n:
        return (None, None, None)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def pool_incumbent(sl):
    w = sum(x.get("wins_incumbent", 0) or 0 for x in sl)
    n = sum(x.get("n_incumbent", 0) or 0 for x in sl)
    return w, n


def mean(sl, k):
    v = [x[k] for x in sl if x.get(k) is not None]
    return sum(v) / len(v) if v else float("nan")


def converged_window(hist):
    """Iters at >=95% of the incumbent_share ceiling (ramp-dilution correction)."""
    shares = [x.get("incumbent_share", 0) or 0 for x in hist]
    ceil = max(shares) if shares else 0
    if ceil <= 0:
        return [], 0.0
    return [x for x in hist if (x.get("incumbent_share", 0) or 0) >= 0.95 * ceil], ceil


def _fmt(p, lo, hi):
    return "%.1f%% CI[%.1f,%.1f]" % (p * 100, lo * 100, hi * 100) if p is not None else "n/a"


def verdict(log_path):
    hist = json.loads(Path(log_path).read_text(encoding="utf-8"))
    if not hist:
        print("empty history")
        return None
    n_it = len(hist)
    games = sum(x.get("n_games", 0) for x in hist)
    elapsed = hist[-1].get("elapsed_s", 0) or 0
    gph = games / elapsed * 3600 if elapsed else 0
    conv, ceil = converged_window(hist)
    conv_games = sum(x.get("n_incumbent", 0) or 0 for x in conv)

    print("=" * 66)
    print("VERDICT  (%s)" % Path(log_path).name)
    print("  iters %d | games %d | %.0f games/h | incumbent_share ceiling %.3f"
          % (n_it, games, gph, ceil))
    print("  converged window: %d iters (from iter %s), %d incumbent games"
          % (len(conv), conv[0].get("iter") if conv else "-", conv_games))

    # ---- winrate_incumbent: converged halves + fresh tail --------------------
    trend_win = "n/a"
    if conv:
        h = len(conv) // 2
        w1 = wilson(*pool_incumbent(conv[:h])) if h else (None, None, None)
        w2 = wilson(*pool_incumbent(conv[h:]))
        wt = wilson(*pool_incumbent(conv[-20:]))
        wa = wilson(*pool_incumbent(conv))
        print("-" * 66)
        print("  winrate_incumbent vs v2.2.0 (converged window, wins-only):")
        print("    all       : %s" % _fmt(*wa))
        print("    1st half  : %s" % _fmt(*w1))
        print("    2nd half  : %s" % _fmt(*w2))
        print("    last 20it : %s" % _fmt(*wt))
        # classify
        if w1[0] is not None and w2[0] is not None:
            if w2[1] > w1[2]:            # 2nd-half lower bound clears 1st upper
                trend_win = "climbing"
            elif w2[2] < w1[1]:          # 2nd-half upper below 1st lower
                trend_win = "declining"
            else:
                trend_win = "flat"
        print("    -> winrate trend: %s" % trend_win.upper())

    # ---- vf / kl / mean_outcome trends over thirds ---------------------------
    t = max(1, n_it // 3)
    early, mid, late = hist[:t], hist[t:2 * t], hist[2 * t:]
    vf_e, vf_m, vf_l = mean(early, "vf"), mean(mid, "vf"), mean(late, "vf")
    kl_e, kl_m, kl_l = mean(early, "kl_anchor"), mean(mid, "kl_anchor"), mean(late, "kl_anchor")
    print("-" * 66)
    print("  mean_outcome  early %.4f -> mid %.4f -> late %.4f"
          % (mean(early, "mean_outcome"), mean(mid, "mean_outcome"), mean(late, "mean_outcome")))
    print("  vf (critic)   early %.5f -> mid %.5f -> late %.5f" % (vf_e, vf_m, vf_l))
    print("  kl_anchor     early %.5f -> mid %.5f -> late %.5f" % (kl_e, kl_m, kl_l))

    # vf plateaued if late did not keep dropping meaningfully
    vf_still_learning = (vf_e > 0 and vf_l < vf_e * (1 - VF_LEARNING_DROP))
    # kl asymptoted if the late increment is <= half the early increment
    inc_early = kl_m - kl_e
    inc_late = kl_l - kl_m
    if inc_early <= 1e-9:
        kl_still_climbing = inc_late > 1e-4     # was flat early, now rising
    else:
        kl_still_climbing = inc_late > 0.5 * inc_early
    print("    -> vf %s ; kl_anchor %s"
          % ("STILL LEARNING" if vf_still_learning else "PLATEAUED",
             "STILL CLIMBING" if kl_still_climbing else "ASYMPTOTED"))

    # ---- K1 / K2 gate reads --------------------------------------------------
    print("-" * 66)
    if conv:
        pr = wilson(*pool_incumbent(conv))
        k1 = "TRIP" if pr[2] < K1_THRESH else ("WARN" if pr[0] < K1_THRESH else "OK")
        print("  K1 (<%.0f%%): converged %s -> %s"
              % (K1_THRESH * 100, _fmt(*pr), k1))
    for g_ckpt, thr in (K2_150K, K2_300K):
        if games >= g_ckpt:
            best = max((wilson(*pool_incumbent(conv))[0] if conv else 0,), default=0)
            print("  K2 @%dk: reached; best converged %.1f%% vs %.0f%% -> %s"
                  % (g_ckpt // 1000, (best or 0) * 100, thr * 100,
                     "OK" if best and best >= thr else "PLATEAU (grow net)"))
        else:
            print("  K2 @%dk: not evaluable (%d/%d games)" % (g_ckpt // 1000, games, g_ckpt))

    # ---- single recommendation ----------------------------------------------
    print("=" * 66)
    enough = conv_games >= CONV_GAMES_MIN
    conf = "HIGH-CONFIDENCE" if enough else "DIRECTIONAL (few converged games)"
    if trend_win == "climbing":
        rec = "CONTINUE TRAINING — winrate_incumbent still improving; capacity is being used, do not grow yet."
    elif trend_win == "declining":
        rec = "REGRESSION — winrate_incumbent falling; investigate (Sanjay 34->5% pattern), do NOT grow."
    elif trend_win == "flat" and not vf_still_learning and not kl_still_climbing:
        if enough:
            rec = ("CAPACITY-LIMITED — grow to the next rung. Flat winrate + plateaued critic + "
                   "asymptoted KL = the small net is saturated, not mid-learning.")
        else:
            # the capacity signature is PRESENT but on too few converged games to
            # act on — exactly run2_local (61 converged iters vs run1's 309). Do
            # not grow yet; accumulate the sample first.
            rec = ("KEEP TRAINING TO CONFIRM — the capacity-limited signature (flat winrate + "
                   "plateaued critic + asymptoted KL) is present, but on only %d converged "
                   "games (< %d). Run to >=%d before treating as conclusive; do NOT grow on this alone."
                   % (conv_games, CONV_GAMES_MIN, CONV_GAMES_MIN))
    elif trend_win == "flat":
        why = []
        if vf_still_learning:
            why.append("critic still improving")
        if kl_still_climbing:
            why.append("KL still climbing")
        rec = ("CONTINUE TRAINING — winrate flat but %s; dynamics still moving, let it run "
               "before declaring capacity-limited." % " and ".join(why))
    else:
        rec = "INCONCLUSIVE — no converged window yet (incumbent ramp unfinished); keep training."
    print("  CONVERGED SAMPLE : %s" % conf)
    print("  RECOMMENDATION   : %s" % rec)
    print("=" * 66)
    return {"trend_win": trend_win, "vf_still_learning": vf_still_learning,
            "kl_still_climbing": kl_still_climbing, "conv_games": conv_games,
            "recommendation": rec}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    verdict(ap.parse_args().log)


if __name__ == "__main__":
    main()
