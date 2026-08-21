# T3 — Fezandipiti-conditional Shadow Bullet tie-break

**Nothing submitted.** Written before any arm below is run.

## What this is

MATCHUP_MINING.md's priority 3: against Fezandipiti/Dudunsparce, top-10
pilots still snipe the lowest-HP-ratio bench target most often (78.7%, vs
82.4% pooled) but break near-ties toward energy count / prize value
noticeably more than pooled (max-energy 66.6% vs 56.2%, max-prize 65.2% vs
59.9%). T2 (shipped) already implements the dominant ratio term. T3 adds a
small additive tie-break (`+2·energy +3·prizes_for_ko`) on top, gated to fire
**only** when the live opponent-archetype detector (`_opp_archetype`,
`main.py`) reads "fezandipiti" — never on any other matchup.

**Detection is new infrastructure**, not previously built: `_opp_archetype`
scans the opponent's active/bench/discard (all public zones) for marquee
card ids (Dudunsparce=66, Alakazam=743 for Fezandipiti; Mega Kangaskhan
ex=756, Raging Bolt ex=63 for Kangaskhan; TR Mewtwo ex=431 for Mewtwo) —
verified against each deck's actual card list so the signature cards are
unique to their archetype and don't collide with the 1x Fezandipiti-ex tech
copy that Kangaskhan's own list also runs.

**Unit-tested before any self-play**: archetype detection correct on
synthetic states (fezandipiti / kangaskhan / unknown), T3 tie-break verified
to only change a tied-ratio decision when TARGET_T3_FEZ_TIEBREAK is on AND
the opponent reads fezandipiti — confirmed OFF in both other conditions.

## Arms — `crossdeck_test.py`, our side = Grimmsnarl vs opponent = v1-alone
## on the named deck, 100 games each, seats alternated

| arm | our-rules | opponent |
|---|---|---|
| **comparator** (already measured) | full (E1+E2+T1+T2) | fezandipiti — 0.4694 (CROSSDECK_MATCHUP.md) |
| **T3 arm** | full_t3 (+ TARGET_T3_FEZ_TIEBREAK) | fezandipiti |
| **regression check** | full_t3 | kangaskhan, mewtwo, grimmsnarl_mirror — confirms zero behavioural change off-target |

## PRE-REGISTERED BANDS — fixed before running

**Primary: T3-arm prize velocity on Fezandipiti vs the established 0.4694.**

| band | condition | reading |
|---|---|---|
| **PASS** | ≥ 0.50 | tie-break adds real value on the one matchup it targets |
| **MARGINAL** | 0.4694 ≤ x < 0.50 | inconclusive at n=100; extend before deciding |
| **FAIL** | < 0.4694 | does not help; do not ship |

**Regression guard (disqualifying on its own, regardless of the primary
read):** on kangaskhan/mewtwo/mirror, T3's own fire count must be **0** —
confirming the gate genuinely never fires outside its target matchup — and
velocity must match the already-measured full-build numbers within noise
(±0.03, the established run-to-run band). `t3_fired` per-game telemetry
reported for the Fezandipiti arm too, to confirm the mechanism actually
engages (expected: nonzero, but well below `t2_fired`, since T3 only matters
on near-tied decisions).

**Bands are not revised after seeing results.** Ambiguous → extend sample,
not redraw the line, same rule as every prior test this session.

---

## RESULTS

100 games each, `crossdeck_test.py` + `crossdeck_analyze.py`.

| matchup | velocity | own turns | atk-when-legal | prizes/g | `t3_fired` |
|---|---|---|---|---|---|
| **Fezandipiti + T3** (primary) | **0.4259** | 6.88 | 86.2% | 2.93 | **48,197** |
| *(comparator, no T3, CROSSDECK_MATCHUP.md)* | *0.4694* | *6.71* | *86.3%* | *3.15* | *0* |
| Kangaskhan + T3 (regression) | 0.4138 | 7.95 | 88.2% | 3.29 | **0** |
| Mewtwo + T3 (regression) | 0.5788 | 7.17 | 83.3% | 4.15 | **0** |
| Grimmsnarl mirror + T3 (regression) | 0.4665 | 7.31 | 90.0% | 3.41 | **0** |

**Regression guard: PASS.** `t3_fired = 0` on all three off-target matchups —
the archetype gate genuinely never fires outside Fezandipiti. Kangaskhan/
Mewtwo/mirror velocities land within the established run-to-run noise band
of their T3-free comparators.

**Primary: FAIL, decisively.** 0.4259 sits **below the FAIL threshold**
(0.4694), not marginal — a real regression, not noise.

## Root cause — an implementation bug, not a falsification of the mined signal

`t3_fired` (48,197) is **69.7% of `t2_fired`** (69,153) on this matchup — T3
is firing on **most** Shadow Bullet decisions, not the rare near-tie the
mined data implies (top-10 still snipes lowest-ratio 78.7% of the time, so
true ties/near-ties should be the minority case).

The bug: `_score_card` scores **one candidate option at a time** and has no
visibility into sibling candidates' scores, so the T3 term I added
(`+2·energy +3·prizes_for_ko`) is an **unconditional additive bonus**
whenever the opponent reads Fezandipiti — not a tie-break gated on actual
proximity to the top ratio score. It is structurally incapable of being a
"break only real ties" rule as designed, because the scoring architecture
doesn't expose the cross-candidate comparison needed to detect a tie in the
first place. It systematically drags target selection away from the
dominant, already-validated ratio heuristic on a large fraction of
decisions, which is exactly why velocity dropped.

**This is not evidence against the underlying mined pattern** (top-10 really
does lean secondary-criteria-ward against Fezandipiti) — it is evidence that
implementing a true tie-break would require restructuring `_score_card` to
see sibling candidates (a materially bigger change than scoped here), for a
signal MATCHUP_MINING.md already rated "moderate confidence, real but
smaller deltas" before this test. That effort-for-payoff ratio does not
clear the bar given everything else already tried tonight.

## VERDICT: does not ship. Do not pursue a second iteration.

`TARGET_T3_FEZ_TIEBREAK` stays in `main.py`, default off, matching the
project's standing pattern for built-but-rejected flags (END_VETO,
A-INCLUDE/A-WEIGHT). No further work on this lever.

