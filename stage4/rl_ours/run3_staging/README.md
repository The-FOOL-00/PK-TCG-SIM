# run3 (256k) staging — 5-minute turnaround card

Use this **only if run2 (128k) plateaus** (`verdict.py` on run2 = CAPACITY-LIMITED
HIGH-CONFIDENCE, or K2@150k misses ≥44%). Full detail: `LAB_RUNBOOK.md` run3
addendum. This card is the short version.

**Key fact:** no checkpoint needs to be shipped or embedded on the laptop. The
256k net is grown **in place on the lab box** from the trained 128k checkpoint via
`train.py --grow-src`. The code to do it is already in the lab delta
(`net.grow_policy_weights`). So the turnaround is ~5 minutes of verify-then-launch.

## The three commands (fill in the chosen iter)

```bash
# 1. pick the best 128k checkpoint from run2
python - <<'PY'
import json,glob,os
h=json.load(open("stage4/rl_ours/runs/run2/history.json"))
best=max((x for x in h if x.get("n_incumbent")), key=lambda x:x.get("winrate_incumbent",0))
print("best iter:", best["iter"], "wr", best.get("winrate_incumbent"))
print("ckpts:", sorted(os.path.basename(p) for p in glob.glob("stage4/rl_ours/runs/run2/policy_iter*.npz")))
PY

# 2. verify the grow is function-preserving on that real checkpoint (KL=0)
python -m stage4.rl_ours.ppo.widen_check \
  --src stage4/rl_ours/runs/run2/policy_iter###.npz \
  --trunk-hidden 512,256 --main-hidden 256 --games 80 --min-decisions 1000
#    expect: params 260418, A/B 0 flips, C EQUAL, VERDICT PASS

# 3. launch run3
nohup python -m stage4.rl_ours.ppo.train \
  --wide --trunk-hidden 512,256 --main-hidden 256 \
  --grow-src stage4/rl_ours/runs/run2/policy_iter###.npz \
  --iters 840 --games-per-iter 240 --workers 10 --ckpt-every 15 \
  --out stage4/rl_ours/runs/run3 --log stage4/rl_ours/runs/run3/history.json \
  > stage4/rl_ours/runs/run3.stdout 2>&1 &

# monitor: python -m stage4.rl_ours.ppo.verdict --log stage4/rl_ours/runs/run3/history.json
```

## Pre-verified before we ever get here
- 256k arch = trunk (512,256)/main 256 = **260,418 params**.
- Function-preservation of the grow tested on the laptop as a **27.8k→256k
  stand-in** (0 argmax flips / 2400 states, max|Δ|~2e-6) and a **128k-format→256k
  same-depth** test (max|Δ|~1.5e-5) — both PASS, KL=0 at init.
- Throughput: 128k→256k slowdown ≈ **1.0×** (game sim dominates) → ~14.5k g/h
  projected at the lab, ~9.6× the 1,500 floor. Same overnight sizing as run2.

## Alternative (only if you want to grow on the laptop instead)
Drop the trained 128k checkpoint into this folder, run
`build_policy_grown(src=<ckpt>, trunk_hidden=(512,256), main_hidden=256)` and
`.export_npz(...)`, then transfer the grown 256k npz back and launch `train.py
--wide ...` warm-starting from it. Not needed given `--grow-src`, but available.
