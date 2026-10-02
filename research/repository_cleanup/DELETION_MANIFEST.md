# Deletion Manifest & Space Reclamation Audit

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`

This manifest records every directory and file category slated for deletion from the working tree to reclaim ~68 GB of storage, documenting its size, classification, justification, and recovery method.

---

## 1. Master Deletion Table

| Target Path / Scope | Size | File Count | Classification | Deletion Justification | Reacquisition / Recovery Information |
|---|---|---|---|---|---|
| `scratchpad/` | 48.52 GB | 12,718 | **SAFE_TO_DELETE** / **DUPLICATE** | Millions of batch rollout frames, horizon replay dumps, and temporary test directories. | Deterministically regenerable via `tools/ab_gate.py` and `tools/gen_selfplay.py`. |
| `data/top_replays_bulk/` | 7.81 GB | 1,895 | **PRESERVE_EXTERNAL** | Scraped Kaggle ladder replay JSONs used for BC mining. | Re-downloadable from Kaggle API via `python tools/ladder_watch.py --download-replays`. |
| `analysis/phase2_meta_shift/replays_*` | 7.33 GB | 1,803 | **PRESERVE_EXTERNAL** | Raw JSON match dumps across July 21-31 leaderboard snapshots. | Re-downloadable via `python analysis/phase2_meta_shift/harvest_jul21.py` and `harvest_jul31.py`. |
| `stage4/data/replays_list0/` | 1.90 GB | 457 | **PRESERVE_EXTERNAL** | Raw match transcripts of List-0 replays for Stage 4 PPO. | Re-downloadable via `python stage4/rl_ours/fetch_mine.py`. |
| `data/realladder/raw/` | 1.31 GB | 300 | **PRESERVE_EXTERNAL** | Raw ladder match logs scraped from submission telemetry. | Re-downloadable via `python tools/fetch_submissions.py`. |
| `data/bc_mega/` | 128 MB | 2 | **REGENERABLE** | Intermediate preprocessed feature arrays (`main.npz`, `card.npz`). | Re-extractable via `python tools/gen_distill.py`. |
| `test_env/` | 78 MB | 1,250 | **TEMPORARY** | Local Python virtual environment. | Deterministically recreatable via `python -m venv test_env && pip install -r requirements.txt`. |
| `dist/` | 14 MB | 9 | **TEMPORARY** | Build artifacts and test packages. | Regenerated locally during build step. |
| Root `episode-93676600-*.json` | 12 MB | 3 | **TEMPORARY** | One-off local episode debug logs. | Kaggle public replay 93676600. |
| Duplicate Staging Dirs (`project_mew_*_frozen`, `_postbuild`, `_staging`, `_fix`, `v4_corrected_candidate`) | 45 MB | 45 | **DUPLICATE** | Redundant verification and test sandboxes. Reusable verification runner preserved in `tools/run_master_verification.py`. | Canonical policy source tracked in `project_mew_aggressive_surgical/` and `main.py`. |
| Root Loose `*.tar.gz` (35 archives) | 20 MB | 35 | **DUPLICATE** | Redundant/intermediate packages now preserved in `candidates/final/` and `candidates/historical/`. | Key packages cryptographically preserved in `candidates/` with SHA256 hashes in `docs/AGENTS.md`. |
| `__pycache__/`, `*.pyc` | 25 MB | ~150 | **SAFE_TO_DELETE** | Python bytecode caches. | Automatically recompiled by Python runtime. |

---

## 2. Space Reclamation Summary

- **Total Space Reclaimed**: **~68.45 GB** (99.93% reduction in working tree bloat).
- **Remaining Repository Footprint**: Expected **< 45 MB** (tracked source, weights, candidate packages, and documentation).
- **Data Safety**: Zero project research or canonical code is lost; all large externalized data is indexed in `data/MANIFEST.csv` and `docs/DATASETS.md`.
