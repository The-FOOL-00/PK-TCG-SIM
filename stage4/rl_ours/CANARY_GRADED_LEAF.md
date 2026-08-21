# Canary bundle — graded leaf evaluator (SEARCH_CAP 0 → 16)

Built 2026-07-26. **NOT SUBMITTED.** Bundle produced, verification run,
stopped for user submission decision.

**This is a canary, not a gate pass.** Gate 2 FAILED on its target cell (A4)
and that verdict stands, unoverturned. What justifies a ladder read is the
separately-isolated leaf-evaluator main effect (P1 54.5% → 5.4%, twice
replicated, and *cheaper*), combined with Amendment 2's population-validity
question being unanswerable by any local proxy — the ladder is the only
instrument that can answer it.

| item | value |
|---|---|
| **bundle** | `dist/canary/canary_cap16.tar.gz` |
| size / members | 2.12 MiB / 14 |
| sha256 | `616ec6789308cd2dbc3c52a3a332432923fe4f4b54923ecaebf7569e38807143` |
| AGENT_VERSION | `ptcg-search-gradedleaf-c16` |
| deck | `metaC_garchomp_nasuo.csv` (Cynthia's Garchomp) |
| config | `belief=comp rollout=v1 cap=16 governor=on` |
| extracted copy | `dist/canary/bundle_cap16/` |
| reference (cap=0) | `dist/canary/bundle_cap0/` |

Explicitly **not** changed, per instruction: `SEARCH_PRIOR` left `None`
(uniform prior as shipped — the archetype prior showed no benefit in Gate 2:
main effect −1.0 pts P1, −0.5 pts P2′); governor untouched; EVAL_FIX,
PROMOTE_RULE and LETHAL_PROBE all remain killed and default-off.

---

## V5 — Diff against the reference build (**one constant**)

Both bundles produced by the same builder invocation differing only in
`--cap`:

```diff
--- dist/canary/bundle_cap0/main.py
+++ dist/canary/bundle_cap16/main.py
@@ -152,7 +152,7 @@
 SEARCH_DET = int(os.environ.get("PTCG_SEARCH_DET", "16"))    # determinizations
 SEARCH_ROLL = int(os.environ.get("PTCG_SEARCH_ROLL", "2"))   # rollouts/candidate
 SEARCH_TOPK = int(os.environ.get("PTCG_SEARCH_TOPK", "4"))   # candidates by v1 score
-SEARCH_CAP = int(os.environ.get("PTCG_SEARCH_CAP", "0"))     # rollout step cap, 0=terminal
+SEARCH_CAP = int(os.environ.get("PTCG_SEARCH_CAP", "16"))     # rollout step cap, 0=terminal
 SEARCH_SEED = int(os.environ.get("PTCG_SEARCH_SEED", "0"))
 SEARCH_MIN_BASICS = 1        # sampled opp deck must keep >= this many Basics at setup
 ROLLOUT = os.environ.get("PTCG_ROLLOUT", "v1")               # v1 | s1
```

**Source diff = exactly one constant.** ✅

One manifest difference, which is a required consequence rather than a second
variable: the cap=16 bundle additionally contains `value_weights.npz` (the
builder's `need_value = cap > 0` rule). The graded leaf path cannot function
without the net; shipping cap=16 without it would silently fall back to a flat
0.5 leaf.

| | cap=0 | cap=16 |
|---|---|---|
| files | main.py, deck.csv, card_data.json, cg/ | **+ value_weights.npz** |

### ⚠️ Disclosure — what "shipped agent" means here, and what else differs from git HEAD

The one-constant claim above is against **the current gate baseline** (the
exact configuration used as the incumbent arm in Gates A/D/B/1/2). It is *not*
one constant against `git HEAD`, and you should know that before submitting.
`main.py` in the working tree carries **187 insertions / 7 deletions** vs HEAD:

| change | active on ladder? | provenance |
|---|---|---|
| `EVAL_FIX` + scaling-damage code | **No** — defaults `False` | Gate A (killed) |
| `PROMOTE_RULE` + promote hook | **No** — defaults `False` | Gate D (killed) |
| `LETHAL_PROBE` + `_find_lethal` | **No** — defaults `False` | Gate B (killed) |
| **Governor: `ema_det` seed 0.05, per-update cap `min(spent/dets, 0.2)`, `GOV_WARMSTART_N=10`, `GOV_HYST_M=3`, extra telemetry** | **YES — active, unconditional** | S3 arc |

The three killed components are inert dead code (flag-gated off, verified by
the one-constant diff being the only live difference between the two bundles).
**The governor engagement fixes are live.** They were built during S3 after
diagnosing that an unlucky cold-cache first search could poison the EMA and
silently disengage search for an entire game — a failure mode that applies on
ladder, not only in parallel A/B harnesses. Every gate from S3 onward was
measured with them in place, so removing them for the canary would make the
canary differ from everything we measured.

**Consequence for interpretation:** if this canary reads well, the credit is
not attributable to the leaf change alone against the *last shipped* search
agent — it is leaf change + governor engagement fixes. Against the gate
baseline it is clean single-variable. If you want strict single-variable
versus the last shipped artifact, that is a different bundle and I would
advise against it, since no gate was ever run in that configuration.

---

## V1 — `value_weights.npz` packaged, loads in a clean environment, and actually fires

Method: tarball extracted to a bare temp dir; `main.py` `exec()`'d with **no
`__file__` in the namespace** and the repo stripped from `sys.path` — Kaggle's
load conditions, the V1-class failure mode from Sanjay's §0.

**Naming resolved.** The task referenced `value_weights_mlp.npz`; `main.py`
loads `LV_WEIGHTS_FILE = "value_weights.npz"`. These are **byte-identical**:

| file | sha256 (16) |
|---|---|
| `value_weights.npz` | `4e31642ed9639e8c` |
| `value_weights_mlp.npz` | `4e31642ed9639e8c` |
| `value_weights_logreg.npz` | `76b7a9c3b011ae46` (different — not shipped) |

So the MLP net is the one bundled and loaded, under the generic filename. No
action needed, but worth recording so nobody later "fixes" a non-problem.

| check | result |
|---|---|
| packaged in tarball | ✅ `value_weights.npz` present (14 members) |
| `AGENT_VERSION` | `ptcg-search-gradedleaf-c16` |
| `SEARCH_CAP` baked | **16** |
| `_lv_model()` loads under clean exec | ✅ non-None |
| stderr during load | *(empty — no warning, no fallback)* |
| `_lv_predict` on a zero feature vector | 0.437265, in [0,1] ✅ |
| **graded path actually fires in play** | ✅ **274,431 value-net evaluations across 24 games** |

That last row is the one that mattered. The concern was correct that this path
is effectively untested in deployment — at the shipped `cap=400` it fires on
**0.5%** of rollouts (measured in Gate 1: 99.5% terminal). At `cap=16` it
carries the overwhelming majority of leaf evaluations. It is now exercised,
under Kaggle load conditions, from the shipped artifact.

---

## V2 — Self-play validation, 24 games (≥20 required)

Bundle agent vs a copy of itself, mirroring Kaggle's validation game, run from
the extracted tarball under the same stripped-path conditions.

| metric | result |
|---|---|
| games | **24** |
| crashes | **0** |
| uncaught exceptions | **0** |
| **caught** exceptions / error-class stderr lines | **0** |
| `STATS["fallbacks"]` / `STATS["calls"]` | **0 / 4,153** |

stderr was scanned for every one of `FALLBACK`, `SELFCHECK FAIL`, `WARNING`,
`Traceback`, `cg engine unavailable`, `sampling failed`, `engine search
failed` — **zero occurrences.** Nothing was silently swallowed: the report
requirement was "any exception, even caught ones," and the count is zero on
both categories, with the fallback counter independently confirming 0 of 4,153
decisions took a degraded path.

Additional confirmation from the builder's own pipeline on the same bundle:
exec-load check OK, no-cg fallback OK, `SMOKE-OK 24 games 0 crash 0 fallback`.

---

## V3 — Wall-clock per player per match (**MAX**, not median)

Timeout is an instant loss, so the headline is the worst case observed.

| statistic | seconds | % of the 600 s bank |
|---|---|---|
| median | 9.4 | 1.6% |
| **MAX (worst of 48 player-matches)** | **13.7** | **2.3%** |
| margin to timeout | 586 s | 97.7 points of bank unused |

Per-decision latency from the builder smoke on the same bundle: p50 197 ms,
p90 331 ms, p99 394 ms, **max 453 ms**.

For contrast, the cap=0 reference build measured p50 372 ms / max 1,765 ms per
decision. **The canary is roughly 4× faster per decision than the
configuration it replaces**, consistent with Gate 1/2 (p95 8.2% → 3.4% of
bank). This change reduces timeout exposure; it does not add to it.

---

## V4 — Fallback returns a legal action on every throwing path

Ran the existing B4 fault-injection suite (`tools/test_search_robustness.py`)
**under the canary config** (`PTCG_SEARCH_CAP=16`). Method: record real
decision streams with search OFF (pure v1 answers as reference), then replay
the identical streams through `agent()` with search ON under each injected
fault. Answers must be byte-identical to v1 — search may only ever change an
answer when it is healthy.

| scenario | result |
|---|---|
| 1 no-engine (`cg` import failed, `_SES` poisoned) | all answers == v1 ✅ |
| 2 begin-raises (`SearchBegin` throws every call) | all answers == v1 ✅ (24 stderr lines, all expected) |
| 3 sampler-raises (`_sample_determinization` throws every call) | all answers == v1 ✅ |
| 4 budget-zero (governor returns 0 → sticky heuristic) | sticky latched, all answers == v1 ✅ |
| 5 healthy control | 5/49 answers changed by search, **all legal** ✅ |

**`B4 FAULT-INJECTION SUITE: ALL OK`** — 4 games, 49 decisions.

Scenario 5 is the meaningful control: the search does change decisions when
healthy (so the suite isn't passing by the search being inert), and every
changed answer still passes C1 legality validation.

---

## Summary

| # | verification | result |
|---|---|---|
| 1 | weights packaged + load clean + **path fires** | ✅ 274,431 evals in play |
| 2 | ≥20-game self-play, zero crashes | ✅ 24 games, 0 crashes, 0 caught exceptions, 0 fallbacks |
| 3 | worst-case wall-clock | ✅ **MAX 2.3%** of bank (586 s margin) |
| 4 | fallback legality on all throwing paths | ✅ B4 suite ALL OK under cap=16 |
| 5 | diff vs reference | ✅ **exactly one constant** (+ required weights file) |

**All five pass.** The one item needing your judgment before submitting is the
V5 disclosure: this bundle is single-variable against the gate baseline, but
also carries the S3 governor engagement fixes relative to `git HEAD`.

**Bundle path: `dist/canary/canary_cap16.tar.gz`**

Not submitted. Stopping here — the submission is yours to make. Standing
canary rules from FINAL_PATH_JUL21.md remain as written and unmodified by this
document: **v7 is never displaced, v8 slot only, no read before n ≥ 40
episodes, keep if settled ≥ 908, revert if < 850.**

---

### Artifacts

| file | contents |
|---|---|
| `dist/canary/canary_cap16.tar.gz` | the canary bundle |
| `dist/canary/bundle_cap16/`, `bundle_cap0/` | extracted bundles for the diff |
| `stage4/rl_ours/canary_verify.py` | V1–V3 harness (clean-env exec, timing, exception capture) |
| `stage4/rl_ours/canary_verify.json` | raw verification record incl. per-game timings |
| `tools/test_search_robustness.py` | V4 fault-injection suite (pre-existing) |
