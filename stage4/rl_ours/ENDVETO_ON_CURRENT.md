# END-veto (narrow) on the current build — never tested in this combination

**Nothing submitted.** Written before any arm below is run.

## Why this exists

END_VETO="narrow" (never END with bench<benchMax while holding a playable
Buddy-Buddy-Poffin-class Basic-searcher) was built and measured in
END_VETO.md, but only ever on **SEARCH=True, cap=0, Garchomp** — a stack
that has since been fully retired (DECK_SWITCH.md: deck moved to Grimmsnarl;
D1 vs D3: search does not help Grimmsnarl, so the shipped build is
v1-alone). It was also submitted once to real ladder on that retired stack
(μ509.2 at n=26, VN_HEALTH_CHECK.md) and never confirmed to convert —
`horizon_test.py`'s own comment records "did not convert on ladder." That
result is about the old stack; it says nothing about the current one.

The mechanism itself (a MAIN-return veto operating on `result`/`scores`,
`main.py:2683`) does not depend on SEARCH being on — it fires identically
against v1's own ranking. Confirmed: Grimmsnarl's decklist carries 4x
Buddy-Buddy Poffin (the exact card the narrow veto targets), so it is live
on this deck. This has never been tested against the shipped E1+E2+T1+T2
build, or against bare v1-alone with SEARCH=False.

## Arms — self-play mirror, Grimmsnarl, 300 games each (`--deck metaG_grimmsnarl_top10.csv`)

| arm | config |
|---|---|
| **T1T2** (comparator, already measured 300g = 0.4953) | E1+E2+T1+T2, no veto |
| **T1T2_EV** | E1+E2+T1+T2 + END_VETO=narrow |
| **C0_EV** | v1-alone + END_VETO=narrow (isolates the veto's own effect, no rules) |

## PRE-REGISTERED BANDS — fixed before running

**Primary: T1T2_EV prize velocity vs T1T2's established 0.4953 (300g).**

| band | condition | reading |
|---|---|---|
| **PASS** | T1T2_EV ≥ 0.52 | veto adds real value on top of the shipped build |
| **MARGINAL** | 0.4953 ≤ T1T2_EV < 0.52 | inconclusive at this n; extend before deciding, same rule as every prior ambiguous read this session |
| **FAIL** | T1T2_EV < 0.4953 | veto does not help here either; do not ship |

**Guard, not a verdict input:** own-turns must not increase and
attack-when-legal must not drop >3pts vs T1T2 — same standing guards used
all session. `end_veto` fire count (via `_seq`/`STATS`) reported to confirm
it actually engages on this deck (expected: low — Grimmsnarl's own hand/board
plan may rarely produce the specific bench<max + Poffin-in-hand state that
E1/E2's sequencing already avoids by other means).

**Bands are not revised after results.** If ambiguous, extend the sample
before redrawing any line — the established response all session.

**What a near-zero `end_veto` fire count would mean:** not a bug — it would
mean E1/E2's existing sequencing already prevents most of the states this
veto targets, so the veto is a no-op safety net rather than an active fix on
this build. That is a valid, reportable outcome, not grounds to force a
different measurement.

---

## RESULTS

300 games each, `prize_velocity.py` bootstrap comparison.

| comparison | baseline | arm | delta | 95% CI | own-turns guard | verdict |
|---|---|---|---|---|---|---|
| C0 vs C0_EV (veto alone, no other rules) | 0.4762 | 0.4730 | −0.0033 | [−0.0350, +0.0294] | OK (7.09 vs 7.36) | no effect |
| **T1T2 vs T1T2_EV** (veto on shipped build) | 0.4953 | 0.5005 | +0.0051 | [−0.0185, +0.0288] | **BROKEN** (own turns 7.27 vs 6.98) | **FAIL** — CI spans zero, guard broken |

**`end_veto` fire count: 0 / 300 games in *both* arms.** Not "rare" — the
veto never engaged once across 600 total games.

### Why zero, definitively (not a measurement gap)

`_end_veto` only replaces a chosen result that is **already END**
(`main.py:2683`). Under `SEARCH=False` (v1-alone, the current build's
config), the chosen result is always v1's own top-scored option, and v1
scores END at −1,000,000 versus ~2400 for a PLAY of Buddy-Buddy Poffin —
**v1 itself always plays the Poffin before it would ever choose END.** The
veto's entire reason to exist, per BEHAVIORAL_GAP_DIAGNOSIS.md, was to catch
*search* overriding v1 to pass; with no search in this build, that failure
mode cannot occur, so the veto is provably dead code here, not merely
untriggered by chance. The two measured deltas above are pure inter-run RNG
noise (consistent with the ~0.02–0.03 run-to-run band already characterised
this session), not any effect of the mechanism.

## VERDICT: does not ship

END_VETO="narrow" adds no value on the current build and its own guard
(own-turns) tripped in the one comparison with a directionally positive
delta — that delta is unattributable noise given 0 fires. This closes the
lever definitively: it is not "unproven," it is architecturally inert under
v1-alone. No further testing of this flag is warranted on this build.
