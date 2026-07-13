# LAB RUNBOOK — manual execution on the lab PC

Lab PC: Xeon E5-1650 v4 (12 threads), 32 GB RAM, GTX 1080 Ti, Ubuntu 24.04.
Workflow: no SSH — you run each block by hand and read the output.

**Ground rules**
- Deadline 2026-08-16. Do NOT submit anything to Kaggle — the user does that.
- Torch runs on **CPU** here (self-play is CPU-bound; the GPU is not needed).
- If any STOP gate fails, do not launch training. Report the output back.

Artifact to upload from the laptop via Google Drive:
`dist/lab_package.tar.gz` (see path printed at the end of this doc).

---

## 1. Extract the tarball

```bash
mkdir -p ~/ptcg && cd ~/ptcg
tar xzf /path/to/lab_package.tar.gz         # <-- point at your Drive download
ls
```
**Check:** you see `main.py`, `tools/`, `stage4/`, `card_data.json`, and the
`*.npz` weight files. If `ls` is empty or errors, the transfer was corrupt —
re-download and re-extract.

## 2. Verify contents (34 files)

```bash
cat MANIFEST.txt | head -40
find . -type f | wc -l          # expect 34
```
**Check:** count is **34**. MANIFEST lists a sha + size per file. If the count
is lower, the tar is truncated — re-download.

## 3. Install dependencies (needs internet)

```bash
python3 --version                # expect 3.12.x; if 3.10/3.11 that is fine too
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r stage4/rl_ours/lab/requirements_lab.txt
```
**Check:** the final line prints no red `ERROR`. Confirm the three imports:
```bash
python -c "import torch, numpy, kaggle_environments; print('torch', torch.__version__, '| ke', kaggle_environments.__version__)"
```
**Check:** prints `torch 2.x ... | ke 1.30.1`. The `ke` version **must be
1.30.1** — a different engine version invalidates the gates. If it is not
1.30.1, run `pip install kaggle-environments==1.30.1` and re-check.

> Every command below assumes you are in `~/ptcg` with `.venv` activated and
> `PYTHONPATH` set. Set it once per shell:
> ```bash
> cd ~/ptcg && source .venv/bin/activate && export PYTHONPATH=$PWD
> ```

## 4. Leakage audit (STOP gate)

```bash
python -m stage4.rl_ours.ppo.leakage_audit --games 40 --cap 1500
```
Ignore the long "Unknown game … Available games are:" banner — that is
harmless OpenSpiel import noise, not an error.

**Check:** the block near the end reads `SCORE : 6/6` and
`VERDICT : PASS`. Every line C1–C6 says `[PASS]`.
**STOP condition:** anything other than `6/6 ... PASS` → do not proceed,
send me the whole block. No training starts on a leakage failure.

## 5. Bit-match test (STOP gate)

```bash
python -m stage4.rl_ours.ppo.bit_match --games 30 --cap 1000
```
**Check:** both lines read `0 argmax flips`, and `VERDICT : PASS`. The
`max|Δlogit|` values are ~1e-6 (expected float noise, fine).
**STOP condition:** any nonzero `argmax flips`, or `VERDICT : FAIL` → do not
proceed, send me the block. The torch mirror is not matching the shipped
policy; training would optimize the wrong artifact.

## 6. Preflight (runs 4+5 again + picks the config)

This is the single "am I clear to launch" command. It re-runs both gates and
reads the core count.

```bash
python -m stage4.rl_ours.lab.preflight; echo "EXIT=$?"
```
**Check the PREFLIGHT SUMMARY block:**
- `nproc : 12 cores` → `fork-gate config : reduced (workers=10, games/iter=240)`
- `leakage audit : PASS`
- `bit-match     : PASS`
- `VERDICT : GO — gates green, config reduced.`
- `EXIT=0`

**Interpret the exit code (pre-registered fork gate):**
| EXIT | Meaning | Action |
|------|---------|--------|
| **0** | GO — gates green, ≥8 cores | Proceed to step 7 |
| **1** | A STOP gate failed | STOP, send me the output |
| **2** | <8 cores (won't happen here — you have 12) | STOP, escalate to me |

Your box is 12 cores → **reduced** config, launch-authorized. Expect EXIT=0.

## 7. Launch training (kill criteria armed)

Use the command preflight prints. For this box it is (pick `--iters` per how
long the slot is; at ~18k games/h measured, `--iters 400` ≈ 96k games ≈ ~5h):

```bash
mkdir -p stage4/rl_ours/runs
nohup python -m stage4.rl_ours.ppo.train \
  --iters 400 --games-per-iter 240 --workers 10 --ckpt-every 15 \
  --out stage4/rl_ours/runs/run1 \
  --log stage4/rl_ours/runs/run1/history.json \
  > stage4/rl_ours/runs/run1.stdout 2>&1 &
echo "launched PID $!"
```
`nohup … &` keeps it running if the terminal closes. The stdout file is
mostly the OpenSpiel banner — the real signal is `history.json`.

## 8. Monitor the run + first gate

The trainer writes `history.json` after every iteration. Watch it:
```bash
python -m stage4.rl_ours.ppo.analyze_run --log stage4/rl_ours/runs/run1/history.json
```
Run this again every ~20–30 min. **Check for a healthy run:**
- `games/h` ≥ **1500** (expect ~15–18k). Below 1500 sustained = throughput
  NO-GO — send me the number.
- `KL-to-BC anchor` stays **< 0.15** (expect ~0.01–0.03). This is the
  prior-destruction guard.
- `anchor winrate early -> late` is **flat or rising**, not collapsing.
- Final line `VALIDATION VERDICT : PASS`.

Quick raw peek at the latest iterations:
```bash
python - <<'PY'
import json
h=json.load(open("stage4/rl_ours/runs/run1/history.json"))
print("iters",len(h),"games",sum(x["n_games"] for x in h))
for x in h[-5:]:
    print("it",x["iter"],"outcome",round(x["mean_outcome"],3),
          "anchWR",round(x["winrate_anchor"],2) if x.get("winrate_anchor") else None,
          "kl",round(x.get("kl_anchor",0),4),"inc",x.get("incumbent_share"))
PY
```

---

## Pre-registered KILL CRITERIA — what fires them, what to do

Report to me if any fires; do not improvise a fix.

| Kill | Output signal | Action |
|------|---------------|--------|
| **Leakage** | step 4/6 not `6/6 PASS` | STOP, no training |
| **Bit-match** | step 5/6 any `argmax flips` > 0 | STOP, no training |
| **nproc NO-GO** | sustained `games/h` < 1500 in step 8 | STOP RL; ride v2.2.0 |
| **Validation regress** | at ~10k games, `anchor winrate late` well below `early` (drop > ~0.05), or `VALIDATION VERDICT : FAIL` | STOP, rediagnose — this is the Sanjay 34→5% pattern |
| **K1 collapse** | a 200-game gate vs v2.2.0 < 29%, twice in a row | halt, revert to prior checkpoint, diagnose |
| **K2 plateau** | no gate ≥ 44% by 150k games / ≥ 48% by 300k | grow net 128k→256k FIRST; Gumbel-AZ only after both plateau |
| **KL runaway** | `KL-to-BC anchor` climbs past ~0.15 and keeps rising | STOP, one KL-halving retry (K3) |

**Prize/deck checkpoints** (`policy_iter###.npz`) are written every 15
iterations under `runs/run1/`. These are the artifacts to sync back and, later,
to gate vs v2.2.0. Do not upload anything to Kaggle — bring the checkpoints and
`history.json` back to me for the ship battery.

## Checkpoint sync (optional, only if the user gave you a remote)
```bash
export PTCG_SYNC_REMOTE=<git url from user>
export PTCG_SYNC_LAB=thefool00
python -m stage4.rl_ours.lab.sync daemon --run stage4/rl_ours/runs/run1 --interval 1800 &
```
If no remote was provided, skip this — sync is a no-op and training is
unaffected.
