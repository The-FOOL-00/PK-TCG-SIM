# Search discrimination fix — scoped design

**DESIGN ONLY. No implementation started. Governor untouched.**
Companion to [PIMC_DIAGNOSTIC.md](PIMC_DIAGNOSTIC.md), whose primary finding
is treated here as the primary defect: **54.5% of contested searched decisions
have zero discriminating determinizations** (46.8% across all searched
decisions), because `cap=400` lets rollouts reach terminal and return exactly
0/1, so worlds already decided regardless of our top-4 choice flatten every
candidate. Tree topology cannot create discrimination where the leaf signal is
flat, so this is scoped ahead of the ISMCTS/strategy-fusion finding.

---

## STEP 0 — How the belief/determinization sampler actually works

**Answer: it is a static consistency filter over unseen cards. There is no
inference from opponent actions. The one dynamic input is literal card
reveals, plus a coarse structural prior that is identical in every game.**

### What it does

**1. Records literal reveals only.** `CardTracker.update` consumes the log
stream and stores identity **only where the engine explicitly told us the
card id**:

```python
if t == LOG_MOVE_CARD and ser is not None and cid is not None:
    self._see(ser, cid)
    to = lg.get("toArea")
    if to == AREA_HAND:
        self.floating.pop(ser, None)
        self.hand_known[ser] = cid
    elif to == AREA_DECK:
        self.hand_known.pop(ser, None)
        self.floating[ser] = cid   # certainly deck; hand-or-deck is safe
    else:
        self._forget(ser)          # visible zone: `current` covers it
elif t == LOG_MOVE_CARD_REVERSE:
    if lg.get("fromArea") == AREA_HAND:
        # an unidentified hand card moved face-down: we no longer
        # know WHICH, so every hand-known card demotes to floating
        self.floating.update(self.hand_known)
        self.hand_known.clear()
elif t in (LOG_PLAY, LOG_ATTACH, LOG_EVOLVE):
    self._see(ser, cid)
    self._forget(ser)
```

This is bookkeeping of observations, not inference. Note that `LOG_PLAY`
immediately `_forget`s the serial — playing a card teaches us nothing about
what *remains* in hand.

**2. A static structural prior.** `_comp_prior()` weights the entire 1,267-card
pool into three buckets, uniform within bucket, with **weights that never
change across turns, games, or opponents**:

```python
_COMP_TARGETS = {"energy": 0.30, "pokemon": 0.35, "trainer": 0.35}
...
for cat, ids in cats.items():
    w = _COMP_TARGETS[cat] / max(1, len(ids))
```

**3. One observation-shaped constraint: energy-type coherence.** The only
place an observation narrows the *sample* rather than just excluding a known
card — and it is driven by revealed energy cards, not by behaviour:

```python
etypes_seen = sorted(tracker.energy_types)
if etypes_seen:
    dom_type = etypes_seen[rng.randrange(len(etypes_seen))]
...
if (dom_type is not None and info.get("cardType") == CT_POKEMON
        and info.get("energyType") == dom_type):
    w *= 6.0
```

**4. Hard legality constraints:** 4-copy-per-name limit, zone-count matching,
a Basic required for a face-down active, ≥1 Basic in a setup deck.

### What it does NOT do — the inference gap

- **No negative inference from actions not taken.** Opponent ENDs with an
  empty bench and cards in hand → a human infers "no Basic, no Poffin, no Nest
  Ball." Our sampler will deal them Poffin in the very next determinization.
- **No positive inference from search/draw effects.** Opponent resolves
  Buddy-Buddy Poffin or Ultra Ball → their hand composition is now strongly
  constrained. `LOG_PLAY` records the Poffin and then `_forget`s it; **no
  consequence is drawn for the remaining hand.**
- **No inference from attach / retreat / attack choices** beyond adding the
  energy type to a set.
- **No archetype posterior — and the hook for one is dead code.**
  `sample_opponent_deck(..., prior=SEARCH_PRIOR)` is the documented plug-in
  point, and:

```python
SEARCH_PRIOR = None   # archetype-prior hook consumed by sample_opponent_deck
```

  `SEARCH_PRIOR` is assigned exactly once, to `None`, and **never populated
  anywhere in the codebase**. Every determinization therefore falls back to
  `_comp_prior()`. This is precisely the "present, plausible-looking, and
  completely inert" component class that Sanjay's §0 warns is only ever found
  by testing whether the thing works.

### Consequence: yes, the D2 entropy is partly self-inflicted — state it plainly

We sample the opponent's unseen cards from the **entire 1,267-card legal
pool**, shaped only by a 3-bucket composition prior and one energy type. The
actual top-10 field in our own 07-22 harvest is **~6 archetypes playing fixed
60-card lists**. Sampling near-uniformly from a pool two orders of magnitude
larger than the true support is a large, avoidable share of the measured
belief width (D2: 4.78–5.25 bits, perplexity 38–48 card identities, flat
across turns 12–24).

The codebase already documents this exact causal chain — belief quality →
rollout saturation → loss of candidate discrimination — and already paid for
it once:

```python
# ... uniform-over-pool sampling produces energy-less strawman opponents whose
# rollouts all saturate at a win, erasing candidate discrimination
# (measured: 96% of rollout values = 1.0).
```

The composition prior was the partial fix for that. **Our 65%-all-tied
measurement is the residual of the same failure mode**, now saturating in both
directions (decided-either-way worlds) rather than only at wins. So belief
inference belongs in this design — not as the primary fix, but as a named,
scoped second stage with a concrete reason to expect it to pay.

**Caveat kept honest:** sharper belief cannot fix a *decided* world. If we
know exactly what the opponent holds and we are winning regardless of which of
our four candidates we play, all four still score 1.0. Belief inference
narrows *which* worlds we sample; it does not change what a terminal return
looks like. That is why it is staged second, not first.

---

## STEP 1 — Design options

Shared baseline for all three (from the 7,398-decision capture):
contested zero-discrimination **54.5%**, contested signal-bearing agreement
median **0.667**, mean within-determinization spread **0.42** (on a 0–2
scale), mean 3.84 candidates, time budget used **~5.4% of 600 s**.

---

### (a) Depth-capped rollout + graded leaf evaluator  ⭐

**Mechanism.** `_rollout` already contains the graded path — it is simply
almost never reached:

```python
cap = SEARCH_CAP if SEARCH_CAP > 0 else 400
...
if steps >= cap:
    v = 0.5
    model = _lv_model()
    if model is not None:
        p = _lv_predict(model, [encode_state(cur)])[0]
        v = p if cur["yourIndex"] == me else 1.0 - p
    break
```

`SEARCH_CAP` defaults to 0 → cap = **400 engine steps**, so the overwhelming
majority of rollouts terminate first and return exactly 0/1. Set
`SEARCH_CAP` to ~24–40 steps (Sanjay's tuned equivalent was 24 steps ≈ 2.85
turns) and the value net becomes the *primary* leaf scorer, returning a
continuous win-probability. Decided worlds then separate by *degree* instead
of collapsing to an exact tie.

*Inference, stated as inference:* I did not instrument terminal-vs-cap rate.
But `value_weights.npz` is present and loads (123 KB, verified), so if
rollouts were routinely hitting the cap the leaves would already be
continuous and exact 4-way ties would be rare. Observing 65% all-tied
therefore implies most rollouts terminate well before 400 steps.
**Confirming that rate is the first, cheap step of any build.**

- **Cost:** ~3–6 h. `SEARCH_CAP` is an existing env var / module attribute;
  no new code path. Most of the time goes to (i) confirming terminal-vs-cap
  rate, (ii) choosing the cap, (iii) checking the value net is calibrated on
  Garchomp-mirror states rather than assuming it.
- **Blast radius: minimal.** Config-only change to an already-supported knob.
  Governor untouched. V1–V6 untouched. No new failure surface: the value-net
  load is already guarded (one stderr line, then permanent heuristic
  fallback), and shorter rollouts strictly *reduce* per-decision work, so
  timeout risk falls.
- **ISMCTS compatible:** yes — leaf evaluation is orthogonal to information-set
  aggregation. It is closer to a **prerequisite**: ISMCTS statistics are only
  meaningful over leaves that discriminate.
- **Key risk, and the disanalogy that matters.** Sanjay's value net measured
  −82 Elo, root-caused as a *signal-shape mismatch*: absolute win-probability
  leaves fed into a backup that expected rollout-scaled reward, corrupting
  UCT sibling comparison. **Our case differs structurally:** our backup is a
  plain mean of leaf values (`totals[i] / n`), our terminal returns are
  already in [0,1], and the value net's sigmoid output is in [0,1] — the same
  scale on both branches of the same `if`. There is no UCT and no mixed-scale
  backup. This must still be *verified*, not assumed, but the mechanism that
  killed his attempt is absent from ours by construction.

---

### (b) Margin-based terminal return

**Mechanism.** Replace the binary terminal return with a graded one — e.g.
`0.5 + 0.5 · (prize_differential / 6)`, or discount by turns-to-terminal — so
that decided worlds still separate by *how* decided.

- **Cost:** ~2–4 h. A single edit to `_rollout`'s terminal branch.
- **Blast radius: low but real.** It changes the meaning of every backed-up
  value, and a mis-signed margin is exactly Sanjay's §6i "confidently wrong
  term" failure, which cost 16 points before it was caught. Would need an
  ABSTAIN path for states where the margin is not cleanly readable.
- **ISMCTS compatible:** yes.
- **Why it is weaker than (a).** The margin at a terminal state is produced by
  ~dozens of intervening rollout-policy choices made by the v1 heuristic. It
  measures how the *playout* went, not the value of our *root* candidate. Add
  variance without adding much root-attributable signal, and you get
  discrimination that is real-valued but not informative. (a) evaluates a
  state ~3 turns out, far closer to the root decision.
- **Worth keeping as a cheap additive** on top of (a) later, not as the
  primary.

---

### (c) Belief inference to sharpen determinizations

**Mechanism.** Populate the dead `SEARCH_PRIOR` hook with an archetype
posterior, following Sanjay's §6d recipe which took his unknown-belief mass
from 92–100% to 28% and lock-on from 0/20 to 15/20 games: meta-share prior ×
`3^(signature-card hits)`, re-prioritised every decision, with copy-count
slack so tech-card variance cannot annihilate the true archetype. Our inputs
already exist — the 07-22 harvest gives ~6 top archetypes with real 60-card
lists (`analysis/phase2_meta_shift/`, `META.md`). Optionally add the cheapest
*behavioural* inferences: a resolved Poffin/Ultra Ball constrains the hand;
an END with an empty bench is evidence against holding a Basic.

- **Cost:** ~8–16 h — signature tables, posterior, per-decision re-prioritise,
  plus validation that unknown mass actually drops (the metric Sanjay used).
- **Blast radius: medium.** Touches every determinization, therefore every
  search decision. Confined to the sampler; governor and V1–V6 untouched.
  Crash path is benign — over-constraining raises `ValueError` and the caller
  resamples, then falls back to the heuristic — but a too-sharp posterior
  could cause *mass silent fallback*, which is the §0 "inert component"
  failure again and needs an explicit fallback-rate telemetry counter.
- **ISMCTS compatible:** yes, and **strongly synergistic** — ISMCTS aggregates
  statistics across an information set, and a sharper information set is
  exactly what makes that aggregation mean something.
- **Why it is staged second.** It cannot fix a decided world (see Step 0
  caveat), and its payoff is partly *gated on* (a): with 0/1 terminal leaves,
  better-sampled worlds still flatten whenever they are decided. Do (a) first
  so (c) can be measured against a leaf signal that is capable of responding.

---

## STEP 2 — Recommendation and its pre-registered gate

### Recommendation: **(a) depth-capped rollout + graded leaf evaluator.**

Rationale, in order: it is the direct fix for the *measured* mechanism
(terminal 0/1 → exact ties); it is the cheapest (~3–6 h) and has the smallest
blast radius (an existing config knob, no new code path, strictly less work
per decision); D4 shows we use ~5.4% of the 600 s bank so there is ~10×
headroom to spend on more rollouts if the shorter ones prove cheap; and it is
a prerequisite for both (c) and any later ISMCTS core. Stage (c) second, and
only after (a)'s discrimination metric moves — that ordering also gives (c) a
fair test instead of a gated one.

### Gate G-DISC — pre-registered, single variable

**Variable:** `SEARCH_CAP` = 0 (control, current shipped behaviour) vs
`SEARCH_CAP` = K (challenger). One variable. Nothing else changes; component
flags stay off; **the governor is not touched.**

**Instrument:** `stage4/rl_ours/pimc_diagnostic.py` unchanged, so every number
is directly comparable to PIMC_DIAGNOSTIC.md. Same deck, same config, 80 games
per arm.

**This is not a mirror A/B.** Mirror A/B has returned null on four consecutive
components (S3 50.0%, EVAL_FIX 45.9, PROMOTE_RULE 43.4, LETHAL_PROBE 45.1);
it is not the instrument for this question. The gate measures *whether the
search discriminates*, which is a property of the search, observable in a
single arm.

#### Metrics and pass band (fixed before any run)

| # | metric | baseline (measured) | PASS | MARGINAL | FAIL |
|---|---|---|---|---|---|
| **P1** | zero-discrimination rate, **contested** decisions | **54.5%** | **≤ 20%** | 20–35% | > 35% |
| **P2** | signal-bearing agreement median, **contested** | **0.667** | **≥ 0.55** | 0.45–0.55 | < 0.45 |
| S1 | zero-discrimination rate, all decisions | 46.8% | reported | — | — |
| S2 | mean within-determinization spread | 0.42 | reported | — | — |
| S3 | seconds/player/match (p95) | 49.0 s (8.2%) | must stay < 60% of bank | — | ≥ 60% |

**PASS requires P1 and P2 together.** P1 alone is gameable — see the null
control below. P2 is the guard that we bought *real* discrimination rather
than noise: it asks whether the worlds that now discriminate still agree with
each other at a rate well above chance.

#### Mandatory null control (the reason P2 exists)

Continuous leaf values almost never tie exactly, so **any** change that makes
leaves real-valued will drive P1 toward 0 — including pure noise. This is the
same trap that invalidated Sanjay's action-flip test until he ran a null
control and found a 42% noise floor (§6j).

Pre-registered control arm: **`SEARCH_CAP` = 0 with uniform random jitter of
±1e-3 added to every leaf value.** Expected behaviour if the metrics are
sound: jitter drives **P1 → ~0% (spuriously "passing")** while **P2 collapses
toward chance** (≈ 0.34 for ~3.8 candidates over 16 determinizations, since
votes become uniform).

- If the jitter arm shows P2 near chance while the real arm holds P2 ≥ 0.55 →
  the metric pair is valid and the result stands.
- **If the jitter arm also holds P2 ≥ 0.55, the metric pair is invalid and
  G-DISC is VOID** — no verdict may be read from it; redesign the metric
  before re-running. This is pre-registered precisely so a spurious pass
  cannot be claimed after the fact.

#### Secondary readout, explicitly not the gate

Win rate is reported for information only, at whatever n is convenient, and
**cannot pass or fail G-DISC**. Given four consecutive mirror nulls, a mirror
win-rate reading carries almost no information about this change and will not
be treated as if it does.

**Strength check is the ladder**, not the mirror: if G-DISC passes on P1+P2,
the candidate goes through the standard bundle pre-flight and then a ladder
canary under the standing rules — **v7 is never displaced, v8 slot only,
no read before n ≥ 40 episodes, keep if settled ≥ 908, revert if < 850.**
No submission is made by me.

#### Kill criteria

- P1 in FAIL band (> 35%) → the terminal-0/1 mechanism was not the binding
  cause; do not proceed to (c) on this theory; return to the ISMCTS branch
  with the diagnostic's strategy-fusion finding as the lead.
- P2 in FAIL band (< 0.45) while P1 passes → we bought noise, not signal;
  the cap is too short (leaves evaluated before the position resolves) — one
  pre-registered retry at a longer K is permitted, then final.
- S3 ≥ 60% of the bank → stop regardless of P1/P2 and re-scope; timeout is an
  instant loss and that is not a trade we make. (The expectation is the
  opposite — shorter rollouts should *reduce* time.)
- Jitter control passes P2 → **gate void**, per above.

#### Choosing K, pre-registered

Sweep `K ∈ {16, 24, 40}` engine steps on a **single 20-game exploratory run
per K**, selecting on **P2 only** (agreement — the coherence metric), then run
the full 80-game G-DISC at the selected K. Selecting on the coherence metric
rather than on P1 avoids tuning the knob against the metric it is meant to
prove. The exploratory runs are labelled exploratory and are not reported as
gate results.

---

## Sequencing after G-DISC

1. **G-DISC passes** → stage (c) belief inference as its own single-variable
   gate against the *new* baseline, with the same instrument, plus a
   determinization-fallback-rate counter so an over-sharp posterior cannot go
   silently inert. Then re-gate one or two of the three killed components
   (EVAL_FIX / PROMOTE_RULE / LETHAL_PROBE) on a search core that actually
   discriminates — the diagnostic's claim that those nulls were caused by
   flat leaves is directly testable, and cheap to test once the core moves.
2. **G-DISC fails** → the flat-leaf theory is wrong; ISMCTS/strategy fusion
   returns as the lead branch, scoped from PIMC_DIAGNOSTIC.md §D1.

Against the Aug 8 hard writeup pivot: (a) is ~3–6 h of build plus two
instrumented runs (~1.5 h each, single-process), so G-DISC is a ~2-day item
including the K sweep. (c) is a further ~8–16 h. Both fit only if started
promptly; neither is started here.

**No implementation has begun. Design doc ends.**
