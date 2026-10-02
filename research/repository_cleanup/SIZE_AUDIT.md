# Repository Size Audit Report

Date: 2026-10-02
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`

## High-Level Size Summary

| Scope | Size (Bytes) | Human-Readable Size | % of Total Workspace |
|---|---|---|---|
| **Total Workspace** | 73,549,627,148 | 68.50 GB | 100.00% |
| **Working Tree (excl .git)** | 73,517,274,720 | 68.47 GB | 99.96% |
| **.git Internal Directory** | 32,352,428 | 30.85 MB | 0.04% |
| **Tracked Files** | 21,545,076 | 20.55 MB | 0.03% |
| **Untracked Files** | 57,354,346,562 | 53.42 GB | 77.98% |
| **Ignored Files** | 16,141,383,082 | 15.03 GB | 21.95% |

## Critical Conclusion: Git History vs Working Tree

- **Git History Size**: **~30.85 MB** (packfile + loose objects).
- **Tracked Files Size**: **~20.55 MB** across 777 tracked files.
- **Untracked / Ignored Bloat**: **~68.45 GB** (99.93% of the total workspace).

**Classification**: `A. Only in working tree`.

The bloat resides strictly in the working tree as uncommitted tar.gz candidate bundles, local replay corpora, virtual environments (`test_env`), stage 4 run checkpoints, and scratchpad trees. **No large files were ever committed into Git history**. Therefore, no Git history rewriting (BFG / git-filter-repo) is needed.

## Large File Distribution by Bucket

| Threshold | Number of Files | Total Size |
|---|---|---|
| Files >= 5 GB | 0 | 0.00 B |
| Files >= 1 GB | 0 | 0.00 B |
| Files >= 500 MB | 0 | 0.00 B |
| Files >= 100 MB | 2 | 305.12 MB |
| Files >= 50 MB | 3 | 391.57 MB |
| Files >= 10 MB | 68 | 1.39 GB |

## Top 15 Largest Directories (Recursive)

| Directory | Recursive Size | File Count |
|---|---|---|
| `scratchpad` | 48.52 GB | 12718 |
| `scratchpad/s3` | 48.50 GB | 12664 |
| `data` | 9.51 GB | 3101 |
| `data/top_replays_bulk` | 7.81 GB | 1895 |
| `analysis` | 7.75 GB | 1930 |
| `analysis/phase2_meta_shift` | 7.33 GB | 1803 |
| `data/top_replays_bulk/junlee789_garchomp` | 3.99 GB | 968 |
| `analysis/phase2_meta_shift/replays_current_top10` | 2.48 GB | 612 |
| `stage4` | 1.91 GB | 690 |
| `stage4/data` | 1.90 GB | 469 |
| `stage4/data/replays_list0` | 1.90 GB | 457 |
| `scratchpad/s3/horizon_K1` | 1.59 GB | 400 |
| `scratchpad/s3/horizon_KE12` | 1.59 GB | 400 |
| `scratchpad/s3/horizon_KE1` | 1.57 GB | 400 |
| `scratchpad/s3/horizon_K0` | 1.57 GB | 400 |
