"""Train the distilled policy (imitate the search teacher) — Phase 2c, cycle 1.

STANDALONE: depends only on numpy. No repo imports, no cg/, no sklearn/torch.
CPU is sufficient (numpy-only — a GPU accelerator would not be used at all).

Input:  a directory of .npz shards produced by tools/gen_distill.py, each with
    state      float32 [D, 170]  state features per searched decision
    n_options  int16   [D]       number of options in that decision
    label      int16   [D]       teacher-chosen option index (0-based)
    turn       int16   [D]
    game_id    int32   [D]       unique per game — the train/val split key
    opt_x      float32 [sum(n_options), 41]  per-option features, decision
               order; option offsets = cumsum(n_options)
(meta.json in the same dir is optional and only used for feature names.)

Objective: cross-entropy over the options WITHIN each decision (softmax over
that decision's option logits, target = the teacher's choice). The split is
BY GAME (game_id % 10 == 0 -> validation) so correlated decisions from one
game never straddle the split.

Trains (i) a linear baseline over concat(state, option) and (ii) the MLP:
    state 170 -> 128 -> 64 state embedding (ReLU),
    option head concat(emb, option 41) = 105 -> 64 -> 1 logit (ReLU hidden)
~37k params, Adam. The epoch snapshot with the best val top-1 accuracy is
what gets saved (ties broken by val logloss).

===========================================================================
OUTPUT WEIGHT FORMAT (policy_weights.npz) — the runtime inference contract
===========================================================================
An .npz containing:
    kind               str array, "policy_mlp" or "policy_linear"
    n_state_features   int64 scalar (must equal 170)
    n_option_features  int64 scalar (must equal 41)
    n_trunk            int64 scalar — number of trunk layers (0 for linear)
    n_head             int64 scalar — number of head layers (>= 1)
    TW0..  Tb0..       float32 trunk weights [in, out] / biases [out]
    HW0..  Hb0..       float32 head weights  [in, out] / biases [out]
Forward pass per decision:
    emb = state;  for i < n_trunk:  emb = relu(emb @ TWi + Tbi)
    for each option:  h = concat(emb, option_features)
        for i < n_head-1:  h = relu(h @ HWi + Hbi)
        logit = h @ HW{last} + Hb{last}
    choose argmax logit (deterministic; ties -> lowest index).
===========================================================================

Also writes: policy_weights_linear.npz, policy_weights_mlp.npz,
policy_weights.npz (copy of the better one by val top-1 accuracy), and
metrics.json (logloss, top-1 imitation accuracy, and the two floor
baselines: v1-agreement rate and uniform-random expectation).

Run:  python train_policy.py --data DATA_DIR --out OUT_DIR \
          [--epochs 10] [--batch 2048] [--lr 1e-3] [--max-decisions 0] [--seed 0]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

N_STATE, N_OPT = 170, 41


# ----------------------------------------------------------------- data ----

class Dataset:
    """Ragged decisions: state [D,170], opt_x [O,41], ptr [D+1], label [D]."""

    def __init__(self, state, opt_x, n_options, label, game_id):
        self.state = state
        self.opt_x = opt_x
        self.n = n_options.astype(np.int64)
        self.ptr = np.concatenate([[0], np.cumsum(self.n)])
        self.label = label.astype(np.int64)
        self.game_id = game_id

    def __len__(self):
        return len(self.label)

    def gather(self, idx):
        """Rows for a batch of decision indices: (state, opt rows, per-batch
        option counts, segment ids, batch option offsets, label positions)."""
        counts = self.n[idx]
        starts = np.repeat(self.ptr[idx], counts)
        within = np.arange(counts.sum()) - np.repeat(
            np.cumsum(counts) - counts, counts)
        rows = starts + within
        seg = np.repeat(np.arange(len(idx)), counts)
        bptr = np.concatenate([[0], np.cumsum(counts)])
        lab_pos = bptr[:-1] + self.label[idx]
        return (self.state[idx], self.opt_x[rows], counts, seg, bptr, lab_pos)


def load_shards(data_dir, max_decisions=0):
    files = sorted(Path(data_dir).glob("shard_*.npz")) \
        or sorted(Path(data_dir).glob("*.npz"))
    if not files:
        raise SystemExit(f"no .npz shards found in {data_dir}")
    parts = {k: [] for k in ("state", "opt_x", "n_options", "label", "game_id")}
    for f in files:
        d = np.load(f)
        for k in parts:
            parts[k].append(d[k])
    state = np.concatenate(parts["state"]).astype(np.float32)
    opt_x = np.concatenate(parts["opt_x"]).astype(np.float32)
    n_options = np.concatenate(parts["n_options"])
    label = np.concatenate(parts["label"])
    game_id = np.concatenate(parts["game_id"])

    if max_decisions and len(label) > max_decisions:
        games = np.unique(game_id)
        rng = np.random.default_rng(0)
        rng.shuffle(games)
        frac = max_decisions / len(label)
        chosen = set(games[: max(1, int(len(games) * frac))].tolist())
        keep = np.fromiter((g in chosen for g in game_id), bool, len(game_id))
        opt_keep = np.repeat(keep, n_options.astype(np.int64))
        state, opt_x = state[keep], opt_x[opt_keep]
        n_options, label, game_id = n_options[keep], label[keep], game_id[keep]

    val = (game_id % 10) == 0  # split by game
    opt_val = np.repeat(val, n_options.astype(np.int64))
    tr = Dataset(state[~val], opt_x[~opt_val], n_options[~val],
                 label[~val], game_id[~val])
    va = Dataset(state[val], opt_x[opt_val], n_options[val],
                 label[val], game_id[val])
    print(f"decisions: {len(label)} ({len(va)} val)  "
          f"games: {len(np.unique(game_id))}  "
          f"option rows: {len(opt_x)}  "
          f"mean options/decision: {n_options.mean():.1f}", flush=True)
    return tr, va


# ---------------------------------------------------------------- model ----

def init_model(trunk_sizes, head_sizes, rng):
    """{"trunk": [[W,b],..], "head": [[W,b],..]} — trunk may be empty."""
    def mk(sizes):
        return [[rng.normal(0, np.sqrt(2.0 / i), (i, o)).astype(np.float32),
                 np.zeros(o, dtype=np.float32)]
                for i, o in zip(sizes[:-1], sizes[1:])]
    return {"trunk": mk(trunk_sizes), "head": mk(head_sizes)}


def params(model):
    return [layer for part in ("trunk", "head") for layer in model[part]]


def forward(model, s, x_opt, seg):
    """Returns (logits [O], cache for backprop)."""
    t_acts = [s]
    h = s
    for w, b in model["trunk"]:
        h = np.maximum(h @ w + b, 0.0)
        t_acts.append(h)
    z = np.concatenate([h[seg], x_opt], axis=1)
    h_acts = [z]
    g = z
    for w, b in model["head"][:-1]:
        g = np.maximum(g @ w + b, 0.0)
        h_acts.append(g)
    w, b = model["head"][-1]
    logits = (g @ w + b).ravel()
    return logits, (t_acts, h_acts, seg, len(s))


def seg_softmax(logits, seg, bptr):
    mx = np.maximum.reduceat(logits, bptr[:-1])
    e = np.exp(logits - mx[seg])
    ssum = np.add.reduceat(e, bptr[:-1])
    return e / ssum[seg]


def backward(model, cache, p, lab_pos, bptr):
    """Softmax-CE gradient. Returns [(dW, db)] aligned with params(model)."""
    t_acts, h_acts, seg, n_dec = cache
    d = p.copy()
    d[lab_pos] -= 1.0
    d /= n_dec
    d = d[:, None]
    head_grads = [None] * len(model["head"])
    for i in range(len(model["head"]) - 1, -1, -1):
        w, _b = model["head"][i]
        head_grads[i] = (h_acts[i].T @ d, d.sum(axis=0))
        d = d @ w.T
        if i > 0:
            d = d * (h_acts[i] > 0)
    emb_dim = t_acts[-1].shape[1]
    # options are contiguous per decision, so the segment sum is a reduceat
    d_emb = np.add.reduceat(d[:, :emb_dim], bptr[:-1], axis=0)
    trunk_grads = [None] * len(model["trunk"])
    d = d_emb
    for i in range(len(model["trunk"]) - 1, -1, -1):
        w, _b = model["trunk"][i]
        d = d * (t_acts[i + 1] > 0)
        trunk_grads[i] = (t_acts[i].T @ d, d.sum(axis=0))
        d = d @ w.T
    return trunk_grads + head_grads


def copy_model(model):
    return {part: [[w.copy(), b.copy()] for w, b in model[part]]
            for part in ("trunk", "head")}


# -------------------------------------------------------------- metrics ----

def evaluate(model, ds, batch=8192):
    """Mean CE + top-1 accuracy over a dataset, in batches."""
    tot_ll, tot_acc, n = 0.0, 0, len(ds)
    for s in range(0, n, batch):
        idx = np.arange(s, min(s + batch, n))
        st, xo, _counts, seg, bptr, lab_pos = ds.gather(idx)
        logits, _ = forward(model, st, xo, seg)
        p = seg_softmax(logits, seg, bptr)
        tot_ll += -np.log(np.clip(p[lab_pos], 1e-9, None)).sum()
        mx = np.maximum.reduceat(logits, bptr[:-1])
        pos = np.arange(len(logits))
        first_max = np.minimum.reduceat(
            np.where(logits == mx[seg], pos, len(logits)), bptr[:-1])
        tot_acc += int((first_max == lab_pos).sum())
    return float(tot_ll / n), float(tot_acc / n)


def train(model, tr, va, epochs, batch, lr, seed, tag):
    rng = np.random.default_rng(seed)
    ps = params(model)
    ms = [[np.zeros_like(w), np.zeros_like(b)] for w, b in ps]
    vs = [[np.zeros_like(w), np.zeros_like(b)] for w, b in ps]
    beta1, beta2, eps, t = 0.9, 0.999, 1e-8, 0
    best = {"acc": -1.0, "ll": float("inf"), "epoch": 0, "model": None}
    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(tr))
        t0 = time.perf_counter()
        for s in range(0, len(order), batch):
            idx = order[s:s + batch]
            st, xo, _counts, seg, bptr, lab_pos = tr.gather(idx)
            logits, cache = forward(model, st, xo, seg)
            p = seg_softmax(logits, seg, bptr)
            grads = backward(model, cache, p, lab_pos, bptr)
            t += 1
            for g_w_b, m, v, layer in zip(grads, ms, vs, params(model)):
                for j in range(2):
                    m[j] = beta1 * m[j] + (1 - beta1) * g_w_b[j]
                    v[j] = beta2 * v[j] + (1 - beta2) * g_w_b[j] ** 2
                    mh = m[j] / (1 - beta1 ** t)
                    vh = v[j] / (1 - beta2 ** t)
                    layer[j] -= lr * mh / (np.sqrt(vh) + eps)
        tr_ll, tr_acc = evaluate(model, tr)
        va_ll, va_acc = evaluate(model, va)
        star = ""
        if (va_acc, -va_ll) > (best["acc"], -best["ll"]):
            best.update(acc=va_acc, ll=va_ll, epoch=epoch,
                        model=copy_model(model))
            star = "  *best*"
        print(f"[{tag}] epoch {epoch}/{epochs}: "
              f"train CE {tr_ll:.4f} acc {tr_acc:.4f} | "
              f"val CE {va_ll:.4f} acc {va_acc:.4f} "
              f"({time.perf_counter()-t0:.0f}s){star}", flush=True)
    return best


def baselines(ds, v1_top_col):
    """Floor accuracies: always-agree-with-v1, and uniform random."""
    lab_abs = ds.ptr[:-1] + ds.label
    v1_acc = float((ds.opt_x[lab_abs, v1_top_col] > 0.5).mean())
    uniform = float((1.0 / ds.n).mean())
    return {"v1_top_accuracy": v1_acc, "uniform_accuracy": uniform}


def save_weights(path, model, kind):
    arrays = {"kind": np.array(kind),
              "n_state_features": np.int64(N_STATE),
              "n_option_features": np.int64(N_OPT),
              "n_trunk": np.int64(len(model["trunk"])),
              "n_head": np.int64(len(model["head"]))}
    for prefix, part in (("T", "trunk"), ("H", "head")):
        for i, (w, b) in enumerate(model[part]):
            arrays[f"{prefix}W{i}"] = w.astype(np.float32)
            arrays[f"{prefix}b{i}"] = b.astype(np.float32)
    np.savez(path, **arrays)
    print(f"wrote {path}", flush=True)


# ----------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dir of gen_distill .npz shards")
    ap.add_argument("--out", default=".", help="output dir")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=2048, help="decisions per batch")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-decisions", type=int, default=0, help="0 = everything")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tr, va = load_shards(args.data, args.max_decisions)
    if tr.state.shape[1] != N_STATE or tr.opt_x.shape[1] != N_OPT:
        raise SystemExit(f"feature dims {tr.state.shape[1]}/{tr.opt_x.shape[1]} "
                         f"!= expected {N_STATE}/{N_OPT}")
    # v1_top is the last option feature; confirm from meta.json when present
    v1_top_col = N_OPT - 1
    meta_fp = Path(args.data) / "meta.json"
    if meta_fp.is_file():
        names = json.loads(meta_fp.read_text(encoding="utf-8")).get(
            "option_feature_names") or []
        if "v1_top" in names:
            v1_top_col = names.index("v1_top")
    floors = {"train": baselines(tr, v1_top_col), "val": baselines(va, v1_top_col)}
    print(f"floor baselines: {floors}", flush=True)

    rng = np.random.default_rng(args.seed)
    results = {}
    for tag, trunk, head in (
            ("linear", [N_STATE], [N_STATE + N_OPT, 1]),
            ("mlp", [N_STATE, 128, 64], [64 + N_OPT, 64, 1])):
        model = init_model(trunk, head, rng)
        n_par = sum(w.size + b.size for w, b in params(model))
        print(f"[{tag}] {n_par} params", flush=True)
        best = train(model, tr, va, args.epochs, args.batch, args.lr,
                     args.seed, tag)
        results[tag] = {"params": n_par, "best_epoch": best["epoch"],
                        "val_logloss": best["ll"],
                        "val_top1_accuracy": best["acc"],
                        "model": best["model"]}
        save_weights(out / f"policy_weights_{tag}.npz", best["model"],
                     f"policy_{tag}")

    best_name = max(results, key=lambda k: (results[k]["val_top1_accuracy"],
                                            -results[k]["val_logloss"]))
    save_weights(out / "policy_weights.npz", results[best_name]["model"],
                 f"policy_{best_name}")
    metrics = {"data": str(args.data),
               "decisions_train": len(tr), "decisions_val": len(va),
               "epochs": args.epochs, "batch": args.batch, "lr": args.lr,
               "baselines": floors, "best": best_name}
    for tag, r in results.items():
        metrics[tag] = {k: v for k, v in r.items() if k != "model"}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2),
                                      encoding="utf-8")
    print(f"wrote {out / 'metrics.json'}", flush=True)
    print(f"BEST: {best_name}  val top-1 accuracy "
          f"{results[best_name]['val_top1_accuracy']:.4f}  "
          f"(v1-agreement floor {floors['val']['v1_top_accuracy']:.4f})",
          flush=True)


if __name__ == "__main__":
    main()
