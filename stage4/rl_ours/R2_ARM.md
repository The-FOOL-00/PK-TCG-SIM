# Pre-registered arm — R2 alone, prize velocity as primary

**Nothing submitted.** Governor untouched. `cap=16`, `END_VETO`, `EVAL_FIX`,
`PROMOTE_RULE`, `LETHAL_PROBE`, the candidate-set arms, **R1 and R3** all stay
off.

Why this file exists: B1b (R2 alone) was found by ablation *after* the bands in
PILOT_KNOWLEDGE.md were fixed, so it could not be promoted from that run. This
is a clean pre-registration for it.

---

## PRE-REGISTERED — written and committed before either arm was run

### Primary counter: **PRIZE VELOCITY = prizes taken per own turn**

Pooled across sides: `total prizes taken / total own turns` (equivalently
mean-prizes / mean-own-turns, which is how the reference figures below were
computed).

Reference values from PILOT_KNOWLEDGE.md §A1/§A3:

| source | prizes/game | own turns/game | **prize velocity** |
|---|---|---|---|
| top-10 jul21 | 3.32 | 6.4 | **0.52** |
| top-10 jul22 | 3.06 | 6.5 | **0.47** |
| B0 (60 g) | 2.66 | 10.3 | **0.258** |
| B1b (60 g, R2 only) | 2.98 | 10.5 | **0.284** |
| B1 (60 g, all three) | 3.10 | 11.8 | **0.263** |

This counter cannot be gamed by the attack-uptake/timing trade-off that tripped
B1, B2 and the `cap=16` arm: attacking more but taking longer scores *worse*,
which is the correct sign.

### Bands — vs a freshly measured `B0'` at `PILOT=""`

| band | condition |
|---|---|
| **PASS** | Δ prize velocity **≥ +0.030** **AND** own turns **not higher** than B0' **AND** first attack **inside 4.1–5.6** |
| **MARGINAL** | Δ **+0.015 to +0.030**, with **both** guards intact |
| **FAIL** | Δ **< +0.015**, **or** either guard broken |

Guards are evaluated on point estimates: mean own turns per side must be
**≤ B0'** mean, and the profiler's `first_attack` must land within **4.1–5.6**.

Primary reported with a **bootstrap 95% CI** on the difference (10,000
resamples over sides, resampled independently per arm).

### Secondary counters, all reported

attack-when-legal (per turn) · attack share (per turn) · first attack · first
evolution · own turns per game · turn of first prize · prizes per game · extra
draws per turn.

### Arms — 100 games each (200 sides)

| arm | config |
|---|---|
| **B0'** | v1 alone, `PILOT=""`, no rules — fresh baseline |
| **B1b'** | v1 alone, `PILOT=""`, **R2 only** |

Fresh output directories, so nothing is pooled with the 60-game runs.

**Bands are not revised after results.**

### Ship condition, also pre-registered

PASS **or** MARGINAL with both guards intact → build with `--card-rules r2`
only, run full ship verification plus the §A6 extraction gate, report sha256,
stop. FAIL → say so and build nothing.

---

## RESULTS

100 games per arm, **200 sides each**, `PILOT=""`, fresh directories. Arm
configs confirmed from the run logs:

```
arm B0p : SEARCH=False PILOT='' R1=False R2=False R3=False
arm B1bp: SEARCH=False PILOT='' R1=False R2=True  R3=False
```

### PRIMARY — prize velocity

| | own turns (total / mean) | prizes (total / mean) | **prize velocity** |
|---|---|---|---|
| **B0'** | 2021 / 10.11 | 524 / 2.62 | **0.2593** |
| **B1b'** | 2248 / 11.24 | 610 / 3.05 | **0.2714** |

**Δ = +0.0121, bootstrap 95% CI [−0.0230, +0.0470]** (10,000 resamples over
sides). **The interval spans zero.**

| band | threshold | result |
|---|---|---|
| PASS | ≥ +0.030 | no |
| MARGINAL | +0.015 to +0.030 | no |
| **FAIL** | **< +0.015** | ✅ **+0.0121** |

### GUARDS — both broken

| guard | requirement | measured | |
|---|---|---|---|
| own turns not higher than B0' | ≤ 10.11 | **11.24** | ❌ **BROKEN** |
| first attack inside 4.1–5.6 | 4.1–5.6 | **7.26** | ❌ **BROKEN** |

### Secondary counters

| metric | **B0'** | **B1b'** | field |
|---|---|---|---|
| attack-when-legal / turn | 55.1% | **60.5%** | 74.6% |
| attack share / turn | 0.34 | 0.36 | 0.47–0.64 |
| **first attack** | **4.85** ✅ *in band* | **7.26** ❌ | 4.1–5.6 |
| first evolution | 4.38 | **4.26** | 3.6–4.2 |
| **own turns / game** | **10.11** | 11.24 | ~6.5 |
| turn of first prize | **10.2** | 12.6 | ~7.2 |
| prizes / game | 2.62 | **3.05** | ~3.06 |
| extra draws / turn | 1.52 | **1.74** | 2.1–2.6 |
| hand T3 / T5 / T7 | 5.23 / 5.15 / 5.37 | 5.29 / 5.17 / 5.00 | — |

R2 does what it was designed to do — more attacks per turn (55.1% → 60.5%),
more prizes per game (2.62 → 3.05), earlier evolution, more draws. **It buys
all of it with extra turns**, and on the counter that prices that trade-off it
comes out flat.

---

## VERDICT — **FAIL. Nothing built.**

Three independent failures, any one of which is disqualifying under the
pre-registered rules:

1. **Primary below the MARGINAL floor** — +0.0121 vs +0.015 required.
2. **Not statistically distinguishable from baseline** — CI spans zero.
3. **Both guards broken** — own turns 11.24 > 10.11, first attack 7.26 outside
   4.1–5.6.

Per the pre-registered ship condition, **no bundle was built and no ship
verification was run.**

### The ablation result did not replicate — and that is the real finding

| | 60-game ablation (post-hoc) | **100-game pre-registered** |
|---|---|---|
| prize velocity Δ | **+0.026** | **+0.0121** |
| own turns vs baseline | 10.5 vs 10.3 (**+0.2**) | 11.24 vs 10.11 (**+1.13**) |
| first attack | 6.19 | **7.26** |

**The effect more than halved, and the own-turns cost grew five-fold, once the
arm was measured fresh under bands fixed in advance.** That is the textbook
signature of a post-hoc selected result regressing toward the mean.

B1b looked like the best arm in PILOT_KNOWLEDGE.md §A5 specifically because it
was chosen after seeing the numbers. Refusing to promote it there, and running
this pre-registration instead, is what caught it. **The discipline earned its
cost here.**

### One thing worth carrying forward

**B0' — plain v1-alone at ship config — has a first-attack turn of 4.85, inside
the field band (4.1–5.6), and the lowest own-turns of any arm measured (10.11).**
That is better than the 60-game reading (5.19) and better than every rules arm.
Eight interventions have now been measured against pre-registered bands and
none has beaten it.

Governor untouched. `cap=16`, `END_VETO`, `EVAL_FIX`, `PROMOTE_RULE`,
`LETHAL_PROBE`, the candidate-set arms, R1, R2 and R3 all remain **off** in the
repo. **Nothing submitted.**

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/prize_velocity.py` | primary counter + bootstrap CI |
| `scratchpad/s3/horizon_B0p/` | 100 games, baseline |
| `scratchpad/s3/horizon_B1bp/` | 100 games, R2 only |
| `scratchpad/s3/r2_arm.json` | raw primary/secondary values |
| `scratchpad/s3/prof_B{0p,1bp}.json` | field-unit profiles |
