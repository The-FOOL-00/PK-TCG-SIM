"""FIRST ACTION ON ARRIVAL — automated preflight for the lab PC.

Runs the pre-registered arrival sequence and prints a go/no-go:
  1. report nproc (core count) and pick the fork-gate config
  2. run the leakage audit  (STOP gate — any fail => no training)
  3. run the bit-match test (STOP gate — any argmax flip => no training)
  4. print the config, throughput note, and the exact launch command

Exit code 0 only if BOTH gates pass AND the fork gate authorizes launch
(>=8 cores). Colab tier (<8) exits 2 = STOP-and-escalate-to-user. Any gate
fail exits 1 = STOP. Nothing here launches training; it clears the runway.

    python -m stage4.rl_ours.lab.preflight
"""

import os
import sys

from stage4.rl_ours.ppo import bit_match, configs, leakage_audit


def main():
    print("=" * 68)
    print("LAB PREFLIGHT  (first action on arrival)")
    print("=" * 68)

    n_cores = os.cpu_count() or 1
    name, cfg, go = configs.select(n_cores)
    print("[1] nproc            : %d cores" % n_cores)
    print("    fork-gate config : %s  (workers=%d, games/iter=%d)"
          % (name, cfg["workers"], cfg["games_per_iter"]))
    if not go:
        print("    >>> COLAB TIER (<8 cores): pre-registered go/no-go.")
        print("    >>> Do NOT launch. Confirm combined throughput >=1500 games/h")
        print("    >>> with the home box before committing, else NO-GO (ride v2.2.0).")

    print("\n[2] leakage audit (STOP gate)...")
    leak_ok = leakage_audit.run(n_games=40, cap=1500, verbose=False)

    print("\n[3] bit-match test (STOP gate)...")
    bit_ok = bit_match.run(n_games=30, cap=1000, verbose=False)

    print("\n" + "=" * 68)
    print("PREFLIGHT SUMMARY")
    print("  leakage audit : %s" % ("PASS" if leak_ok else "FAIL"))
    print("  bit-match     : %s" % ("PASS" if bit_ok else "FAIL"))
    print("  fork config   : %s (%s)"
          % (name, "launch-authorized" if go else "GO/NO-GO -> escalate"))
    gates_ok = leak_ok and bit_ok
    if not gates_ok:
        print("  VERDICT       : STOP — a STOP gate failed. No training.")
        print("=" * 68)
        return 1
    if not go:
        print("  VERDICT       : STOP — <8 cores. Report to user before launch.")
        print("=" * 68)
        return 2
    print("  VERDICT       : GO — gates green, config %s. Launch command:" % name)
    print("    python -m stage4.rl_ours.ppo.train --iters <N> \\")
    print("      --games-per-iter %d --workers %d \\"
          % (cfg["games_per_iter"], cfg["workers"]))
    print("      --out stage4/rl_ours/runs/run1 --log stage4/rl_ours/runs/run1/history.json")
    print("  (kill criteria are armed by the driver — see ppo/configs.py KILL)")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
