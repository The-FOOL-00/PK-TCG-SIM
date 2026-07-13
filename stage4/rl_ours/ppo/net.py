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


class WiderPolicyNet(nn.Module):
    """Capacity-grown policy (~128k params) that EMBEDS the 27.8k BC-v2 net
    function-preservingly (Net2WiderNet zero-output + identity-carry for the
    added trunk layer). At init it computes the BC-v2 function bit-for-bit, so
    KL(pi_wide || pi_BC) = 0 and training starts from the known policy, not a
    cold net. The 48-dim embedding interface is held fixed so the FROZEN card
    head stays byte-identical to BC-v2 (the export/bit-match contract).

    Default: trunk 170->320->160->48 (3 layers, one deeper than BC-v2's 2),
    MAIN head 89->160->1, card head 121->48->1 (frozen)."""

    def __init__(self, trunk_hidden=(320, 160), emb=48, main_hidden=160):
        super().__init__()
        self.trunk_hidden = tuple(trunk_hidden)
        self.emb = emb
        self.main_hidden = main_hidden
        dims = [common.N_STATE] + list(trunk_hidden) + [emb]
        self.trunk_layers = nn.ModuleList(
            nn.Linear(dims[i], dims[i + 1]) for i in range(len(dims) - 1))
        self.h0 = nn.Linear(emb + common.N_MAIN_FEAT, main_hidden)
        self.h1 = nn.Linear(main_hidden, 1)
        # card head fixed 48-wide, frozen at BC-v2
        self.c0 = nn.Linear(emb + common.N_CARD_FEAT, 48)
        self.c1 = nn.Linear(48, 1)

    def trunk(self, state):
        x = state
        for lin in self.trunk_layers:
            x = torch.relu(lin(x))
        return x

    def _head_logits(self, emb, rows, lin0, lin1):
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
        emb = states
        for lin in self.trunk_layers:
            emb = torch.relu(lin(emb))
        B, M, _ = rows.shape
        h = torch.cat([emb.unsqueeze(1).expand(B, M, -1), rows], dim=2)
        h = torch.relu(self.h0(h))
        logits = self.h1(h).squeeze(-1)
        return logits.masked_fill(~mask, -1e9)

    def embed_from_narrow(self, path=common.BC_WEIGHTS, seed=0, scale=0.01):
        """Function-preserving embed of the 27.8k BC-v2 net. Requires the
        default arch (trunk 170->320->160->48, MAIN 89->160->1)."""
        assert len(self.trunk_layers) == 3, "embed assumes a 3-layer trunk"
        m = common.load_policy_npz(path)
        (O1, o1b), (O2, o2b) = m["trunk"]          # (170,80),(80,48) npz conv
        (H0, h0b), (H1, h1b) = m["head"]           # (89,48),(48,1)
        (C0, c0b), (C1, c1b) = m["head_card"]      # frozen
        h1w = self.trunk_hidden[0]                 # 320
        h2w = self.trunk_hidden[1]                 # 160
        n0 = O1.shape[1]                           # 80 (BC trunk hidden-1)
        n1 = O2.shape[1]                           # 48 (BC emb)
        rng = np.random.default_rng(seed)
        z = np.zeros

        # L1 (170 -> h1w): first n0 units = O1; rest new (small random in,
        # zero out via L2). identity-carry needs the real signal in [0:n0].
        L1 = z((common.N_STATE, h1w), np.float32)
        L1[:, :n0] = O1
        L1[:, n0:] = (rng.standard_normal((common.N_STATE, h1w - n0)) * scale)
        L1b = z(h1w, np.float32); L1b[:n0] = o1b

        # L2 (h1w -> h2w): outputs [0:n0] copy the carried signal via identity
        # (input dims [0:n0] only), so relu preserves a>=0 exactly; outputs
        # [n0:] are new capacity (zeroed downstream by L3).
        L2 = z((h1w, h2w), np.float32)
        L2[:n0, :n0] = np.eye(n0, dtype=np.float32)
        L2[:, n0:] = (rng.standard_normal((h1w, h2w - n0)) * scale)
        L2b = z(h2w, np.float32)

        # L3 (h2w -> emb=n1): apply O2 to the carried signal in [0:n0]; new
        # dims [n0:] get ZERO outgoing weight -> exact function preservation.
        L3 = z((h2w, n1), np.float32)
        L3[:n0, :] = O2
        L3b = o2b.astype(np.float32)

        # MAIN head h0 (89 -> main_hidden): first n1 units = H0; rest new.
        Hw = self.main_hidden
        HW0 = z((O2.shape[1] + common.N_MAIN_FEAT, Hw), np.float32)  # (89,Hw)
        HW0[:, :n1] = H0
        HW0[:, n1:] = (rng.standard_normal((HW0.shape[0], Hw - n1)) * scale)
        HW0b = z(Hw, np.float32); HW0b[:n1] = h0b
        # h1 (main_hidden -> 1): first n1 = H1; new = zero outgoing.
        HW1 = z((Hw, 1), np.float32); HW1[:n1, :] = H1
        HW1b = h1b.astype(np.float32)

        _copy_linear(self.trunk_layers[0], L1, L1b)
        _copy_linear(self.trunk_layers[1], L2, L2b)
        _copy_linear(self.trunk_layers[2], L3, L3b)
        _copy_linear(self.h0, HW0, HW0b)
        _copy_linear(self.h1, HW1, HW1b)
        _copy_linear(self.c0, C0, c0b)   # card head frozen == BC-v2
        _copy_linear(self.c1, C1, c1b)
        return self

    def export_npz(self, path):
        def wb(lin):
            W = lin.weight.detach().cpu().numpy().T.astype(np.float32)
            b = lin.bias.detach().cpu().numpy().astype(np.float32)
            return W, b
        model = {
            "trunk": [wb(l) for l in self.trunk_layers],
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


def make_policy(cfg=None):
    """Factory keyed on cfg so trainer AND parallel workers build the same
    architecture from the pickled config (state_dict must match the class)."""
    if cfg and cfg.get("wide"):
        return WiderPolicyNet(
            trunk_hidden=tuple(cfg.get("trunk_hidden", (320, 160))),
            emb=cfg.get("emb", 48),
            main_hidden=cfg.get("main_hidden", 160))
    return PolicyNet()


def build_policy_wide(warmstart=True, src=common.BC_WEIGHTS,
                      trunk_hidden=(320, 160), emb=48, main_hidden=160):
    net = WiderPolicyNet(trunk_hidden=trunk_hidden, emb=emb,
                         main_hidden=main_hidden)
    if warmstart:
        net.embed_from_narrow(src)
    net.eval()
    return net


# ------------------------------------------------------- general grower -----
# The capacity ladder (27.8k -> 128k -> 256k -> ...) needs a grower that is NOT
# hardcoded to today's widths. grow_policy_weights embeds ANY source policy npz
# (arbitrary trunk depth/widths, 2-layer MAIN head) into ANY wider/deeper target
# WiderPolicyNet function-preservingly, so KL(pi_target || pi_source) = 0 at init
# for whatever checkpoint we point it at tomorrow. Two mechanisms, both already
# validated in embed_from_narrow, now generalized:
#   - Net2WiderNet: new output units get small-random INCOMING weights and ZERO
#     OUTGOING weights (into the next layer's original units) -> exact function.
#   - Net2DeeperNet: when the target trunk is DEEPER than the source, the extra
#     layers are inserted as identity-carry (eye on the carried units, small
#     random on the new units) -> ReLU-safe pass-through of the source signal.
# emb (48) and input (170) are held fixed so the FROZEN card head stays byte-
# identical and the embedding interface is unchanged.

def grow_policy_weights(src_model, trunk_hidden, main_hidden, emb=48,
                        seed=0, scale=0.01):
    """Return a WiderPolicyNet(trunk_hidden, emb, main_hidden) that computes the
    src_model function bit-for-bit at init. src_model is a loaded policy dict
    {trunk:[(W,b)...], head:[(W,b),(W,b)], head_card:[...]} (npz in,out convention).
    Requires target trunk depth >= source trunk depth and target widths >=
    source widths at every matched layer; emb and the 170-dim input must match."""
    rng = np.random.default_rng(seed)
    z = np.zeros
    tgt = WiderPolicyNet(trunk_hidden=tuple(trunk_hidden), emb=emb,
                         main_hidden=main_hidden)

    # ---- trunk ----
    src_tr = src_model["trunk"]                      # [(W,b), ...] npz (in,out)
    Ls = len(src_tr)
    Lt = len(tgt.trunk_layers)
    assert Lt >= Ls, "target trunk must be at least as deep as source (%d<%d)" % (Lt, Ls)
    assert src_tr[0][0].shape[0] == common.N_STATE, "source input must be 170"
    assert src_tr[-1][0].shape[1] == emb, "source emb must match target emb (%d)" % emb
    n_insert = Lt - Ls
    # source carried widths at each source-layer boundary: [170, s1, ..., emb]
    src_w = [common.N_STATE] + [W.shape[1] for (W, b) in src_tr]
    tgt_w = [common.N_STATE] + list(trunk_hidden) + [emb]

    # target layer plan: layer 0 = src layer 0 (widened); layers 1..n_insert =
    # identity inserts (carrying src_w[1]); then src layers 1..Ls-1 (widened).
    for ti in range(Lt):
        din, dout = tgt_w[ti], tgt_w[ti + 1]
        if ti == 0:
            si = 0
            kind = "src"
        elif ti <= n_insert:
            kind = "id"
        else:
            si = ti - n_insert
            kind = "src"

        if kind == "src":
            W, b = src_tr[si]                        # (src_w[si], src_w[si+1])
            cin, cout = src_w[si], src_w[si + 1]     # carried in/out widths
            T = z((din, dout), np.float32)
            T[:cin, :cout] = W                       # original signal
            if dout > cout:                          # new output units: random in
                T[:, cout:] = rng.standard_normal((din, dout - cout)).astype(np.float32) * scale
            # new INPUT dims (cin:) already contribute 0 to original outputs
            # (T[cin:, :cout] left zero) -> exact preservation.
            Tb = z(dout, np.float32); Tb[:cout] = b
        else:  # identity-carry insert; carried width is src_w[1]
            c = src_w[1]
            T = z((din, dout), np.float32)
            T[:c, :c] = np.eye(c, dtype=np.float32)
            if dout > c:
                T[:, c:] = rng.standard_normal((din, dout - c)).astype(np.float32) * scale
            Tb = z(dout, np.float32)
        _copy_linear(tgt.trunk_layers[ti], T, Tb)

    # ---- MAIN head (always 2 layers; only main_hidden widens) ----
    (H0, h0b), (H1, h1b) = src_model["head"]         # (emb+MAIN_FEAT, s_mh),(s_mh,1)
    s_mh = H0.shape[1]
    M = main_hidden
    assert H0.shape[0] == emb + common.N_MAIN_FEAT, "head input width mismatch"
    HW0 = z((emb + common.N_MAIN_FEAT, M), np.float32)
    HW0[:, :s_mh] = H0
    if M > s_mh:
        HW0[:, s_mh:] = rng.standard_normal((HW0.shape[0], M - s_mh)).astype(np.float32) * scale
    HW0b = z(M, np.float32); HW0b[:s_mh] = h0b
    HW1 = z((M, 1), np.float32); HW1[:s_mh, :] = H1  # new units: zero outgoing
    HW1b = h1b.astype(np.float32)
    _copy_linear(tgt.h0, HW0, HW0b)
    _copy_linear(tgt.h1, HW1, HW1b)

    # ---- card head: frozen byte-copy of the source card head ----
    (C0, c0b), (C1, c1b) = src_model["head_card"]
    _copy_linear(tgt.c0, C0, c0b)
    _copy_linear(tgt.c1, C1, c1b)
    tgt.eval()
    return tgt


def build_policy_grown(src=common.BC_WEIGHTS, trunk_hidden=(512, 256),
                       main_hidden=256, emb=48, seed=0, scale=0.01):
    """Convenience: load a source policy npz and grow it into the target arch."""
    return grow_policy_weights(common.load_policy_npz(src), trunk_hidden,
                               main_hidden, emb=emb, seed=seed, scale=scale)


def build_value(warmstart=True):
    net = ValueNet()
    if warmstart:
        try:
            net.load_warmstart()
        except Exception as e:  # value warm-start is optional, policy is not
            print("[net] value warm-start skipped (%r); random init" % e)
    return net
