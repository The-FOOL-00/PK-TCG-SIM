# Git Branch Audit & Historical Lineage Verification

Date: 2026-10-02  
Workspace: `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`  
Remote: `origin` (`https://github.com/The-FOOL-00/PK-TCG-SIM.git`)

---

## 1. Current Branch State

Command: `git branch -avv`

```text
  archive/project-mew-v4                        d7849c8 feat(project_mew): add Project Mew research pipelines, deck searches, and audit reports
  archive/stage4-ppo-league                     ce30384 Stage 4 capacity ladder: run1 capacity-limited verdict; 128k built+validated; 256k grower + verdict.py + run3 pkg + Gumbel scoping
  archive/v1-heuristic                          66ada6c Initial commit: heuristic agent v1, eval tools, gitignore competition data
  archive/v2-search-determinized                e8c7e25 Phase F: 6x governor stress PASS (max own-time 48.5s/600s); ab_gate sets DECK per side
  archive/v3-behavior-cloning                   148a58c G6b-full PASS 69.7% [64.2,74.6]: Option A gate matrix complete, all green
* main                                          291d2e2 [origin/main] research(cleanup): add comprehensive repository cleanup, size audit, and archival reports
  remotes/origin/HEAD                           -> origin/main
  remotes/origin/archive/project-mew-v4         d7849c8 feat(project_mew): add Project Mew research pipelines, deck searches, and audit reports
  remotes/origin/archive/stage4-ppo-league      ce30384 Stage 4 capacity ladder: run1 capacity-limited verdict; 128k built+validated; 256k grower + verdict.py + run3 pkg + Gumbel scoping
  remotes/origin/archive/v1-heuristic           66ada6c Initial commit: heuristic agent v1, eval tools, gitignore competition data
  remotes/origin/archive/v2-search-determinized e8c7e25 Phase F: 6x governor stress PASS (max own-time 48.5s/600s); ab_gate sets DECK per side
  remotes/origin/archive/v3-behavior-cloning    148a58c G6b-full PASS 69.7% [64.2,74.6]: Option A gate matrix complete, all green
  remotes/origin/main                           291d2e2 research(cleanup): add comprehensive repository cleanup, size audit, and archival reports
```

---

## 2. Ancestry & Divergence Verification

Every archive branch was formally checked via `git merge-base --is-ancestor <branch> main`:

| Branch Name | Commit Hash | Ancestor of `main`? | Remote Match (`origin/<branch>`)? | Historical Significance |
|---|---|---|---|---|
| **`main`** | `291d2e2` | Self | **100% Match** | Canonical production branch containing final agent, full verification suite, and archival documentation. |
| **`archive/v1-heuristic`** | `66ada6c` | **TRUE** | **100% Match** | Initial baseline heuristic agent v1 with basic card scoring and eval tools. |
| **`archive/v2-search-determinized`** | `e8c7e25` | **TRUE** | **100% Match** | Belief-sampled Monte-Carlo determinized search milestone on cg engine. |
| **`archive/v3-behavior-cloning`** | `148a58c` | **TRUE** | **100% Match** | Supervised two-headed neural imitation learning network (69.7% gate pass). |
| **`archive/stage4-ppo-league`** | `ce30384` | **TRUE** | **100% Match** | PPO league self-play, capacity ladder experiments, GAE, and kill criteria verdicts. |
| **`archive/project-mew-v4`** | `d7849c8` | **TRUE** | **100% Match** | Project Mew 243-deck hybrid search, E19 high-velocity engine, and surgical override development. |

---

## 3. Worktree & Stash Audit

- `git worktree list`: Exactly **1 active worktree** (`main` at `c:\Users\Sundareswaran\pokemon-tcg-ai-battle`). Zero stale or detached worktrees.
- `git stash list`: **0 stashes** (clean stash stack).
- `git tag -l`: **0 tags**.

---

## 4. Branch Retention & Safety Conclusion

- All 5 historical archive branches are preserved both locally and remotely on GitHub (`The-FOOL-00/PK-TCG-SIM`).
- No branch deletions were executed or required; every milestone represents a necessary rung in the competition provenance.
- History is strictly linear and fast-forward; no force pushes or history rewrites are necessary.
