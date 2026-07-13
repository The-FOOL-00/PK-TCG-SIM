# FIRST ACTION ON ARRIVAL — lab PC checklist

Deadline: **2026-08-16** submission lock. Freeze Aug 14, train-stop Aug 12.
Do NOT submit to Kaggle from the lab — the user makes every submission.

Run these IN ORDER. Do not launch training until item 4 reports GO.

## 0. Environment (one-time, ~3 min)
```
python -m venv .venv && . .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r stage4/rl_ours/lab/requirements_lab.txt
```
Python 3.12. Torch is CPU-only (no GPU needed — self-play is CPU-bound).

## 1. nproc → config
Reported automatically by preflight (item 4). Fork gate (pre-registered):
- **≥16 cores** → `central` config, launch-authorized.
- **8–15 cores** → `reduced` config, launch-authorized.
- **<8 cores** → **STOP.** Go/no-go: confirm combined throughput with the
  home box ≥1500 games/h before committing, else NO-GO (ride v2.2.0).
  Report to the user before launching anything.

## 2. Leakage audit (STOP gate)
Must print 6/6 PASS. Any fail = training does not start, period.

## 3. Bit-match test (STOP gate)
Must print 0 argmax flips (both A: torch-vs-numpy-BC, B: export round-trip).
Any flip = STOP, diagnose the torch mirror.

## 4. Run preflight (does 1–3 and prints GO/NO-GO)
```
python -m stage4.rl_ours.lab.preflight
```
Exit 0 = GO (gates green, config chosen). Exit 1 = a gate failed (STOP).
Exit 2 = <8 cores (STOP, escalate to user).

## 5. Report status BEFORE launching
Send the user: core count, chosen config, both gate results. Wait for the
Colab-tier go/no-go if <8 cores. Otherwise proceed.

## 6. Configure checkpoint sync (if PTCG_SYNC_REMOTE provided)
```
export PTCG_SYNC_REMOTE=<shared git url>   # from the user
export PTCG_SYNC_LAB=thefool00             # or: sanjay
python -m stage4.rl_ours.lab.sync daemon --run stage4/rl_ours/runs/run1 --interval 1800 &
```
If PTCG_SYNC_REMOTE is unset, sync is a no-op and training is unaffected.

## 7. Launch training (kill criteria armed)
Use the exact command preflight prints. Kill criteria (ppo/configs.py KILL):
- **validation**: winrate-vs-anchor at 10k games < start → STOP, rediagnose.
- **K1**: two consecutive 200-game gates <29% vs v2.2.0 → halt, revert.
- **K2**: no gate ≥44% by 150k / ≥48% by 300k → grow net 128k→256k FIRST,
  Gumbel-AZ only after both widths plateau.
- **leakage regression** → STOP.

## What "best day 1" means
Gates pass → validation run shows reward improving, no Sanjay-pattern
regression → real run launched with kill criteria armed → first 30k–100k
games of PPO overnight. NOT: unvalidated overnight launch.
