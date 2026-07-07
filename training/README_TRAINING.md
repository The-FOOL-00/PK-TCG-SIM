# Training runbook (external — Kaggle notebook / Colab)

Everything here is standalone: the scripts import **numpy only** — no repo
code, no cg/, no sklearn/pytorch. A **CPU** notebook is sufficient. Nothing
in the data or scripts is competition-redistributable content (feature
vectors + outcomes only), but keep the Kaggle dataset **private** anyway.

## Run 1 — value model (Phase 1, rung a)

### What you upload

Create ONE private Kaggle dataset (e.g. `ptcg-selfplay-v1`) containing:

1. `train_value.py` (this folder)
2. The contents of `data/selfplay_v1/` — all `shard_w*.npz` files and
   `meta.json` (~a few hundred MB total; upload the files as-is, no zip
   nesting needed — Kaggle unzips a dataset automatically).

### Notebook settings

- New Notebook -> **Add Input** -> your `ptcg-selfplay-v1` dataset.
- Accelerator: **None (CPU)**. Internet: off is fine.
- Environment: default Kaggle Python (numpy preinstalled).

### What you run (one cell)

```python
!python /kaggle/input/ptcg-selfplay-v1/train_value.py \
    --data /kaggle/input/ptcg-selfplay-v1 \
    --out  /kaggle/working
```

(If you nested the shards in a subfolder, point `--data` there instead. The
script globs `*.npz` in that one directory.)

### Expected output / runtime

- Prints per-epoch train/val logloss for `logreg` then `mlp`
  (6 epochs each). On ~1.5M rows expect roughly **10–25 min total on CPU**.
- Files in `/kaggle/working`:
  - `value_weights.npz`  <- **the one file to download back**
  - `value_weights_logreg.npz`, `value_weights_mlp.npz` (both variants,
    grab them too if convenient — cheap insurance)
  - `metrics.json` (train/val logloss, AUC, calibration table — download
    this as well; the integration gate report needs the calibration table)

### What to hand back

`value_weights.npz` + `metrics.json` into the repo root (or just tell me
where they are). Integration (flag `PTCG_LEARNED_VALUE`, pure-numpy inference,
heuristic fallback) and the 300-game ab_gate run happen on this side.

### Sanity expectations

- val AUC should be comfortably > 0.5 (0.65–0.80 plausible); val logloss
  < 0.693 (= coin flip). If AUC ~ 0.5, something is wrong — stop and report.
- The local end-to-end check already ran on a 2k-game subsample (see
  EXPERIMENT_LOG.md), so any failure in the notebook is environmental
  (paths, dataset layout), not the script.

## Run 2 — policy distillation (Phase 2, rung b)

_To be extended at Training Handoff #2: `train_policy.py`, data under
`data/distill_v1/`, same upload pattern, val split by game, target <100k
params, outputs `policy_weights.npz`._
