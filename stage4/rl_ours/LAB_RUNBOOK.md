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

---

# ADDENDUM — run2: capacity growth 27.8k → 128k (wide net)

**Why:** run1 (narrow 27.8k net) trained cleanly for 83.5k games — no collapse,
KL bounded, anchor winrate flat ~46% — but made **zero** matchup progress vs
v2.2.0 (winrate_incumbent dead flat ~27.1% across 309 converged iterations,
critic plateaued, KL anchor asymptoted ~0.018). That is the pre-registered
**K2_diagnostic** signature: *capacity-limited, not algorithm-limited.* The
response is to grow the net (Net2WiderNet function-preserving embed of BC-v2),
NOT to pivot algorithm. run2 is that wider net, trained from the same BC-v2
start. The KL anchor re-attaches to the **same frozen 27.8k BC-v2** reference.

The wide net (`--wide`): trunk 170→320→160→48 (3 layers), MAIN head 89→160→1,
frozen card head 121→48→1 unchanged = **134,274 params**. At init it computes
the BC-v2 function bit-for-bit (KL=0), so training starts from the known policy.

## Morning checklist — run these in order, STOP on any failure

All three are laptop-verified GREEN (2026-07-13); re-run on the lab box to
confirm the transferred code before committing the overnight slot.

**M1. Function-preservation (the KL=0 proof — new gate for the wide net):**
```bash
python -m stage4.rl_ours.ppo.widen_check --games 80 --min-decisions 1000; echo "EXIT=$?"
```
Expect: `A ... 0 argmax flips`, `B ... 0 argmax flips`, `C ... EQUAL`,
`KL(pi_wide || pi_BC) = 0 at init : YES`, `VERDICT : PASS`, `EXIT=0`.
Laptop read: A/B max|Δlogit| ≈ 3e-6 (float noise), card head byte-identical.
**STOP** on any argmax flip or `NOT EQUAL` — the embed is wrong, do not train.

**M2. Leakage audit (unchanged encoder; must still be 6/6):**
```bash
python -m stage4.rl_ours.ppo.leakage_audit; echo "EXIT=$?"
```
Expect `SCORE : 6/6`, `VERDICT : PASS`, `EXIT=0`. Widening touches no leakage
surface, but re-confirm — don't assume.

**M3. Throughput smoke (wide net, real games/hour on THIS box):**
```bash
python -m stage4.rl_ours.ppo.train --wide --iters 3 --games-per-iter 240 \
  --workers 10 --ckpt-every 999 \
  --out stage4/rl_ours/runs/smoke_wide \
  --log stage4/rl_ours/runs/smoke_wide/history.json
python - <<'PY'
import json; h=json.load(open("stage4/rl_ours/runs/smoke_wide/history.json"))
g=sum(x["n_games"] for x in h); s=h[-1]["elapsed_s"]
print("wide throughput: %.0f games/h" % (g/s*3600))
PY
```
Expect **~15,000 games/h** (laptop measured a 1.27× slowdown vs narrow →
19k narrow becomes ~15k wide). Floor is **1500** — clears it ~10×.
**STOP** only if sustained < 1500 games/h.

## Launch the overnight wide run (run2)

Kill criteria armed exactly as run1, with **K1 threshold unchanged at 29%** and
**K2 game-counts reset to fresh from 0** (this net starts at game 0; do NOT
carry over run1's 83.5k). At ~15k games/h, `--iters 840` ≈ **201,600 games ≈
13.5 h** — an overnight slot that clears the **K2@150k** checkpoint (iter 625,
~10 h in) with margin. Size `--iters` to your slot: 625 = 150k (~10h, min to
evaluate K2@150k), 840 = 200k (~13.5h), 1250 = 300k (~20h, K2@300k).

```bash
mkdir -p stage4/rl_ours/runs
nohup python -m stage4.rl_ours.ppo.train \
  --wide --iters 840 --games-per-iter 240 --workers 10 --ckpt-every 15 \
  --out stage4/rl_ours/runs/run2 \
  --log stage4/rl_ours/runs/run2/history.json \
  > stage4/rl_ours/runs/run2.stdout 2>&1 &
echo "launched PID $!"
```
`--wide` is the only line that differs from run1's launch. Checkpoints land as
`runs/run2/policy_iter###.npz` every 15 iters (bring these + `history.json`
back — do NOT upload to Kaggle).

## Monitor run2 (same analyzer, thresholds unchanged)
```bash
python -m stage4.rl_ours.ppo.analyze_run --log stage4/rl_ours/runs/run2/history.json
```
Healthy: `games/h` ≥ 1500 (expect ~15k), `KL-to-BC anchor` < 0.15,
`VALIDATION VERDICT : PASS`. **The run2-specific question** is whether
`winrate_incumbent` (the K1/K2 proxy block) now **climbs above run1's flat 27%**
— that is the capacity hypothesis under test. Gate calls (fresh game count):

| Kill | run2 trigger | Action |
|------|--------------|--------|
| **K1 collapse** | 200-game gate vs v2.2.0 < 29% twice running | halt, revert, tell me |
| **K2 plateau** | no gate ≥ 44% by **150k games** (iter 625) / ≥ 48% by **300k** | grow 128k→**256k** next; algorithm pivot only after both widths plateau |
| **K2_diagnostic** | reward at p90-achievable but gate < 44% | still capacity-limited → next width |
| **KL runaway** | anchor KL past ~0.15 and rising | STOP, one KL-halving retry (K3) |

If `winrate_incumbent` is climbing (even slowly) at the 150k checkpoint, the
capacity hypothesis is **confirmed** — let it run to 300k / bring it back for a
formal gate. If it is flat at ~27% again by 150k, 128k was not enough width →
the pre-registered next step is **256k**, still not an algorithm pivot.

---

# ADDENDUM — run3: capacity growth 128k → 256k (only if run2 plateaus)

**Trigger:** run2 (128k) shows the same flat plateau run1 did — i.e.
`verdict.py` on run2's history reads **CAPACITY-LIMITED, HIGH-CONFIDENCE** (flat
winrate + plateaued critic + asymptoted KL over ≥15k converged games), OR the
**K2@150k** gate misses ≥44%. This is the next rung on the pre-registered ladder,
**still PPO — no algorithm change.** Do NOT run this if run2's winrate is climbing.

**What run3 is:** grow the **best** run2 128k checkpoint (not necessarily the
last iter — pick by winrate_incumbent) into a **256k** net, function-preservingly
(KL(π_256‖π_128)=0 at init), then keep training from there. Arch: trunk
170→**512**→**256**→48, MAIN head 89→**256**→1, frozen card head 121→48→1 =
**260,418 params**. The KL anchor stays the **same frozen 27.8k BC-v2** (it is the
fixed prior for the whole ladder, not the 128k net). Throughput at 256k is
**essentially unchanged from 128k** (measured 128k→256k slowdown ≈ 1.0×; the game
sim dominates, not the net) → still **~14.5k games/h** projected, ~9.6× the floor,
**same overnight sizing as run2**.

**No new code or checkpoint transfer needed** — the trainer grows the 256k net
*in place* from the 128k checkpoint already on this box, via `--grow-src`. This is
the whole point of the general grower (`net.grow_policy_weights`): tomorrow-evening
turnaround is ~5 minutes.

## Morning-of-run3 checklist (pick best ckpt → verify grow → launch)

**R1. Pick the best 128k checkpoint from run2:**
```bash
python - <<'PY'
import json,glob,os
h=json.load(open("stage4/rl_ours/runs/run2/history.json"))
best=max((x for x in h if x.get("n_incumbent")), key=lambda x:x.get("winrate_incumbent",0))
print("best iter by winrate_incumbent:", best["iter"], "wr", best.get("winrate_incumbent"))
print("available ckpts:", sorted(os.path.basename(p) for p in glob.glob("stage4/rl_ours/runs/run2/policy_iter*.npz")))
PY
```
Choose the `policy_iter###.npz` at (or nearest below) that best iter → call it `$CKPT`.

**R2. Verify the 128k→256k grow is function-preserving (KL=0) on the REAL checkpoint:**
```bash
python -m stage4.rl_ours.ppo.widen_check \
  --src stage4/rl_ours/runs/run2/policy_iter###.npz \
  --trunk-hidden 512,256 --main-hidden 256 --games 80 --min-decisions 1000; echo "EXIT=$?"
```
Expect `target net params: 260418`, `A/B 0 argmax flips`, `C EQUAL`,
`KL(pi_wide||pi_BC)=0 : YES`, `VERDICT : PASS`, `EXIT=0`. **STOP** on any flip
or `NOT EQUAL`. (This same grow was pre-verified on the laptop as a 27.8k→256k
stand-in and a 128k-format→256k same-depth test: 0 flips, max|Δ|~2e-6.)

**R3. Leakage audit (unchanged encoder):** `python -m stage4.rl_ours.ppo.leakage_audit; echo "EXIT=$?"` → `6/6 PASS`, `EXIT=0`.

## Launch run3 (256k, grown from the 128k checkpoint)
```bash
mkdir -p stage4/rl_ours/runs
nohup python -m stage4.rl_ours.ppo.train \
  --wide --trunk-hidden 512,256 --main-hidden 256 \
  --grow-src stage4/rl_ours/runs/run2/policy_iter###.npz \
  --iters 840 --games-per-iter 240 --workers 10 --ckpt-every 15 \
  --out stage4/rl_ours/runs/run3 --log stage4/rl_ours/runs/run3/history.json \
  > stage4/rl_ours/runs/run3.stdout 2>&1 &
echo "launched PID $!"
```
`--grow-src` is the only structural change vs run2's launch (plus the wider
`--trunk-hidden/--main-hidden`). `--iters 840` ≈ 200k games ≈ ~13.8h. The trunk
grows in-process at startup; the KL anchor is still the narrow 27.8k BC-v2.

## Monitor run3 — use the auto-verdict, no manual pooling
```bash
python -m stage4.rl_ours.ppo.verdict --log stage4/rl_ours/runs/run3/history.json
```
`verdict.py` auto-detects the converged window and prints the one-line call.
Kill criteria (fresh game count from 0), unchanged thresholds:

| Kill | run3 trigger | Action |
|------|--------------|--------|
| **K1 collapse** | 200-game gate vs v2.2.0 < 29% twice running | halt, revert, tell me |
| **K2 plateau** | verdict = CAPACITY-LIMITED HIGH-CONFIDENCE, or no gate ≥ 44% by 150k / ≥ 48% by 300k | **both widths now plateaued** → this is the Gumbel-AZ trigger; see `gumbel_az_scoping.md`, escalate to me |
| **KL runaway** | anchor KL past ~0.15 and rising | STOP, one KL-halving retry (K3) |

**If 256k also plateaus** (verdict HIGH-CONFIDENCE capacity-limited on ≥15k
converged games), that is the pre-registered end of the widen ladder — the next
branch is the **Gumbel-AZ pivot** (scoped in `stage4/rl_ours/gumbel_az_scoping.md`).
Do not start it without a decision from me + advisor.
