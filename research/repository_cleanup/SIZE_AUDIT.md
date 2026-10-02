# Final Repository Size Audit Report

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`  
Remote: `https://github.com/The-FOOL-00/PK-TCG-SIM.git`

## 1. High-Level Size Summary

| Scope | Size (Bytes) | Human-Readable Size | % of Total Workspace | File Count |
|---|---|---|---|---|
| **Total Workspace** | 475,377,449 | 453.36 MB | 100.00% | 2,023 |
| **.git Internal Database** | 42,482,515 | 40.51 MB | 8.94% | 907 |
| **Working Tree (excl .git)** | 432,894,934 | 412.84 MB | 91.06% | 1,116 |
| **Tracked Files in Git** | 31,731,052 | 30.26 MB | 6.67% | 827 |
| **Untracked Files** | 21,418 | 0.02 MB | 0.00% | 2 |
| **Ignored Files** | 401,142,464 | 382.56 MB | 84.38% | 287 |

## 2. Space Reclamation Comparison

| Metric | Before Initial Cleanup | After Bulk Pass | After Corrective Pass | Overall Reduction |
|---|---|---|---|---|
| **Workspace Size** | 68.50 GB | 660.67 MB | 443.68 MB | **-68.06 GB (99.35%)** |
| **Working Tree Files** | 23,580 | 3,097 | 1,114 | **-22,466 files (95.28%)** |
| **Untracked Files** | 10,000+ | 0 | 0 (post-commit) | **Zero untracked clutter** |
| **Git Database** | 30.85 MB | 30.85 MB | 30.85 MB | Stable & Compact |

## 3. Top 20 Largest Remaining Working Tree Files

| Rank | File Path | Size (MB) | Size (Bytes) | Category / Status |
|---|---|---|---|---|
| 1 | `Card_ID List_JP.pdf` | 173.84 | 182,284,028 | Official Competition Asset (Ignored per Rules) |
| 2 | `Card_ID List_EN.pdf` | 131.28 | 137,654,485 | Official Competition Asset (Ignored per Rules) |
| 3 | `analysis/phase2_meta_shift/pop_previous.json` | 3.94 | 4,128,110 | Leaderboard Snapshot / Analysis (Tracked in Git) |
| 4 | `data/selfplay_v1/shard_w2_000.npz` | 3.36 | 3,524,588 | Model Checkpoint / Weights (Tracked in Git) |
| 5 | `data/selfplay_v1/shard_w5_000.npz` | 3.35 | 3,509,147 | Model Checkpoint / Weights (Tracked in Git) |
| 6 | `data/selfplay_v1/shard_w4_000.npz` | 3.34 | 3,498,985 | Model Checkpoint / Weights (Tracked in Git) |
| 7 | `data/selfplay_v1/shard_w3_000.npz` | 3.33 | 3,496,718 | Model Checkpoint / Weights (Tracked in Git) |
| 8 | `data/selfplay_v1/shard_w6_000.npz` | 3.32 | 3,479,690 | Model Checkpoint / Weights (Tracked in Git) |
| 9 | `data/selfplay_v1/shard_w1_000.npz` | 3.32 | 3,479,297 | Model Checkpoint / Weights (Tracked in Git) |
| 10 | `data/selfplay_v1/shard_w0_000.npz` | 3.30 | 3,461,870 | Model Checkpoint / Weights (Tracked in Git) |
| 11 | `data/selfplay_v1/shard_w7_000.npz` | 3.29 | 3,448,097 | Model Checkpoint / Weights (Tracked in Git) |
| 12 | `analysis/phase2_meta_shift/pop_current.json` | 3.03 | 3,181,695 | Leaderboard Snapshot / Analysis (Tracked in Git) |
| 13 | `data/bs_cei_v1/shard_w3_000.npz` | 2.02 | 2,115,280 | Model Checkpoint / Weights (Tracked in Git) |
| 14 | `data/bs_cei_v1/shard_w4_000.npz` | 2.01 | 2,104,481 | Model Checkpoint / Weights (Tracked in Git) |
| 15 | `data/bs_cei_v1/shard_w6_000.npz` | 2.00 | 2,101,297 | Model Checkpoint / Weights (Tracked in Git) |
| 16 | `data/bc_junlee789_full/main.npz` | 2.00 | 2,096,943 | Model Checkpoint / Weights (Tracked in Git) |
| 17 | `data/bc_junlee789_garchomp/decisions.npz` | 2.00 | 2,096,943 | Model Checkpoint / Weights (Tracked in Git) |
| 18 | `data/bs_cei_v1/shard_w1_000.npz` | 2.00 | 2,096,875 | Model Checkpoint / Weights (Tracked in Git) |
| 19 | `data/bs_cei_v1/shard_w7_000.npz` | 1.99 | 2,084,618 | Model Checkpoint / Weights (Tracked in Git) |
| 20 | `data/bs_cei_v1/shard_w2_000.npz` | 1.99 | 2,082,924 | Model Checkpoint / Weights (Tracked in Git) |

## 4. Working Tree Directory Distribution

| Directory | File Count | Size (MB) | Size (Bytes) |
|---|---|---|---|
| `(root)` | 65 | 308.89 | 323,894,641 |
| `data` | 92 | 66.00 | 69,204,060 |
| `analysis` | 36 | 11.52 | 12,082,268 |
| `candidates` | 15 | 9.57 | 10,031,332 |
| `sample_submission` | 11 | 5.20 | 5,448,769 |
| `runs` | 153 | 3.35 | 3,509,373 |
| `stage4` | 149 | 3.01 | 3,159,564 |
| `ptcg_engine` | 45 | 1.34 | 1,404,583 |
| `report` | 13 | 1.22 | 1,281,331 |
| `bot` | 30 | 0.69 | 719,292 |
| `tools` | 88 | 0.59 | 614,188 |
| `project_mew_v4_research` | 276 | 0.53 | 552,976 |
| `project_mew_v5_research` | 25 | 0.32 | 333,828 |
| `bc_weights_clean_v21.npz` | 2 | 0.12 | 129,179 |
| `project_mew_v4` | 13 | 0.08 | 82,129 |
| `training` | 7 | 0.07 | 73,944 |
| `research` | 12 | 0.06 | 63,341 |
| `project_mew_replay_policy` | 11 | 0.05 | 52,258 |
| `project_mew_v3` | 9 | 0.05 | 49,954 |
| `project_mew_aggressive_surgical` | 16 | 0.05 | 49,198 |
| `deck_search` | 14 | 0.04 | 40,830 |
| `.claude` | 1 | 0.03 | 35,965 |
| `project_mew_shls` | 6 | 0.03 | 33,191 |
| `docs` | 4 | 0.03 | 26,280 |
| `deck_search_ogerpon_counter` | 20 | 0.01 | 12,496 |
| `deck_search_v2` | 3 | 0.01 | 9,964 |