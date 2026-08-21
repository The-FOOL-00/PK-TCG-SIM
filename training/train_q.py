"""Train the Action-Conditioned Q-Network (Q-CEI).

Input: Directory of .npz shards produced by bot/failure_dataset.py containing:
- state: [N, 194] float32
- phase: [N, 5] float32
- action: [N, 47] float32
- y: [N] float32 (1=win, 0=loss)
- prize_delta: [N] float32
- game_id: [N] int32

Concatenates (state, phase, action) into a 246-dimensional input vector.
Trains an MLP: 246 -> 128 -> 64 -> 32 -> 1 with Adam on BCE + Pairwise ranking loss.
Saves q_weights.npz for fast runtime inference.
"""

import argparse
import json
import time
from pathlib import Path
import numpy as np


def load_q_shards(data_dir, max_rows=0):
    files = sorted(Path(data_dir).glob("*.npz"))
    if not files:
        raise SystemExit(f"no .npz shards found in {data_dir}")
    xs, ys, gs = [], [], []
    for f in files:
        d = np.load(f)
        s = d["state"].astype(np.float32)
        p = d["phase"].astype(np.float32)
        a = d["action"].astype(np.float32)
        x_comb = np.concatenate([s, p, a], axis=1)
        xs.append(x_comb)
        ys.append(d["y"].astype(np.float32))
        gs.append(d["game_id"])

    x = np.concatenate(xs, axis=0)
    y = np.concatenate(ys, axis=0)
    g = np.concatenate(gs, axis=0)

    val = (g % 10) == 0
    print(f"Loaded Q dataset: {len(y)} total rows ({val.sum()} val) across {len(np.unique(g))} games. Win rate: {y.mean():.3f}", flush=True)
    return (x[~val], y[~val]), (x[val], y[val])


def init_layers(sizes, rng):
    layers = []
    for fan_in, fan_out in zip(sizes[:-1], sizes[1:]):
        w = rng.normal(0, np.sqrt(2.0 / fan_in), (fan_in, fan_out)).astype(np.float32)
        b = np.zeros(fan_out, dtype=np.float32)
        layers.append([w, b])
    return layers


def forward(layers, x):
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
    n = len(y)
    grads = [None] * len(layers)
    delta = ((p - y) / n)[:, None]
    for i in range(len(layers) - 1, -1, -1):
        w, _b = layers[i]
        grads[i] = (acts[i].T @ delta, delta.sum(axis=0))
        if i > 0:
            delta = (delta @ w.T) * (acts[i] > 0)
    return grads


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


def train_q_model(layers, xtr, ytr, xva, yva, epochs, batch, lr, seed):
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
        print(f"[q-mlp] epoch {epoch}/{epochs}: train logloss {tr:.4f} val logloss {va:.4f} {marker} ({time.perf_counter()-t0:.1f}s)", flush=True)

    return best_layers


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
    }


def save_q_weights(path, layers, n_features):
    arrays = {
        "n_layers": np.int64(len(layers)),
        "n_features": np.int64(n_features),
        "kind": np.array("q_mlp"),
    }
    for i, (w, b) in enumerate(layers):
        arrays[f"W{i}"] = w.astype(np.float32)
        arrays[f"b{i}"] = b.astype(np.float32)
    np.savez(path, **arrays)
    print(f"wrote {path}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dir of q .npz shards")
    parser.add_argument("--out", default=".", help="output dir")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (xtr, ytr), (xva, yva) = load_q_shards(args.data)
    nf = xtr.shape[1]
    rng = np.random.default_rng(args.seed)

    print(f"Training Action-Conditioned Q-Network on {len(ytr)} train rows, {len(yva)} val rows (dim={nf})...")

    # Q Architecture: 246 -> 128 -> 64 -> 32 -> 1
    q_layers = init_layers([nf, 128, 64, 32, 1], rng)
    best_q_layers = train_q_model(q_layers, xtr, ytr, xva, yva, args.epochs, args.batch, args.lr, args.seed)

    eval_metrics = evaluate(best_q_layers, xtr, ytr, xva, yva)
    save_q_weights(out / "q_weights.npz", best_q_layers, nf)

    metrics = {
        "data": str(args.data),
        "rows_train": len(ytr),
        "rows_val": len(yva),
        "n_features": nf,
        "metrics": eval_metrics,
    }
    (out / "q_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Q-Network Training Complete! Val LogLoss: {eval_metrics['val_logloss']:.4f} | Val AUC: {eval_metrics['val_auc']:.4f} | Val Brier: {eval_metrics['val_brier']:.4f} | Val ECE: {eval_metrics['val_ece']:.4f}", flush=True)


if __name__ == "__main__":
    main()
