"""Self-play rollout: play one cabt game, collect the learner's trajectory.

The learner acts with the torch PolicyNet on MAIN single-select decisions
(sampled at train temperature) and delegates ST_CARD-family and every other
decision to main.py's own agent (BC card head under LEARNER_SPEC, v1 else).
MAIN is where the strategic policy lives and is what the ship artifact's
raw head decides; the ST_CARD head enters the gradient in a later iteration
(logged as a known scope boundary, not a silent omission).

The draw-brake is OFF during training (LEARNER_SPEC sets BC_BRAKE=0): PPO must
learn not to deck itself out — that self-deckout-becomes-negative-gradient is
the whole point (writeup §5-iii). The brake returns as an ablatable ship flag.

Reward: terminal only, {win:1, draw:0.5, loss:0}. Potential-based shaping on
visible prize/deck counts is added with coefficient `shaping_coef` (0 = pure
terminal); being potential-based, it never changes the optimal policy, only
the credit-assignment density.
"""

import contextlib
import io

import numpy as np
import torch

from . import common


class Step:
    __slots__ = ("state", "rows", "action", "logprob", "value", "phi")

    def __init__(self, state, rows, action, logprob, value, phi):
        self.state = state        # (170,) float32
        self.rows = rows          # (n, 41) float32
        self.action = action      # int index into rows
        self.logprob = logprob    # float, under T=1 policy at collection
        self.value = value        # float, critic P(win) at this state
        self.phi = phi            # float, shaping potential at this state


def _potential(cur, w_prize, w_deck):
    """Φ(s) in [~-1,1]: prize lead (their taken - our taken) + deck margin.
    Uses only visible counts (leakage audit C6)."""
    myp, oppp, myd, oppd = common.shaping_scalars(cur)
    prize_lead = ((6 - oppp) - (6 - myp)) / 6.0        # +ve when we're ahead
    deck_margin = (myd - oppd) / 60.0
    return w_prize * prize_lead + w_deck * deck_margin


class _LearnerAgent:
    def __init__(self, deck, attrs, defaults, seat, pnet, vnet, cfg, rng, sink):
        self.deck, self.attrs, self.defaults = deck, attrs, defaults
        self.seat, self.pnet, self.vnet = seat, pnet, vnet
        self.cfg, self.rng, self.sink = cfg, rng, sink

    def __call__(self, obs, _config=None):
        if obs.get("select") is None:
            return list(self.deck)
        common.apply_attrs(self.deck, self.attrs, self.defaults)
        sel = obs.get("select") or {}
        cur = obs.get("current") or {}
        if (cur.get("yourIndex") == self.seat
                and common.decision_kind(sel) == "main"):
            state, rows = common.encode_decision_main(sel, cur)
            with torch.no_grad():
                s = torch.from_numpy(state)
                r = torch.from_numpy(rows)
                logits = self.pnet.main_logits(s, r).cpu().numpy()
                value = float(self.vnet(s.unsqueeze(0))[0])
            action, logprob = common.sample_from_logits(
                logits, self.rng, temperature=self.cfg["temperature"])
            phi = _potential(cur, self.cfg["shaping_prize"],
                             self.cfg["shaping_deck"])
            self.sink.append(Step(state, rows, action, logprob, value, phi))
            return [action]
        return common.agent_mod.agent(obs)


def _finish(steps, outcome, cfg):
    """Fill shaped rewards + GAE advantages/returns onto the trajectory.

    Terminal reward r_T = outcome in {1,0.5,0}. Shaping adds
    γΦ(s_{t+1}) - Φ(s_t) per step (Φ(terminal)=0). Advantages via GAE(λ).
    Returns (advantages, value_targets, old_logprobs) aligned to steps.
    """
    n = len(steps)
    gamma, lam = cfg["gamma"], cfg["gae_lambda"]
    adv = np.zeros(n, dtype=np.float64)
    values = np.array([s.value for s in steps] + [0.0], dtype=np.float64)
    phis = [s.phi for s in steps]
    last_gae = 0.0
    for t in reversed(range(n)):
        # base reward is 0 mid-game, outcome at terminal step
        r = outcome if t == n - 1 else 0.0
        phi_next = 0.0 if t == n - 1 else phis[t + 1]
        r += gamma * phi_next - phis[t]      # potential-based shaping
        next_v = 0.0 if t == n - 1 else values[t + 1]
        delta = r + gamma * next_v - values[t]
        last_gae = delta + gamma * lam * last_gae
        adv[t] = last_gae
    ret = adv + values[:n]
    return adv, ret


def rollout_game(pnet, vnet, opp_spec, cfg, seat, rng):
    """Play one game; return (steps, advantages, returns, outcome, reason)."""
    ld, la = common.parse_spec(common.LEARNER_SPEC)
    od, oa = common.parse_spec(opp_spec)
    defaults = common.collect_defaults(la, oa)
    sink = []
    learner = _LearnerAgent(ld, la, defaults, seat, pnet, vnet, cfg, rng, sink)
    opp = common.make_league_wrapper(opp_spec, defaults)
    wrappers = [None, None]
    wrappers[seat] = learner
    wrappers[1 - seat] = opp
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        env = common.make_env()
        env.run(wrappers)
    r = env.state[seat].reward
    outcome = 1.0 if r == 1 else (0.5 if r == 0 else 0.0)
    reason = None
    try:
        from tools import deck_compare
        ev = deck_compare.game_events(env)
        reason = (ev["result"] or {}).get("reason")
    except Exception:
        pass
    if not sink:
        return [], np.zeros(0), np.zeros(0), outcome, reason
    adv, ret = _finish(sink, outcome, cfg)
    return sink, adv, ret, outcome, reason


# ------------------------------------------------------- parallel worker ----
# Module-level so ProcessPoolExecutor can pickle it. Each worker rebuilds the
# torch nets from state-dict files on disk (light, no net pickling), plays its
# assigned games, and returns picklable arrays. This is the lab-scale path.

def worker_collect(job):
    """job = (policy_sd_path, value_sd_path, cfg, opp_specs, seats, seed).
    Returns (packed_steps, outcomes, reasons) where packed_steps is a list of
    (state, rows, action, logprob, adv, ret) per decision."""
    import torch as _t
    from . import net as _net
    policy_sd, value_sd, cfg, opp_specs, seats, seed = job
    pnet = _net.make_policy(cfg)
    pnet.load_state_dict(_t.load(policy_sd, map_location="cpu"))
    pnet.eval()
    vnet = _net.ValueNet()
    vnet.load_state_dict(_t.load(value_sd, map_location="cpu"))
    vnet.eval()
    rng = np.random.default_rng(seed)
    packed, outcomes, reasons = [], [], []
    for opp, seat in zip(opp_specs, seats):
        steps, adv, ret, outcome, reason = rollout_game(
            pnet, vnet, opp, cfg, seat, rng)
        outcomes.append((opp, outcome))
        reasons.append(reason)
        for k, s in enumerate(steps):
            packed.append((s.state, s.rows, s.action, s.logprob,
                           float(adv[k]), float(ret[k])))
    return packed, outcomes, reasons
