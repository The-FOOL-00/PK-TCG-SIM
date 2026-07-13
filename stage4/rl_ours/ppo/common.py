"""Shared plumbing for the Stage-4 PPO stack.

Single source of truth for: repo paths, engine loading (banner-suppressed),
agent-module attr contract (same semantics as tools/ab_gate.make_wrapper),
the numpy policy forward pass (actors + bit-match reference + export check),
and trajectory encoding. Every consumer — rollout workers, leakage audit,
bit-match, export — encodes through encode_decision_* here, so the audited
path IS the training path.
"""

import contextlib
import io
import math
import os
import random
import sys
from pathlib import Path

# repo root: env override (lab package) > two levels up from this file's
# stage4/rl_ours/ppo/ location.
REPO = Path(os.environ.get("PTCG_REPO", "")
            or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
    from kaggle_environments import make as _ke_make  # noqa: E402

import main as agent_mod  # noqa: E402

ST_MAIN = agent_mod.ST_MAIN
ST_CARD = agent_mod.ST_CARD
ST_ATTACHED_CARD = agent_mod.ST_ATTACHED_CARD
ST_CARD_OR_ATTACHED = agent_mod.ST_CARD_OR_ATTACHED

N_STATE = 170
N_MAIN_FEAT = 41
N_CARD_FEAT = 73

# ---------------------------------------------------------------- specs ----
# Agent specs use the exact tools/ab_gate syntax: "deck.csv+NAME=VALUE".
LEARNER_SPEC = "stage4/deck_list0.csv+BC=list0_b+DYN_DECK_TABLES=true+BC_BRAKE=0"
V220_SPEC = "metaC_garchomp_nasuo.csv+BC=garchomp_full+DYN_DECK_TABLES=true"
BC_ANCHOR_SPEC = "stage4/deck_list0.csv+BC=list0_b+DYN_DECK_TABLES=true+BC_BRAKE=0"
V1_SPECS = (
    "metaC_garchomp_nasuo.csv",
    "metaB_alakazam.csv",
    "metaC_kangaskhan.csv",
    "metaD_mewtwo_kashiwashira.csv",
    "deck.csv",
)

BC_WEIGHTS = "bc_weights_list0_b.npz"
VALUE_WARMSTART = "value_weights_mlp.npz"


def make_env():
    """cabt env with all import/creation banner noise suppressed."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return _ke_make("cabt", debug=True)


def read_deck(path):
    p = Path(path)
    if not p.is_absolute():
        p = REPO / p
    return [int(line.strip()) for line in open(p) if line.strip()]


def parse_spec(spec):
    """'deck.csv+BC=x+FLAG=true' -> (deck list, {attr: value}). ab_gate syntax."""
    parts = str(spec).split("+")
    deck = read_deck(parts[0])
    attrs = {}
    for tok in parts[1:]:
        if tok == "v3":
            attrs["V3_EVAL"] = True
            continue
        name, val = tok.split("=", 1)
        for cast in (int, float):
            try:
                val = cast(val)
                break
            except ValueError:
                continue
        else:
            val = {"true": True, "false": False}.get(str(val).lower(), val)
        attrs[name] = val
    return deck, attrs


def apply_attrs(deck, attrs, defaults):
    """Reset `defaults` then apply this side's attrs + deck-derived attrs.
    Same both-seats-share-the-module contract as ab_gate.make_wrapper."""
    agent_mod.DECK = list(deck)
    agent_mod.TOTAL_BASIC_ENERGY = sum(
        1 for cid in deck
        if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)
    for name, val in defaults.items():
        setattr(agent_mod, name, val)
    for name, val in attrs.items():
        setattr(agent_mod, name, val)


def collect_defaults(*attr_dicts):
    """Module-default values for every attr any side touches (reset set)."""
    names = set()
    for d in attr_dicts:
        names |= set(d)
    return {n: getattr(agent_mod, n) for n in names if hasattr(agent_mod, n)}


def make_league_wrapper(spec, defaults):
    """Plain main.py agent under `spec` — a league opponent."""
    deck, attrs = parse_spec(spec)

    def wrapper(obs, _config=None):
        if obs.get("select") is None:
            return list(deck)
        apply_attrs(deck, attrs, defaults)
        return agent_mod.agent(obs)
    return wrapper


# ------------------------------------------------------- numpy policy ----

def load_policy_npz(path):
    """{'trunk': [(W,b)...], 'head': [...], 'head_card': [...]} float32."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO / p
    z = np.load(p)
    def stack(prefix_w, prefix_b, n):
        return [(z["%s%d" % (prefix_w, i)].astype(np.float32),
                 z["%s%d" % (prefix_b, i)].astype(np.float32))
                for i in range(n)]
    return {
        "trunk": stack("TW", "Tb", int(z["n_trunk"])),
        "head": stack("HW", "Hb", int(z["n_head"])),
        "head_card": stack("CW", "Cb", int(z["n_head_card"])),
    }


def save_policy_npz(path, model):
    """Inverse of load_policy_npz, schema-compatible with main.py _bc_model."""
    out = {
        "kind": np.asarray("policy_two_head"),
        "n_state_features": np.asarray(N_STATE),
        "n_option_features": np.asarray(N_MAIN_FEAT),
        "n_option_features_card": np.asarray(N_CARD_FEAT),
        "n_trunk": np.asarray(len(model["trunk"])),
        "n_head": np.asarray(len(model["head"])),
        "n_head_card": np.asarray(len(model["head_card"])),
    }
    for pre, key in (("T", "trunk"), ("H", "head"), ("C", "head_card")):
        for i, (W, b) in enumerate(model[key]):
            out["%sW%d" % (pre, i)] = W.astype(np.float32)
            out["%sb%d" % (pre, i)] = b.astype(np.float32)
    np.savez(path, **out)


def trunk_forward(model, state):
    emb = np.asarray(state, dtype=np.float32)
    for W, b in model["trunk"]:
        emb = np.maximum(emb @ W + b, 0.0)
    return emb


def head_logits(model, head_key, emb, rows):
    """Per-option logits — numerically identical to main.py _pol_choose /
    _bc_card_choose (same op order: concat, ReLU MLP, final affine)."""
    rows = np.asarray(rows, dtype=np.float32)
    h = np.concatenate([np.repeat(emb[None, :], len(rows), 0), rows], axis=1)
    for W, b in model[head_key][:-1]:
        h = np.maximum(h @ W + b, 0.0)
    W, b = model[head_key][-1]
    return (h @ W + b).ravel()


def softmax(x):
    x = np.asarray(x, dtype=np.float64)
    x = x - x.max()
    e = np.exp(x)
    return e / e.sum()


# ------------------------------------------------- decision encoding ----
# The one true encode path: rollout workers, the leakage audit, bit-match
# and gates all call these. main.py owns the feature math.

def encode_decision_main(sel, cur):
    """(state170, rows n*41) for a MAIN single-select decision."""
    state = np.asarray(agent_mod.encode_state(cur), dtype=np.float32)
    rows = np.asarray(agent_mod.encode_options(sel, cur), dtype=np.float32)
    return state, rows


def encode_decision_card(sel, cur):
    """(state170, rows n*73) for an ST_CARD-family decision."""
    state = np.asarray(agent_mod.encode_state(cur), dtype=np.float32)
    rows = np.asarray(agent_mod.encode_card_options(sel, cur), dtype=np.float32)
    return state, rows


def decision_kind(sel):
    """'main' | 'card' | None — exactly _bc_decide's eligibility rule."""
    if not isinstance(sel, dict):
        return None
    stype = sel.get("type")
    nopt = len(sel.get("option") or [])
    if (stype == ST_MAIN and sel.get("minCount", 1) == 1
            and sel.get("maxCount", 1) == 1 and nopt > 1):
        return "main"
    if stype in (ST_CARD, ST_ATTACHED_CARD, ST_CARD_OR_ATTACHED) and nopt > 1:
        return "card"
    return None


def shaping_scalars(cur):
    """Visible counters for potential-based shaping: (my_prizes_left,
    opp_prizes_left, my_deck, opp_deck). Counts only — no identities."""
    me = cur.get("yourIndex") or 0
    players = cur.get("players") or [{}, {}]
    mine, theirs = players[me], players[1 - me]
    return (len(mine.get("prize") or []), len(theirs.get("prize") or []),
            mine.get("deckCount") or 0, theirs.get("deckCount") or 0)


def sample_from_logits(logits, rng, temperature=1.0):
    """(index, logprob of the sample). rng is a np.random.Generator.
    Logprob is under the T=1 distribution the learner optimizes, even when
    sampling at temperature != 1 (importance weights stay consistent as long
    as training uses T=1 everywhere; default keeps them identical)."""
    z = np.asarray(logits, dtype=np.float64)
    zt = (z / max(temperature, 1e-6)) - (z / max(temperature, 1e-6)).max()
    pt = np.exp(zt)
    pt /= pt.sum()
    i = int(rng.choice(len(pt), p=pt))
    z1 = z - z.max()
    p1 = np.exp(z1)
    p1 /= p1.sum()
    return i, float(math.log(max(p1[i], 1e-30)))
