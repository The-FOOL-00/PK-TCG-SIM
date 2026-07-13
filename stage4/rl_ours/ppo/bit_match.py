"""Tier-1 STOP gate: torch mirror must decide identically to shipped numpy.

Two guarantees on real decision states:

  A. Warm-start fidelity — the torch mirror loaded from bc_weights_list0_b.npz
     produces the SAME argmax (and near-identical logits) as main.py's numpy
     forward. Confirms PPO starts from the BC policy, not a corrupted copy.

  B. Export round-trip (the ship guarantee) — export the torch mirror to npz,
     run it through main.py's own forward, and confirm identical decisions.
     This is exactly what ships, so this is the bit-exactness that matters.

PASS requires 100% argmax agreement on every captured MAIN and ST_CARD
decision for BOTH guarantees. Max abs logit diff is reported; float32 BLAS
backends differ at ~1e-5, so a nonzero diff is expected and fine as long as
no decision flips. Any argmax disagreement = STOP (no training).
"""

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

from . import collect, common, net


def _numpy_logits(model, kind, sel, cur):
    """main.py's exact forward for one decision -> per-option logits."""
    state, rows = (common.encode_decision_main(sel, cur) if kind == "main"
                   else common.encode_decision_card(sel, cur))
    emb = common.trunk_forward(model, state)
    head = "head" if kind == "main" else "head_card"
    return common.head_logits(model, head, emb, rows), state, rows


def _torch_logits(pnet, kind, state, rows):
    with torch.no_grad():
        s = torch.from_numpy(np.asarray(state, dtype=np.float32))
        r = torch.from_numpy(np.asarray(rows, dtype=np.float32))
        return pnet.logits(kind, s, r).cpu().numpy()


def run(n_games=40, cap=1200, verbose=True):
    if verbose:
        print("collecting decision states from %d self-play games..." % n_games)
    decisions = collect.collect_decisions(n_games=n_games, cap=cap)
    n_main = sum(1 for d in decisions if d[0] == "main")
    n_card = sum(1 for d in decisions if d[0] == "card")
    if verbose:
        print("captured %d decisions (%d MAIN, %d ST_CARD)"
              % (len(decisions), n_main, n_card))
    if len(decisions) < 200:
        print("FAIL: too few decisions captured (%d < 200)" % len(decisions))
        return False

    # guarantee A: torch-from-BC vs numpy-BC
    numpy_bc = common.load_policy_npz(common.BC_WEIGHTS)
    pnet = net.build_policy(warmstart=True)

    # guarantee B: export torch -> npz -> numpy, compare to torch
    tmp = Path(tempfile.gettempdir()) / "ppo_bitmatch_export.npz"
    pnet.export_npz(tmp)
    numpy_exported = common.load_policy_npz(tmp)

    a_flips = b_flips = 0
    a_maxdiff = b_maxdiff = 0.0
    checked = 0
    for kind, sel, cur in decisions:
        np_logits, state, rows = _numpy_logits(numpy_bc, kind, sel, cur)
        if len(np_logits) < 2:
            continue
        checked += 1
        t_logits = _torch_logits(pnet, kind, state, rows)
        exp_logits = common.head_logits(
            numpy_exported, "head" if kind == "main" else "head_card",
            common.trunk_forward(numpy_exported, state), rows)

        if int(np.argmax(np_logits)) != int(np.argmax(t_logits)):
            a_flips += 1
        a_maxdiff = max(a_maxdiff, float(np.abs(np_logits - t_logits).max()))
        if int(np.argmax(t_logits)) != int(np.argmax(exp_logits)):
            b_flips += 1
        b_maxdiff = max(b_maxdiff, float(np.abs(t_logits - exp_logits).max()))

    ok = (a_flips == 0 and b_flips == 0)
    print("=" * 60)
    print("BIT-MATCH  (checked %d multi-option decisions)" % checked)
    print("  A numpy-BC vs torch-mirror : %d argmax flips, max|Δlogit|=%.3e"
          % (a_flips, a_maxdiff))
    print("  B torch-mirror vs exported : %d argmax flips, max|Δlogit|=%.3e"
          % (b_flips, b_maxdiff))
    print("  VERDICT : %s" % ("PASS" if ok else "FAIL -- STOP, no training"))
    print("=" * 60)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--cap", type=int, default=1200)
    args = ap.parse_args()
    ok = run(n_games=args.games, cap=args.cap)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
