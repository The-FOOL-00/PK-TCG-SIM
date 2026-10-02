# File Classification & Disposition Policy

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`

This document classifies all major files and directories within the 68.5 GB workspace into explicit retention, externalization, and deletion categories.

---

## 1. Classification Categories

- **`MUST_COMMIT`**: Core source code, reusable research tools, validation scripts, manifests, documentation, publication figures, and canonical agent candidates.
- **`PRESERVE_EXTERNAL`**: Large reproducible datasets, Kaggle replay corpora, and benchmark traces that are documented in `data/MANIFEST.csv` and `docs/DATASETS.md` for reacquisition.
- **`REGENERABLE`**: Self-play shards, precomputed feature tensors, and compilation binaries that can be deterministically rebuilt from committed scripts.
- **`TEMPORARY`**: Virtual environments (`test_env`), intermediate staging directories, log streams, execution sandboxes, and browser/IDE caches.
- **`DUPLICATE`**: Redundant unpacked candidate directories and redundant tar.gz bundles whose contents are already preserved in canonical locations.
- **`SAFE_TO_DELETE`**: Cache artifacts (`__pycache__`, `*.pyc`), temporary test outputs, and unneeded trajectory dumps.

---

## 2. Directory & Component Classification Matrix

| Path / Pattern | Current Size | Classification | Rationale | Disposition |
|---|---|---|---|---|
| `main.py`, `deck.csv` | 182 KB | **MUST_COMMIT** | Canonical final deterministic heuristic agent and active deck configuration. | Commit to `main` |
| `bot/` | 148 KB | **MUST_COMMIT** | Modular bot components, tactical policies, evaluators, and heuristics. | Commit to `main` |
| `tools/` | 420 KB | **MUST_COMMIT** | Reusable diagnostic, evaluation, harvesting, packaging, and auditing tools. | Commit to `main` |
| `training/` | 110 KB | **MUST_COMMIT** | Standalone training pipelines for value models, policy distillation, and Q-learning. | Commit to `main` |
| `stage4/` (excl replays) | 12 MB | **MUST_COMMIT** | Stage 4 PPO trainer, capacity ladder experiments, validation gates, and runbooks. | Commit to `main` |
| `project_mew_v4_research/` | 4.8 MB | **MUST_COMMIT** | Research pipelines, deck search candidates, and empirical hybrid audit reports. | Commit to `main` |
| `project_mew_v5_research/` | 2.1 MB | **MUST_COMMIT** | V5 Alakazam/Tech research, head-to-head gates, and audit reports. | Commit to `main` |
| `project_mew_aggressive_surgical/` | 1.8 MB | **MUST_COMMIT** | Final aggressive surgical policy definition, experiment audits, and reports. | Commit to `main` |
| `report/` | 8.5 MB | **MUST_COMMIT** | Final competition writeup drafts, Kaggle writeup, review notes, and figures. | Commit to `main` |
| `docs/` | 250 KB | **MUST_COMMIT** | System documentation: `FINAL_ARTIFACTS.md`, `RESEARCH_HISTORY.md`, `AGENTS.md`, `DATASETS.md`. | Commit to `main` |
| `candidates/final/` | 5.1 KB | **MUST_COMMIT** | Exact verified Kaggle final submission archive and pre-build package. | Commit to `main` |
| `candidates/historical/` | 11.2 MB | **MUST_COMMIT** | Curated historical candidate packages representing all validated competition rungs. | Commit to `main` |
| `data/README_DATA.md`, `data/MANIFEST.csv` | 15 KB | **MUST_COMMIT** | Data schema definitions, generation commands, and dataset reacquisition manifest. | Commit to `main` |
| `bc_weights_clean_v21.npz/` | 2.3 MB | **MUST_COMMIT** | Shipped behavior cloning weights and training metrics. | Commit to `main` |
| `scratchpad/s3/` | 48.50 GB | **SAFE_TO_DELETE** | Millions of batch trajectory simulation frames and horizon outputs. | Delete from working tree |
| `scratchpad/` (other) | 22 MB | **DUPLICATE** | Duplicate extractions of Sanjay v2/v3, v220, and test logs. | Delete from working tree |
| `data/top_replays_bulk/` | 7.81 GB | **PRESERVE_EXTERNAL** | Scraped Kaggle top-10 replays. Recoverable via `tools/ladder_watch.py`. | Delete from working tree; document in manifest |
| `analysis/phase2_meta_shift/` (replays) | 7.33 GB | **PRESERVE_EXTERNAL** | Scraped leaderboard replays for meta shifts. Recoverable via `analysis/.../harvest_*.py`. | Delete from working tree; document in manifest |
| `stage4/data/replays_list0/` | 1.90 GB | **PRESERVE_EXTERNAL** | Stage 4 raw scraped list-0 match JSONs. Recoverable via `stage4/rl_ours/fetch_mine.py`. | Delete from working tree; document in manifest |
| `data/realladder/raw/` | 1.31 GB | **PRESERVE_EXTERNAL** | Scraped ladder match logs. Recoverable via `tools/ladder_watch.py`. | Delete from working tree; document in manifest |
| `data/bc_mega/` | 128 MB | **REGENERABLE** | Preprocessed training tensors for BC. Deterministically rebuildable via `tools/gen_distill.py`. | Delete from working tree; gitignored |
| `test_env/` | 78 MB | **TEMPORARY** | Virtual environment. Deterministically reinstallable via `pip install -r requirements.txt`. | Delete from working tree; gitignore |
| `dist/` | 14 MB | **TEMPORARY** | Build output staging. | Delete from working tree; gitignore |
| `runs/` (replays & html) | 120 MB | **REGENERABLE** | Replay HTML visualizers and run logs. Re-generated during benchmark runs. | Keep gitignored; remove unneeded logs |
| `project_mew_*_frozen`, `_postbuild`, `_staging` | 45 MB | **DUPLICATE** | Intermediate testing and staging sandboxes used during packaging. | Delete from working tree |
| Root unneeded `*.tar.gz` (35 archives) | 20 MB | **DUPLICATE** | Intermediate/redundant candidate archives superseded by final and curated historical packages. | Delete from working tree |
| `Card_ID List_*.pdf` | 305 MB | **PRESERVE_EXTERNAL** | Official competition PDFs. Downloadable from Kaggle competition Data tab. | Keep gitignored |
| `ptcg_engine/` | 15 MB | **PRESERVE_EXTERNAL** | Official competition simulation engine. Downloadable from Kaggle competition Data tab. | Keep gitignored |
| `__pycache__/`, `*.pyc` | 25 MB | **SAFE_TO_DELETE** | Python bytecode cache files. | Delete from working tree; gitignore |
| `episode-93676600-*.json` | 12 MB | **TEMPORARY** | Local debug logs for a single Kaggle episode. | Delete from working tree |
