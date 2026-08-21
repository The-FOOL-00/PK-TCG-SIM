"""PPO league self-play trainer for the list-0 policy (MAIN head).

Design (algorithm_survey.md + amendments):
  - warm start: direct weight copy from bc_weights_list0_b.npz (net.py)
  - KL(π_θ ‖ π_BC) anchor to a FROZEN BC reference — the guardrail against
    the teammate's prior-destruction failure (34→5%)
  - GAE + value baseline (critic warm-started from value_weights_mlp)
  - potential-based prize/deck shaping, coefficient rampable from 0
  - league = {BC-v2 anchor, v2.2.0 incumbent, v1 archetypes, past self
    checkpoints}, incumbent share RAMPED from 0 (curriculum) — directly
    fixes Sanjay's opp_frac=0.4-from-iter-1 value poisoning

Config is a plain dict so it round-trips to JSON in the lab package. Kill
criteria (K1/K2 and the pre-Tier-3 validation check) are enforced by the
caller/driver, which owns the gate schedule; this module owns one iteration.

Scope boundary (logged, not silent): only MAIN single-select decisions carry
policy gradient this iteration; ST_CARD plays under the frozen BC card head.
"""

import argparse
import json
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from . import common, net, rollout


class _Packed:
    """Lightweight step for the update path (parallel workers return tuples)."""
    __slots__ = ("state", "rows", "action")

    def __init__(self, state, rows, action):
        self.state, self.rows, self.action = state, rows, action

DEFAULT_CFG = {
    "temperature": 1.0,
    "gamma": 0.997,
    "gae_lambda": 0.95,
    "clip": 0.2,
    "vf_coef": 0.5,
    "ent_coef": 0.003,
    "kl_coef": 0.5,          # β on KL(π_θ ‖ π_BC); the anchor strength
    "lr": 3e-4,
    "epochs": 4,
    "minibatch": 512,
    "shaping_prize": 0.0,    # ramp target; 0 = pure terminal reward
    "shaping_deck": 0.0,
    "games_per_iter": 64,
    "incumbent_share": 0.0,   # current P(opponent = v2.2.0); set by the ramp
    "incumbent_final": 0.35,  # ramp target — never poison the value head early
    "incumbent_ramp_iters": 40,  # linear 0 -> final over this many iters
    "workers": 1,
    "max_grad_norm": 1.0,
    "seed": 0,
}


def sample_opponent(cfg, rng, checkpoints):
    """League draw. incumbent_share to v2.2.0; else uniform over
    {BC-v2 anchor, v1 archetypes, past self checkpoints}."""
    if rng.random() < cfg["incumbent_share"]:
        return common.V220_SPEC
    pool = [common.BC_ANCHOR_SPEC] + list(common.V1_SPECS) + list(checkpoints)
    return str(rng.choice(pool))


def _pad_batch(steps, idx, n_feat):
    """Stack a minibatch of MAIN steps into padded tensors."""
    B = len(idx)
    M = max(steps[i].rows.shape[0] for i in idx)
    states = np.zeros((B, common.N_STATE), np.float32)
    rows = np.zeros((B, M, n_feat), np.float32)
    mask = np.zeros((B, M), bool)
    actions = np.zeros(B, np.int64)
    for b, i in enumerate(idx):
        s = steps[i]
        states[b] = s.state
        n = s.rows.shape[0]
        rows[b, :n] = s.rows
        mask[b, :n] = True
        actions[b] = s.action
    return (torch.from_numpy(states), torch.from_numpy(rows),
            torch.from_numpy(mask), torch.from_numpy(actions))


def ppo_update(pnet, vnet, bc_ref, opt, steps, adv, ret, old_lp, cfg):
    """One PPO update over collected MAIN steps. Returns a stats dict."""
    n = len(steps)
    adv = np.asarray(adv, np.float64)
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)
    adv_t = torch.from_numpy(adv.astype(np.float32))
    ret_t = torch.from_numpy(np.asarray(ret, np.float32))
    old_lp_t = torch.from_numpy(np.asarray(old_lp, np.float32))
    stats = {"pg": 0.0, "vf": 0.0, "kl_anchor": 0.0, "ent": 0.0,
             "clipfrac": 0.0, "nb": 0}
    order = np.arange(n)
    for _ in range(cfg["epochs"]):
        np.random.shuffle(order)
        for start in range(0, n, cfg["minibatch"]):
            idx = order[start:start + cfg["minibatch"]]
            if len(idx) < 2:
                continue
            states, rows, mask, actions = _pad_batch(steps, idx, common.N_MAIN_FEAT)
            logits = pnet.main_logits_batched(states, rows, mask)
            logp_all = F.log_softmax(logits, dim=1)
            logp = logp_all.gather(1, actions.unsqueeze(1)).squeeze(1)
            with torch.no_grad():
                bc_logits = bc_ref.main_logits_batched(states, rows, mask)
                bc_logp_all = F.log_softmax(bc_logits, dim=1)
            p = logp_all.exp()
            kl_anchor = (p * (logp_all - bc_logp_all)).sum(dim=1).mean()
            ent = -(p * logp_all).sum(dim=1).mean()

            mb_adv = adv_t[torch.from_numpy(idx)]
            ratio = (logp - old_lp_t[torch.from_numpy(idx)]).exp()
            unclipped = ratio * mb_adv
            clipped = torch.clamp(ratio, 1 - cfg["clip"], 1 + cfg["clip"]) * mb_adv
            pg = -torch.min(unclipped, clipped).mean()

            v = vnet(states)
            vf = F.mse_loss(v, ret_t[torch.from_numpy(idx)])

            loss = (pg + cfg["vf_coef"] * vf + cfg["kl_coef"] * kl_anchor
                    - cfg["ent_coef"] * ent)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(pnet.parameters()) + list(vnet.parameters()),
                cfg["max_grad_norm"])
            opt.step()

            with torch.no_grad():
                clipfrac = ((ratio - 1.0).abs() > cfg["clip"]).float().mean()
            stats["pg"] += float(pg.detach())
            stats["vf"] += float(vf.detach())
            stats["kl_anchor"] += float(kl_anchor.detach())
            stats["ent"] += float(ent.detach())
            stats["clipfrac"] += float(clipfrac)
            stats["nb"] += 1
    nb = max(1, stats["nb"])
    for k in ("pg", "vf", "kl_anchor", "ent", "clipfrac"):
        stats[k] /= nb
    return stats


def _collect_serial(pnet, vnet, cfg, rng, checkpoints):
    all_steps, all_adv, all_ret, all_lp = [], [], [], []
    outcomes, reasons = [], []
    for g in range(cfg["games_per_iter"]):
        opp = sample_opponent(cfg, rng, checkpoints)
        steps, adv, ret, outcome, reason = rollout.rollout_game(
            pnet, vnet, opp, cfg, g % 2, rng)
        outcomes.append((opp, outcome))
        reasons.append(reason)
        for k, s in enumerate(steps):
            all_steps.append(s)
            all_adv.append(float(adv[k]))
            all_ret.append(float(ret[k]))
            all_lp.append(s.logprob)
    return all_steps, all_adv, all_ret, all_lp, outcomes, reasons


def _collect_parallel(pnet, vnet, cfg, rng, checkpoints, executor, tmpdir):
    """Export current nets, fan games out to the worker pool, gather steps."""
    psd = Path(tmpdir) / "policy_sd.pt"
    vsd = Path(tmpdir) / "value_sd.pt"
    torch.save(pnet.state_dict(), psd)
    torch.save(vnet.state_dict(), vsd)
    W = cfg["workers"]
    specs = [sample_opponent(cfg, rng, checkpoints)
             for _ in range(cfg["games_per_iter"])]
    seats = [g % 2 for g in range(cfg["games_per_iter"])]
    jobs = []
    for w in range(W):
        js, se = specs[w::W], seats[w::W]
        if js:
            jobs.append((str(psd), str(vsd), cfg, js, se,
                         int(rng.integers(0, 2**31))))
    all_steps, all_adv, all_ret, all_lp = [], [], [], []
    outcomes, reasons = [], []
    for packed, outs, rsn in executor.map(rollout.worker_collect, jobs):
        outcomes.extend(outs)
        reasons.extend(rsn)
        for state, rows, action, logprob, adv, ret in packed:
            all_steps.append(_Packed(state, rows, action))
            all_adv.append(adv)
            all_ret.append(ret)
            all_lp.append(logprob)
    return all_steps, all_adv, all_ret, all_lp, outcomes, reasons


def run_iteration(pnet, vnet, bc_ref, opt, cfg, rng, checkpoints, it,
                  executor=None, tmpdir=None):
    """Collect games_per_iter self-play games and do one PPO update."""
    if executor is not None and cfg.get("workers", 1) > 1:
        all_steps, all_adv, all_ret, all_lp, outcomes, reasons = \
            _collect_parallel(pnet, vnet, cfg, rng, checkpoints, executor, tmpdir)
    else:
        all_steps, all_adv, all_ret, all_lp, outcomes, reasons = \
            _collect_serial(pnet, vnet, cfg, rng, checkpoints)
    stats = {"n_steps": len(all_steps), "n_games": cfg["games_per_iter"]}
    if all_steps:
        upd = ppo_update(pnet, vnet, bc_ref, opt, all_steps,
                         all_adv, all_ret, all_lp, cfg)
        stats.update(upd)
    # win rate vs the self-anchor subset (curriculum-invariant signal)
    anch = [o for spec, o in outcomes if spec == common.BC_ANCHOR_SPEC]
    inc = [o for spec, o in outcomes if spec == common.V220_SPEC]
    stats["n_anchor"] = len(anch)
    stats["wins_anchor"] = int(sum(1 for o in anch if o == 1))
    stats["n_incumbent"] = len(inc)
    stats["wins_incumbent"] = int(sum(1 for o in inc if o == 1))
    stats["winrate_anchor"] = (stats["wins_anchor"] / len(anch)) if anch else None
    stats["winrate_incumbent"] = (stats["wins_incumbent"] / len(inc)) if inc else None
    stats["mean_outcome"] = float(np.mean([o for _s, o in outcomes]))
    stats["iter"] = it
    return stats


def train(cfg, n_iters, out_dir, log_path=None, ckpt_every=10, verbose=True):
    torch.manual_seed(cfg["seed"])
    rng = np.random.default_rng(cfg["seed"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if cfg.get("wide"):
        th = tuple(cfg.get("trunk_hidden", (320, 160)))
        mh = cfg.get("main_hidden", 160)
        if cfg.get("grow_src"):
            # capacity ladder rung N>1: grow an ARBITRARY trained checkpoint
            # (e.g. best 128k iter) into the wider target, function-preservingly.
            pnet = net.build_policy_grown(
                src=cfg["grow_src"], trunk_hidden=th, main_hidden=mh,
                emb=cfg.get("emb", 48))
            pnet.train()
        else:
            # rung 1: embed the 27.8k BC-v2 (default warm start)
            pnet = net.build_policy_wide(
                warmstart=True, trunk_hidden=th,
                emb=cfg.get("emb", 48), main_hidden=mh)
    else:
        pnet = net.build_policy(warmstart=True)
    pnet.train()
    vnet = net.build_value(warmstart=True)
    vnet.train()
    bc_ref = net.build_policy(warmstart=True)   # frozen KL anchor: 27.8k BC-v2
    bc_ref.eval()
    for p in bc_ref.parameters():
        p.requires_grad_(False)
    opt = torch.optim.Adam(
        list(pnet.parameters()) + list(vnet.parameters()), lr=cfg["lr"])

    history = []
    t0 = time.time()
    checkpoints = []
    executor = None
    tmpdir = tempfile.mkdtemp(prefix="ppo_")
    if cfg.get("workers", 1) > 1:
        import multiprocessing as _mp
        from concurrent.futures import ProcessPoolExecutor
        # SPAWN, not fork. The wide embed copies 170x320 and 320x160 tensors,
        # which exceed torch's parallel grain size (32768) and so spin up the
        # OpenMP thread pool in this process. libgomp is not fork-safe: forked
        # children inherit its mutexes but none of its threads and deadlock on
        # their first parallel op (load_state_dict of those same wide tensors)
        # before running a single game. The narrow net stays under the grain
        # size, never starts the pool, and so survived fork by luck.
        executor = ProcessPoolExecutor(max_workers=cfg["workers"],
                                       mp_context=_mp.get_context("spawn"))
    try:
        for it in range(n_iters):
            # incumbent-share curriculum ramp (0 -> incumbent_final): the direct
            # fix for the teammate's opp_frac=0.4-from-iter-1 value poisoning.
            ramp = cfg.get("incumbent_ramp_iters", 1) or 1
            cfg["incumbent_share"] = min(
                cfg.get("incumbent_final", 0.0),
                cfg.get("incumbent_final", 0.0) * it / ramp)
            st = run_iteration(pnet, vnet, bc_ref, opt, cfg, rng,
                               checkpoints, it, executor, tmpdir)
            st["incumbent_share"] = round(cfg["incumbent_share"], 3)
            st["elapsed_s"] = round(time.time() - t0, 1)
            history.append(st)
            if verbose:
                print("it %3d | games %d steps %5d | outcome %.3f "
                      "anchorWR %s | pg %+.4f vf %.4f kl %.4f ent %.3f clip %.2f"
                      % (it, st["n_games"], st["n_steps"], st["mean_outcome"],
                         ("%.2f" % st["winrate_anchor"]) if st["winrate_anchor"]
                         is not None else " - ",
                         st.get("pg", 0), st.get("vf", 0), st.get("kl_anchor", 0),
                         st.get("ent", 0), st.get("clipfrac", 0)))
            if (it + 1) % ckpt_every == 0 or it == n_iters - 1:
                ck = out_dir / ("policy_iter%03d.npz" % it)
                pnet.export_npz(ck)
                # TODO(lab-day-1): register ck via main.py's file resolution and
                # append its spec to `checkpoints` so past selves enter the
                # league (approved design; needs _find_file path wired+tested).
            if log_path:
                Path(log_path).write_text(json.dumps(history, indent=1),
                                          encoding="utf-8")
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    return history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=5)
    ap.add_argument("--games-per-iter", type=int, default=32)
    ap.add_argument("--out", default="stage4/rl_ours/runs/smoke")
    ap.add_argument("--log", default="stage4/rl_ours/runs/smoke/history.json")
    ap.add_argument("--kl-coef", type=float, default=None)
    ap.add_argument("--incumbent-share", type=float, default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--ckpt-every", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    # capacity growth: build the 128k wide net (Net2WiderNet embed of BC-v2)
    ap.add_argument("--wide", action="store_true",
                    help="use WiderPolicyNet (trunk 170->320->160->48, MAIN "
                         "head 89->160->1), function-preservingly embedded")
    ap.add_argument("--trunk-hidden", default="320,160",
                    help="comma-separated wide-trunk hidden dims (needs 2 for "
                         "the 3-layer embed); only used with --wide")
    ap.add_argument("--main-hidden", type=int, default=160,
                    help="wide MAIN-head hidden width; only used with --wide")
    ap.add_argument("--grow-src", default=None,
                    help="grow this trained policy npz (ladder rung >1, e.g. a "
                         "128k checkpoint -> 256k). Omit to warm-start the wide "
                         "net from BC-v2. KL anchor stays the frozen 27.8k BC-v2.")
    args = ap.parse_args()
    cfg = dict(DEFAULT_CFG)
    cfg["games_per_iter"] = args.games_per_iter
    cfg["workers"] = args.workers
    cfg["seed"] = args.seed
    if args.wide:
        cfg["wide"] = True
        cfg["trunk_hidden"] = tuple(int(x) for x in args.trunk_hidden.split(","))
        cfg["main_hidden"] = args.main_hidden
        if args.grow_src:
            gs = Path(args.grow_src)
            cfg["grow_src"] = str(gs if gs.is_absolute() else common.REPO / gs)
    if args.kl_coef is not None:
        cfg["kl_coef"] = args.kl_coef
    if args.incumbent_share is not None:
        cfg["incumbent_share"] = args.incumbent_share
    out = args.out if Path(args.out).is_absolute() else common.REPO / args.out
    log = args.log if Path(args.log).is_absolute() else common.REPO / args.log
    train(cfg, args.iters, out, log, ckpt_every=args.ckpt_every)


if __name__ == "__main__":
    main()
