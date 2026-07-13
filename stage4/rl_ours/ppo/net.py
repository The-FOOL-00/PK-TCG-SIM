"""Torch mirror of the shipped numpy BC-v2 policy + a PPO value critic.

The policy trunk and two heads are a bit-for-bit structural mirror of
bc_weights_list0_b.npz (main.py _pol_choose / _bc_card_choose). Warm-start is
a DIRECT weight copy: torch Linear stores weight as (out, in) and computes
x @ W.T, while the npz stores (in, out) for x @ W, so weight = npz_W.T and
bias = npz_b. Export inverts the transpose, so a round-trip through
save_policy_npz reproduces the exact float32 weights main.py loads.

The critic is a SEPARATE MLP over the raw 170-dim state (warm-started from
value_weights_mlp.npz). Keeping it off the shared trunk means value-gradient
noise never perturbs the trunk that produces the shipped policy — only the
policy loss and the KL anchor touch it. The critic never ships.
"""

import numpy as np
import torch
import torch.nn as nn

from . import common


def _copy_linear(lin, W, b):
    """Load npz (in,out) W and (out,) b into a torch Linear (out,in)."""
    assert lin.weight.shape == (W.shape[1], W.shape[0]), \
        (lin.weight.shape, W.shape)
    assert lin.bias.shape == (b.shape[0],), (lin.bias.shape, b.shape)
    with torch.no_grad():
        lin.weight.copy_(torch.from_numpy(np.ascontiguousarray(W.T)))
        lin.bias.copy_(torch.from_numpy(np.ascontiguousarray(b)))


class PolicyNet(nn.Module):
    """Shared trunk + MAIN head + ST_CARD head. Forward takes a state vector
    and a batch of option-feature rows, returns per-option logits — the same
    quantity main.py turns into an argmax at serve time."""

    def __init__(self):
        super().__init__()
        # trunk 170 -> 80 -> 48
        self.t0 = nn.Linear(common.N_STATE, 80)
        self.t1 = nn.Linear(80, 48)
        # MAIN head (emb48 + opt41=89) -> 48 -> 1
        self.h0 = nn.Linear(48 + common.N_MAIN_FEAT, 48)
        self.h1 = nn.Linear(48, 1)
        # ST_CARD head (emb48 + card73=121) -> 48 -> 1
        self.c0 = nn.Linear(48 + common.N_CARD_FEAT, 48)
        self.c1 = nn.Linear(48, 1)

    def trunk(self, state):
        x = torch.relu(self.t0(state))
        return torch.relu(self.t1(x))

    def _head_logits(self, emb, rows, lin0, lin1):
        # emb: (E,)  rows: (n, F) -> (n, E+F) -> (n, 48) -> (n,)
        n = rows.shape[0]
        h = torch.cat([emb.unsqueeze(0).expand(n, -1), rows], dim=1)
        h = torch.relu(lin0(h))
        return lin1(h).squeeze(-1)

    def main_logits(self, state, rows):
        return self._head_logits(self.trunk(state), rows, self.h0, self.h1)

    def card_logits(self, state, rows):
        return self._head_logits(self.trunk(state), rows, self.c0, self.c1)

    def logits(self, kind, state, rows):
        return self.main_logits(state, rows) if kind == "main" \
            else self.card_logits(state, rows)

    def main_logits_batched(self, states, rows, mask):
        """Batched MAIN logits for the PPO update.
        states (B,170), rows (B,M,41), mask (B,M) bool. Returns (B,M) with
        masked-out options set to -1e9 (so log_softmax zeroes them)."""
        emb = torch.relu(self.t1(torch.relu(self.t0(states))))   # (B,48)
        B, M, _ = rows.shape
        h = torch.cat([emb.unsqueeze(1).expand(B, M, -1), rows], dim=2)
        h = torch.relu(self.h0(h))
        logits = self.h1(h).squeeze(-1)                          # (B,M)
        return logits.masked_fill(~mask, -1e9)

    # ---- warm start / export ----
    def load_bc_npz(self, path=common.BC_WEIGHTS):
        m = common.load_policy_npz(path)
        (tW0, tb0), (tW1, tb1) = m["trunk"]
        (hW0, hb0), (hW1, hb1) = m["head"]
        (cW0, cb0), (cW1, cb1) = m["head_card"]
        _copy_linear(self.t0, tW0, tb0)
        _copy_linear(self.t1, tW1, tb1)
        _copy_linear(self.h0, hW0, hb0)
        _copy_linear(self.h1, hW1, hb1)
        _copy_linear(self.c0, cW0, cb0)
        _copy_linear(self.c1, cW1, cb1)
        return self

    def export_npz(self, path):
        def wb(lin):
            W = lin.weight.detach().cpu().numpy().T.astype(np.float32)  # (in,out)
            b = lin.bias.detach().cpu().numpy().astype(np.float32)
            return W, b
        model = {
            "trunk": [wb(self.t0), wb(self.t1)],
            "head": [wb(self.h0), wb(self.h1)],
            "head_card": [wb(self.c0), wb(self.c1)],
        }
        common.save_policy_npz(path, model)


class ValueNet(nn.Module):
    """Critic over raw state: 170 -> 128 -> 64 -> 1, sigmoid output = P(win),
    matching value_weights_mlp's contract (relu hidden, sigmoid = P(win|state)).
    Values and returns live in [0,1] ({win:1, draw:0.5, loss:0})."""

    def __init__(self):
        super().__init__()
        self.v0 = nn.Linear(common.N_STATE, 128)
        self.v1 = nn.Linear(128, 64)
        self.v2 = nn.Linear(64, 1)

    def forward(self, state):
        x = torch.relu(self.v0(state))
        x = torch.relu(self.v1(x))
        return torch.sigmoid(self.v2(x).squeeze(-1))

    def load_warmstart(self, path=common.VALUE_WARMSTART):
        import pathlib
        p = pathlib.Path(path)
        if not p.is_absolute():
            p = common.REPO / p
        z = np.load(p)
        _copy_linear(self.v0, z["W0"], z["b0"])
        _copy_linear(self.v1, z["W1"], z["b1"])
        _copy_linear(self.v2, z["W2"], z["b2"])
        return self


def build_policy(warmstart=True):
    net = PolicyNet()
    if warmstart:
        net.load_bc_npz()
    net.eval()
    return net


def build_value(warmstart=True):
    net = ValueNet()
    if warmstart:
        try:
            net.load_warmstart()
        except Exception as e:  # value warm-start is optional, policy is not
            print("[net] value warm-start skipped (%r); random init" % e)
    return net
