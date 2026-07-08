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

## Run 2 — policy distillation (Phase 2c cycle 1) — TRAINING HANDOFF #2

Same standalone pattern as Run 1: `train_policy.py` imports numpy only.

### What you upload

Create ONE private Kaggle dataset (e.g. `ptcg-distill-c1`) containing:

1. `train_policy.py` (this folder)
2. The contents of `data/distill_c1/` — all `shard_w*.npz` files and
   `meta.json`. This dataset is much SMALLER than Run 1: ~2.5 MB per
   40k-decision shard, ~35 MB total for the full 500k-decision run
   (option features are sparse one-hots and compress hard).

### Notebook settings

- New Notebook -> **Add Input** -> your `ptcg-distill-c1` dataset.
- Accelerator: **None (CPU)** — do NOT enable GPU. The script is pure
  numpy; a GPU would sit completely unused. Internet: off is fine.
- Environment: default Kaggle Python (numpy preinstalled).

### What you run (one cell)

```python
!python /kaggle/input/ptcg-distill-c1/train_policy.py \
    --data /kaggle/input/ptcg-distill-c1 \
    --out  /kaggle/working --epochs 15
```

(Nesting is handled: the script looks for `shard_*.npz` in `--data` and one
subdirectory down, and reads `meta.json` from wherever the shards are. If it
finds no shards it exits with a listing of what IS under `--data` — fix the
path from that.)

### Expected output / runtime

- Prints the shard count + RAM estimate, floor baselines (v1-agreement +
  uniform-random accuracy), then per-epoch train/val cross-entropy and
  top-1 accuracy for `linear` (212 params) then `mlp` (~37k params). On
  500k decisions expect roughly **25–60 min total on CPU** (~1 min/epoch
  for the MLP; measured 0.3 s/epoch on a 5.8k-decision dry run, scaled).
  Peak RAM is ~2–3 GB — far inside the ~30 GB Kaggle CPU box.
- If val accuracy is still climbing at epoch 15, rerun with `--epochs 25`
  — the saved weights are always the best-val-accuracy epoch snapshot, so
  extra epochs can only help.
- Files in `/kaggle/working`:
  - `policy_weights.npz`  <- **the one file to download back**
  - `policy_weights_linear.npz`, `policy_weights_mlp.npz` (cheap insurance)
  - `metrics.json` (top-1 imitation accuracy, baselines, per-epoch
    train/val curves, and exact decision/game counts per split — download
    too; the integration gate report needs it)

### What to hand back

`policy_weights.npz` + `metrics.json` into the repo root (or tell me where
they are). Integration (flag `PTCG_DISTILLED`, standard fallback chain +
time guard) and the ab_gate runs happen on this side.

### Sanity expectations

- The number that matters: **val `top1_accuracy` for `mlp` vs the val
  `v1_top_accuracy` baseline** printed at the start. The model only adds
  value where it beats always-copying-v1; on the local 2.5k-decision
  subsample the MLP was already at the floor (53.1% vs 52.8%) with CE still
  falling — at 200x the data it should be clearly above. If mlp top-1 is
  BELOW the v1 floor, something is wrong — stop and report.
- `linear` scoring far below `mlp` is normal and expected.
- The local end-to-end check already ran (generation -> training -> weight
  round-trip through the documented inference contract), so any failure in
  the notebook is environmental (paths, dataset layout), not the script.
