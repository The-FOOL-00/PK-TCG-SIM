# Git Branch Audit & Consolidation Strategy

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`  
Remote: `origin` (`https://github.com/The-FOOL-00/PK-TCG-SIM.git`)

---

## 1. Current Branch State

Command: `git branch -avv`

```text
* main                7f3bd4a [origin/main: ahead 69] docs(report): add final writeup documents, review notes, and publication figures
  remotes/origin/main 66ada6c Initial commit: heuristic agent v1, eval tools, gitignore competition data
```

### Analysis of Branch Heads
- **Local `main`**: Commit `7f3bd4a` (HEAD). Ahead of `origin/main` by 69 logically sequenced commits containing all modular code, bot architectures, training suites, stage4 experiments, project mew pipelines, reports, and documentation.
- **Remote `origin/main`**: Commit `66ada6c` (Initial baseline commit).
- **Merge Status**: Fast-forward linear history. `git merge-base --is-ancestor origin/main main` is **TRUE**. No divergence, no conflicts, no force-push needed.

---

## 2. Historical Milestone Branches to Establish & Push

In accordance with Section 8 ("Prefer: main, archive/vXX, research/vXX over copying historical versions into the same physical folder"), we establish dedicated historical archive branch references pointing to the major validated architectural milestones in the commit history:

| Branch Name | Commit Hash | Historical Phase / Purpose | Classification | Action |
|---|---|---|---|---|
| **`main`** | `7f3bd4a` (HEAD + cleanup) | Canonical completed competition project: final agent, writeups, reports, hardened config. | **Active / Canonical** | Keep as default branch, push to `origin/main`. |
| **`archive/v1-heuristic`** | `66ada6c` | Initial baseline: pure deterministic heuristic agent v1, eval tools, and initial setup. | **C — Historical Milestone** | Create branch reference at `66ada6c`, push to origin. |
| **`archive/v2-search-determinized`** | `e8c7e25` | Search & Determinization milestone: belief-sampled determinized Monte-Carlo search on cg API engine. | **C — Historical Milestone** | Create branch reference at `e8c7e25`, push to origin. |
| **`archive/v3-behavior-cloning`** | `148a58c` | Supervised imitation milestone: two-headed Behavior Cloning network (Option A gate pass 69.7%). | **C — Historical Milestone** | Create branch reference at `148a58c`, push to origin. |
| **`archive/stage4-ppo-league`** | `ce30384` | Reinforcement Learning milestone: PPO league self-play, capacity ladder (128k/256k), KL-to-BC anchor. | **C — Historical Milestone** | Create branch reference at `ce30384`, push to origin. |
| **`archive/project-mew-v4`** | `d7849c8` | Project Mew research milestone: 243-deck hybrid search, E19 velocity engine, V3/V4 surgical overrides. | **C — Historical Milestone** | Create branch reference at `d7849c8`, push to origin. |

---

## 3. Branch Classification Matrix

| Branch | Classification | Rationale | Disposition |
|---|---|---|---|
| `main` | **Canonical** | Contains all project work, final agent, benchmarks, documentation. | Retain & Push |
| `archive/v1-heuristic` | **C — Historical** | Preserves initial competition submission state. | Retain & Push |
| `archive/v2-search-determinized` | **C — Historical** | Preserves search phase implementation before the BC pivot. | Retain & Push |
| `archive/v3-behavior-cloning` | **C — Historical** | Preserves behavior cloning breakthrough and gate validations. | Retain & Push |
| `archive/stage4-ppo-league` | **C — Historical** | Preserves PPO trainer, capacity ladder experiments, and kill verdicts. | Retain & Push |
| `archive/project-mew-v4` | **C — Historical** | Preserves Project Mew deck search pipelines and empirical ledger. | Retain & Push |

---

## 4. Redundant Branch Deletion & Cleanup Policy

- **Local Branches Fully Contained in `main`**: None currently exist outside `main`.
- **Remote Branches**: `origin/main` is an ancestor of local `main`. No remote branch deletion is warranted.
- **Historical Retention**: All 5 archive branches point to immutable commits already incorporated into the history of `main`. They provide immediate, permanent navigation points in GitHub without creating repository bloat.
