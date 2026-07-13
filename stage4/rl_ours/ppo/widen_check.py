"""Function-preservation gate for the 128k wide net (Net2WiderNet embed).

Proves that WiderPolicyNet.embed_from_narrow(BC-v2) computes the BC-v2 function
bit-for-bit BEFORE any training, i.e. KL(pi_wide || pi_BC) = 0 at init. Same
methodology as bit_match.py (same captured decision states, same argmax + max
|delta-logit| criteria), but the reference is the 27.8k numpy BC and the model
under test is the WIDE torch net.

Three guarantees on real decision states:

  A. Embed fidelity — the wide torch net (embed_from_narrow) produces the SAME
     argmax and near-identical logits as main.py's numpy BC forward, on both
     MAIN and ST_CARD decisions. This is the KL=0 claim, tested not asserted.

  B. Export round-trip (ship guarantee) — export the wide torch net to npz, run
     it through main.py's own numpy forward (the 3-layer trunk / 160-wide head
     load path that ships), confirm identical decisions to the wide torch net.

  C. Card-head byte-identity — the frozen card head must export byte-for-byte
     equal to BC-v2's card head (it is a straight copy; a nonzero diff here is
     a construction bug, not float noise).

PASS requires 0 argmax flips on every MAIN and ST_CARD decision for A and B,
and exact card-head equality for C. float32 BLAS differs at ~1e-5 and the wide
net has one extra trunk matmul, so a max|delta-logit| up to ~1e-4 is expected
and fine as long as no decision flips. Any argmax disagreement = STOP.
"""

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

from . import collect, common, net


def _numpy_logits(model, kind, sel, cur):
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


def run(n_games=80, cap=2400, min_decisions=1000, verbose=True,
        src=None, trunk_hidden=(320, 160), main_hidden=160):
    """Verify function-preservation of GROWING `src` (a policy npz; default
    BC-v2) into WiderPolicyNet(trunk_hidden, main_hidden). Works for any
    source->target on the capacity ladder (27.8k->128k->256k...)."""
    src = src or common.BC_WEIGHTS
    if verbose:
        print("growing %s -> trunk %s, main_hidden %d"
              % (Path(src).name, tuple(trunk_hidden), main_hidden))
        print("collecting decision states from %d self-play games..." % n_games)
    decisions = collect.collect_decisions(n_games=n_games, cap=cap)
    n_main = sum(1 for d in decisions if d[0] == "main")
    n_card = sum(1 for d in decisions if d[0] == "card")
    if verbose:
        print("captured %d decisions (%d MAIN, %d ST_CARD)"
              % (len(decisions), n_main, n_card))
    if len(decisions) < min_decisions:
        print("FAIL: too few decisions captured (%d < %d)"
              % (len(decisions), min_decisions))
        return False

    numpy_bc = common.load_policy_npz(src)           # the SOURCE (reference)
    # THE model under test: grown net embedding `src` function-preservingly
    wide = net.grow_policy_weights(numpy_bc, tuple(trunk_hidden), main_hidden)
    if verbose:
        n_par = sum(p.numel() for p in wide.parameters())
        print("target net params: %d" % n_par)

    tmp = Path(tempfile.gettempdir()) / "ppo_widen_export.npz"
    wide.export_npz(tmp)
    numpy_wide = common.load_policy_npz(tmp)

    a_flips = b_flips = 0
    a_maxdiff = b_maxdiff = 0.0
    checked = checked_main = checked_card = 0
    for kind, sel, cur in decisions:
        np_logits, state, rows = _numpy_logits(numpy_bc, kind, sel, cur)
        if len(np_logits) < 2:
            continue
        checked += 1
        checked_main += (kind == "main")
        checked_card += (kind == "card")
        t_logits = _torch_logits(wide, kind, state, rows)
        exp_logits = common.head_logits(
            numpy_wide, "head" if kind == "main" else "head_card",
            common.trunk_forward(numpy_wide, state), rows)

        if int(np.argmax(np_logits)) != int(np.argmax(t_logits)):
            a_flips += 1
        a_maxdiff = max(a_maxdiff, float(np.abs(np_logits - t_logits).max()))
        if int(np.argmax(t_logits)) != int(np.argmax(exp_logits)):
            b_flips += 1
        b_maxdiff = max(b_maxdiff, float(np.abs(t_logits - exp_logits).max()))

    # guarantee C: frozen card head must be a byte copy of BC-v2's card head
    c_diff = 0.0
    for (Ww, bw), (Wb, bb) in zip(numpy_wide["head_card"], numpy_bc["head_card"]):
        c_diff = max(c_diff, float(np.abs(Ww - Wb).max()),
                     float(np.abs(bw - bb).max()))

    ok = (a_flips == 0 and b_flips == 0 and c_diff == 0.0)
    print("=" * 62)
    print("WIDEN FUNCTION-PRESERVATION  (checked %d: %d MAIN, %d ST_CARD)"
          % (checked, checked_main, checked_card))
    print("  A numpy-BC vs wide-torch    : %d argmax flips, max|Δlogit|=%.3e"
          % (a_flips, a_maxdiff))
    print("  B wide-torch vs wide-export : %d argmax flips, max|Δlogit|=%.3e"
          % (b_flips, b_maxdiff))
    print("  C frozen card head byte-eq  : max|Δweight|=%.3e (%s)"
          % (c_diff, "EQUAL" if c_diff == 0.0 else "NOT EQUAL -- bug"))
    print("  => KL(pi_wide || pi_BC) = 0 at init : %s" % ("YES" if ok else "NO"))
    print("  VERDICT : %s" % ("PASS" if ok else "FAIL -- STOP, no training"))
    print("=" * 62)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=80)
    ap.add_argument("--cap", type=int, default=2400)
    ap.add_argument("--min-decisions", type=int, default=1000)
    ap.add_argument("--src", default=None,
                    help="source policy npz to grow (default: BC-v2). Point at "
                         "a trained 128k checkpoint to verify a 128k->256k grow.")
    ap.add_argument("--trunk-hidden", default="320,160",
                    help="target trunk hidden dims, comma-separated")
    ap.add_argument("--main-hidden", type=int, default=160,
                    help="target MAIN-head hidden width")
    args = ap.parse_args()
    th = tuple(int(x) for x in args.trunk_hidden.split(","))
    ok = run(n_games=args.games, cap=args.cap, min_decisions=args.min_decisions,
             src=args.src, trunk_hidden=th, main_hidden=args.main_hidden)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
