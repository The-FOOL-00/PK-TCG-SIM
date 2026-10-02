# Dataset Inventory & Reacquisition Guide

Date: 2026-10-02  
Repository: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`

This document details all large reproducible datasets, replay corpora, simulation outputs, and external assets associated with the competition project, documenting their local path, size, purpose, source, schema, and exact reacquisition or regeneration procedures.

---

## 1. Master Dataset Summary

| Dataset Name | Local Path | Approximate Size | Origin / Source | Exact Reproduction Needed? |
|---|---|---|---|---|
| **Scratchpad S3 Horizon Simulations** | `scratchpad/s3/` | 48.50 GB | Local Simulation Harness | No (Regenerable) |
| **Top Replays Bulk Corpus** | `data/top_replays_bulk/` | 7.81 GB | Kaggle Leaderboard API | No (Scraped Public Replays) |
| **Phase 2 Meta Shift Replays** | `analysis/phase2_meta_shift/` | 7.33 GB | Kaggle Leaderboard API | No (Scraped Public Replays) |
| **Stage 4 List-0 Replays** | `stage4/data/replays_list0/` | 1.90 GB | Kaggle Leaderboard API | No (Scraped Public Replays) |
| **Real Ladder Match Logs** | `data/realladder/raw/` | 1.31 GB | Kaggle Submission API | No (Live Telemetry Logs) |
| **Behavior Cloning Tensors** | `data/bc_mega/` | 128 MB | Feature Extraction Pipeline | No (Regenerable) |
| **Official Engine Binaries** | `ptcg_engine/` | 15 MB | Kaggle Competition Data Tab | No (Downloadable) |
| **Official Card ID Lists** | `Card_ID List_*.pdf` | 305 MB | Kaggle Competition Data Tab | No (Downloadable) |

---

## 2. Reacquisition & Regeneration Protocols

### A. Kaggle Leaderboard Replay Corpora (~18.35 GB total)
The replay files (`data/top_replays_bulk/`, `analysis/phase2_meta_shift/replays_*`, `stage4/data/replays_list0/`, `data/realladder/raw/`) contain serialized JSON representations of matches played on the public Kaggle ladder.

- **Source URL**: `https://www.kaggle.com/competitions/pokemon-tcg-ai-battle`
- **Authentication**: Requires valid `~/.kaggle/credentials.json` or `~/.kaggle/kaggle.json`.
- **Retrieval Scripts**:
  - Replay scraping by episode IDs:
    ```bash
    python tools/ladder_watch.py --poll --download-replays
    ```
  - Historical meta shift harvesting:
    ```bash
    python analysis/phase2_meta_shift/harvest_jul21.py
    python analysis/phase2_meta_shift/harvest_jul31.py
    ```
  - Stage 4 List-0 harvest:
    ```bash
    python stage4/rl_ours/fetch_mine.py
    ```
  - User submission history and match transcripts:
    ```bash
    python tools/fetch_submissions.py
    ```
- **Schema**: Standard Kaggle Environments episode JSON containing:
  - `steps`: Array of state observations and action outputs.
  - `rewards`: Final game scores `[+1, -1]`.
  - `info`: Episode metadata (submission ID, rating, agent timestamps).

---

### B. Local Simulation & Horizon Datasets (~48.50 GB)
The `scratchpad/s3/` directory contains multi-horizon rollout batches (`horizon_K*`, `cdk_grimmsnarl_*`) evaluated during tactical priority tuning.

- **Regeneration Script**:
  ```bash
  python tools/ab_gate.py --games 300 --out runs/ab_test
  ```
- **Self-Play Training Data**:
  As documented in `data/README_DATA.md`:
  ```bash
  python tools/gen_selfplay.py --games 50000 --workers 8 --out data/selfplay_v1
  ```
- **Search-Distillation Shards**:
  ```bash
  python tools/gen_distill.py --decisions 500000 --workers 8 --out data/distill_c1
  ```
- **Schema**: NumPy compressed `.npz` archives containing aligned arrays:
  - `x`: `float32 [N, 170]` state features from acting player perspective (`main.encode_state`).
  - `y`: `int8 [N]` outcome labels (+1 win / -1 loss / 0 draw).
  - `turn`: `int16 [N]` turn number.
  - `game_id`: `int32 [N]` unique identifier for game grouping.

---

### C. Official Competition Assets
In accordance with Kaggle Competition Rules, official engine binaries (`ptcg_engine/`) and card data PDFs (`Card_ID List_*.pdf`) are non-redistributable intellectual property and must be downloaded directly by participants:

- **Source URL**: `https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/data`
- **Kaggle CLI Download**:
  ```bash
  kaggle competitions download -c pokemon-tcg-ai-battle
  ```
- All official assets are strictly ignored by `.gitignore` to prevent licensing violations.
