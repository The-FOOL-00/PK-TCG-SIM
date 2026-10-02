# Deletion Manifest & Working Tree Hygiene Audit

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`  
Remote: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`

This manifest records all disposable and generated files removed from the working tree to ensure zero clutter, eliminate VS Code change-detection saturation, and guarantee clean archival status.

---

## 1. Corrective Pass Deletion Table (1,407 Files Reclaimed)

| Target Path / Group | Size (MB) | File Count | Classification | Deletion Justification | Canonical / Reacquisition Information |
|---|---|---|---|---|---|
| `runs/` | 175.29 MB | 383 | **DISPOSABLE_GENERATED** | Raw Kaggle episode replay JSON dumps (e.g. `84229192.json`, 8MB each) and heuristic run logs. | Scraped replays re-downloadable via `tools/ladder_watch.py`; distilled models preserved in `candidates/` and `bc_weights_*.npz`. |
| `data/` non-tracked (`distill_c1/`, `final_forensics/`, `live_replays/`, `v3/`, `v4/`, `master_artifact_inventory.json`) | 101.67 MB | 852 | **REGENERABLE_INTERMEDIATE** | Intermediate batch distillations, live replay scrapes, and temporary forensic inventories. | All datasets and reproduction recipes documented in `data/MANIFEST.csv` and `docs/DATASETS.md`. |
| `build/` (`bundle/`, `hardened_garchomp_bundle/`, `probe/`, `search_bundle/`, `bc_bundle/`) | 23.91 MB | 85 | **TEMPORARY_STAGING** | Packaging and build sandbox staging directories. | Packaging script preserved in `tools/build_hardened_garchomp.py` and `tools/run_master_verification.py`. |
| `stage4/` non-tracked (`data/bc_v2/`, `rl_ours/runs/`, non-tracked `runs/`) | 11.91 MB | 70 | **TRAINING_INTERMEDIATE** | Intermediate checkpoint zips (`policy_iter*.npz.zip`) and BC tensor partitions. | Stage 4 code and research reports tracked in `stage4/rl_ours/`; canonical weights tracked in `bc_weights_*.npz`. |
| `cg/` | 5.19 MB | 9 | **PRECOMPILED_DISPOSABLE** | Precompiled alternative simulator binaries (`libcg-arm64.so`, `libcg.dylib`). | Official engine tracked in `ptcg_engine/` and listed in `.gitignore`. |
| `__pycache__/`, `bot/__pycache__/` | 0.25 MB | 8 | **BYTECODE_CACHE** | Compiled Python `.pyc` bytecode files. | Automatically regenerated on demand by Python runtime. |

---

## 2. Total Reclaimed Space

- **Previous Bulk Deletion (Scratchpad & Replay Bulk)**: **67.82 GB** (20,483 files).
- **Corrective Pass Deletion (Clutter Elimination)**: **318.22 MB** (1,407 files).
- **Cumulative Space Reclaimed**: **~68.14 GB** (21,890 files).
- **Remaining Working Tree Footprint**: Clean, minimal footprint containing only tracked project source, canonical candidates (`candidates/`), model checkpoints, documentation, and non-redistributable official assets.

---

## 3. Preservation Safeguards

- Canonical final candidate `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` (SHA256: `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`) is verified intact and immutable.
- Historical candidate archives in `candidates/historical/` are preserved and tracked in Git.
- Research reports, analysis tools, and dataset manifests (`data/MANIFEST.csv`, `docs/DATASETS.md`) are preserved and tracked in Git.
