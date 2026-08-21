# Gate 2 — 2×2 factorial: leaf evaluator × belief model

Run 2026-07-25. Companion to [PIMC_DIAGNOSTIC.md](PIMC_DIAGNOSTIC.md) and
[GATE1_GRADED_LEAF.md](GATE1_GRADED_LEAF.md) (amended same day — see that
file's verdict-amendment section, applied before this gate was built).
**Governor untouched. No ladder canary. No submission.** Same instrumentation
throughout (`pimc_diagnostic.py`), so every number is comparable across all
three documents.

Two factors, five arms (games each = 80, Garchomp mirror,
`metaC_garchomp_nasuo.csv`, all component-gate flags off):

| arm | leaf evaluator | belief model | note |
|---|---|---|---|
| A1 | terminal (cap=400) | uniform (`_comp_prior`+`dom_type`) | = shipped baseline |
| A2 | graded (cap=16) | uniform | = Gate 1 arm |
| A3 | terminal (cap=400) | archetype (`SEARCH_PRIOR` populated) | |
| A4 | graded (cap=16) | archetype | **target cell — the hypothesis under test** |
| A5 | terminal (cap=400) + jitter ±1e-3 | archetype | concurrent null control |

**Semantic note, stated before results (not discovered after):** in
`sample_opponent_deck`, both `_comp_prior()` and the `dom_type`
energy-coherence mechanism live under `if prior is None`. Populating
`SEARCH_PRIOR` bypasses both at once. The belief-model factor is therefore
**"which belief model,"** not "prior weights in isolation" — archetype lists
carry energy coherence intrinsically, so this is one coherent alternative
mechanism, correctly treated as a single factor level, not a hidden second
variable.

---

## PRE-REGISTRATION (fixed before this run — quoted verbatim from before launch)

**P1** — contested zero-discrimination rate, unchanged definition and band
from Gate 1: **PASS ≤ 20%**.

**P2′** — median signal-bearing agreement minus **that arm's own** simulated
chance floor (Gate 1's fix for the moving-floor defect: 0.694 at ~1.5 strict
dets vs ~0.42 at 16). Raw modal shares are never compared across arms.

> P2′ band, fixed from Gate 1's measured noise amplitude: Gate 1 jitter
> excess was −0.0194; the largest excess from any arm expected to carry no
> real signal was +0.0201 (devK16, strawman worlds) and the largest absolute
> deviation 0.0278 (baseline). Band: **PASS ≥ +0.05** (≈2.5× the largest
> uninformative positive), **MARGINAL +0.02 to +0.05**, **FAIL < +0.02** —
> plus the hard requirement that A4's bootstrap CI not overlap A5's.

**Mandatory:** A4's 95% bootstrap CI must not overlap A5's. If it overlaps,
A4 fails regardless of P1. Any arm with fewer than 200 contested decisions
carrying a strict determinization is reported INCONCLUSIVE rather than as a
number (none triggered this — see telemetry check below).

**Overall PASS** requires P1 PASS **and** P2′ PASS **and** the mandatory
separation — carried over from Gate 1's "PASS requires both metrics together"
structure, which the P2′ band above was explicitly set to preserve.

---

## Archetype prior construction

Built from `analysis/phase2_meta_shift/profile_top10_jul22.json` (350 sides,
the same harvest cited throughout FINAL_PATH_JUL21.md):

| archetype | share | sides | unique cards |
|---|---|---|---|
| Marnie's Grimmsnarl ex / Munkidori | 30.3% | 102 | 19 |
| Fezandipiti ex / Dudunsparce | 22.0% | 74 | 22 |
| Cynthia's Garchomp ex / Cynthia's Roserade | 19.0% | 64 | 20 |
| Team Rocket's Mewtwo ex / Team Rocket's Spidops | 10.7% | 36 | 20 |
| Dragapult ex / Fezandipiti ex | 9.2% | 31 | 25 |
| Mega Kangaskhan ex / Crustle | 8.9% | 30 | 19 |

87 of 1,267 pool cards receive archetype weight; mass ratio archetype:off ≈
**24,000 : 2.4**. `_comp_prior()` (uniform arm) remains switchable, not
deleted — a live factorial arm, per instruction.

### ⚠️ Caveat on what was actually built — read before interpreting the prior's null effect below

`build_prior()` sums `share(archetype) × copies(card)` **across all six
archetypes into one aggregate weight table**, used identically for every
determinization. This gives correct **marginal card-frequency** realism (only
real archetype cards get non-negligible weight) but does **not** enforce
**within-determinization coherence** — a single sampled hand can still mix
cards from Grimmsnarl, Fezandipiti, and Mewtwo lists simultaneously, which no
real 60-card deck does. This is weaker than the posterior-based,
commit-to-one-archetype-per-determinization sampler sketched in
DISCRIMINATION_FIX_DESIGN.md Step 0 (Sanjay's §6d recipe). **This gate tests
"does frequency-reweighting help," not "does archetype-coherent sampling
help."** The distinction matters for how the prior's result below should be
read, and is flagged here — before results — precisely so it cannot be raised
as a post-hoc excuse if the arm underperforms.

---

## Telemetry check (concurrency confound audit)

All 5 arms ran **concurrently** (5 single-threaded processes on a 12-thread
box) to fit the calendar. Governor dets-per-decision depends on wall-clock
availability, so concurrency is a candidate confound and is checked, not
assumed clear:

| arm | mean dets/decision (of max 16) | p95 time (% of 600 s bank) |
|---|---|---|
| A1 | 15.9 | 13.8% |
| A2 | 16.0 | 4.8% |
| A3 | 15.8 | 14.3% |
| A4 | 16.0 | 5.0% |
| A5 | 16.0 | 18.4% |

All arms achieved 15.8–16.0 of 16 possible determinizations — **no arm was
starved of search depth by concurrency.** A5 shows elevated p95 (18.4% vs
13.8–14.3% for the other cap=400 arms), consistent with it running alone for
its tail after A1–A4 (all faster or equal-speed) finished first; since dets
stayed at the maximum, this is a wall-clock-only effect, not a discrimination-
metric confound. Zero timeouts, all well under the 600 s bank.

---

## RESULTS

| arm | contested | **P1** | raw P2 | floor | **P2′** | bootstrap 95% CI |
|---|---|---|---|---|---|---|
| A1 (baseline) | 5,409 | 54.1% | 0.6667 | 0.6982 | **−0.0316** | [−0.0609, +0.0044] |
| A2 (graded, uniform) | 5,768 | **6.2%** | 0.4375 | 0.4119 | **+0.0256** | [+0.0017, +0.0299] |
| A3 (terminal, archetype) | 5,792 | 52.8% | 0.6667 | 0.7023 | **−0.0356** | [−0.0662, −0.0034] |
| **A4 (graded, archetype)** | 6,707 | **5.4%** | 0.4375 | 0.4187 | **+0.0188** | **[+0.0031, +0.0306]** |
| A5 (null: terminal+jitter, archetype) | 7,309 | 0.0% | 0.3750 | 0.3919 | −0.0169 | [−0.0294, −0.0121] |

A1's P1 (54.1%) and P2′ (−0.0316) closely replicate the original 80-game
baseline (54.5%, −0.0278) — a clean cross-run consistency check.

### Mandatory separation check

**A4 [+0.0031, +0.0306] vs A5 [−0.0294, −0.0121]: NON-OVERLAPPING —
separates.** A4's small positive excess is not attributable to the jitter
noise floor.

### Factorial decomposition

| metric | main(leaf: terminal→graded) | main(prior: uniform→archetype) | interaction |
|---|---|---|---|
| P1 | **−0.4769** | −0.0103 | +0.0046 |
| P2′ | **+0.0558** | **−0.0054** | −0.0027 |

Cells for reference: P1 {A1 0.541, A2 0.062, A3 0.528, A4 0.054}; P2′
{A1 −0.0316, A2 +0.0256, A3 −0.0356, A4 +0.0188}.

**Attribution is unambiguous and explicit: the leaf evaluator does virtually
all the work on both metrics.** It moves P1 by 47.7 points and P2′ by 5.6
points. The belief-model main effect is negligible on P1 (−1.0 points, as the
design doc predicted — "sharper belief cannot fix a decided world") and **small
and negative** on P2′ (−0.5 points, i.e. no measurable benefit, possibly a
slight cost, well inside single-arm CI half-widths of ~0.015–0.02).
Interaction terms are negligible on both (< 0.5 points).

**Counter-intuitive point, stated plainly:** the *uniform*-prior graded-leaf
cell (A2, +0.0256) scores slightly *higher* on P2′ than the *archetype*-prior
graded-leaf cell (A4, +0.0188) — the opposite direction from what the
population-validity hope would predict. The gap (0.0068) is well within the
combined CI noise of the two arms and should not be asserted as a real
degradation; it is accurately described as **no measurable prior benefit**,
not as "the prior hurts."

---

## VERDICT

Applying the pre-registered rule mechanically, on the target cell A4:

- **P1 = 5.4% → PASS** (≤ 20%).
- **P2′ = +0.0188 → FAIL** (< +0.02 — by **0.0012**, essentially at the
  boundary, but mechanically on the FAIL side of the pre-registered line).
- **Mandatory A4-vs-A5 separation → SATISFIED** (non-overlapping CIs).

**PASS requires all three. P2′ does not clear. Overall: GATE 2 = FAIL on the
target cell (A4), despite a clean P1 pass and a clean null-separation.**

No arm in this factorial achieves a full PASS (P1 PASS **and** P2′ PASS
together). The closest is A2 (P1 6.2%, P2′ +0.0256 → MARGINAL, not PASS) — the
uniform-prior arm, not the one this gate was built to validate.

I am reporting this exactly at the line, not rounding up. 0.0188 vs 0.0200 is
a difference smaller than the bootstrap CI's own resolution, and it would have
been easy to read the CI's upper bound (+0.0306, which clears MARGINAL) or the
clean null-separation as grounds for a favorable call. Per the standing rule
from Gates A, D, and 1: the band was fixed before the run and is not revised
by a compelling-looking argument that only appears after seeing the number.

---

## What this gate established and did not

**Established:**
- The leaf-evaluator fix (Gate 1's mechanism) is now doubly confirmed and
  cleanly attributed via a proper factorial: it is the dominant, essentially
  sole driver of both P1 and P2′ movement, independent of belief model.
- The specific archetype prior built here (aggregate frequency reweighting,
  not per-determinization coherent archetype sampling) produces **no
  measurable improvement** on either metric, and possibly a small,
  noise-level cost on P2′.
- A4's small positive P2′ excess is real relative to pure noise (separates
  cleanly from the concurrent jitter null) but is **too small to clear the
  pre-registered magnitude bar**.
- No concurrency confound: all arms held 15.8–16.0 of 16 determinizations.

**Not established:**
- Whether **genuinely coherent** archetype-conditioned sampling (commit to one
  archetype per determinization, from a posterior, per the caveat above)
  would move P2′ differently. This gate tested a weaker mechanism than the one
  the population-validity concern was raised against.
- Whether the amendment-2 worry itself ("graded leaves manufacture
  discrimination on strawman worlds") is confirmed or refuted. The small A2→A4
  direction is technically consistent with the worry but far too small
  relative to CI width to assert either way. **Inconclusive on that specific
  question**, not resolved.
- Anything about ladder strength — out of scope for this gate by design, and
  categorically excluded regardless of outcome (no canary, no submission).

## Recommendation — escalated, not taken

1. **Accept Gate 2 as a clean FAIL** for the archetype-prior-as-implemented
   hypothesis and close this branch: bank the factorial (clean attribution to
   the leaf evaluator; null prior effect; the coherent-sampling caveat) into
   `writeup_notes.md` as a completed, well-instrumented negative result, and
   return to the Aug 8 writeup pivot track.
2. **Build genuinely coherent archetype-conditioned sampling** (posterior over
   archetypes informed by revealed cards, commit to one list per
   determinization, per Sanjay's §6d recipe) as a distinct Gate 3, since this
   gate tested a materially weaker mechanism than that hypothesis requires.
3. **Pursue the leaf-evaluator-alone result (A2)** toward the standard
   bundle/pre-flight process on its own track — explicitly noting this would
   leave the Amendment 2 population-validity concern unresolved, and that
   Gate 2's own constraints (no canary, no submission, regardless of outcome)
   still apply; overriding that would need a fresh decision from you, not one
   I would make here.

No preference stated between 1 and 2, as with Gate 1. **Stopping here as
instructed — no further gate, no canary, nothing shipped.**

---

### Artifacts

| file | contents |
|---|---|
| `stage4/rl_ours/archetype_prior.py` | builds `SEARCH_PRIOR` from the 07-22 harvest |
| `stage4/rl_ours/archetype_prior.json` | the 87-card weight table + archetype shares |
| `stage4/rl_ours/pimc_diagnostic.py` | extended with `--prior {uniform,archetype}` |
| `stage4/rl_ours/gate2_analyze.py` | P1/P2′ with bootstrap CI on the moving floor |
| `scratchpad/s3/g2_A{1..5}.json` | 80-game captures, one per arm |
