"""Train the value model (win-probability from state) — Phase 1b, rung (a).

STANDALONE: depends only on numpy. No repo imports, no cg/, no sklearn/torch.
Works CPU-only; a Kaggle CPU notebook is plenty (see README_TRAINING.md).

Input:  a directory of .npz shards produced by tools/gen_selfplay.py, each with
    x        float32 [N, 170]   state feature vectors
    y        int8    [N]        game outcome for the acting player (+1/-1/0)
    turn     int16   [N]
    game_id  int32   [N]        unique per game — the train/val split key
(meta.json in the same dir is optional and only used for feature names.)

Trains (i) logistic regression and (ii) an MLP 170 -> 128 -> 64 -> 1
(~30k params, ReLU hidden, sigmoid output) with Adam on binary cross-entropy.
Draws (y == 0) are dropped; labels are win=1 / loss=0. The split is BY GAME
(game_id % 10 == 0 -> validation) so correlated decisions from one game never
straddle the split.

===========================================================================
OUTPUT WEIGHT FORMAT (value_weights.npz) — the runtime inference contract
===========================================================================
An .npz containing, for L layers (logreg: L=1; MLP: L=3):
    n_layers   int64 scalar
    n_features int64 scalar (must equal 170)
    kind       str array, "logreg" or "mlp"
    W0 .. W{L-1}   float32 [in, out] weight matrices
    b0 .. b{L-1}   float32 [out]     biases
Forward pass:  h = x;  for i < L-1: h = relu(h @ Wi + bi);
               p = sigmoid(h @ W{L-1} + b{L-1})      (p = our win probability)
===========================================================================

Also writes: value_weights_logreg.npz, value_weights_mlp.npz (both models),
value_weights.npz (copy of the better one by val logloss), and metrics.json
(train/val logloss, AUC, 10-bucket calibration table for both models).

Run:  python train_value.py --data DATA_DIR --out OUT_DIR \
          [--epochs 6] [--batch 8192] [--lr 1e-3] [--max-rows 0] [--seed 0]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np


# ----------------------------------------------------------------- data ----

def load_shards(data_dir, max_rows=0):
    files = sorted(Path(data_dir).glob("*.npz"))
    if not files:
        raise SystemExit(f"no .npz shards found in {data_dir}")
    xs, ys, gs = [], [], []
    for f in files:
        d = np.load(f)
        xs.append(d["x"])
        ys.append(d["y"])
        gs.append(d["game_id"])
    x = np.concatenate(xs).astype(np.float32)
    y = np.concatenate(ys)
    g = np.concatenate(gs)
    keep = y != 0  # drop draws
    x, y, g = x[keep], (y[keep] > 0).astype(np.float32), g[keep]
    if max_rows and len(y) > max_rows:
        # subsample by GAME so no game is partially kept
        games = np.unique(g)
        rng = np.random.default_rng(0)
        rng.shuffle(games)
        take_frac = max_rows / len(y)
        chosen = set(games[: max(1, int(len(games) * take_frac))].tolist())
        keep = np.fromiter((gi in chosen for gi in g), bool, len(g))
        x, y, g = x[keep], y[keep], g[keep]
    val = (g % 10) == 0  # split by game
    print(f"rows: {len(y)} ({val.sum()} val)  games: {len(np.unique(g))}  "
          f"win rate: {y.mean():.3f}", flush=True)
    return (x[~val], y[~val]), (x[val], y[val])


# ---------------------------------------------------------------- model ----

def init_layers(sizes, rng):
    layers = []
    for fan_in, fan_out in zip(sizes[:-1], sizes[1:]):
        w = rng.normal(0, np.sqrt(2.0 / fan_in), (fan_in, fan_out)).astype(np.float32)
        layers.append([w, np.zeros(fan_out, dtype=np.float32)])
    return layers


def forward(layers, x):
    """Returns (probability, cached activations for backprop)."""
    acts = [x]
    h = x
    for w, b in layers[:-1]:
        h = np.maximum(h @ w + b, 0.0)
        acts.append(h)
    w, b = layers[-1]
    z = (h @ w + b).ravel()
    p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
    return p, acts


def backward(layers, acts, p, y):
    """BCE gradient. Returns [(dW, db)] aligned with layers."""
    n = len(y)
    grads = [None] * len(layers)
    delta = ((p - y) / n)[:, None]                       # d loss / d z_last
    for i in range(len(layers) - 1, -1, -1):
        w, _b = layers[i]
        grads[i] = (acts[i].T @ delta, delta.sum(axis=0))
        if i > 0:
            delta = (delta @ w.T) * (acts[i] > 0)        # through ReLU
    return grads


def train(layers, xtr, ytr, xva, yva, epochs, batch, lr, seed, tag):
    rng = np.random.default_rng(seed)
    ms = [[np.zeros_like(w), np.zeros_like(b)] for w, b in layers]
    vs = [[np.zeros_like(w), np.zeros_like(b)] for w, b in layers]
    beta1, beta2, eps, t = 0.9, 0.999, 1e-8, 0
    best_va = float("inf")
    best_layers = [[w.copy(), b.copy()] for w, b in layers]
    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(ytr))
        t0 = time.perf_counter()
        for s in range(0, len(order), batch):
            idx = order[s:s + batch]
            p, acts = forward(layers, xtr[idx])
            grads = backward(layers, acts, p, ytr[idx])
            t += 1
            for li, (g_w_b, m, v, layer) in enumerate(zip(grads, ms, vs, layers)):
                for j in range(2):
                    m[j] = beta1 * m[j] + (1 - beta1) * g_w_b[j]
                    v[j] = beta2 * v[j] + (1 - beta2) * g_w_b[j] ** 2
                    mh = m[j] / (1 - beta1 ** t)
                    vh = v[j] / (1 - beta2 ** t)
                    layer[j] -= lr * mh / (np.sqrt(vh) + eps)
        tr = logloss(forward(layers, xtr)[0], ytr)
        va = logloss(forward(layers, xva)[0], yva)
        if va < best_va:
            best_va = va
            best_layers = [[w.copy(), b.copy()] for w, b in layers]
            marker = "*"
        else:
            marker = ""
        print(f"[{tag}] epoch {epoch}/{epochs}: train logloss {tr:.4f} "
              f"val logloss {va:.4f} {marker} ({time.perf_counter()-t0:.0f}s)", flush=True)
    return best_layers


# -------------------------------------------------------------- metrics ----

def logloss(p, y):
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def auc(p, y):
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    n_pos, n_neg = y.sum(), (1 - y).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def brier_score(p, y):
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(p, y, buckets=10):
    ece = 0.0
    n_total = len(y)
    for i in range(buckets):
        lo, hi = i / buckets, (i + 1) / buckets
        m = (p >= lo) & (p < hi) if i < buckets - 1 else (p >= lo) & (p <= hi)
        if m.any():
            pred_m = p[m].mean()
            act_m = y[m].mean()
            ece += (m.sum() / n_total) * abs(pred_m - act_m)
    return float(ece)


def calibration(p, y, buckets=10):
    table = []
    for i in range(buckets):
        lo, hi = i / buckets, (i + 1) / buckets
        m = (p >= lo) & (p < hi) if i < buckets - 1 else (p >= lo) & (p <= hi)
        table.append({
            "bucket": f"[{lo:.1f}, {hi:.1f})",
            "n": int(m.sum()),
            "predicted_mean": float(p[m].mean()) if m.any() else None,
            "actual_win_rate": float(y[m].mean()) if m.any() else None,
        })
    return table


def evaluate(layers, xtr, ytr, xva, yva):
    ptr, _ = forward(layers, xtr)
    pva, _ = forward(layers, xva)
    return {
        "params": int(sum(w.size + b.size for w, b in layers)),
        "train_logloss": logloss(ptr, ytr),
        "val_logloss": logloss(pva, yva),
        "train_auc": auc(ptr, ytr),
        "val_auc": auc(pva, yva),
        "val_brier": brier_score(pva, yva),
        "val_ece": expected_calibration_error(pva, yva),
        "val_calibration": calibration(pva, yva),
    }


def save_weights(path, layers, kind, n_features):
    arrays = {"n_layers": np.int64(len(layers)),
              "n_features": np.int64(n_features),
              "kind": np.array(kind)}
    for i, (w, b) in enumerate(layers):
        arrays[f"W{i}"] = w.astype(np.float32)
        arrays[f"b{i}"] = b.astype(np.float32)
    np.savez(path, **arrays)
    print(f"wrote {path}", flush=True)


# ----------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dir of gen_selfplay .npz shards")
    ap.add_argument("--out", default=".", help="output dir")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=8192)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-rows", type=int, default=0, help="0 = use everything")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (xtr, ytr), (xva, yva) = load_shards(args.data, args.max_rows)
    nf = xtr.shape[1]
    rng = np.random.default_rng(args.seed)

    print(f"Training Value Models on {len(ytr)} train rows, {len(yva)} val rows (dim={nf})...")

    logreg = train(init_layers([nf, 1], rng), xtr, ytr, xva, yva,
                   args.epochs, args.batch, args.lr, args.seed, "logreg")
    mlp = train(init_layers([nf, 128, 64, 1], rng), xtr, ytr, xva, yva,
                args.epochs, args.batch, args.lr, args.seed, "mlp")
    mlp_deep = train(init_layers([nf, 256, 128, 64, 1], rng), xtr, ytr, xva, yva,
                      args.epochs, args.batch, args.lr, args.seed, "mlp_deep")

    models = {"logreg": logreg, "mlp": mlp, "mlp_deep": mlp_deep}
    evals = {name: evaluate(m, xtr, ytr, xva, yva) for name, m in models.items()}

    metrics = {"data": str(args.data), "rows_train": len(ytr), "rows_val": len(yva),
               "epochs": args.epochs, "batch": args.batch, "lr": args.lr,
               "evaluations": evals}
    for name, m in models.items():
        save_weights(out / f"value_weights_{name}.npz", m, name, nf)

    best_name = min(evals.keys(), key=lambda k: evals[k]["val_logloss"])
    metrics["best"] = best_name
    save_weights(out / "value_weights.npz", models[best_name], best_name, nf)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"wrote {out / 'metrics.json'}", flush=True)
    print(f"BEST MODEL: {best_name} | Val LogLoss: {evals[best_name]['val_logloss']:.4f} | "
          f"Val AUC: {evals[best_name]['val_auc']:.4f} | Val Brier: {evals[best_name]['val_brier']:.4f} | "
          f"Val ECE: {evals[best_name]['val_ece']:.4f}", flush=True)


if __name__ == "__main__":
    main()
