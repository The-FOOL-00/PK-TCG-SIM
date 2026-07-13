# Status report — lab day-1 readiness (built 2026-07-12 night)

Deadline **2026-08-16** confirmed. Freeze Aug 14, train-stop Aug 12. No Kaggle
submissions made or pending — the user makes every submission.

## Tier 1 — MUST be ready by 08:00: ALL GREEN, committed

| Item | State | Evidence |
|------|-------|----------|
| Leakage audit (our encoder + path) | **6/6 PASS** | `ppo/leakage_audit.py`; C6 power-control proves the audit detects a planted leak |
| Torch mirror + weight copy + bit-match | **PASS, 0 flips** | `ppo/bit_match.py`; max\|Δlogit\| 2e-6 (warm-start), 9.5e-7 (export round-trip) |
| Lab package (both labs, identical) | **Built + verified** | `lab/build_package.py` → 1.6MB/31 files; extracted to clean dir, bit-match PASS with no source repo |
| FIRST-ACTION checklist + preflight | **Ready** | `lab/FIRST_ACTION.md`, `lab/preflight.py` (nproc→config→gates→GO/NO-GO exit codes) |
| Checkpoint sync protocol | **Ready, 1 user action** | `lab/sync.py` git-branch channel, 30-min push/pull |

**USER ACTION (only external dependency):** provide a shared git remote both
labs can push to, set `PTCG_SYNC_REMOTE` + `PTCG_SYNC_LAB`. Until then sync is
a safe no-op; training is unaffected.

## Tier 2 — trainer + validation: DONE

- **PPO trainer built** (`ppo/train.py`, `ppo/rollout.py`, `ppo/net.py`):
  BC-v2 warm start by direct weight copy, KL-to-BC anchor, GAE, potential-based
  prize/deck shaping (coef 0, rampable), parallel rollout workers, incumbent
  share ramp 0→0.35 (the fix for Sanjay's opp_frac=0.4-from-iter-1 poisoning).
- **Validation run: PASS** (`runs/valA/`, `ppo/analyze_run.py`):
  - 90 iters, **10,800 games, 36 min, 17,891 games/h** (12× the 1,500 NO-GO floor)
  - anchor win-rate early **0.421 → 0.455** late — no regression
  - KL-to-BC anchor **0.0114 → 0.0156** — bounded, no prior destruction
  - **The teammate's 34→5% collapse pattern did NOT reproduce.**
  - Honest read: this is a *regression/pattern* check, not a strength claim.
    "Loop trains without collapsing" is proven; "PPO beats v2.2.0" is the later
    G8a gate at scale, not this.

## nproc fork gate (armed in `ppo/configs.py`)
- ≥16 cores → `central` (workers 16, 480 games/iter) — launch-authorized
- 8–15 cores → `reduced` (workers 10, 240 games/iter) — launch-authorized
- <8 cores → **STOP**, go/no-go: combined ≥1,500 games/h with home box or
  NO-GO (ride v2.2.0). Preflight exits 2 and tells the operator to escalate.

## Kill criteria armed (`ppo/configs.py` KILL)
validation-regress · K1 (two gates <29% → revert) · K2 (no ≥44%@150k /
≥48%@300k → grow net 128k→256k FIRST, Gumbel-AZ only after both plateau) ·
K3 (one KL-halving retry) · leakage regression → STOP.

## What's NOT started (correctly, per instruction)
Tier 3 real training run — launches at the lab tomorrow AFTER nproc + the two
STOP gates pass on lab hardware. Not started tonight.

## Known scope boundaries (logged, not silent)
- Only MAIN single-select decisions carry policy gradient this iteration;
  ST_CARD plays under the frozen BC card head. Card head enters the gradient
  as a later refinement.
- Past-self checkpoints not yet fed into the league (needs main.py file
  resolution wired + tested — `train.py` TODO). Anchor + incumbent + v1
  archetypes are live now.
