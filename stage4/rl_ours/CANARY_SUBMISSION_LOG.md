# Canary submission log — graded leaf evaluator

Record for the `ptcg-search-gradedleaf-c16` canary. Verification detail lives
in [CANARY_GRADED_LEAF.md](CANARY_GRADED_LEAF.md); this file is the operational
record of the upload and the decision rules that govern it.

**Documentation only.** Nothing in this file was submitted by the agent. The
upload is the user's action.

---

## 1. Bundle identity

| field | value |
|---|---|
| path | `dist/canary/canary_cap16.tar.gz` |
| sha256 | `616ec6789308cd2dbc3c52a3a332432923fe4f4b54923ecaebf7569e38807143` |
| size / members | 2.12 MiB / 14 |
| version string | `ptcg-search-gradedleaf-c16` |
| deck | `metaC_garchomp_nasuo.csv` (Cynthia's Garchomp) |
| config | `belief=comp rollout=v1 cap=16 governor=on` |
| **diff vs gate baseline** | **one constant: `SEARCH_CAP` 0 → 16** |
| bundled weights | `value_weights.npz` — byte-identical to `value_weights_mlp.npz` (sha256 prefix `4e31642ed9639e8c`); `value_weights_logreg.npz` (`76b7a9c3b011ae46`) is **not** shipped |

Verification summary (all five passed, detail in CANARY_GRADED_LEAF.md):
weights load under clean exec and the graded path fires (274,431 value-net
evaluations / 24 games); 24-game self-play with 0 crashes, 0 caught
exceptions, 0 fallbacks across 4,153 calls; worst-case wall clock 13.7 s =
**2.3%** of the 600 s bank; B4 fault-injection suite ALL OK under `cap=16`;
source diff exactly one constant.

> **First ladder submission in a long time.** Agents enter the pool at an
> initial rating of **600** and climb from there. Early scores are therefore
> *structurally* low regardless of agent quality — this is an independent
> reason (on top of the variance argument) why no band in §3 may be applied
> before the n ≥ 40 threshold in §5.

---

## 2. Slot state — TO BE FILLED BY USER

> **The Kaggle last-2 rule is TEAM-level, not per-member.** The two most
> recent uploads by *anyone on the team* are the active pair. **Two uploads
> from us displaces Sanjay's v7.** Exactly **one** canary goes up.

| item | value |
|---|---|
| Team's two active submissions BEFORE this upload | `[ ]` `[ ]` |
| Was Sanjay's v7 (μ 881) in a slot before upload? | `[ ]` |
| Team's two active submissions AFTER this upload | `[ ]` `[ ]` |
| Sanjay notified not to submit while canary settles? | `[ ]` |
| Upload date/time | `[ ]` |
| Kaggle submission ID | `[ ]` |

---

## 3. Two separate band sets — these govern DIFFERENT decisions. Do not merge them.

### 3a. SLOT DECISION — governs what occupies the active pair

Baseline for comparison: **Sanjay's v7 at μ 881.**

| settled score | action |
|---|---|
| **≥ 908** | hold the slot |
| **< 850** | revert the slot, restore v7 |
| 850–908 | no automatic action — user call |

**v7 is never displaced regardless of outcome.**

### 3b. MECHANISM DECISION — governs whether the search line continues

Baseline for comparison: **OUR agent at μ 697** — *not* v7. This asks whether
the discrimination fix converts into strength on our own stack, which is a
different question from whether it beats the team's best artifact.

| settled score | reading | action |
|---|---|---|
| **< 750** | discrimination fix does not convert to strength | close the search line, full writeup pivot |
| **750–880** | real improvement on our stack | Gate 3 (coherent archetype sampler) justified |
| **> 880** | matched Sanjay's class on our own stack | — |

### Worked example — recorded so it cannot be misread later

> **A settle at 800 means: REVERT THE SLOT *and* KEEP THE MECHANISM.**
>
> - Slot decision: 800 < 850 → revert the slot, restore v7.
> - Mechanism decision: 800 is inside 750–880 → the search line is validated,
>   Gate 3 is justified.
>
> **These are not contradictory.** The slot question is "is this the best
> artifact the team can field right now?" (no — v7 at 881 is better). The
> mechanism question is "did the discrimination fix make *our* stack
> stronger?" (yes — 800 vs our 697 baseline). Losing the slot and keeping the
> research direction is the expected outcome across most of the plausible
> range.

---

## 4. Attribution caveat — this wording must survive into the writeup unchanged

> Against `git HEAD` this bundle carries the S3 governor fixes (EMA seed,
> per-update cap, warm-start, hysteresis) in addition to the leaf change.
> Therefore this canary reads as **"current stack vs last-shipped stack."** A
> good result is **NOT** attributable to the graded leaf evaluator alone.

Supporting detail: the three killed component flags (`EVAL_FIX`,
`PROMOTE_RULE`, `LETHAL_PROBE`) are present but inert — default-off and
verified dead by the one-constant bundle diff. The governor fixes are
**active and unconditional**, which is why the caveat above is required. The
one-constant claim in §1 is against the *gate baseline*, not against
`git HEAD`.

---

## 5. Read rule

**No score is read, quoted, or acted on before n ≥ 40 games.** Neither band
set in §3 may be applied below that threshold.

| item | value |
|---|---|
| Date of upload | `[ ]` |
| Date n ≥ 40 reached | `[ ]` |
| n at first read | `[ ]` |
| Settled score at read | `[ ]` |
| Slot decision applied (§3a) | `[ ]` |
| Mechanism decision applied (§3b) | `[ ]` |

> **If either band is applied at n < 40, mark that read INVALID** and do not
> carry its conclusion forward into any document or decision.

Rationale, for the record: byte-identical archives have scored 600–955 on this
ladder (repo2, 146 submissions), and fresh agents additionally start at 600 and
climb — so a low early number is the default expectation and carries no
information about agent quality.

---

## 6. Open items

| item | status / deadline |
|---|---|
| **Sanjay** — repo access, slot permission, availability call | **window expires Jul 28** |
| **Gate 3** — coherent archetype sampler (commit to one archetype per determinization, posterior-driven) | **conditional on the 750–880 mechanism band**; not authorized otherwise |
| **Writeup** | starts this week **in parallel — not blocked on the canary read** |
| Aug 8 | hard writeup pivot |
| Aug 14 | internal freeze |
| Aug 16 | submission lock |

Note on Gate 3's dependency: Gate 2's archetype prior was an aggregate
frequency mixture, which does not enforce within-determinization coherence —
a single sampled world can still blend cards from multiple archetype lists.
Gate 3 would test the stronger mechanism (one archetype committed per
determinization). That distinction is recorded in
[GATE2_FACTORIAL.md](GATE2_FACTORIAL.md) and is why a Gate 2 null does not
settle the coherent-sampling question.
