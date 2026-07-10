"""Behavior-cloning trainer (Stage 3B): imitate a top-ladder pilot's
MAIN-single decisions from replay-extracted targets.

STANDALONE except for train_policy.py in the same directory (numpy only —
CPU sufficient; the dataset is a few thousand decisions). Reuses
train_policy's Dataset/loader/eval/save machinery; adds what small data
needs: inverted dropout on hidden layers, decoupled L2 weight decay, and
patience-based early stopping. Output .npz follows the SAME inference
contract as policy_weights.npz (train_policy.py header), so main.py serves
it with the existing numpy forward.

Run:  python train_bc.py --data data/bc_garchomp --out runs/bc_garchomp \
          [--trunk 96,48] [--head 48] [--dropout 0.2] [--wd 1e-4] \
          [--epochs 200] [--patience 25] [--batch 256] [--lr 1e-3]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_policy as tp  # noqa: E402

N_STATE, N_OPT = tp.N_STATE, tp.N_OPT


# ------------------------------------------------- dropout-aware training ----

def forward_train(model, s, x_opt, seg, rng, p_drop):
    """Like tp.forward but with inverted dropout after every hidden ReLU.
    Cache keeps post-ReLU (pre-dropout) activations + masks for backprop."""
    keep = 1.0 - p_drop
    t_acts, t_masks = [s], []
    h = s
    for w, b in model["trunk"]:
        h = np.maximum(h @ w + b, 0.0)
        t_acts.append(h)
        m = (rng.random(h.shape) < keep).astype(np.float32) / keep if p_drop > 0 \
            else None
        t_masks.append(m)
        if m is not None:
            h = h * m
    z = np.concatenate([h[seg], x_opt], axis=1)
    h_acts, h_masks = [z], []
    g = z
    for w, b in model["head"][:-1]:
        g = np.maximum(g @ w + b, 0.0)
        h_acts.append(g)
        m = (rng.random(g.shape) < keep).astype(np.float32) / keep if p_drop > 0 \
            else None
        h_masks.append(m)
        if m is not None:
            g = g * m
    w, b = model["head"][-1]
    logits = (g @ w + b).ravel()
    return logits, (t_acts, t_masks, h_acts, h_masks, seg, len(s))


def backward_train(model, cache, p, lab_pos, bptr):
    """Gradient for forward_train (dropout masks applied where used)."""
    t_acts, t_masks, h_acts, h_masks, seg, n_dec = cache
    d = p.copy()
    d[lab_pos] -= 1.0
    d /= n_dec
    d = d[:, None]
    head_grads = [None] * len(model["head"])
    for i in range(len(model["head"]) - 1, -1, -1):
        w, _b = model["head"][i]
        act = h_acts[i]
        act_in = act if i == 0 or h_masks[i - 1] is None else act * h_masks[i - 1]
        head_grads[i] = (act_in.T @ d, d.sum(axis=0))
        d = d @ w.T
        if i > 0:
            if h_masks[i - 1] is not None:
                d = d * h_masks[i - 1]
            d = d * (h_acts[i] > 0)
    emb_dim = t_acts[-1].shape[1]
    d_emb = np.add.reduceat(d[:, :emb_dim], bptr[:-1], axis=0)
    if t_masks and t_masks[-1] is not None:
        d_emb = d_emb * t_masks[-1]
    trunk_grads = [None] * len(model["trunk"])
    d = d_emb
    for i in range(len(model["trunk"]) - 1, -1, -1):
        w, _b = model["trunk"][i]
        d = d * (t_acts[i + 1] > 0)
        act_in = t_acts[i] if i == 0 or t_masks[i - 1] is None \
            else t_acts[i] * t_masks[i - 1]
        trunk_grads[i] = (act_in.T @ d, d.sum(axis=0))
        d = d @ w.T
        if i > 0 and t_masks[i - 1] is not None:
            d = d * t_masks[i - 1]
    return trunk_grads + head_grads


def train_bc(model, tr, va, epochs, batch, lr, wd, p_drop, patience, seed, tag):
    rng = np.random.default_rng(seed)
    ps = tp.params(model)
    ms = [[np.zeros_like(w), np.zeros_like(b)] for w, b in ps]
    vs = [[np.zeros_like(w), np.zeros_like(b)] for w, b in ps]
    beta1, beta2, eps, t = 0.9, 0.999, 1e-8, 0
    best = {"acc": -1.0, "ll": float("inf"), "epoch": 0, "model": None,
            "history": []}
    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(tr))
        t0 = time.perf_counter()
        for s in range(0, len(order), batch):
            idx = order[s:s + batch]
            st, xo, _c, seg, bptr, lab_pos = tr.gather(idx)
            logits, cache = forward_train(model, st, xo, seg, rng, p_drop)
            p = tp.seg_softmax(logits, seg, bptr)
            grads = backward_train(model, cache, p, lab_pos, bptr)
            t += 1
            for g_w_b, m, v, layer in zip(grads, ms, vs, tp.params(model)):
                for j in range(2):
                    m[j] = beta1 * m[j] + (1 - beta1) * g_w_b[j]
                    v[j] = beta2 * v[j] + (1 - beta2) * g_w_b[j] ** 2
                    mh = m[j] / (1 - beta1 ** t)
                    vh = v[j] / (1 - beta2 ** t)
                    layer[j] -= lr * mh / (np.sqrt(vh) + eps)
                if wd > 0:
                    layer[0] -= lr * wd * layer[0]   # decoupled L2 on W only
        tr_ll, tr_acc = tp.evaluate(model, tr)
        va_ll, va_acc = tp.evaluate(model, va)
        dt = time.perf_counter() - t0
        best["history"].append(
            {"epoch": epoch, "train_ce": tr_ll, "train_acc": tr_acc,
             "val_ce": va_ll, "val_acc": va_acc, "seconds": round(dt, 1)})
        star = ""
        if (va_acc, -va_ll) > (best["acc"], -best["ll"]):
            best.update(acc=va_acc, ll=va_ll, epoch=epoch,
                        model=tp.copy_model(model))
            star = "  *best*"
        print(f"[{tag}] epoch {epoch}/{epochs}: "
              f"train CE {tr_ll:.4f} acc {tr_acc:.4f} | "
              f"val CE {va_ll:.4f} acc {va_acc:.4f} ({dt:.1f}s){star}",
              flush=True)
        if epoch - best["epoch"] >= patience:
            print(f"[{tag}] early stop: no val improvement for {patience} epochs "
                  f"(best epoch {best['epoch']})", flush=True)
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--trunk", default="96,48")
    ap.add_argument("--head", default="48")
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--patience", type=int, default=25)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="bc")
    args = ap.parse_args()

    tr, va, _src = tp.load_shards(args.data)
    trunk_hidden = [int(x) for x in args.trunk.split(",") if x]
    head_hidden = [int(x) for x in args.head.split(",") if x]
    trunk_sizes = [N_STATE] + trunk_hidden
    head_sizes = [trunk_sizes[-1] + N_OPT] + head_hidden + [1]
    rng = np.random.default_rng(args.seed)
    model = tp.init_model(trunk_sizes, head_sizes, rng)
    n_params = sum(w.size + b.size for w, b in tp.params(model))
    print(f"[{args.tag}] trunk {trunk_sizes} head {head_sizes} = {n_params} params, "
          f"dropout {args.dropout}, wd {args.wd}")

    best = train_bc(model, tr, va, args.epochs, args.batch, args.lr,
                    args.wd, args.dropout, args.patience, args.seed, args.tag)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tp.save_weights(out / f"bc_weights_{args.tag}.npz", best["model"], "policy_mlp")

    lab_abs = va.ptr[:-1] + va.label
    floors = {
        "uniform": float((1.0 / va.n).mean()),
        "always_index_0": float((va.label == 0).mean()),
        "v1_agreement": float((va.opt_x[lab_abs, N_OPT - 1] > 0.5).mean()),
    }
    metrics = {"params": int(n_params), "val_top1": best["acc"],
               "val_logloss": best["ll"], "best_epoch": best["epoch"],
               "floors": floors, "history": best["history"],
               "decisions_train": len(tr), "decisions_val": len(va),
               "games_train": tr.n_games, "games_val": va.n_games}
    (out / f"metrics_{args.tag}.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nBEST epoch {best['epoch']}: val top-1 {best['acc']:.4f} "
          f"(floors: uniform {floors['uniform']:.3f}, "
          f"always-0 {floors['always_index_0']:.3f}, "
          f"v1-agree {floors['v1_agreement']:.3f})")
    print(f"wrote {out / ('bc_weights_%s.npz' % args.tag)} and metrics")


if __name__ == "__main__":
    main()
