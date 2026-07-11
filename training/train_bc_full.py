"""BC-full trainer (Stage 3B Option A): two-headed behavior cloning over
MAIN single-selects AND ST_CARD-family sub-decisions.

STANDALONE except train_policy.py / train_bc.py in this directory (numpy
only). One shared state trunk (all decisions train it — the thin ST_CARD
stream alone couldn't), two option heads because the option encodings differ
(41-dim MAIN vs 73-dim ST_CARD). Training interleaves shuffled mini-batches
from both streams; each step updates the trunk plus that stream's head
(per-parameter Adam step counters keep bias correction exact). Dropout, L2
weight decay and patience-based early stopping as in train_bc.py; the best
snapshot by COMBINED val top-1 (decision-weighted, ties by combined logloss)
is saved.

Output bc_weights_full_<tag>.npz extends the policy_weights contract:
    kind = "policy_two_head", n_state_features, n_trunk, TW*/Tb*,
    n_option_features (41), n_head, HW*/Hb*            — MAIN head
    n_option_features_card (73), n_head_card, CW*/Cb*  — ST_CARD head
Forward per decision: emb = relu-trunk(state); logit_i = head(concat(emb,
option_i)) with the head matching the selection type; argmax, ties lowest
index. Multi-select ST_CARD serve = iterative argmax over the shrinking
option set (mirrors the Plackett-Luce extraction).

Run:  python train_bc_full.py --data data/bc_garchomp_full --out runs/bc_full \
          [--trunk 80,48] [--head 48] [--dropout 0.2] [--wd 1e-4]
          [--epochs 200] [--patience 25] [--batch 256] [--lr 1e-3] [--tag garchomp]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_policy as tp  # noqa: E402
import train_bc as tb      # noqa: E402

N_STATE, N_OPT_MAIN, N_OPT_CARD = 170, 41, 73

CTX_NAMES = {1: "SETUP_ACTIVE", 2: "SETUP_BENCH", 3: "SWITCH", 4: "TO_ACTIVE",
             5: "TO_BENCH", 6: "TO_FIELD", 7: "TO_HAND", 8: "DISCARD",
             9: "TO_DECK", 10: "TO_DECK_BOT", 11: "TO_PRIZE", 12: "NOT_MOVE",
             13: "DMG_COUNTER", 14: "DMG_ANY", 15: "DAMAGE", 16: "REMOVE_DMG",
             17: "HEAL", 18: "EVOLVES_FROM", 19: "EVOLVES_TO",
             21: "ATTACH_FROM", 22: "ATTACH_TO", 23: "DETACH_FROM",
             24: "LOOK", 25: "EFFECT_TARGET"}
AREA_NAMES = {1: "deck", 2: "hand", 3: "discard", 4: "active", 5: "bench",
              6: "prize", 7: "stadium", 12: "looking"}


def load_stream(fp, extra_keys=()):
    """One .npz -> (train Dataset, val Dataset, {extra: (tr_arr, va_arr)}).
    Same by-game split rule as train_policy (game_id % 10 == 0 -> val)."""
    d = np.load(fp)
    state = d["state"].astype(np.float32, copy=False)
    opt_x = d["opt_x"].astype(np.float32, copy=False)
    n_options, label, game_id = d["n_options"], d["label"], d["game_id"]
    val = (game_id % 10) == 0
    opt_val = np.repeat(val, n_options.astype(np.int64))
    tr = tp.Dataset(state[~val], opt_x[~opt_val], n_options[~val],
                    label[~val], game_id[~val])
    va = tp.Dataset(state[val], opt_x[opt_val], n_options[val],
                    label[val], game_id[val])
    extras = {k: (d[k][~val], d[k][val]) for k in extra_keys if k in d}
    return tr, va, extras


def floors(ds, n_opt):
    lab_abs = ds.ptr[:-1] + ds.label
    return {
        "uniform": float((1.0 / ds.n).mean()),
        "always_index_0": float((ds.label == 0).mean()),
        "v1_agreement": float((ds.opt_x[lab_abs, n_opt - 1] > 0.5).mean()),
    }


def eval_correct(model, ds, batch=8192):
    """Per-decision correctness vector + mean CE (same math as tp.evaluate)."""
    correct = np.zeros(len(ds), dtype=bool)
    tot_ll = 0.0
    for s in range(0, len(ds), batch):
        idx = np.arange(s, min(s + batch, len(ds)))
        st, xo, _c, seg, bptr, lab_pos = ds.gather(idx)
        logits, _ = tp.forward(model, st, xo, seg)
        p = tp.seg_softmax(logits, seg, bptr)
        tot_ll += -np.log(np.clip(p[lab_pos], 1e-9, None)).sum()
        mx = np.maximum.reduceat(logits, bptr[:-1])
        pos = np.arange(len(logits))
        first_max = np.minimum.reduceat(
            np.where(logits == mx[seg], pos, len(logits)), bptr[:-1])
        correct[idx] = first_max == lab_pos
    return correct, float(tot_ll / max(1, len(ds)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dir with main.npz + card.npz")
    ap.add_argument("--out", default=".")
    ap.add_argument("--trunk", default="80,48")
    ap.add_argument("--head", default="48")
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--patience", type=int, default=25)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="garchomp")
    args = ap.parse_args()

    data = Path(args.data)
    tr_m, va_m, _ = load_stream(data / "main.npz")
    tr_c, va_c, extras = load_stream(data / "card.npz", ("ctx", "dom_area"))
    ctx_va, area_va = extras["ctx"][1], extras["dom_area"][1]
    print(f"MAIN: {len(tr_m)} train / {len(va_m)} val decisions "
          f"({tr_m.n_games}/{va_m.n_games} games)")
    print(f"CARD: {len(tr_c)} train / {len(va_c)} val steps "
          f"({tr_c.n_games}/{va_c.n_games} games)")

    trunk_hidden = [int(x) for x in args.trunk.split(",") if x]
    head_hidden = [int(x) for x in args.head.split(",") if x]
    trunk_sizes = [N_STATE] + trunk_hidden
    rng = np.random.default_rng(args.seed)
    trunk = tp.init_model(trunk_sizes, [1, 1], rng)["trunk"]
    head_m = tp.init_model([1], [trunk_sizes[-1] + N_OPT_MAIN] + head_hidden + [1],
                           rng)["head"]
    head_c = tp.init_model([1], [trunk_sizes[-1] + N_OPT_CARD] + head_hidden + [1],
                           rng)["head"]
    view_m = {"trunk": trunk, "head": head_m}
    view_c = {"trunk": trunk, "head": head_c}
    n_params = sum(w.size + b.size for part in (trunk, head_m, head_c)
                   for w, b in part)
    print(f"[{args.tag}] trunk {trunk_sizes} heads +{head_hidden}+[1] "
          f"(MAIN {N_OPT_MAIN}d, CARD {N_OPT_CARD}d) = {n_params} params, "
          f"dropout {args.dropout}, wd {args.wd}")

    # per-parameter Adam state; index = position in trunk+head_m+head_c
    all_layers = trunk + head_m + head_c
    ms = [[np.zeros_like(w), np.zeros_like(b)] for w, b in all_layers]
    vs = [[np.zeros_like(w), np.zeros_like(b)] for w, b in all_layers]
    ts = [0] * len(all_layers)
    idx_map = {"m": list(range(len(trunk)))
                    + list(range(len(trunk), len(trunk) + len(head_m))),
               "c": list(range(len(trunk)))
                    + list(range(len(trunk) + len(head_m), len(all_layers)))}
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    best = {"score": (-1.0, float("inf")), "epoch": 0, "trunk": None,
            "head_m": None, "head_c": None, "history": []}
    rng_tr = np.random.default_rng(args.seed + 1)
    for epoch in range(1, args.epochs + 1):
        t0 = time.perf_counter()
        batches = [("m", i) for i in range(0, len(tr_m), args.batch)] \
                + [("c", i) for i in range(0, len(tr_c), args.batch)]
        rng_tr.shuffle(batches)
        order_m = rng_tr.permutation(len(tr_m))
        order_c = rng_tr.permutation(len(tr_c))
        for stream, s in batches:
            ds, view, order = (tr_m, view_m, order_m) if stream == "m" \
                else (tr_c, view_c, order_c)
            idx = order[s:s + args.batch]
            st, xo, _c, seg, bptr, lab_pos = ds.gather(idx)
            logits, cache = tb.forward_train(view, st, xo, seg, rng_tr,
                                             args.dropout)
            p = tp.seg_softmax(logits, seg, bptr)
            grads = tb.backward_train(view, cache, p, lab_pos, bptr)
            for g_w_b, li in zip(grads, idx_map[stream]):
                ts[li] += 1
                layer, m, v = all_layers[li], ms[li], vs[li]
                for j in range(2):
                    m[j] = beta1 * m[j] + (1 - beta1) * g_w_b[j]
                    v[j] = beta2 * v[j] + (1 - beta2) * g_w_b[j] ** 2
                    mh = m[j] / (1 - beta1 ** ts[li])
                    vh = v[j] / (1 - beta2 ** ts[li])
                    layer[j] -= args.lr * mh / (np.sqrt(vh) + eps)
                if args.wd > 0:
                    layer[0] -= args.lr * args.wd * layer[0]

        corr_m, ll_m = eval_correct(view_m, va_m)
        corr_c, ll_c = eval_correct(view_c, va_c)
        acc_m, acc_c = float(corr_m.mean()), float(corr_c.mean())
        n_all = len(va_m) + len(va_c)
        acc_all = (corr_m.sum() + corr_c.sum()) / n_all
        ll_all = (ll_m * len(va_m) + ll_c * len(va_c)) / n_all
        dt = time.perf_counter() - t0
        best["history"].append(
            {"epoch": epoch, "val_acc_main": acc_m, "val_acc_card": acc_c,
             "val_acc_combined": acc_all, "val_ce_main": ll_m,
             "val_ce_card": ll_c, "seconds": round(dt, 1)})
        star = ""
        if (acc_all, -ll_all) > best["score"]:
            best.update(score=(acc_all, -ll_all), epoch=epoch,
                        trunk=[[w.copy(), b.copy()] for w, b in trunk],
                        head_m=[[w.copy(), b.copy()] for w, b in head_m],
                        head_c=[[w.copy(), b.copy()] for w, b in head_c])
            star = "  *best*"
        print(f"[{args.tag}] epoch {epoch}/{args.epochs}: "
              f"val MAIN acc {acc_m:.4f} CE {ll_m:.3f} | "
              f"CARD acc {acc_c:.4f} CE {ll_c:.3f} | "
              f"combined {acc_all:.4f} ({dt:.1f}s){star}", flush=True)
        if epoch - best["epoch"] >= args.patience:
            print(f"[{args.tag}] early stop: no combined-val improvement for "
                  f"{args.patience} epochs (best epoch {best['epoch']})",
                  flush=True)
            break

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    arrays = {"kind": np.array("policy_two_head"),
              "n_state_features": np.int64(N_STATE),
              "n_option_features": np.int64(N_OPT_MAIN),
              "n_option_features_card": np.int64(N_OPT_CARD),
              "n_trunk": np.int64(len(best["trunk"])),
              "n_head": np.int64(len(best["head_m"])),
              "n_head_card": np.int64(len(best["head_c"]))}
    for prefix, part in (("T", best["trunk"]), ("H", best["head_m"]),
                         ("C", best["head_c"])):
        for i, (w, b) in enumerate(part):
            arrays[f"{prefix}W{i}"] = w.astype(np.float32)
            arrays[f"{prefix}b{i}"] = b.astype(np.float32)
    wpath = out / f"bc_weights_full_{args.tag}.npz"
    np.savez(wpath, **arrays)

    best_view_m = {"trunk": best["trunk"], "head": best["head_m"]}
    best_view_c = {"trunk": best["trunk"], "head": best["head_c"]}
    corr_m, ll_m = eval_correct(best_view_m, va_m)
    corr_c, ll_c = eval_correct(best_view_c, va_c)
    fl_m, fl_c = floors(va_m, N_OPT_MAIN), floors(va_c, N_OPT_CARD)

    per_ctx = {}
    for ctx, area in sorted(set(zip(ctx_va.tolist(), area_va.tolist()))):
        m = (ctx_va == ctx) & (area_va == area)
        key = f"{CTX_NAMES.get(ctx, ctx)}/{AREA_NAMES.get(area, area)}"
        sub = corr_c[m]
        lab_abs = va_c.ptr[:-1] + va_c.label
        v1_sub = float((va_c.opt_x[lab_abs, N_OPT_CARD - 1] > 0.5)[m].mean())
        per_ctx[key] = {"n_val": int(m.sum()), "acc": float(sub.mean()),
                        "uniform_floor": float((1.0 / va_c.n[m]).mean()),
                        "v1_agree_floor": v1_sub}

    print(f"\nBEST epoch {best['epoch']} ({wpath.name}):")
    print(f"  MAIN val top-1 {corr_m.mean():.4f}  floors: "
          f"uniform {fl_m['uniform']:.3f} always-0 {fl_m['always_index_0']:.3f} "
          f"v1-agree {fl_m['v1_agreement']:.3f}")
    print(f"  CARD val top-1 {corr_c.mean():.4f}  floors: "
          f"uniform {fl_c['uniform']:.3f} always-0 {fl_c['always_index_0']:.3f} "
          f"v1-agree {fl_c['v1_agreement']:.3f}")
    print("  CARD per-context val accuracy:")
    for key, r in sorted(per_ctx.items(), key=lambda kv: -kv[1]["n_val"]):
        print(f"    {key:24s} n={r['n_val']:4d}  acc {r['acc']:.3f}  "
              f"(uniform {r['uniform_floor']:.3f}, v1 {r['v1_agree_floor']:.3f})")

    metrics = {"params": int(n_params), "best_epoch": best["epoch"],
               "val_top1_main": float(corr_m.mean()),
               "val_top1_card": float(corr_c.mean()),
               "val_ce_main": ll_m, "val_ce_card": ll_c,
               "floors_main": fl_m, "floors_card": fl_c,
               "card_per_context": per_ctx, "history": best["history"],
               "decisions": {"main_train": len(tr_m), "main_val": len(va_m),
                             "card_train": len(tr_c), "card_val": len(va_c)},
               "args": vars(args)}
    (out / f"metrics_full_{args.tag}.json").write_text(
        json.dumps(metrics, indent=2))
    print(f"wrote {wpath} and metrics")


if __name__ == "__main__":
    main()
