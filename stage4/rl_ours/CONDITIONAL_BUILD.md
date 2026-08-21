# PHASE 3 — build complete; C0/C1 screened (engine restored)

**Nothing submitted.** v1-alone; governor, `cap=16`, `END_VETO`, `EVAL_FIX`,
`PROMOTE_RULE`, `LETHAL_PROBE`, the candidate-set arms and R1/R2/R3 all stay
off. All four gates default **off** and live in the always-active path — never
inside `_pilot_score_main`.

> **Screen calibration.** Self-play overstates ladder by ~**2×** (0.4574 vs
> 0.2370, n=19). A passing screen means "worth a ladder slot", not "this works."

---

# (RESOLVED) BLOCKER — engine was unavailable; see the addendum for the re-check

The self-play screen cannot run. `kaggle_environments` fails to register the
competition environment:

```
Loading environment cabt failed: [WinError 4551]
An Application Control policy has blocked this file
```

`make("cabt")` therefore raises `InvalidArgument: Unknown Environment
Specification`, and **no game can be played locally.**

| | |
|---|---|
| blocked artifact | `…/site-packages/kaggle_environments/envs/cabt/cg/cg.dll` |
| package present? | **yes** — `cabt.py`, `cabt.json`, `cg/` all on disk, unmodified since Jul 7 |
| registered envs | 29 OpenSpiel envs + connectx/halite/etc. — **`cabt` absent** |
| cause | **Windows Application Control (WDAC / Smart App Control) blocking the native `cg.dll`** |

**This is a machine-level security policy, and it changed during this session** —
the D0–D3 arms and the SW_* deck sweep ran on this same engine a few hours ago.
Nothing in the Phase 3 code touches it; the failure reproduces on a bare
`from kaggle_environments import make; make("cabt")` with `main.py` never
imported.

**I have not attempted to bypass it.** Disabling or working around an
Application Control policy is a security decision that is yours, not mine.

### To unblock

The policy needs to allow `cg.dll` under the Python site-packages path — via
Windows Security → App & browser control → Smart App Control, or the relevant
WDAC policy. A reinstall of `kaggle-environments==1.30.1` will not help on its
own; the file is present and being blocked at load.

Once `make("cabt")` succeeds, the screen is a single command per arm and the
harness is already wired.

---

# 1. BUILD — complete and verified

Four gates, each independently flagged, all defaulting off.

| flag | env var | rule |
|---|---|---|
| `SEQ_E1` | `PTCG_SEQ_E1` | do not attack while a board-advancing play (`PLAY`/`ATTACH`/`EVOLVE`) remains |
| `SEQ_E2` | `PTCG_SEQ_E2` | do not attack while an `ABILITY` is available |
| `SEQ_E3` | `PTCG_SEQ_E3` | do not retreat while our active is not KO-able |
| `SEQ_E4` | `PTCG_SEQ_E4` | when BEHIND on prizes, disable E1 (push damage) |
| `SEQ_E1B_LETHAL` | `PTCG_SEQ_E1B` | attack at once when the KO takes our last prize — **off, evidence against** |
| `SEQ_E1C_DOOMED` | `PTCG_SEQ_E1C` | attack at once when our active is doomed — **off** |

**Implemented as an option-set override, not a reweight.** `_seq_gate()` runs
after `_decide()` and before `_validate_result()`, exactly where `_end_veto`
sits. It replaces the *chosen index*; **no v1 constant is touched**, which is
the specific way A-WEIGHT went wrong.

Guards: `E1_MAX_VETO = 12` vetoes per own turn (top-10 p90 is 9, max 15), and
the gate only fires when a non-attack option demonstrably exists.

## Default-off verification

```
SEQ_E1/E2/E3/E4/E1B/E1C = False   E1_MAX_VETO = 12   DEVELOP_TYPES = (7, 8, 9)
```

## Logic verification — 10/10 correct

The engine is unavailable, but the gate is pure state→decision logic and was
tested directly against synthetic observations:

| # | scenario | result | expected |
|---|---|---|---|
| 1 | E1 off, attack chosen | `[0]` unchanged | ✅ |
| 2 | E1 on, PLAY available | `[1]` deferred | ✅ |
| 3 | E1 on, no free play | `[0]` attacks | ✅ |
| 4 | E2 on, ABILITY available | `[1]` deferred | ✅ |
| 5 | E1 + E1b, game-winning KO | `[0]` attacks | ✅ |
| 6 | E1 + E4, BEHIND | `[0]` attacks | ✅ |
| 7 | E1 + E4, AHEAD | `[1]` deferred | ✅ |
| 8 | E3 on, active safe, retreat chosen | `[1]` retreat vetoed | ✅ |
| 9 | E3 on, active doomed, retreat chosen | `[0]` retreat allowed | ✅ |
| 10 | veto budget exhausted at 12 | `[0]` ceiling honoured | ✅ |

**This is not a substitute for the screen.** It shows the rules do what they say
in the states tested; it says nothing about whether they help.

## Arms wired and ready

`C0` → `C1(E1)` → `C2(+E2)` → `C3(+E3)` → `C4(+E4)` are defined in
`horizon_test.py`, `PILOT=""`, Grimmsnarl deck. Each saved game now carries a
`_seq` block with `e1_veto`, `e2_veto`, `e3_veto`, `turns` and `ceiling_turns`
so Amendment 1 can be evaluated.

---

# 2. SCREEN RULE — fixed, with both amendments folded in

An increment is **KEPT** only if **all** hold:

1. prize velocity improves by **≥ +0.02** with a bootstrap 95% CI excluding zero
2. own turns/game **does not increase**
3. **(Amendment 2)** attack-when-legal per **TURN** is **not more than 3 points
   below C0** (C0 ≈ 88.5%) — **binding, regardless of prize velocity**

Otherwise **DROPPED**, and the next increment is screened on the last kept arm.
Every increment is reported either way.

## Amendment 1 — mechanism gate, evaluated BEFORE the verdict

For each arm, check first and report:

- **vetoes per own turn** for that rule — must be non-zero and **not pinned at
  the `E1_MAX_VETO = 12` ceiling**
- **actions-before-attack per attacking turn** — baseline **2.97**, top-10 **5.87**

| observation | verdict |
|---|---|
| vetoes ≈ 0 | **INCONCLUSIVE, not FAIL** — the rule did not fire; diagnose before the next increment |
| vetoes pinned at 12 on a large share of turns | **the free-option set is not exhausting** — E1 is deferring attacks rather than sequencing them; say so plainly |

A rule that did not fire has not been tested.

**Amendment 2 exists because we have been burned by this shape twice** —
`cap=16` and B1 both raised a headline counter while attacking less per turn.
It is now a hard drop condition, not an observation.

---

# 3. STATUS

| item | state |
|---|---|
| E1–E4 implemented, flagged, default off | ✅ **done** |
| always-active path, not `_pilot_score_main` | ✅ **verified** |
| option-set override, no v1 constant changed | ✅ **verified** |
| gate logic correctness | ✅ **10/10 synthetic tests** |
| mechanism telemetry wired | ✅ **done** |
| arms C0–C4 defined | ✅ **done** |
| screen rule + both amendments fixed in writing | ✅ **done** |
| **100-game screen per arm** | ⛔ **BLOCKED — engine unavailable** |

**Nothing is inferred about whether these rules work.** No arm has run, so no
prize-velocity number exists and none is estimated here.

### What happens when the engine is restored

```bash
for a in C0 C1 C2 C3 C4; do py -3.12 -X utf8 stage4/rl_ours/horizon_test.py --arm $a --games 100 --deck metaG_grimmsnarl_top10.csv; done
```

Then the mechanism gate, then the screen rule, in that order.

### Artifacts

| path | contents |
|---|---|
| [main.py](../../main.py) | `_seq_gate()` + six flags, all default off |
| `stage4/rl_ours/horizon_test.py` | arms C0–C4 + `_seq` telemetry |
| `stage4/rl_ours/lethal_split.py` | Phase 2 §0 measurement |

**STOP — Phase 3 gate. Build is complete and verified; the screen needs the
engine unblocked before it can run.**

---

# ENGINE RESTORED — C0 and C1 measured

## 0. Engine verification

| step | result |
|---|---|
| bare `from kaggle_environments import make; make("cabt")`, `main.py` **not** imported | ✅ **LOADS OK** (`'main' in sys.modules` = False) |
| WinError 4551 | **gone** |

The Application Control policy change took effect. Proceeding.

## 1. MECHANISM GATE (Amendment 1) — evaluated BEFORE the verdict. **PASS.**

| check | C0 | **C1** | top-10 |
|---|---|---|---|
| `e1_veto` (run total) | 0 | **988** | — |
| own turns | 1466 | 1414 | 3025 |
| vetoes per own turn | — | **0.70** | — |
| **`ceiling_turns`** (turns pinned at `E1_MAX_VETO=12`) | 0 | **0** | — |
| **actions before the attack** (mean) | **2.96** | **4.18** | **5.87** |
| median | 2 | 4 | 6 |
| **attacked as the FIRST action of the turn** | **42.4%** | **1.9%** | **2.0%** |

**The rule fired, and it did exactly what it was designed to do.**

- Vetoes are non-zero (988) and **never pinned at the ceiling** (0 turns of
  1414). E1 is *sequencing* attacks, not deferring them into oblivion — the
  specific failure mode flagged in Phase 2.
- **Attack-first collapsed from 42.4% to 1.9%, against top-10's 2.0%.** On the
  Phase 1 headline counter, C1 is indistinguishable from the top-10 field.
- Actions-before-attack moved 2.96 → 4.18, closing **42%** of the gap to 5.87.
  It does not close fully because E1 covers card plays only; abilities are E2's
  job and E2 is off in this arm (`e2_veto` = 0, as configured).

## 2. SCREEN METRICS — 100 games / 200 sides per arm

| counter | **C0** baseline | **C1** (E1) | change |
|---|---|---|---|
| **PRIZE VELOCITY** | **0.4762** | **0.5035** | **+0.0273** |
| bootstrap 95% CI on the difference | — | — | **[−0.0118, +0.0667]** |
| own turns / game | 7.36 | **7.08** | −0.28 ✅ |
| prizes / game | 3.50 | **3.56** | +0.06 |
| **attack-when-legal / turn** | 88.9% | **91.3%** | **+2.4** ✅ |
| attack share / turn | 48.0% | 45.7% | −2.3 |
| turn of first prize | 8.6 | 8.8 | +0.2 |
| first attack turn | 6.08 | 6.39 | +0.31 |
| first evolution turn | 4.77 | **4.62** | −0.15 |
| extra draws / turn | 1.64 | **2.04** | **+0.40** |
| turns using an ability | 59.5% | 64.7% | +5.2 |
| wall-clock / side p50 / p99 / max | 0.004 / 0.012 / 0.099 s | 0.004 / 0.007 / **0.007 s** | — |

## 3. SCREEN RULE APPLIED

| # | condition | result |
|---|---|---|
| 1 | prize velocity **≥ +0.02** | ✅ **+0.0273** |
| 2 | **bootstrap 95% CI excludes zero** | ❌ **[−0.0118, +0.0667] SPANS ZERO** |
| 3 | own turns/game not increased | ✅ 7.08 < 7.36 |
| 4 | *(Amendment 2)* attack-when-legal not down > 3 pts | ✅ **UP 2.4** |

### **VERDICT: C1 is DROPPED — condition 2 fails.**

Three of four conditions pass, the mechanism worked as designed, and the point
estimate clears the threshold. **The confidence interval includes zero, and the
pre-registered rule requires it to exclude zero.** The rule was fixed in writing
before the run and is not being revised now.

## 4. Why the CI is the right call here — a power calibration

**C0 and D1 are the same configuration** — v1-alone, `PILOT=""`, Grimmsnarl,
no rules — run with different seeds:

| run | prize velocity |
|---|---|
| D1 (DECK_SWITCH.md) | 0.4574 |
| **C0 (this run)** | **0.4762** |
| **same-config run-to-run difference** | **0.0188** |

**The C1 effect (+0.0273) is only 1.45× the difference between two runs of an
identical configuration.** At 200 sides this screen cannot resolve an effect of
this size, which is exactly what the CI is reporting.

That is a statement about **statistical power, not about E1**. It does not mean
E1 does nothing; it means 100 games cannot tell. Two honest options exist and
both are yours to choose:

- **Re-run C0/C1 at 300–400 games** to narrow the CI, and re-apply the same
  unchanged rule; or
- **Accept the DROP and move to C2**, treating E1 as unproven-but-harmless
  (it costs nothing on any guard and improves three secondary counters).

I am **not** picking between these, and I am **not** proceeding to C2 — the
brief says stop after C0/C1.

## 5. What C1 tells us about the framework question

You framed C1 as the arm that tests whether **the framework was the defect**.
The honest split:

- **The framework hypothesis is confirmed at the behavioural level.** A static
  tier ladder genuinely could not express "attack last"; a single ordering gate
  moved attack-first from 42.4% to 1.9% and matched the top-10 field on that
  counter. Nine prior interventions never moved a behavioural counter to field
  parity. This one did, on the first try.
- **It is not confirmed at the outcome level.** Prize velocity moved +0.0273 and
  the screen cannot distinguish that from noise at n=200.

So: **the diagnosis looks right and the fix does what it claims; the payoff is
unproven.** Those are different claims and I am keeping them apart.

One more restraint worth stating: even a clean pass here would have been a
screen, not a verdict. Self-play overstates ladder ~2× (0.4574 vs 0.2370), so a
+0.027 self-play gain projects to roughly **+0.014 on ladder** — well inside the
run-to-run noise of a 19-episode ladder sample. **Nothing about C1 justifies a
ladder slot on its own.**

## Artifacts

| path | contents |
|---|---|
| `scratchpad/s3/horizon_C0/`, `horizon_C1/` | 100 games each, with `_seq` telemetry |
| `scratchpad/s3/c0_c1.json` | velocity + bootstrap CI |
| `scratchpad/s3/prof_C0.json`, `prof_C1.json` | field-unit profiles |

**STOP — C0 and C1 reported. Not proceeding to C2 without your call.**


---

# C2 / C3 BATCH — header recorded BEFORE running

## Why E1 is retained despite being DROPPED

**C1's DROP verdict stands and is not revised.** E1 is recorded as **DROPPED**,
not promoted, and nothing below claims otherwise.

E1 remains **enabled in C2/C3 as a screen baseline, not as a shipped
component**, for two stated reasons:

1. **The drop was a power failure, not a negative result.** Same-config
   run-to-run noise is **0.0188** (D1 0.4574 vs C0 0.4762); the C1 effect
   (+0.0273) is 1.45x that. The CI cannot resolve it at n=200 and would not at
   n=400 either.
2. **E2 is designed to compose with E1** — E1 covers card plays, E2 covers
   abilities, disjoint by construction (CONDITIONAL_DESIGN.md §3). Testing E2
   without E1 would test a different rule than the one designed.

**Binding condition, fixed here before any arm runs:** if **E1+E2 does not clear
the threshold with a CI excluding zero, BOTH are dropped together** and no part
of E1 is claimed. **E1 does not get to ride along on E2's result.**

## Arms and rule

| arm | config |
|---|---|
| **C2** | E1 + E2 |
| **C3** | E1 + E2 + E3 **if C2 clears**; otherwise **C3B = E1 + E3**, so E3 is screened on a clean base |

Baseline for all comparisons is **C0 = 0.4762**, measured in this same session.
E1b, E1c stay OFF. E4 is not scheduled — Phase 2 ranked it weakest and expects
null; it is only worth running if C2 or C3 passes.

**Screen rule unchanged, all four conditions evaluated explicitly:**
(1) velocity >= +0.02 vs C0 · (2) bootstrap 95% CI excludes zero ·
(3) own turns/game not increased · (4) attack-when-legal not > 3 pts below 88.9%.

**Mechanism gate (Amendment 1) is evaluated first, before any velocity read.**

## RESULTS — C2 and C3B

### Mechanism gate (Amendment 1) — evaluated first

| counter | C0 | C1 (E1) | **C2 (E1+E2)** | C3B (E1+E3) | top-10 |
|---|---|---|---|---|---|
| `e1_veto` (run total) | 0 | 988 | **1061** | 1040 | — |
| **`e2_veto`** | 0 | 0 | **364** | 0 | — |
| **`e3_veto`** | 0 | 0 | 0 | **0** ⚠️ | — |
| **`ceiling_turns`** | 0 | 0 | **0** | 0 | — |
| **turns using an ability** | 59.5% | 64.7% | **89.5%** | — | **80.2%** |
| **actions before attack** | 2.96 | 4.18 | **4.75** | — | **5.87** |
| attacked FIRST in turn | 42.4% | 1.9% | **0.1%** | — | 2.0% |

**C2's mechanism gate PASSES.** `e2_veto`=364, never pinned at the ceiling, and
E2's direct counter — turns using an ability — moved **59.5% → 89.5%**, past
top-10's 80.2%. Actions-before-attack advanced 4.18 → 4.75. E2 fired and did
what it was designed to do.

**C3B's mechanism gate FAILS: `e3_veto` = 0. E3 never fired.** Per Amendment 1
that is **INCONCLUSIVE, not FAIL** — diagnosed below.

### Screen rule — C2 (E1 + E2)

| # | condition | result |
|---|---|---|
| 1 | velocity ≥ +0.02 vs C0 | ❌ **+0.0035** |
| 2 | bootstrap 95% CI excludes zero | ❌ **[−0.0367, +0.0419]** |
| 3 | own turns/game not increased | ❌ **7.38 vs 7.36** |
| 4 | attack-when-legal not >3 pts below 88.9% | ✅ 88.8% (−0.1) |

**C2 = 0.4797 vs C0 = 0.4762. DROPPED on three of four conditions.**

### **Binding condition fires: E1 and E2 are BOTH dropped together**

The header condition, recorded before the run:

> if **E1+E2 does not clear the threshold with a CI excluding zero, BOTH are
> dropped together** and no part of E1 is claimed.

**E1+E2 did not clear. E1 and E2 are both dropped. Neither is claimed, and E1
does not ride along on E2's result.**

### Screen rule — C3B (E1 + E3)

| # | condition | result |
|---|---|---|
| 1 | velocity ≥ +0.02 vs C0 | ❌ **+0.0022** |
| 2 | CI excludes zero | ❌ **[−0.0369, +0.0410]** |
| 3 | own turns/game not increased | ❌ **7.42 vs 7.36** |
| 4 | attack-when-legal not >3 pts below | ✅ 90.0% (+1.1) |

**C3B = 0.4784. DROPPED — but the E3 component is INCONCLUSIVE, not tested,
because it never fired.** C3B is in effect an E1-only replicate.

---

## DIAGNOSIS — why E3 could never fire

E3 vetoes RETREAT when the active is not KO-able **and a better option exists**.
Over all 100 C3B games, on every decision where the agent chose RETREAT with a
safe active:

| | count | share |
|---|---|---|
| safe-active RETREAT decisions | **318** | 100% |
| **menu was `{RETREAT, END}` and nothing else** | **318** | **100.0%** |
| menu contained any real alternative (`PLAY`/`ATTACH`/`EVOLVE`/`ABILITY`/`ATTACK`) | **0** | **0.0%** |

The single most common menu, across all 318, is `[12, 14]` — retreat or pass.

**E3 is not buggy. It is correctly declining to fire, because there is never
anything else to do.** Verified by replaying real observations through
`_seq_gate`: the veto reaches its trigger, finds `alt is None`, and returns the
result unchanged, exactly as written.

### What this means for the Phase 1 evidence

**E3's design premise was wrong.** Phase 1 measured `safe_active` retreat at
**8.6% for us vs 1.6% for top-10** and I read that as "we waste tempo retreating
when we could develop." The correct reading is:

> **We do not retreat instead of developing. We retreat instead of passing.**

The divergence is real, but it reflects **how often we reach a depleted menu**,
not what we choose once there. Retreating beats ENDing the turn in those states,
so the behaviour v1 already exhibits is defensible.

**E3 should not be re-run as designed.** Any redesign would have to target the
upstream cause — arriving at `{RETREAT, END}` menus at all — which is a
different rule with no Phase 1 cell behind it yet.

*This is exactly what Amendment 1 exists for: without the veto counter, C3B's
DROP would have been recorded as "E3 does not help", which is false. E3 was
never tested.*

---

## An unplanned but useful measurement: run-to-run noise, again

C1 and C3B are **both effectively E1-only** (E3 inert in C3B), so they are two
runs of the same policy at different seeds:

| run | config | prize velocity |
|---|---|---|
| C1 | E1 | **0.5035** |
| C3B | E1 (+ inert E3) | **0.4784** |
| **difference** | — | **0.0251** |

| pair | same-config difference |
|---|---|
| D1 vs C0 (plain v1-alone) | 0.0188 |
| **C1 vs C3B (E1-only)** | **0.0251** |

**Same-config run-to-run noise at n=200 sides is 0.019–0.025.** Every effect
measured in this batch (+0.0035, +0.0022) and C1's earlier +0.0273 sit **at or
below that band**. The screen simply cannot resolve effects of this size at 100
games, and the CIs have said so consistently.

---

## STATUS AFTER THIS BATCH

| arm | config | velocity | vs C0 | CI | mechanism | verdict |
|---|---|---|---|---|---|---|
| **C0** | baseline | 0.4762 | — | — | n/a | baseline |
| **C1** | E1 | 0.5035 | +0.0273 | [−0.0118, +0.0667] | ✅ fired | **DROPPED** (CI) |
| **C2** | E1+E2 | 0.4797 | +0.0035 | [−0.0367, +0.0419] | ✅ fired | **DROPPED** (3 of 4) |
| **C3B** | E1+E3 | 0.4784 | +0.0022 | [−0.0369, +0.0410] | ❌ **E3 never fired** | **DROPPED**; E3 **INCONCLUSIVE** |

**E1, E2 and E3 are all dropped. Nothing from the conditional-policy project is
claimed or recommended for a ladder slot.**

E4 remains unscheduled: Phase 2 ranked it weakest and expected null, and it was
conditional on C2 or C3 passing. **Neither passed, so E4 is not run.**

## What was learned, stated separately from the verdicts

Three things are worth keeping even though every arm dropped:

1. **The behavioural diagnosis was correct and the fix works mechanically.**
   Attack-first went 42.4% → 0.1% and ability-turns 59.5% → 89.5%, both to or
   past field parity. No previous intervention moved a behavioural counter to
   the field's value.
2. **Field-parity behaviour did not produce field-parity results.** C2 matches
   top-10 on two headline counters and sits at 0.4797 against their 0.5725. The
   remaining gap is not in these two behaviours.
3. **E3's premise was falsified by its own telemetry** — the retreat divergence
   is about menu depletion, not choice.

**The honest summary: the framework hypothesis is confirmed at the behavioural
level and unproven at the outcome level, and this screen is not powerful enough
to settle it at 100 games per arm.**

### Artifacts

| path | contents |
|---|---|
| `scratchpad/s3/horizon_C2/`, `horizon_C3B/` | 100 games each with `_seq` telemetry |
| `scratchpad/s3/c0_c2.json`, `c0_c3b.json` | velocity + bootstrap CIs |

**STOP — C2 and C3B reported. E4 not run (its precondition did not hold).**
