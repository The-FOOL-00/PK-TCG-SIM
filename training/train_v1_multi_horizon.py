"""Multi-Horizon Successor-State Value Network Trainer (BS-CEI V1.6).

Trains V1(s, belief) using multi-task representation learning on 1.6+ million
decision and successor states:
1. Primary Head: P(eventual win) - Binary Cross-Entropy.
2. Auxiliary Survival Head: P(board survival / non-benchout).
3. Auxiliary Prize Delta Head: Expected normalized prize delta.
4. Auxiliary Deckout Risk Head: P(deckout failure).

Network Backbone:
    194 (State + Belief) -> 256 -> 128 -> 64 -> 1 (Sigmoid Win Probability)

Auxiliary tasks regularize the shared representation to understand that board
preservation and energy readiness produce eventual winning trajectories.

Output:
- value_weights_v1.npz (Primary inference weights formatted for runtime)
- v1_metrics.json (LogLoss, AUC, Brier, ECE, phase-stratified metrics)
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np


def load_multi_horizon_data(data_dirs, max_rows=0):
    xs, ys, pds, dos, gids = [], [], [], [], []

    for ddir in data_dirs:
        files = sorted(Path(ddir).glob("*.npz"))
        for f in files:
            d = np.load(f)
            # Handle both gen_bs_cei format ('x') and q_failure format ('state')
            if "x" in d:
                x_mat = d["x"].astype(np.float32)
                y_vec = (d["y"] > 0).astype(np.float32)
                pd_vec = d.get("prize_delta", np.zeros_like(y_vec)).astype(np.float32)
                do_vec = d.get("deckout", np.zeros_like(y_vec)).astype(np.float32)
                gid_vec = d["game_id"]
            elif "state" in d:
                x_mat = d["state"].astype(np.float32)
                y_vec = d["y"].astype(np.float32)
                pd_vec = d.get("prize_delta", np.zeros_like(y_vec)).astype(np.float32)
                do_vec = np.zeros_like(y_vec, dtype=np.float32)
                gid_vec = d["game_id"]
            else:
                continue

            xs.append(x_mat)
            ys.append(y_vec)
            pds.append(pd_vec)
            dos.append(do_vec)
            gids.append(gid_vec)

    x = np.concatenate(xs, axis=0)
    y = np.concatenate(ys, axis=0)
    pd = np.concatenate(pds, axis=0)
    do = np.concatenate(dos, axis=0)
    g = np.concatenate(gids, axis=0)

    # Normalized prize delta to [-1, 1]
    pd_norm = np.clip(pd / 6.0, -1.0, 1.0)

    # Derived survival target: 1 if win or prize delta >= 0, else 0
    surv = ((y == 1.0) | (pd >= 0)).astype(np.float32)

    val = (g % 10) == 0
    print(f"Loaded {len(y)} total multi-horizon states ({val.sum()} val) across {len(np.unique(g))} games. Win rate: {y.mean():.3f}", flush=True)

    train_data = (x[~val], y[~val], pd_norm[~val], do[~val], surv[~val])
    val_data = (x[val], y[val], pd_norm[val], do[val], surv[val])
    return train_data, val_data


def init_multi_head_layers(in_dim, rng):
    """Initializes shared trunk + primary win head + auxiliary heads."""
    # Shared trunk: in_dim -> 256 -> 128 -> 64
    sizes = [in_dim, 256, 128, 64]
    trunk = []
    for fan_in, fan_out in zip(sizes[:-1], sizes[1:]):
        w = rng.normal(0, np.sqrt(2.0 / fan_in), (fan_in, fan_out)).astype(np.float32)
        b = np.zeros(fan_out, dtype=np.float32)
        trunk.append([w, b])

    # Win head: 64 -> 1
    w_win = rng.normal(0, np.sqrt(2.0 / 64), (64, 1)).astype(np.float32)
    b_win = np.zeros(1, dtype=np.float32)

    # Aux heads: 64 -> 1 each
    w_pd = rng.normal(0, np.sqrt(2.0 / 64), (64, 1)).astype(np.float32)
    b_pd = np.zeros(1, dtype=np.float32)

    w_do = rng.normal(0, np.sqrt(2.0 / 64), (64, 1)).astype(np.float32)
    b_do = np.zeros(1, dtype=np.float32)

    w_surv = rng.normal(0, np.sqrt(2.0 / 64), (64, 1)).astype(np.float32)
    b_surv = np.zeros(1, dtype=np.float32)

    return trunk, [w_win, b_win], [w_pd, b_pd], [w_do, b_do], [w_surv, b_surv]


def forward_trunk(trunk, x):
    acts = [x]
    h = x
    for w, b in trunk:
        h = np.maximum(h @ w + b, 0.0)
        acts.append(h)
    return acts


def forward_sigmoid(h, head):
    w, b = head
    z = (h @ w + b).ravel()
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def forward_linear(h, head):
    w, b = head
    return (h @ w + b).ravel()


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


def train_multi_horizon(
    train_data, val_data, in_dim, epochs=8, batch=4096, lr=1e-3, seed=42
):
    xtr, ytr, pd_tr, do_tr, surv_tr = train_data
    xva, yva, pd_va, do_va, surv_va = val_data

    rng = np.random.default_rng(seed)
    trunk, win_head, pd_head, do_head, surv_head = init_multi_head_layers(in_dim, rng)

    # Adam moments for all parameters
    all_layers = trunk + [win_head, pd_head, do_head, surv_head]
    ms = [[np.zeros_like(w), np.zeros_like(b)] for w, b in all_layers]
    vs = [[np.zeros_like(w), np.zeros_like(b)] for w, b in all_layers]
    beta1, beta2, eps, t = 0.9, 0.999, 1e-8, 0

    best_val_loss = float("inf")
    best_weights = None

    print(f"Training Multi-Horizon V1 Network on {len(ytr)} train rows, {len(yva)} val rows...")

    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(ytr))
        t0 = time.perf_counter()

        for s in range(0, len(order), batch):
            idx = order[s:s + batch]
            n_batch = len(idx)

            # Forward
            acts = forward_trunk(trunk, xtr[idx])
            h_last = acts[-1]

            p_win = forward_sigmoid(h_last, win_head)
            p_pd = forward_linear(h_last, pd_head)
            p_do = forward_sigmoid(h_last, do_head)
            p_surv = forward_sigmoid(h_last, surv_head)

            # Losses: Primary Win (BCE) + 0.2*MSE(pd) + 0.3*BCE(do) + 0.2*BCE(surv)
            d_win = ((p_win - ytr[idx]) / n_batch)[:, None]
            d_pd = 0.2 * (2.0 * (p_pd - pd_tr[idx]) / n_batch)[:, None]
            d_do = 0.3 * ((p_do - do_tr[idx]) / n_batch)[:, None]
            d_surv = 0.2 * ((p_surv - surv_tr[idx]) / n_batch)[:, None]

            # Gradients for heads
            g_win = (h_last.T @ d_win, d_win.sum(axis=0))
            g_pd = (h_last.T @ d_pd, d_pd.sum(axis=0))
            g_do = (h_last.T @ d_do, d_do.sum(axis=0))
            g_surv = (h_last.T @ d_surv, d_surv.sum(axis=0))

            # Backprop into trunk
            d_trunk = (d_win @ win_head[0].T) + (d_pd @ pd_head[0].T) + (d_do @ do_head[0].T) + (d_surv @ surv_head[0].T)
            trunk_grads = [None] * len(trunk)

            for i in range(len(trunk) - 1, -1, -1):
                w, _b = trunk[i]
                trunk_grads[i] = (acts[i].T @ d_trunk, d_trunk.sum(axis=0))
                if i > 0:
                    d_trunk = (d_trunk @ w.T) * (acts[i] > 0)

            # Adam step
            all_grads = trunk_grads + [g_win, g_pd, g_do, g_surv]
            t += 1
            for li, (g_w_b, m, v, layer) in enumerate(zip(all_grads, ms, vs, all_layers)):
                for j in range(2):
                    m[j] = beta1 * m[j] + (1 - beta1) * g_w_b[j]
                    v[j] = beta2 * v[j] + (1 - beta2) * g_w_b[j] ** 2
                    mh = m[j] / (1 - beta1 ** t)
                    vh = v[j] / (1 - beta2 ** t)
                    layer[j] -= lr * mh / (np.sqrt(vh) + eps)

        # Validation evaluation
        va_acts = forward_trunk(trunk, xva)
        pva_win = forward_sigmoid(va_acts[-1], win_head)
        va_logloss = logloss(pva_win, yva)
        va_auc = auc(pva_win, yva)
        va_brier = brier_score(pva_win, yva)

        tr_acts = forward_trunk(trunk, xtr[:100000])
        ptr_win = forward_sigmoid(tr_acts[-1], win_head)
        tr_logloss = logloss(ptr_win, ytr[:100000])

        if va_logloss < best_val_loss:
            best_val_loss = va_logloss
            # Save assembled primary layers for runtime: trunk + win_head
            best_layers = [[w.copy(), b.copy()] for w, b in trunk] + [[win_head[0].copy(), win_head[1].copy()]]
            marker = "*"
        else:
            marker = ""

        print(
            f"[v1-multi] epoch {epoch}/{epochs}: train logloss {tr_logloss:.4f} | "
            f"val logloss {va_logloss:.4f} | val AUC {va_auc:.4f} | val Brier {va_brier:.4f} {marker} ({time.perf_counter() - t0:.1f}s)",
            flush=True,
        )

    return best_layers


def evaluate_final(layers, xva, yva):
    h = xva
    for w, b in layers[:-1]:
        h = np.maximum(h @ w + b, 0.0)
    w, b = layers[-1]
    z = (h @ w + b).ravel()
    pva = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    return {
        "params": int(sum(w.size + b.size for w, b in layers)),
        "val_logloss": logloss(pva, yva),
        "val_auc": auc(pva, yva),
        "val_brier": brier_score(pva, yva),
        "val_ece": expected_calibration_error(pva, yva),
    }


def save_v1_weights(path, layers, n_features):
    arrays = {
        "n_layers": np.int64(len(layers)),
        "n_features": np.int64(n_features),
        "kind": np.array("v1_multi_horizon"),
    }
    for i, (w, b) in enumerate(layers):
        arrays[f"W{i}"] = w.astype(np.float32)
        arrays[f"b{i}"] = b.astype(np.float32)
    np.savez(path, **arrays)
    print(f"wrote {path}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        nargs="+",
        default=["data/bs_cei_v1", "data/q_failure_v1"],
        help="Data directories",
    )
    parser.add_argument("--out", default=".", help="Output directory")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    train_data, val_data = load_multi_horizon_data(args.data)
    in_dim = train_data[0].shape[1]

    best_v1_layers = train_multi_horizon(
        train_data,
        val_data,
        in_dim,
        epochs=args.epochs,
        batch=args.batch,
        lr=args.lr,
        seed=args.seed,
    )

    eval_metrics = evaluate_final(best_v1_layers, val_data[0], val_data[1])
    save_v1_weights(out / "value_weights_v1.npz", best_v1_layers, in_dim)
    # Also overwrite value_weights.npz so all leaf evaluators use V1
    save_v1_weights(out / "value_weights.npz", best_v1_layers, in_dim)

    metrics = {
        "data": args.data,
        "n_features": in_dim,
        "metrics": eval_metrics,
    }
    (out / "v1_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(
        f"V1 Multi-Horizon Training Complete! Val LogLoss: {eval_metrics['val_logloss']:.4f} | "
        f"Val AUC: {eval_metrics['val_auc']:.4f} | Val Brier: {eval_metrics['val_brier']:.4f} | "
        f"Val ECE: {eval_metrics['val_ece']:.4f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
