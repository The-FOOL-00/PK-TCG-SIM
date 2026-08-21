# Gate 1 — graded leaf evaluator (depth-capped rollout)

Run 2026-07-25. Single variable: `SEARCH_CAP` (0 = shipped 400-step cap →
terminal 0/1 leaves; K = capped, leaves scored by the existing value net via
the graded path already present in `_rollout`).
**Governor untouched. Sampler untouched. `SEARCH_PRIOR` left as dead code
(`None`) — populating it is Gate 2 and is not part of this gate.**

Instrument: `stage4/rl_ours/pimc_diagnostic.py`, identical to the one that
produced [PIMC_DIAGNOSTIC.md](PIMC_DIAGNOSTIC.md), so every number is directly
comparable to those baselines (contested zero-discrimination **54.5%**,
contested signal-bearing agreement **0.667**).

---

## PRE-REGISTRATION (amended; fixed before any Gate 1 run)

### Metrics

Contested := (≥3 legal actions) AND (aggregated top-1 − top-2 margin < 0.10 of
the [0,1] eval range). Identical definition to PIMC_DIAGNOSTIC.md.

| # | metric | baseline | PASS | MARGINAL | FAIL |
|---|---|---|---|---|---|
| **P1** | contested zero-discrimination rate | 54.5% | ≤ 20% | 20–35% | > 35% |
| **P2** | contested signal-bearing agreement (median) | 0.667 | ≥ 0.55 | 0.45–0.55 | < 0.45 |

**PASS requires P1 and P2 together.**

### AMENDMENT 1 — held-out K selection

K is swept on a **development set** and evaluated on a **disjoint evaluation
set never touched during selection**. Selection criterion on dev is **P2 only**
(the coherence metric), so the knob is not tuned against P1, the metric it is
meant to move.

*Implementation note:* the engine RNG is not controllable (Sanjay §6k:
`random.seed()` does not reach the engine, verified), so dev/eval disjointness
is achieved by **separate runs**, not by partitioning one fixed corpus. The
eval games were generated after selection and were not used in it.
Dev = 20 games per K ∈ {16, 24, 40}. Eval = 80 fresh games at the selected K.

### AMENDMENT 2 — population-validity caveat

The jitter null control catches *"any real-valued leaf passes P1."* It does
**not** catch *"graded evaluation of strawman worlds."* Determinizations
currently sample from a ~1,267-card pool shaped only by a 3-bucket composition
prior (`SEARCH_PRIOR` is dead code) when real support is ~6 archetypes. A
graded evaluator will produce consistent, non-random discrimination **on
unrealistic opponents** and can pass P1+P2 while being uninformative about
ladder strength — the BC-v2 population-coverage failure (writeup ch. 2) one
level down.

Therefore, pre-registered: **a P1+P2 pass authorizes GATE 2 only**
(`SEARCH_PRIOR` population from the 07-22 archetype harvest, single variable,
same instrumentation). **It does NOT authorize a ladder canary. No canary
until Gate 2 reports.**

### AMENDMENT 3 — where the bands came from

Both are **judgment calls, stated as such and not revised after results**:

- **P1 ≤ 20%** — no principled threshold exists. Chosen as a ~63% relative
  reduction from the 54.5% baseline: large enough that the defect is
  substantially removed rather than nudged, loose enough not to demand
  perfection. Judgment.
- **P2 ≥ 0.55** — chosen as roughly midway between my design-doc estimate of
  the chance floor (~0.34, for ~3.8 candidates over 16 determinizations) and
  the 0.667 baseline, on the reasoning that buying discrimination in
  previously-flat worlds should cost *some* coherence but must stay clearly
  above chance. Judgment. **This band turned out to be mis-specified — see
  "Metric defect" below. It is reported and honored anyway.**

### Null control (pre-registered)

Control arm: `SEARCH_CAP=0` with uniform ±1e-3 jitter added to every leaf.
Expected: P1 → ~0% (spuriously "passing") while P2 collapses toward chance.
**If the jitter arm also holds P2 ≥ 0.55, the metric pair is invalid and the
gate is VOID — no verdict may be read.**

---

## VERIFICATION (done before the gate, not assumed)

**1. Terminal-vs-cap rate — the open question from the design doc, now
measured.** At the shipped `cap=400`: **99.5% of rollouts reach terminal,
0.5% hit the cap.** The value net effectively never fires today. The design
doc inferred this from the 65%-all-tied observation; it is now direct.
At K=16 the cap binds as intended: **90.1% of leaves scored by the value net.**

**2. Sanjay's −82 Elo disanalogy — verified empirically, not asserted.**
His value net failed on a *signal-shape mismatch*: absolute win-probability
leaves fed into a backup expecting rollout-scaled reward, corrupting UCT
sibling comparison. In our stack:
- backup is `totals[i] / n` — a **plain arithmetic mean**, no UCT, no
  mixed-scale combination;
- both branches of the leaf `if` return the same scale — terminal gives
  {0.0, 0.5, 1.0}, the value-net path gives a sigmoid in (0,1);
- **measured leaf range across 934,560 rollouts at K=16: [0.0000, 1.0000].**

No signal-shape mismatch is introduced. The mechanism that killed his attempt
is absent from ours by construction, now confirmed by measurement.

---

## RESULTS

### Dev set — K sweep (20 games per K, selection on P2 only)

| K | contested | P1 zero-disc | **P2 (selection metric)** | chance floor | P2 − chance | terminal % | p95 % bank |
|---|---|---|---|---|---|---|---|
| 16 | 1,491 | 4.4% | **0.4375** | 0.4174 | +0.0201 | 8.8% | 2.8% |
| 24 | 1,470 | 8.2% | **0.4375** | 0.4202 | +0.0173 | 17.3% | 4.1% |
| 40 | 1,671 | 9.9% | **0.4167** | 0.4313 | −0.0147 | 27.6% | 6.7% |

K=16 and K=24 **tie exactly on the selection metric** (0.4375 to 4 d.p.).
Tie-break, stated rather than left implicit: K=16 on P1 (4.4% vs 8.2%), which
also agrees with excess-over-chance and with wall-clock cost.
**Selected K = 16.**

### Evaluation set — held out, 80 fresh games at K=16

| arm | games | contested | **P1** | **P2** | chance | P2 − chance | spread | terminal % | p95 % bank | seat0 WR |
|---|---|---|---|---|---|---|---|---|---|---|
| BASELINE (cap=400) | 80 | 5,925 | **54.5%** | **0.667** | 0.694 | −0.028 | 0.421 | 99.5% | 8.2% | 57.5% |
| **EVAL K=16** | 80 | 6,139 | **5.7%** | **0.438** | 0.423 | +0.014 | 0.591 | 9.9% | 3.4% | 53.8% |
| JITTER CONTROL | 80 | 7,579 | **0.0%** | **0.375** | 0.394 | −0.019 | 0.418 | 99.6% | 10.8% | 52.5% |

Supporting: all-decision zero-discrimination 46.8% → **4.9%**; fraction of
determinizations where all candidates tie 0.673 → **0.102**; p95 time
8.2% → **3.4%** of the 600 s bank (shorter rollouts are cheaper, as predicted);
S3 time constraint satisfied with large margin.

### Null control outcome

Jitter drove P1 to **0.0%** — confirming P1 alone is gameable by pure noise,
which is exactly why P2 was paired with it. Jitter's P2 = **0.375**, below the
0.55 band. **The pre-registered VOID trigger ("jitter holds P2 ≥ 0.55") did
not fire.**

---

## VERDICT

Applying the pre-registered rule mechanically:

- **P1 = 5.7% → PASS** (band ≤ 20%). The measured defect is substantially
  removed: 54.5% → 5.7%, a 90% relative reduction.
- **P2 = 0.438 → FAIL** (band ≥ 0.55; 0.438 is below even the 0.45–0.55
  MARGINAL band).
- PASS requires both.

# → GATE 1: ~~FAIL~~ **INCONCLUSIVE-ON-P2 · P1 PASS** (amended 2026-07-25)

Nothing ships. `SEARCH_CAP` stays at its shipped default of 0; the change was
never applied outside the diagnostic harness.

## VERDICT AMENDMENT (2026-07-25, user ruling)

**The Gate 1 verdict is corrected from FAIL to INCONCLUSIVE-ON-P2, with P1
recorded as a clean PASS.**

**Rationale — dirty instrumentation, not a failed treatment.** P2's chance
floor is not a constant: it moves with the number of strict determinizations
(**0.694 at ~1.5 strict dets, ~0.42 at ~16**). The 0.55 band was therefore
unachievable by construction, and the 0.667 baseline it was calibrated against
sat *below* its own floor. Under our standing telemetry-gates-outcome rule —
the G-S1 dilution precedent, where a run whose instrumentation is compromised
is read as INCONCLUSIVE rather than as a result in either direction — a metric
that cannot return a valid reading yields **no verdict**, not a negative one.

**Why this is a metric defect and not a post-hoc rescue.** The defect
invalidates readings in *both* directions. Had the arm returned P2 = 0.60 it
would have "passed" a band whose floor had silently moved, and that pass would
have been exactly as meaningless as this fail. A metric that cannot be trusted
when it favours us cannot be trusted when it opposes us. That symmetry is what
distinguishes this correction from the arguments declined at Gate A and Gate D,
both of which were one-directional appeals made only after an unfavourable
number.

**The excess-over-chance reading remains NO VERDICT.** K=16's +0.014 over its
own floor is *not* restated as a pass here and is not carried forward as
evidence of success. It is retained only as the noise-amplitude measurement
used to derive Gate 2's band.

**P2 was confounded regardless of the floor defect.** Cross-world agreement is
uninterpretable while determinizations are drawn near-uniformly from ~1,267
cards with `SEARCH_PRIOR` dead. **Implausible worlds *should* disagree** — a
sampler that deals the opponent an incoherent 60 cards produces worlds whose
best moves genuinely differ, and low agreement is the correct response to
that, not a defect in the leaf evaluator. P2 only becomes a meaningful measure
of search coherence once the prior is populated. **That is why the next step
is Gate 2 (populate `SEARCH_PRIOR`) rather than a re-gate of Gate 1 on a
repaired P2** — repairing the statistic without repairing the population would
still measure agreement over strawman worlds.

**Unchanged by this amendment:** P1's result (54.5% → 5.7%) stands as measured;
the jitter null still showed P1 is gameable by pure noise (0.0%); the
verification results stand (99.5% terminal at shipped cap; leaf range
[0,1]; plain-mean backup, so Sanjay's −82 Elo signal-shape failure is absent);
no canary, no submission, nothing shipped.

---

## Metric defect — reported, not used to overturn the verdict

**The P2 band was unachievable by construction, and that is my error in the
design doc.** The evidence:

The chance floor for P2 is **not a constant** — it depends on how many
determinizations produce a strict argmax, because P2 is a modal *share*:

| arm | strict dets per contested decision | chance floor |
|---|---|---|
| BASELINE | ~1.5 of 16 | **0.694** |
| EVAL K=16 | ~16 of 16 | **0.423** |
| JITTER | 16 of 16 | 0.394 |

With ~1.5 strict votes, "modal share" is trivially ~1.0; with 16 it falls to
~0.42. So **the 0.667 baseline sat at −0.028 *below* its own chance floor** —
it was never evidence of coherence, only an artifact of tiny denominators.
Any intervention that increases the number of discriminating determinizations
— i.e. any intervention that fixes P1 — *mechanically* lowers raw P2. **No
version of this fix could have passed a raw P2 ≥ 0.55 band.** My design-doc
chance estimate (~0.34) was right for 16 strict dets and wrong for the
baseline I benchmarked against.

Read as excess over each arm's own chance floor, the ordering is the one the
metric was meant to detect — but the margins are small and I am explicitly
**not** claiming this as a pass:

| arm | P2 − chance |
|---|---|
| BASELINE | −0.028 |
| **EVAL K=16** | **+0.014** |
| JITTER | −0.019 |

K=16 is the only arm above its own chance floor, and it separates from the
jitter control by ~3.3 points of excess agreement. That is a real but **weak**
signal on a metric I have just shown to be mis-specified, at a magnitude I
would not ship on.

**The verdict stands at FAIL.** I am not revising the band, and I am not
substituting the excess-over-chance reading for it — that would be exactly the
post-hoc goalpost move the pre-registration exists to prevent, and it is the
same move I declined at Gate A and Gate D.

## What this gate did and did not establish

**Established:**
- The mechanism in PIMC_DIAGNOSTIC.md is real and the fix removes it: 99.5%
  terminal → 90.1% value-net-scored, zero-discrimination 54.5% → 5.7%.
- Doing so is **cheaper**, not more expensive: p95 8.2% → 3.4% of the bank.
- No signal-shape mismatch is introduced (leaf range measured [0,1], plain-mean
  backup) — Sanjay's −82 Elo failure mode is genuinely absent here.
- P1 alone is worthless as a gate: pure noise scores 0.0% on it.

**Not established:**
- That the restored discrimination is *informative*. K=16 clears its chance
  floor by only +0.014, and the honest reading is that this gate could not
  resolve whether graded leaves produce meaningful discrimination or merely
  well-behaved discrimination.
- Anything about ladder strength. Amendment 2's caveat is unaddressed and
  remains the live objection: we are grading strawman worlds drawn from a
  1,267-card pool, and `SEARCH_PRIOR` is still dead code.

## Recommendation — escalated, not taken

The FAIL is on a metric I have shown to be mis-specified, so treating it as
"graded leaves don't work" would over-read it, and treating it as a pass would
be a goalpost move. Both are wrong; the decision is yours. Options as I see
them:

1. **Redesign P2 and re-gate** (~1.5 h of runs, no new build): pre-register
   excess-over-chance with a stated minimum, or replace modal-share with a
   rank-correlation between per-determinization orderings and the aggregate.
   Same instrumentation, same arms, one fresh eval run.
2. **Proceed to Gate 2 anyway**, on the argument that Amendment 2 named
   strawman worlds as the dominant threat to validity and P1's 90% reduction
   is the prerequisite Gate 2 needs — accepting that Gate 1's coherence
   question is unresolved.
3. **Stop the search-core line** and return to the Aug 8 writeup pivot with
   this as a completed negative result plus a documented metric-design lesson.

I have no strong preference between 1 and 2 and would not choose between them
without you. **Stopping here as instructed — no Gate 2, no canary, nothing
shipped, `SEARCH_CAP` unchanged in the shipped agent.**

---

### Artifacts

| file | contents |
|---|---|
| `stage4/rl_ours/pimc_diagnostic.py` | instrumented harness (+ `--search-cap`, `--jitter`, leaf audit) |
| `stage4/rl_ours/gate1_analyze.py` | P1/P2 + simulated chance floor |
| `scratchpad/s3/g1_dev_k{16,24,40}.json` | dev sweep, 20 games each |
| `scratchpad/s3/g1_eval_k16.json` | held-out eval, 80 games |
| `scratchpad/s3/g1_jitter.json` | jitter null control, 80 games |
| `scratchpad/s3/pimc_raw.json` | baseline, 80 games |
