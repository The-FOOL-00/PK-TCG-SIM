# Piloting Is the Product: A Falsification-Driven Agent for the Pokémon TCG

### Complete reference version — every experiment, gate and verdict
*(Internal / appendix document. The submittable ≤2000-word version is `WRITEUP_SUBMIT.md`.)*

---

## 0. Summary

We built a deterministic, sub-millisecond heuristic pilot for the Pokémon TCG
and spent the project trying to beat it. Across ~20 pre-registered experiments
we killed nine policy-side interventions, two behaviour-cloning generations,
one runtime search architecture and four mined rule families. The three things
that survived — a deck-fit criterion, a sequencing rule pair, and a
card-specific ability rule — are the three we ship.

The single most valuable output is not a win rate. It is a **measurement**: a
deck-pilot fit metric ("envelope closure") that predicts, before any match is
played, whether a given agent can pilot a given deck. It explains every
architectural failure in this project retroactively and it is the reason our
final deck choice is what it is.

---

## 1. The agent

**`main.py`, one file, pure Python standard library at runtime.** No numpy in
the shipped path, no engine binary, no learned weights. Median decision time
**0.10 ms**, p99 **3 ms** — the same speed class the top-10 ladder pilots
occupy (31–92 ms measured), roughly 1000× faster than our own search prototype.

The core is a **fixed priority ladder** over the engine's legal option menu:

| tier | weight | action class |
|---|---|---|
| lethal attack | 100 000 | attack that KOs the active |
| energy attach | 3 000 | attach to the best target |
| evolve | 2 800 | + best-attack bonus, + active-slot bonus |
| item | 2 400 | play a Trainer item |
| bench | 2 300 | (2 300 → *urgent* if board is nearly empty) |
| ability | 2 200 | once-per-turn abilities |
| attack (non-lethal) | ~1 100 | + damage/2 |
| retreat / end | low | terminal |

Sub-decisions (`ST_CARD` family: which Pokémon a fetch retrieves, what a
discard gives up, which bench target a gust pulls) have their own scorer keyed
by decision context (`SC_*`).

**Safety envelope, unchanged since the first bundle:**
- `_validate_result` + `resolve_selection` — every hook can only substitute
  *which legal option index* is returned; it can never emit an illegal answer.
- A fallback chain: any hook exception → one stderr line → the v1 answer.
- `INVALID = loss` in this competition, so the agent's contract is
  *"always answer legally"* before *"answer well."*
- Every ladder bundle emits a one-time `SELFCHECK` line and per-game telemetry,
  so a silently-inert component is detectable from episode logs.

**Every candidate improvement lives behind its own default-off flag.** Nothing
ships until it passes a pre-registered statistical gate. This is the whole
methodology, and it is why most of this document is negative results.

---

## 2. Statistical protocol

`tools/ab_gate.py`: **≥300 games, seats alternated by construction, 95%
Wilson CI, PASS only if the CI lower bound exceeds 50%** against the incumbent.

Two protocol facts were learned the hard way and then enforced mechanically:

1. **Small samples lie.** A deck variant read 48% at n=50 and **25% at n=150**.
   Rule adopted: never conclude below n=150, never ship below n=300.
2. **Seat matters enormously.** In one gate the challenger won **72% in seat 0
   and 36% in seat 1** (n=150 each). Any comparison that does not alternate
   seats is invalid. The tool alternates by construction so it cannot be
   forgotten.

Later screens added **pre-registered PASS / AMBIGUOUS / FAIL bands written into
a markdown file before the run**, plus **mechanism telemetry** (a fire counter
per rule): *a rule that did not fire has not been tested.*

---

## 3. The full experimental record

### 3.1 H1 — Deck redesign (REJECTED, 6 variants)

Our starting deck was a 35/60 basic-Water build whose engine was Hammer-lanche
(damage = 100 × basic Energy in the top 6 of deck; measured average 354).
Six redesigned variants, v1 policy on both sides, seats alternated:

| variant | basics | energy | n | win rate |
|---|---|---|---|---|
| deck_v2 | 12 | 20 | 50 | 48% |
| **deck_v2 (rerun)** | 12 | 20 | **150** | **25%** |
| deck_v2b | 12 | 26 | 50 | 38% |
| deck_v2c | 10 | 31 | 50 | 36% |
| deck_v2d | 8 | 33 | 50 | 42% |
| deck_v2f | 10 | 27 | 50 | 36% |
| deck_v2g | 10 | 31 | 50 | 40% |

deck_v2 *fixed its nominal targets* (no-active losses 42%→20% of games,
mulligans 0.82→0.26/game) and still lost. Mechanism: every added Basic is
one-shot prize fodder (Mega ex KO = 3 prizes, ex = 2, else 1), and cutting
energy starves the damage engine. It still lost at 30% with improved routing
on **both** sides — so the deck itself was inferior, not merely mis-piloted.

### 3.2 H2 — Analytic 1-ply evaluator (FAIL at gate)

`evaluate_state()` + 1-ply analytic option deltas, hill-climbed weights
(`tools/tune_v3.py`, 100-game rounds). The single improving move in the entire
hill-climb was one weight halving. Confirm run 53.0% at n=200; formal gate
**54.0%, 95% CI [48.3%, 59.6%], n=300 → FAIL.** Flag stays off.

### 3.3 H3 — Learned value model (FAIL at gate)

50 000 self-play games → **1 521 362 decision rows** (170-dim state encoder,
outcome labels, split by game). MLP 170→128→64→1, **30 209 params**:
**val AUC 0.8445**, logloss 0.4810 (train 0.4800 — no overfit).

Deployed as tier + `400 × clip(P(win|after) − P(win|now), ±0.25)`, with the
"after" vector built analytically in feature space by the *same encoder used in
training* (no train/serve drift). Gate: **48.7%, CI [43.1%, 54.3%] → FAIL.**

In-game calibration over 3 123 decisions was monotone and tight at the
extremes ([0.0,0.1) → 0.045 actual; [0.9,1.0) → 0.973 actual), mid-buckets
optimistic by 5–10 pts.

**Reading: the value function is accurate; greedy 1-ply use of it does not beat
co-adapted heuristics.** H2 + H3 together quantify the 1-ply ceiling and
motivate depth.

### 3.4 H4 — Determinized Monte-Carlo teacher

**Finding: `cg.api.search_begin` is not a search algorithm — it is a
determinized forward simulator.** You supply predictions for every hidden zone;
it returns a root state. `search_step` applies an option and returns a new
state; old ids stay live, so tree branching is the caller's job. There are no
depth/time/node parameters. Any actual search is ours to build.

Flat determinized MC on top of it, both sides rolling out with v1:

| samples/option | win rate | 95% CI | verdict |
|---|---|---|---|
| 2 | 48.0% | [42.4, 53.6] | FAIL |
| 16 | 56.0% | [50.3, 61.5] | PASS |
| **32** | **58.7%** | **[53.0, 64.1]** | **PASS** |
| 64 | 57.0% | [51.3, 62.5] | PASS (saturated) |
| 32, topk 8 | 58.7% | [53.0, 64.1] | PASS (= topk 4) |

First CI-backed >50% policy in the project — and **saturated at ~58%**. 64
samples buy nothing over 32; widening the candidate set buys nothing. The
ceiling is algorithmic (1-action lookahead, rollouts assuming v1 forever), not
statistical.

### 3.5 The pivot — search at test time

Three independent facts forced a re-plan:
(i) v1 sat at **μ≈512** on ladder, below the 600 entry rating;
(ii) both 1-ply upgrades failed their gates despite an accurate value net;
(iii) the ladder allows **600 s/player of overage with `actTimeout=0`** —
roughly 15 s/decision — and we were using **<2%** of it.

**Engine feasibility verified.** The official sample submission bundles `cg/`
with binaries for every platform including `libcg.so` (Linux x86-64), and its
`main.py` does a plain `import cg` — bundling the engine is the intended
pattern. The pip package ships no search bindings, so the bundle must carry the
sample's `cg/`. A probe bundle (byte-identical v1 play + one logged
search cycle) was submitted: **GREEN on-ladder**, image Linux-x86_64 /
Python 3.11.13, `SearchBegin` **3.28 ms on Kaggle vs 0.16 ms local — a 20×
sandbox overhead** that materially changes the compute budget (16
determinizations pay one begin each ≈ 53 ms fixed cost per decision).

### 3.6 Belief sampling, and why it failed (E1)

**`CardTracker`** — serial-keyed (engine serials are unique per match, so
re-processing a log entry is a no-op). Tracks `hand_known`, `floating`
(hand-or-deck after face-down shuffles), 4-copy budgets, observed energy types.
Validated on 20 recorded games: 392 decisions, serial identities identical to
the omniscient transcript, revealed multiset ⊆ true opponent list, and 1 176
sampled determinizations accepted by the engine with zero errors.

**The sampler finding: uniform-over-pool belief builds a strawman opponent.**
Basic energy is 8 of 1 267 cards in the pool, so uniform remainder sampling
gives the opponent essentially no energy; 96–98% of rollout values saturate at
1.0 and candidate discrimination vanishes (zero overrides). A composition prior
(energy 30 / Pokémon 35 / trainer 35) fixed the counts but not type coherence
(energy no sampled Pokémon can use) — still 96% saturation. Only adding
**per-determinization type coherence** (dominant energy type sampled from
observed evidence, matching Pokémon boosted 6×) restored override rates.

**Gate E1 (belief-search vs v1, n=300): 49.0% [43.4, 54.6] → FAIL.**
The same search with exact-knowledge (mirror) determinization scored
**58.3% [52.7, 63.8] → PASS**, faithfully reproducing the teacher. So the
runtime port is correct; **the belief is what fails.**

**Diagnosis** (249 identical searched positions, matched per-position RNG):

| metric | mirror belief | honest belief |
|---|---|---|
| override rate vs v1 | 38% | 18% |
| of mirror's overrides, honest makes the same one | — | 9% |
| of mirror's overrides, honest reverts to v1 | — | 76% |
| top1−top2 rollout-value gap (median) | 0.031 | **0.000** |
| positions with **zero** value separation | 39% | **76%** |

Honest belief → flat value landscape → the search cannot rank candidates →
falls back to v1 → plays at v1 strength (49% ≈ 50%). **The bottleneck is
belief quality, not search budget.** More determinizations cannot sharpen a
flat landscape.

### 3.7 The gate that was structurally incapable of answering its question

E1's incumbent was v1 **on our own deck** — a mirror by construction, which
makes exact/mirror belief tautologically correct and penalises honest hedging
against variation the gate contains none of.

We re-gated against **three real top-ladder decklists** extracted from episode
replays (Cynthia's Garchomp ex, 5 energy; Dudunsparce/Alakazam, 3 energy, a
73%-win-rate field deck; Mega Kangaskhan ex, 16 energy), each piloted by v1,
all structurally unlike our 35-energy build. 300 games each:

| opponent | v1 baseline | honest belief | exact-mirror belief | **oracle (true list)** |
|---|---|---|---|---|
| Garchomp ex | 72.5% | 73.7% [68.4, 78.3] | 71.0% | **78.3%** [73.3, 82.6] |
| Dudunsparce/Alakazam | 37.5% | 42.7% [37.2, 48.3] | 40.7% | **51.3%** [45.7, 56.9] |
| Mega Kangaskhan | 75.0% | 75.3% [70.2, 79.9] | 72.3% | 73.3% |

Three findings:
1. **E1's mirror advantage was a gate artifact.** Against opponents that
   actually differ, honest belief equals or beats exact-mirror belief on all
   three decks (+2.7 / +2.0 / +3.0 pt).
2. **Belief accuracy is a real lever and it converts.** Oracle beats honest by
   +4.6 and +8.6 pt where there is headroom; on the deck we lose to, perfect
   knowledge swings us **+13.8 pt (37.5% → 51.3%)** — a loss turned into a coin
   flip. Position-level: perfect belief roughly halves the flat-value fraction;
   honest belief captures only **11–18%** of the overrides perfect belief makes.
3. **A deck-power ceiling.** Even *perfect* search only reaches parity against
   the strongest field deck (51.3%, CI spanning 50%). Against the best
   archetypes **our deck, not our decision quality, was the limiter.**

### 3.8 Ship-config pilots (both nets rejected)

| pilot | result | verdict |
|---|---|---|
| distilled-policy rollouts vs v1 rollouts | 45.0% [38.3, 51.9] at 7.6× per-step cost | **REJECT** |
| value-net leaf truncation (cap 10) vs terminal | 51.5% [44.6, 58.3] | **REJECT** (strength-neutral) |

Both confirm the E1 diagnosis: neither net-in-the-loop addition converts,
because belief quality — not rollout fidelity or sample count — was the
bottleneck. Ship config became belief + terminal rollouts + v1 rollout policy +
governor, and therefore **numpy-free**.

### 3.9 Time governor

`budget = min(3 s, 0.5 × remainingOverageTime / max(est_remaining_decisions, 8))`,
with `est` from live decisions-per-turn × (p90 turns − current turn); p90 = 20
taken from a 27 260-game distribution and padded because ladder games run
longer than mirrors. Degradation full → ½ → ¼ determinizations → skip; sticky
heuristic-only below 0.2 s.

**Stress test at 3× the ship config:** own-time mean 10.0 s / p90 21.2 s /
max 35.6 s against a 400 s requirement; decisions p50 370 ms / p99 3.07 s.
**PASS with 17× headroom**, 0 sticky, 0 crashes.

Three governor bugs surfaced across later A/B iterations and are recorded
honestly because they bear on methodology: (i) **seed poisoning** — an EMA
initialised to `None` let one unlucky cold-cache search permanently pin a
worker to no-search; (ii) **missing input cap** — one high sample inflated the
running estimate; (iii) **cold-run bias**. Each was caught by a pre-registered
engagement-telemetry criterion, and each fix revealed the next.

**The coupling problem, stated rather than hidden:** the same adaptive governor
that protects the ladder time bank in production is the mechanism whose
behaviour we gate on offline. If a component ever passes offline and
underperforms on ladder, we cannot cleanly separate "the model is worse against
the real population" from "the governor engages differently under real decision-cost
distributions." Ship-vs-gate isolation is *imperfect for adaptive
infrastructure.* Two controls make it observable rather than invisible: hard
engagement guarantees (warm-start N=10 + hysteresis M=3 + input cap) that are
independent of the EMA, and per-episode `[gov]` telemetry lines.

### 3.10 The ladder falsified a local gate — the project's hardest lesson

A feasibility gate said our search agent piloting the Dudunsparce/Alakazam list
beat our search agent piloting our old deck **74.7% [69.5, 79.3]**. We shipped
it. On the ladder it scored **μ = 548 — 66 points *below* the old-deck build
(μ = 614).**

The gate was **structurally incapable** of predicting this: its opponent was
*our own agent on our old deck*, and **both sides mispiloted the complex
Alakazam engine symmetrically**, so the comparison could not surface the
piloting weakness they shared.

Ladder intel then delivered the decisive irony: **the rank-1 player (μ 1260)
played a deck byte-identical to the one we shipped** (19/19 ids, 60/60 copies).
The entire gap was piloting. He grinds 44-turn denial games, first attack turn
4.1; we attacked at turn 11.2 and **never attacked at all in 30% of games**.

**The rule, now permanent: a deck gate must use strong, representative
opponents (real top-team decks) and be anchored to a known ladder result —
never to a weak or self-mirrored reference. Local win rate against the wrong
opponent predicts nothing.**

Ladder intel also showed **top teams run fast policies** (median 31–92 ms/decision),
not search. We were running 200–320 ms. Search was competitive but was not how
anyone reached the top.

### 3.11 The architectural finding

Two complex decks, same failure shape:

| deck | result |
|---|---|
| Dudunsparce/Alakazam + search | ladder **μ 548** |
| Cynthia's Garchomp + search + deck-specific tempo heuristics | gate **39.3% [34.0, 45.0]** vs our own simple deck |
| our simple aggro deck + search | ladder **μ 614** |

Mechanism: the search only searches **MAIN single-select** decisions and rolls
out with a heuristic that is **blind to the sub-decision layer** where combo
decks live (which Pokémon a fetch retrieves, what a discard gives up). Deck-specific
heuristic patches cannot fix a shallow-planning problem.

### 3.12 A tooling bug we caught ourselves

Two diagnostic tools inserted `sample_submission/` at `sys.path[0]` **before**
`import main` — and that directory ships its own `main.py`: the 38-line
**random** sample agent. Every historical run of both tools had been measuring
random-vs-random play.

**Invalidated** (diagnostic numbers only, never gate results): the "first-attack
turn 10.8", "ex online 13.6", and the BC "first-attack 14.6" telemetry.
**Not affected:** every `ab_gate` result, the feasibility study, all training,
and all ladder scores — those import the repo `main` first.

Re-measurement with the fixed tool overturned our own published mechanism story:

| configuration | win (30 g) | first attack | attacker online |
|---|---|---|---|
| BC-full | 53% | 6.4 | 6.9 (27/30 games) |
| search + tempo heuristics | 37% | 6.4 | 7.8 (23/30) |
| **v1 alone** | **30%** | **4.6** | 7.0 (20/30) |
| BC (MAIN-only) | 10% | 6.8 | 7.2 (17/30) |
| expert truth (140 replays) | — | 5.9 | 5.9 |

**First-attack turn was never the discriminator** — v1 attacks *earliest* at
4.6 and still loses. The real discriminator is **sub-decision quality** (what
gets fetched and discarded) and **consistency** (attacker online in 17/30 games
versus 27/30).

### 3.13 Behaviour cloning — the two-generation arc

**Feasibility.** The active agent's `observation.select` at `steps[i]` is
answered by that agent's action at `steps[i+1]`. Naive same-step pairing is
wrong. With the shift: **99.2% clean index recovery** (later 99.7% at scale).

**Generation 1 — MAIN-only BC.** 4 610 winning decisions from a rank-7 pilot.
Val top-1 **69.4%** against a *v1-agreement floor of 20.8%* — the net learned
strongly non-heuristic play. It did not convert:

| gate | result |
|---|---|
| vs incumbent | **31.0% [26.0, 36.4] FAIL** |
| vs our own search on the **same deck** (pure piloting A/B) | **42.7% [37.2, 48.3] FAIL** |
| vs search + Alakazam | 44.7% [39.1, 50.3] FAIL |

Two textbook causes:
1. **Sub-decision blindness.** BC answered only MAIN selects (60% of
   decisions); the fetch *targets* — the actual setup mechanism — were
   `ST_CARD` sub-decisions still answered by v1. BC says "play Poffin", v1
   fetches the wrong Pokémon, and the imitated line's pieces never reach hand.
2. **Compounding off-distribution error.** 69% per-decision fidelity gives
   0.69⁵ ≈ **16%** chance of following a five-step line; the first deviation
   lands the net where its validation accuracy says nothing.

**Generation 2 — BC-full.** We built a **73-dim `ST_CARD` option encoder**
(card identity over the piloted deck, board slot/area, decision-context
buckets, v1 prior), decomposed multi-selects **Plackett-Luce style** into
sequential single choices (serving mirrors this with iterative argmax), and
trained a **two-headed net** — shared 170→80→48 trunk, separate MAIN (41-dim)
and CARD (73-dim) heads, **27.9k params** — on 4 610 MAIN + 2 397 `ST_CARD`
targets.

| head | val top-1 | floor |
|---|---|---|
| MAIN | 68.9% | 21.4% |
| ST_CARD | 76.1% | 51.6% |

The diagnosed killer contexts trained strongest: **Poffin bench fetches 100%
vs v1's 36%; hand discards 87% vs v1's 9%.**

| gate | result |
|---|---|
| **BC-full vs incumbent** | **60.7% [55.0, 66.0] PASS** — first challenger ever to beat it |
| **BC-full vs MAIN-only BC** (same weights, same MAIN head; *only* change is who answers sub-decisions) | **77.0% [71.9, 81.4] PASS** |
| BC-full vs search + same deck | 69.7% [64.2, 74.6] PASS |

The middle row is the causal proof: **piloting a combo deck lives in the
sub-decisions.** Shipped at ~1 ms/decision (p99 3 ms) and reached **μ 697** —
our best ladder result.

**Generation 2's ceiling — the pathology imitation cannot fix.** Against
defensive/stall opponents the policy decks *itself* out: **41–52 self-deckouts
per 100 games** for the second BC (vs 10 for the first). Static accuracy sees
nothing — decision accuracy in those very games matches overall, and the
prize-fetch context reads **96.8%**.

**Cause: thin-deck states are structurally absent from win-side imitation
data.** Winners close games by turn 12–15, so the states where a draw-brake
matters are exactly the states the expert never demonstrates. *Imitation learns
the racing line superbly and cannot learn to stop racing.*

**The prosthetic and the discipline moment.** We added an inference-time
draw-brake over frozen weights (trigger: own deck ≤ N **and** not ahead on
prizes → exclude optional self-draw/fetch options), ablatable for causal proof.
N was chosen from 41 recorded self-deckout trajectories:

| N | trigger | won-side interference | deckout games touched / saved ≥4 | fires < T10 |
|---|---|---|---|---|
| 12 | not-ahead | 8 decisions, 4 games | 34/41, 26/41 | 6 |
| **10** | **not-ahead** | **5 decisions, 2 games** | **34/41, 20/41** | **3** |
| 12 | strictly-behind | 5 decisions, 1 game | 27/41, 17/41 | 1 |

N=12 breached the **pre-registered** interference limits (>6 decisions or >3 of
29 wins). We dropped to N=10 rather than relax the limits after seeing the
data — the limits existed precisely so the evaluation could not argue us out of
them.

It did not save the line. **Gate: 39.0% [33.7, 44.6] — FAIL, decisively (the
CI *upper* bound is below 50%).** Loss anatomy across 183 losses: 107 lost
prize races (58%), **52 self-deckouts (28%, with the brake armed)**, 24
no-active. The second BC fixed both diagnosed causes and scored *slightly
worse* than the first.

### 3.14 The proxy-objective lesson, stated in full

| artifact | offline metric | head-to-head reality |
|---|---|---|
| analytic evaluator | hill-climbed to 53% | 54.0% → FAIL |
| value net | val AUC 0.8445, calibrated | 48.7% → FAIL |
| BC gen-1 | val top-1 69.4% (floor 20.8%) | 31.0% / 42.7% → FAIL |
| BC gen-2 | ST_CARD 76.1%, prize-fetch 96.8% | 39.0% → FAIL |

**Any offline metric that is not "win rate of the artifact you ship, measured in
the deployment configuration" has misled us every single time it was leaned
on.** This is why our final line is rule-level, flag-gated, and measured only
by head-to-head play.

---

## 4. The original contribution: deck–pilot fit, measured

### 4.1 The experiment

Same generic agent, `PILOT=""`, v1-alone, no rules, **only `deck.csv` differs**.
100 games per arm, seats alternated:

| counter | Garchomp | **Grimmsnarl** |
|---|---|---|
| **prize velocity** (prizes / own turn) | **0.2628** | **0.4574** |
| own turns / game | 11.17 | **7.63** |
| prizes / game | 2.94 | **3.49** |
| turn of first prize | 11.2 | **9.2** |
| attack-when-legal | 54.4% | **88.5%** |

**Δ prize velocity = +0.1946, bootstrap 95% CI [+0.1569, +0.2324]**
(10 000 resamples over sides).

### 4.2 Envelope closure

Raw velocity is not comparable across decks — different archetypes have
different natural clocks. We therefore measure each arm against **its own
archetype's top-10 envelope**, harvested from real top-10 replays of that
archetype:

> **closure = our mirror prize velocity ÷ that archetype's top-10 prize velocity**

| arm | our velocity | archetype envelope | **closure** |
|---|---|---|---|
| Garchomp, v1-alone | 0.2628 | 0.495 | **53.1%** |
| **Grimmsnarl, v1-alone** | 0.4574 | 0.5725 | **79.9%** |

Pre-registered PASS required the closure *ratio* to exceed 1.30. Measured
**1.505 → PASS.**

Two counters are worth naming: **prizes per game 3.49 — identical to the top-10
Grimmsnarl figure of 3.49**, and **attack-when-legal 88.5% vs their 84.5% — we
exceed them.** The remaining gap to the envelope is almost entirely game
*length* (7.63 vs 6.1 own turns), not prize output.

### 4.3 The 2×2 that closed the search question

| | Garchomp | Grimmsnarl | **deck effect** |
|---|---|---|---|
| **v1-alone** | 0.2628 | 0.4574 | **+0.1946** |
| **+ search** | 0.2430 | 0.4288 | +0.1858 |
| **search effect** | **−0.0198** | **−0.0286** | — |

Bootstrap CIs on the search effect: Garchomp −0.0198 [−0.0538, +0.0144],
Grimmsnarl −0.0286 [−0.0666, +0.0096]. Neither is significant; both point
estimates are negative; search worsens *turn of first prize* on **both** decks.

**The deck effect is ~10× the search effect, and they have opposite signs.**
Switching deck is worth +0.19 on either policy; adding search is worth −0.02 on
either deck. The two are nearly independent.

Search had now been measured against a matched no-search control on two
different decks and was non-positive on both, while costing ~500 ms per
decision plus the governor's entire failure surface. **There is no
configuration in this project's measurements where it earns its cost.** The
search line closed.

### 4.4 Why it happens — the mechanism

Grimmsnarl's line is Impidimp → Morgrem → Grimmsnarl ex **with Rare Candy**,
and its attacker needs Darkness energy on a body that is cheap to field. The
v1 tier order — **attach 3000 > evolve 2800 > item 2400 > bench 2300 >
attack ~1100** — *happens to be* a reasonable Grimmsnarl line.

Garchomp's plan requires holding an attacker back through a three-stage line
while accumulating counters. The same fixed order produces slow, passive play.

> **The agent was never bad at piloting. It was piloting the wrong deck for its
> fixed priority order.**

This is a *different* diagnosis from every previous one in the project, and the
first that **predicted** a measurement instead of being fitted to one.

### 4.5 Generalisation — the canonical closure sweep

**Five archetypes, one script, one protocol** (v1-alone, `PILOT=""`, 100 games /
200 sides each, each closed against its *own* harvested top-10 envelope). Every
top-10 archetype with a recoverable 60-card list was included; all validated
against the live engine pool with zero unconstructible cards:

| deck | attacker online via | velocity | **envelope** | **closure** | own turns | atk-when-legal | draws/turn |
|---|---|---|---|---|---|---|---|
| **Marnie's Grimmsnarl ex** | Stage-2 **+ Rare Candy** | **0.4574** | 0.5725 | **79.9%** | 7.63 | **88.5%** | 1.63 |
| Cynthia's Garchomp | Stage-2, no Rare Candy | 0.2628 | 0.4950 | 53.1% | 11.17 | 54.4% | 1.63 |
| TR Mewtwo / Spidops | Basic, stall plan | 0.3303 | **0.6754** | 48.9% | 10.40 | 68.1% | 2.97 |
| Mega Kangaskhan / Raging Bolt | Basic + Mega evolution | 0.3025 | **0.6729** | 45.0% | 7.74 | **38.5%** | 1.64 |
| Fezandipiti / Dudunsparce | Stage-1 engine | 0.2061 | 0.5084 | 40.5% | 7.06 | 66.9% | **4.18** |

Two archetypes measured later with a second harness (ranking transfers; absolute
values not directly comparable to the rows above):

| deck | attacker online via | velocity | envelope | closure |
|---|---|---|---|---|
| Teal Mask Ogerpon ex | **Basic, no evolution at all** | 0.4726 | 0.5845 | **80.9%** |
| Dragapult ex / Munkidori | Stage-2, no Rare Candy | 0.2324 | 0.5021 | 46.3% |

**Grimmsnarl leads the canonical sweep by 26.8 points. No other deck is close.**

### 4.6 Three findings from the sweep

**(i) Closure tracks turns-to-attacker, not deck strength.** One-step decks — a
Basic, or a Stage-2 collapsed by Rare Candy — close at **79–81%**. Every deck
requiring a genuine multi-turn climb closes at **40–53%**.

**(ii) High envelope with low closure is the trap.** TR Mewtwo (0.6754) and
Kangaskhan (0.6729) have the **highest envelopes we measured** — top-10 pilots
get *more* out of them than out of Grimmsnarl — and we convert the least of it.
Any deck-selection heuristic based on field strength picks exactly these.
Dragapult ex is the current meta's strongest archetype (76.5% pooled, 10–2
versus Grimmsnarl) and we close 46.3% of it; adopting it would *lower* our
rating. Kangaskhan's attack-when-legal is **38.5%**, the worst of any deck
measured — its plan does not fit a fixed tier ladder at all.

**(iii) Card flow is not our bottleneck.** Fezandipiti draws **4.18 cards per
turn against Grimmsnarl's 1.63** and posts the *worst* velocity in the sweep.

### 4.7 The decisive control — a strong player's own deck

We reconstructed a strong ladder player's exact 60-card list (validated clean
against the engine pool) and ran **our unmodified agent** on it — the same
isolation the Garchomp/Grimmsnarl experiment used:

| arm | velocity | own turns | atk-when-legal |
|---|---|---|---|
| our agent, v1-alone, on that deck | **0.2510** | 9.01 | 42.3% |
| our agent, **+ all our shipped rules**, on that deck | **0.2207** | 9.43 | 36.9% |
| *our agent on Grimmsnarl, same rules* | *0.4953* | *7.00* | *87.5%* |
| *that deck's own pilot, real ladder* | *0.4718* | *6.17* | *64.9%* |

**Our own rules made it worse** (0.2207 < 0.2510). Root cause verified directly
against 40 games of replay: E1 defers the attack whenever a develop option is
legal — **1059 / 1059 decisions, 100.0% of the time**, exactly as designed. The
design premise ("attack is terminal; everything else is free") is **false** for
that deck's key attack, which searches for energy *and* deals damage — it *is* a
development action. Deferring it every time delays the ramp the deck depends on.

**A top deck is not a transferable asset.** It is conditional on execution built
for it. This is the cleanest statement of the whole result.

**This is the deliverable.** Closure is measurable in ~20 minutes of self-play
before a single competitive game is played. It retroactively explains the μ 548
disaster, the Garchomp 39.3% gate, and every architectural failure above.

---

## 5. What we ship, and why

### 5.1 Deck: Marnie's Grimmsnarl ex / Munkidori

Harvested from top-10 replays (list seen 163 times), 60 cards / 19 unique:

| n | card | role |
|---|---|---|
| 3 | **Marnie's Grimmsnarl ex** (HP 320) | the payoff attacker |
| 3 | Marnie's Morgrem | evolution bridge |
| 4 | Marnie's Impidimp | line starter |
| 3 | **Rare Candy** | **collapses the Stage-2 climb — the reason this deck is pilotable** |
| 4 | **Munkidori** | Adrena-Brain: move up to 3 damage counters to the opponent |
| 2 | Froslass | Freezing Shroud: passive chip on every Ability holder |
| 2 | Snorunt | Froslass line |
| 4 | Buddy-Buddy Poffin | Basic search |
| 4 | Poké Pad / 1 Pokégear 3.0 | draw / Supporter search |
| 3 | Night Stretcher | recursion |
| 4 | Team Rocket's Petrel, 4 Lillie's Determination, 1 Dawn | draw engine |
| 2 | **Boss's Orders** | gust — the target of our T1 rule |
| 4 | Spikemuth Gym | stadium |
| 1 | Unfair Stamp, 1 Tool Scrapper | tech |
| 10 | Basic {D} Energy | fuel |

**The concept in one sentence:** a 320-HP attacker that arrives *early* because
**Punk Up** (on evolving from hand, search up to **5 Basic {D} Energy** and
attach them freely) pays its own energy cost, plus **Shadow Bullet** (180 to
the active **and 30 to a benched Pokémon**) which converts a single attack into
two-target prize pressure, backed by **Munkidori**'s free damage-counter
relocation to finish what Shadow Bullet started.

**Why it fits our pilot, stated mechanically:**
- **Rare Candy** turns a three-turn climb into a one-turn one. Our fixed
  priority order ranks evolve (2 800) just under attach (3 000), so the agent
  naturally executes *attach → Rare Candy → Grimmsnarl ex* — the correct line
  falls out of the tier order rather than needing planning.
- **Punk Up** removes the energy-accumulation phase that our pilot handles
  worst; a single evolve delivers five energy.
- **Shadow Bullet + Adrena-Brain + Freezing Shroud** stack chip damage so the
  prize race is won by accumulation rather than by precise multi-turn setup —
  again matching a greedy pilot.

This is not our original list. **Deck selection here is deliberately a
second-order lever**: our own evidence says the field's decks are already
near-optimal and that every remaining point is in the pilot, so we chose the
field's strongest *pilotable-by-us* list rather than inventing one.

### 5.2 Rules that survived: mined, not invented

**The mining method (original).** Record the full state context of every MAIN
decision, partition it into cells, and rank cells by

> **leverage = cell frequency × total-variation distance** between the top-10
> action distribution and ours

Deck-matched: **top-10 Grimmsnarl (504 sides, 19 323 decisions)** vs **our own
arm on the same 60 cards (200 sides, 6 692 decisions)** — so any divergence is
piloting, not deck. Every feature is computed from the seat's own observation,
so everything the miner sees, the agent can see at decision time.

**The headline cell was not a priority problem. It was a sequencing problem:**

| over own turns containing an attack | top-10 | **ours** |
|---|---|---|
| turns using an ability | **80.2%** | 61.8% |
| **actions taken before the attack** | **mean 5.87** | **mean 2.97** |
| **attacked as the FIRST action of the turn** | **2.0%** | **43.0%** |
| in the `can_KO` cell, share choosing ATTACK | 22% | **100%** |

**Attack ends the turn; every other action is free.** `WEIGHT_LETHAL = 100 000`
meant that the instant a KO appeared, the attack outranked everything and the
turn ended with cards unplayed and abilities unused.

**Shipped rules** (all default-off flags, all baked explicitly into the bundle):

| rule | what it does |
|---|---|
| **E1** | before a terminal action, take any board-advancing play first (bounded: max 12 vetoes/turn) |
| **E2** | before a terminal action, fire an available once-per-turn Ability first |
| **T1** | Boss's Orders targets by **prize value**, not by generic "best Pokémon" — `1000 × prizes_for_KO + 50 × energy − 10 × HP-fraction` |
| **T2** | splash/bench damage ranks by **HP *ratio***, not raw HP, so a fresh low-max-HP Basic no longer outranks a half-dead attacker |

### 5.3 The mirror-vs-ladder asymmetry — why these shipped despite "failing"

On the **pre-registered self-play screen, E1/E2 were DROPPED.** Same-config
run-to-run noise at n=200 sides is 0.019–0.025 velocity, and the measured
effects sat at or below that band. We recorded the drop honestly.

The behavioural mechanism nonetheless worked *perfectly*: attack-first
**42.4% → 0.1%**, ability-turns **59.5% → 89.5%** — both to or past field
parity. No previous intervention had moved a behavioural counter to the field's
value. **Field-parity behaviour did not produce field-parity self-play
results.**

Then we compared two of our own *ladder* submissions:

| ladder bundle | n | prize velocity | actions before attack | ability-turns |
|---|---|---|---|---|
| `v1_grimmsnarl` (no rules) | 43 | 0.3069 | 2.90 | 41.3% |
| **`v1_grimm_seq_e1e2`** (E1+E2) | 38 | **0.3922** | **4.62** | **72.9%** |

**+0.0853 — well outside the 0.019–0.025 noise band**, and moving in the
mechanism-predicted direction on *both* diagnostic counters (toward the top-10
values of 5.87 and 80.2%).

**The explanation is structural, and it is a genuine methodological finding: a
sequencing fix that both sides receive cancels in a mirror.** Self-play is
blind to any improvement that is *strictly dominated* — taking a free action
before a terminal one is not a trade-off, so both mirrored agents gain equally
and the win rate does not move. It shows up only against opponents who do not
have it.

This is observational (different opponent pools, n < 60), so it does not
overturn the recorded self-play verdict. It changed our *instrument*: every
rule of this shape is now screened **cross-deck**, never in a mirror.

### 5.4 The cross-deck instrument and the KE family

Re-screening the same rule shape against a *different* opponent archetype
(our Kangaskhan build vs a v1-piloted Grimmsnarl, 200 games, seats alternated):

| arm | win rate | Δ | fires |
|---|---|---|---|
| baseline (no rules) | 32.0% | — | — |
| **KE1** (Mega Kangaskhan *Run Errand* free-draw before a terminal action) | **39.0%** | **+7.0 pt** | 695 |
| KE2 (a second free-ability veto) | 35.5% | +3.5 | — |
| KE3 (a third, different card) | 36.4% | +4.0 | 385 |
| KE1 + KE2 | 35.5% | +3.5 | — |
| KE1 + KE3 | 33.3% | +1.3 | KE1 507, **KE3 4** |

**Rule composition is not automatic.** KE2 and KE3 each helped alone and each
*regressed* when stacked on KE1: all three compete for the same once-per-turn
Ability slot, and whichever fires first in the hook chain suppresses the
other's fire rate by **99%** (385 → 4). Standing rule adopted: **test every new
rule alone *and* stacked, and assume competition until proven otherwise.**

### 5.5 Four honest failures from the final mining cycle

Every one pre-registered, unit-tested (6–11 synthetic assertions each), screened
cross-deck at n=200:

| rule | mined signal | alone | stacked with KE1 | why it failed |
|---|---|---|---|---|
| **KE_SUP** | in `atk_legal & supporter_pending`, top-10 ATTACK 15.9% vs our 34.7% | **25.0%** (−7.0) | 29.5% (−9.5) | after the supporter resolves, v1 re-scores from scratch and often does *not* return to ATTACK; attack-when-legal fell 3.4 pt |
| **KE_BOLT** | top-10 use Bellowing Thunder 0.412×/game; **we used it 0 times in 200 games** despite 135 offers (v1 reads its *printed* damage of 0 for a dynamic-damage attack) | 32.5% (+0.5) | 37.0% (−2.0) | mechanism correct (both hooks fired 1:1) but **environment-starved**: only 13 fires per 200 games, because our pilot rarely powers Raging Bolt |
| **KE_WELL** | attach targets: top-10 Kangaskhan 43.6% / Wellspring 23.7%; **ours 62.4% / 4.6%**. Downstream, top-10 fire Torrential Pump 0.576×/g, we 0.035×/g — 16× under-use | **28.5%** (−3.5) | 29.5% (−9.5) | rule worked as designed — fired 164×/200 g and lifted Torrential Pump **4.7×** — but diverting attaches **starved the primary attacker**; attack-when-legal fell 7.2 pt |
| **G_ABIL_BROAD** | fresh mining on **post-shipped-bundle** play shows we *still* trail top-10 by 14–20 pt on ABILITY in critical cells (KOable & powered: **38.9% vs 18.6%**) | +0.017 velocity unfiltered, **+0.004** filtered | — | unfiltered it fired a Pokémon's *return-to-hand* ability and cost 6.5 pt cross-deck; narrowing to a strictly-positive whitelist protected the other deck but removed 75% of the gain |

**The law these four teach, stated as a design rule:**

> A rule that **substitutes an unconditionally-valuable free action** for a
> terminal one (KE1: take a free draw before ending the turn) succeeds, because
> it requires no follow-up: the next menu is unchanged minus that action, and
> the pilot re-picks the terminal action.
>
> A rule that **promotes an action the pilot would not otherwise take**
> (KE_SUP, KE_WELL) fails, because it shifts the state into a line the pilot
> cannot continue. Matching an expert's *rate* is not matching their *policy*.

---

## 6. Consistency and stability

| criterion | evidence |
|---|---|
| **Determinism** | fixed policy, **no RNG at decision time**; ties break on lowest index |
| **Legality** | 0 INVALID / ERROR / TIMEOUT sides across every ladder submission; `_validate_result` + `resolve_selection` byte-identical across all variants |
| **Crash-freedom** | 0 crashes / 0 fallbacks in every gate reported here (300 games each) and in 20-game clean-env runs (3 333 agent calls, 0 Traceback, 0 hook-error) |
| **Timing** | median **0.10 ms**, p99 **3 ms**, max 2 ms against a **600 s** per-player budget → **0.0% of bank** |
| **Fault injection** | engine removed → legal; `card_data.json` removed → legal; malformed option → legal. Each degrades to v1 with one stderr line |
| **Deployment integrity** | shipped bundle contains **no project-local module imports**; deck, card data and any weights load via a `_find_file()` probe (`__file__` → cwd → `/kaggle_simulations/agent` → `sys.path`), so it is immune by construction to the `sys.path`-strip failure class |
| **Ship-gate parity** | **A6 gate**: every bundle is extracted to a **bare temp directory**, `sys.path` stripped, exec-loaded with no `__file__`, and every flag re-asserted. This gate has caught real bugs — a flag baked off, and a cwd-sensitivity where the repo's own `deck.csv` shadowed the bundled one |
| **Not matchup-dependent** | the shipped rules are card-mechanic-driven, not opponent-driven; the one archetype-conditional rule we built (a matchup-specific tiebreak) was screened separately and is **off** |

**Ladder record of our own line:**

| bundle | policy | deck | μ |
|---|---|---|---|
| v1 heuristic | v1 | 35-energy Water | ~504–512 |
| v2.0.0 | belief search | 35-energy Water | **614** |
| v2.1.0 | belief search | Dudunsparce/Alakazam | **548** ← the falsified gate |
| v2.2.0 | BC-full (fast policy) | Cynthia's Garchomp | **697 / 682.5** |
| `v1_grimmsnarl` | v1-alone | Grimmsnarl | 440.5 (n=43) |
| **`v1_grimm_seq_e1e2`** | **v1 + E1 + E2** | **Grimmsnarl** | **482.5 (n=38)** |

We report these plainly, including the two that went down. The μ 548 result is
the most valuable number in the table because of what it falsified.

---

## 7. Honest limits

1. **We never crossed μ 1000.** Our best is μ 697. The top of the ladder sits
   above μ 1150. We can characterise the gap precisely (closure 79.9%, own
   turns 7.63 vs the envelope's 6.1) but we did not close it.
2. **Mirror self-play systematically overstates ladder strength by ~2× for us**
   (0.4574 self-play → 0.2370 ladder on the same build). Every self-play number
   in this document should be read as an upper bound.
3. **The ladder-observational comparison in §5.3 is not a controlled A/B** —
   different opponent pools, n < 60 per side.
4. **The governor coupling in §3.9 is not fully separable.** We made it
   observable, not solved.
5. **Envelope closure is validated on six archetypes, not proven in general.**
   It correctly predicts every failure we have on record, which is evidence, not
   proof.
6. **Some early cluster-level matchup claims rest on n ≤ 14** and should be read
   as direction only; our formal gates all comply with n ≥ 300.

---

## 7b. Material read after the first draft — findings that changed the report

The first version of this document was built from a subset of the project's
records. A full pass over every file surfaced six evidence sets that changed it,
recorded here because the omission is itself a methodological point.

**1. The closure sweep was five decks, not three, and one number was wrong.**
The first draft estimated Kangaskhan at "~48% closure, envelope ~0.60"; measured
values are **45.0% and 0.6729**. TR Mewtwo and Fezandipiti were absent entirely.
The high-envelope/low-closure finding (§4.6 ii) only exists once all five are in
the same table — it was invisible in the subset.

**2. The deck-transfer control existed and was stronger than anything in the
draft** (§4.7). Running our agent on a strong player's own list, and finding our
own rules made it *worse*, is the single most direct evidence for the thesis.

**3. The passivity had a measured cause.** Of 261 own turns in a ladder audit,
97 ended in ATTACK and **164 ended in END**. Of those 164, **94 (57.3%) still
had a development option on the menu** — split **32 in wins, 62 in losses**.
Since the heuristic scores END at −1,000,000 it would *never* choose END while
anything else existed: every one of those 94 was the **search overriding the
heuristic to pass**. The same pathology measures **46.3% at a 400-step rollout
cap and 0.0% with search disabled** — it is caused by search, not tuning.

**4. A formal search-adequacy diagnostic had been run** (§3.4 addendum below).

**5. Our worst matchup is not a decision problem.** Damage-log accounting over
100 games per matchup: damage dealt **26,470 vs 26,850**, attacks **372 vs 365**
— unchanged versus the mirror — and we *take less* damage. Prizes/game 3.04 vs
3.60. The opposing roster is bulkier (16 of 17 non-energy Pokémon slots are
ex/Mega), so identical output buys fewer knockouts. **No targeting or sequencing
rule addresses a raw damage/HP mismatch.**

**6. The field independently confirmed our search verdict.** Across two
snapshots, **9 of 10 top teams decide in 28–136 ms**. The single search-class
agent (~1.5 s/decision) fell **#1 → #3**, with the worst attrition record in the
pool (**34 of 45 losses by deckout**). Meanwhile two *different* top-10 teams
piloted the same archetype we shipped at μ697 — one at **36 ms (μ1147.8)**, one
at **1208 ms (μ1119.6)**. Same deck, opposite architectures, both far above us:
architecture class is not the constraint; per-decision quality is.

### 3.4 addendum — the search-adequacy diagnostic

Instrumented run over **7,398 searched decisions / 80 games**, with a
pre-registered decision rule and grounding in the imperfect-information search
literature (strategy fusion / non-locality; ISMCTS).

A measurement artifact was caught **before** the run: in 65% of determinizations
every candidate returned an identical value, so the recorded "argmax" was the
instrumentation's own index tie-break. Naive agreement read **0.938**;
excluding non-discriminating worlds gave **0.667**. The naive figure would have
landed in the "do not rebuild" band on an artifact.

Verdict via the pre-registered rule: contested median **0.667** → inconclusive
band → tie-broken on belief entropy, which stays at **4.78–5.25 bits
(perplexity 38–48) through the game-deciding turns 12–24** and *rises* after
turn 8 → **SEVERE**.

But the same diagnostic bounded its own recommendation: **46.8% of searched
decisions have no discriminating determinization at all.** Restructuring how
information sets are aggregated cannot create discrimination between actions a
terminal-valued rollout scores identically. **Signal poverty, not strategy
fusion, is the larger effect** — and it retro-explains four prior null results
as components that altered values which were ties anyway.

**No rewrite was started.** The finding that mattered for shipping was simpler:
search was net-negative on both decks it was measured on.

## 8. What we would tell the next team

1. **Measure deck–pilot fit before you measure anything else.** Twenty minutes
   of mirror self-play against a harvested envelope predicts whether a deck is
   pilotable by your agent. We spent weeks learning this the expensive way.
2. **A gate whose opponent is yourself cannot see a weakness you share.** This
   cost us 66 ladder points in one submission.
3. **Never trust an offline proxy.** Four separate artifacts passed their
   offline metric and failed head-to-head, three of them badly.
4. **Mirror self-play is blind to strictly-dominated improvements.** If a fix
   helps both sides equally, the mirror shows nothing. Screen cross-deck.
5. **Pre-register the read rule, then honour it when the argument to break it is
   *strong*.** Rules that only bind when the counter-argument is weak are
   decoration. We killed a component whose point estimate was positive and whose
   mechanism story was correct, because the CI said no.
6. **A rule that did not fire has not been tested.** Every rule ships with a
   fire counter.
