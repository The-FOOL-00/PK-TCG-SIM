# Session handoff — 2026-07-13 (PPO capacity ladder: run1 done, run2 ready, run3 prepped)

Pick-up point for a fresh session. Operational detail lives in
`stage4/rl_ours/LAB_RUNBOOK.md` (run2 + run3 addenda); this is the summary.
NOTE: `stage4/rl_ours/runs/` is **gitignored** — the run histories/checkpoints
persist on disk but are not in git, so the conclusions below are recorded here.

## 1. run1 (narrow 27.8k PPO) — CAPACITY-LIMITED, high confidence
Stopped manually at iter 347 = **83,520 games** (voluntary pause, no kill fired).
Full diagnostic (`runs/history_full_347.json`, reproduce with
`python -m stage4.rl_ours.ppo.verdict --log <that>`):
- `winrate_incumbent` vs v2.2.0 **dead flat ~27.1%** — windows 27.3/26.9/27.2%,
  converged halves 27.2/27.0%. Incumbent-share ramp finished by iter ~39, so
  **309 converged iters all at 27%**, no drift up or down.
- **vf plateaued** 0.036→0.033 (critic converged, no untapped value).
- **kl_anchor asymptoted ~0.018** (rose then leveled — NOT runaway → K3 low value).
- anchor WR flat 46.5/46.1%, no Sanjay-collapse. Loop healthy, zero matchup progress.
- = textbook **K2_diagnostic capacity-limited** (not algorithm-limited). Earlier
  formal K1 gates (ckpt044/059) read 31.5/34.5% greedy — K1 NOT fired, but zero
  improvement over BC-v2 start 33.5% (`stage4/rl_ours/GATE_K1_ckpt044_059.md`).
- **Decision: grow capacity (PPO, not algorithm pivot).**

## 2. run2 (128k wide) — BUILT + verified; laptop-validated tonight
Net2WiderNet function-preserving embed of BC-v2. Arch trunk 170→320→160→48,
MAIN head 89→160→1, frozen card head = **134,274 params**. KL anchor stays the
frozen 27.8k BC-v2. Pre-launch gates GREEN (laptop): `widen_check` 0 flips/2400
states (KL=0 proven), leakage 6/6, throughput clears floor ~10×.
**Local validation run tonight** (`runs/run2_local`, 100 iters/24k games, i7-1355U):
no crash, KL bounded 0.020, anchor WR flat ~46% (no collapse), checkpoints written,
throughput **13.6k g/h** (validates lab ~15k projection). winrate_incumbent flat
~26% — expected/inconclusive at 61 converged iters (run1 needed ~309). Code path
de-risked; **NOT a verdict on the capacity hypothesis** (too early).

## 3. run3 (256k) contingency — PREPPED, do NOT launch unless run2 plateaus
General grower `net.grow_policy_weights` (any src→wider/deeper target; Net2Wider +
Net2Deeper identity-insert). `train.py --grow-src <ckpt>` grows a trained checkpoint
in place at launch. 256k arch = trunk (512,256)/main 256 = **260,418 params**.
Verified: 27.8k→256k stand-in + 128k→256k same-depth + **end-to-end --grow-src launch
from a real 128k ckpt** = 0 argmax flips, KL=0, checkpoint round-trips. Throughput
128k→256k slowdown ≈**1.0×** (game sim dominates) → ~14.5k g/h lab, same overnight
sizing. Package: `run3_staging/README.md` (5-min turnaround), LAB_RUNBOOK run3 addendum.

## 4. verdict.py — automated diagnostic (`stage4/rl_ours/ppo/verdict.py`)
Standalone on any `history.json`: auto-detects converged window, pools
winrate_incumbent CIs, trends vf/kl, emits ONE recommendation
(CAPACITY-LIMITED / CONTINUE / KEEP-TRAINING-TO-CONFIRM / REGRESSION). Validated:
reproduces run1 (capacity-limited, high-conf) and run2_local (keep-training, directional).

## 5. Gumbel-AZ scoping (`stage4/rl_ours/gumbel_az_scoping.md`)
Pivot ONLY if BOTH 128k and 256k plateau. Reuses Sanjay's ISMCTS/determinization +
engine-opponent wrapper + our leakage-audited encoder; needs Gumbel-top-k +
sequential-halving root, completed-Q targets, replay-buffer loop. **~4-5 days to a
first loop** — schedule-risk vs the Aug 12 freeze flagged (may favor shipping v2.2.0).

## 6. Tomorrow's plan
1. Transfer **`lab_delta.tar.gz`** (repo root, 8 files) to the lab; extract over the run1 checkout.
2. Run **M1–M3** (LAB_RUNBOOK run2 addendum): `widen_check` → `leakage_audit` → throughput smoke. All must be GREEN.
3. Launch **run2**: `train.py --wide --iters 840 --games-per-iter 240 --workers 10 --ckpt-every 15 --out runs/run2`.
4. Monitor with **`verdict.py --log runs/run2/history.json`**. K1 unchanged 29%; K2 counts reset from 0 (150k=iter625, 300k=iter1250).
5. **If run2 plateaus** (verdict = CAPACITY-LIMITED high-conf, or K2@150k misses ≥44%): run the run3 addendum — pick best 128k ckpt, `widen_check --src <ckpt> --trunk-hidden 512,256 --main-hidden 256`, launch `train.py --grow-src <ckpt> ...`. **If run2 climbs**, let it run; do NOT grow.
6. If 256k ALSO plateaus → Gumbel-AZ decision with user + advisor (do not auto-start).

## Constraints (standing)
Do NOT submit to Kaggle. Lab run1 was a voluntary pause (not killed). Nothing here
is launched — all launches await user decision on real lab data. No Co-Authored-By in commits.
