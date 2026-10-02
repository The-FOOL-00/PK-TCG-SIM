# Root Cause Analysis & Cleanup Reconciliation

## 1. Executive Summary

A discrepancy was identified between:
1. **VS Code Source Control UI**: Displayed *"Too many changes were detected. Only the first 10000 changes will be shown."* with numerous files marked `U` (Untracked).
2. **Previous Cleanup Report**: Claimed the working tree was clean (0 untracked files, 660 MB workspace).
3. **Current Authoritative Git & Filesystem Audit**:
   - `git status --porcelain -uall` returned **0 lines** (clean).
   - `git ls-files --others --exclude-standard` returned **0 files**.
   - `git ls-files --others --ignored --exclude-standard` returned **1,471 files** (630.69 MB).
   - Tracked files in Git: **827 files** (30.26 MB).
   - Total working tree files on disk: **2,298 files** (660.96 MB).

---

## 2. Detailed Root-Cause Breakdown

### Cause 1: VS Code Git Extension Change-Cap Throttling (The "10,000" Artifact)
Prior to the previous cleanup session, the local repository contained **23,580 files** totaling **68.47 GB**:
- `scratchpad/`: 12,718 files (48.52 GB) of raw simulation rollout dumps.
- `data/top_replays_bulk/`: 1,895 files (7.81 GB) of Kaggle replay JSONs.
- `analysis/phase2_meta_shift/replays_*`: 1,803 files (7.33 GB) of leaderboard match files.
- `stage4/data/replays_list0/`: 457 files (1.90 GB).
- `data/realladder/raw/`: 300 files (1.31 GB).
- Root directory: dozens of `submission_*.tar.gz` and `episode-*.json` files.

When a repository exceeds 10,000 untracked changes, VS Code's built-in Git extension (`vscode.git`) triggers an internal circuit breaker:
> *"The git repository at '<path>' has too many active changes, only a subset of Git features will be enabled."*
> *"Too many changes were detected. Only the first 10000 changes will be shown."*

At that moment, VS Code **disables automatic background polling and file-watcher event processing** to prevent IDE UI freeze or memory exhaustion. Even after the previous session deleted over 20,480 files, VS Code's Source Control panel preserved the cached 10,000+ change list and warning banner until an explicit UI refresh or window reload occurs.

### Cause 2: Physical Working-Tree Clutter Left As "Ignored"
While the previous cleanup removed 67.8 GB of scratchpad and raw replay bulk, it relied heavily on `.gitignore` to mask remaining disposable files rather than deleting them:
- **`runs/`**: 383 files (175.29 MB), containing 42 raw Kaggle episode replays from 2026-07-06 (e.g., `84229192.json`, 8 MB each) and heuristic run logs.
- **`build/`**: 85 files (23.91 MB) of temporary bundle directories (`hardened_garchomp_bundle`, `search_bundle`, `bundle/`).
- **`data/`**: 854 files (101.67 MB) of intermediate distill partitions (`data/distill_c1/`), live replays (`data/live_replays/`), and forensics.
- **`stage4/`**: 70 files (11.91 MB) of RL run outputs.
- **Official Competition PDFs in Root**: `Card_ID List_JP.pdf` (173.84 MB) and `Card_ID List_EN.pdf` (131.28 MB) (totaling 305.12 MB).
- **`__pycache__/`**: Python bytecode caches.
- **`cg/`**: 9 files (5.19 MB) of precompiled engine libraries.

These 1,471 files were ignored by `.gitignore` so `git status` showed clean, but they were still physically present in the local workspace.

### Cause 3: Verification of Other Hypotheses

| Hypothesis | Investigated | Finding |
|---|---|---|
| 1. Files recreated after cleanup? | Yes | No background processes or timers are actively generating files. |
| 2. Files copied back? | Yes | No external restore occurred; file timestamps reflect August 2026 for legacy data and today for cleanup commits. |
| 3. Generated files produced by script? | Yes | No background simulation scripts are running. |
| 4. `.gitignore` did not match them? | Yes | The `.gitignore` committed in `8b64eb5` matched all 1,471 files, making `git status` clean from Git CLI's perspective. |
| 5. Another branch/worktree contributed files? | Yes | `git worktree list` confirmed exactly 1 worktree on `main`. |

---

## 3. Reconciliation Plan

To achieve an authoritative, zero-clutter, clean repository:
1. **Audit & Classify All 1,471 Non-Tracked Files**: Ensure no unique source code, model weights, or research conclusions are lost.
2. **Safely Remove Disposable Ignored Data**:
   - Delete `runs/` (175 MB of raw replay logs).
   - Delete `build/` (24 MB of disposable bundle staging).
   - Delete temporary intermediate data in `data/` (`distill_c1/`, `live_replays/`, etc.) whose lineage and reproduction steps are documented in `data/MANIFEST.csv`.
   - Delete `__pycache__` and `.pyc` caches.
   - Delete temporary precompiled test binaries in `cg/`.
3. **Verify Competition Artifact Integrity**:
   - `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` (SHA256: `0ee9c21a51f139e20de9038ae34e90d860f4d43603bdb20142107ec72146a4c8`) is verified intact.
4. **Preserve Official PDFs & Metadata**:
   - Ensure official assets are documented in `data/MANIFEST.csv` and `docs/DATASETS.md`.
5. **Harden `.gitignore`**: Ensure no temporary or generated data can ever become untracked changes.
6. **Re-Verify with Git CLI**: Ensure `git status --porcelain -uall` remains empty, working tree is compact, and all remotes match.
