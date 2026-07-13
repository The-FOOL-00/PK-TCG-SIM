# Formal K1 gates — PPO ckpt iter044 / iter059 vs v2.2.0 (2026-07-13)

Dedicated 200-game gates through the **ship path** (`tools/ab_gate.py`, main.py
greedy `_bc_decide`, **search off**, seats alternated, Wilson 95% CI). Learner
checkpoint registered as `BC=ckptNNN` (copy of `runs/policy_iterNNN.npz`).
Incumbent = v2.2.0 (`metaC_garchomp_nasuo.csv+BC=garchomp_full`). Run on the
laptop; the lab PC run1 was NOT touched.

Pre-registered **K1 = two consecutive 200-game gates < 29% vs v2.2.0**.

| Gate | W/L/D | win rate | 95% Wilson CI | vs 29% (K1) | vs 50% (ship) |
|------|-------|----------|---------------|-------------|---------------|
| BC-v2 no-brake (PPO **start**) | 67/133/0 | **33.5%** | [27.3, 40.3] | above | FAIL |
| PPO **iter044** | 63/137/0 | **31.5%** | [25.5, 38.2] | above | FAIL |
| PPO **iter059** | 69/131/0 | **34.5%** | [28.3, 41.3] | above | FAIL |

Zero draws in all three (draws-as-0.5 and draws-excluded scoring coincide).
Zero crashes (INVALID/ERROR/TIMEOUT = 0) in all three.

## Verdict

- **K1 has NOT formally fired.** Both consecutive checkpoints read **above**
  29% (31.5%, 34.5%). The specific numeric trigger did not trip.
- **But there is no improvement.** iter044/059 (31.5/34.5%) are statistically
  indistinguishable from the BC-v2 start (33.5%) — CIs overlap almost
  completely. Across ~14k training games, PPO moved winrate-vs-v2.2.0 by
  ~0 points. Flat, exactly as the in-training proxy indicated (shape, not level).
- **Still fails the ship bar** (needs > 50%; sitting at ~1/3).

## Two methodology notes that matter

1. **Greedy > sampled.** The earlier in-training proxy read ~25–28% because it
   SAMPLED at temperature 1 and scored wins-only. The ship path is greedy
   argmax → 31–34%. The proxy was a conservative lower bound; it OVER-predicted
   a K1 trip. Running the formal greedy gate (not acting on the proxy) is why
   we did not wrongly declare K1.
2. **Brake confound vs G7a.** G7a (39% [33.7,44.6]) was BC-v2 **with** the
   draw-brake (N=10). These gates are **no-brake** (the trained artifact). The
   clean no-brake comparison is start 33.5% → ckpt 31.5/34.5% = flat. The brake
   is an orthogonal, untested-on-PPO lever, not part of this measurement.

## Loss anatomy (consistent across all three)

Losses dominated by lost prize races (reason 1: 74/65/83 of ~133 losses),
then self-deckout (reason 2: ~40), then no-active (reason 3). Same signature as
the G6/G7 Alakazam-vs-Garchomp finding — the matchup deficit is structural, not
a training-instability artifact.

## What this is / isn't

- NOT a K1 collapse (nothing < 29%; nothing below the BC start).
- NOT improvement (dead flat vs the ship opponent over 14k games).
- It IS the "healthy loop / no matchup progress" plateau: anchor winrate holds
  (~44–47%), KL bounded (~0.015), throughput 19.7k games/h, no Sanjay-collapse —
  the loop trains stably but KL-anchored policy gradient near BC does not close
  the Alakazam-vs-Garchomp matchup. The situation K1 was meant to catch is
  present in the milder "no-improvement" form rather than the "collapse" form.

Decision on next steps (capacity growth 27.8k→128k, or otherwise) deferred to
the user + advisor. No further work begun.
