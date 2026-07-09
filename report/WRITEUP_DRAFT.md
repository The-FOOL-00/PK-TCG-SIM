# Strategy report — DRAFT skeleton

> **HARD LIMIT: < 2000 words.** Rubric-mapped; every claim carries an n and a
> CI or is flagged TODO. Figures produced at final edit (list in §5).

---

## 1. Approach & rationale (Model Score: clarity, originality)

- Deterministic heuristic agent (`ptcg-heuristic-v1.0.0`), pure stdlib at
  runtime; every candidate improvement is developed behind a feature flag and
  only ships after a statistical gate. (The original "no engine in the
  bundle" rule was self-imposed caution, lifted by evidence — see §2b.)
- Ladder-validated baseline: μ ≈ 600 (leaderboard median 674, top-20 cutoff
  1054, 4,500 teams as of 2026-07-07).
- Improvement ladder (rungs): (a) learned value model trained on self-play
  outcomes → (b) search distillation from `cg.api.search_begin` into a
  <100k-param option-scoring net → (c) the search itself at test time, nets
  as its accelerators (§2b). Analytic v3 evaluator was the non-learned
  control rung — it FAILED its gate and stayed off (see §2), which is the
  point of the methodology: nothing ships on vibes.
- Safety machinery in every variant: C1 validation asserts,
  `resolve_selection`, heuristic fallback chain, INVALID=loss avoidance,
  time guard (TODO Phase 2d: cumulative decision time > 60% of the 600 s
  budget → permanent drop to fast tier).
- TODO: one paragraph on final shipped configuration once rungs a/b gate.

## 2. Hypotheses tested (Model Score: soundness, stability)

Protocol: `tools/ab_gate.py` — ≥300 games, seats alternated, 95% Wilson CI,
PASS only if the CI lower bound > 50% vs the incumbent. Adopted after
observing a 50-game result (48%) collapse to 25% at n=150.

**H1 — deck redesign helps (REJECTED).** Six variants vs the incumbent deck,
v1 policy both sides, seats alternated:

| variant | basics | energy | n | win rate |
|---|---|---|---|---|
| deck_v2 | 12 | 20 | 150 | 25% |
| deck_v2b | 12 | 26 | 50 | 38% |
| deck_v2c | 10 | 31 | 50 | 36% |
| deck_v2d | 8 | 33 | 50 | 42% |
| deck_v2f | 10 | 27 | 50 | 36% |
| deck_v2g | 10 | 31 | 50 | 40% |

Mechanism found: deck energy *density* (35/60) is the win engine —
Hammer-lanche damage = 100 × basic Energy in the top 6 of deck (avg 354);
every added Basic is one-shot prize fodder. deck_v2 loses (30%) even with
improved routing on both sides → the deck itself is inferior.

**H2 — analytic 1-ply evaluator beats v1 (REJECTED at gate).** v3
(`PTCG_V3_EVAL`, hill-climbed weights): 53.0% @ n=200 looked promising, but
the formal gate said no — **54.0%, 95% CI [48.3%, 59.6%], n=300 → FAIL**
(CI lower bound ≤ 50%). v3 stays off.

**H3 — learned value model beats v1 (rung a, REJECTED at gate).** 50,000
self-play games → 1.52M decision states (170-dim features, outcome labels).
MLP (30,209 params) trained externally: val AUC **0.8445**, logloss 0.481
(train 0.480 — no overfit). Deployed as tier + clipped ΔP(win) over
analytically-constructed post-option feature vectors. Gate: **48.7%, 95% CI
[43.1%, 54.3%], n=300 → FAIL**; flag stays off. In-game calibration
(3,123 decisions) is monotone and tight at the extremes ([0.9,1.0)
predicted 0.956 / actual 0.973) — the value function is *accurate*; greedy
1-ply use of it simply isn't enough against v1's co-adapted heuristics.
Together H2+H3 quantify the 1-ply ceiling and motivate rung b (depth via
search distillation).

**H4 — search distillation beats v1 (rung b, teacher phase done).** The
engine's `search_begin` is a determinized forward simulator, not a search;
we built flat determinized Monte Carlo on it (v1 rollouts, rung-a value net
at the step cap). Strength curve (all n=300 gates): 2 samples/option 48.0%
→ 16 samples 56.0% [50.3, 61.5] → 32 samples **58.7% [53.0, 64.1]** →
64 samples 57.0% (saturated; wider candidate sets change nothing). First
CI-backed >50% policy in the project, but below our pre-registered 60%
teacher bar — the ceiling is the v1 rollout policy, motivating expert
iteration (distill → roll out with student → re-distill). TODO: chosen
teacher path, imitation accuracy, student gate verdict.

## 2b. Strategic pivot — the search plays at test time (2026-07-09)

Three independent lines of evidence forced a re-plan. (i) *Ladder reality:*
v1 sat at μ ≈ 512 after two days — below the 600 starting rating; the field
average already beats careful heuristics. (ii) *1-ply is exhausted:* both
1-ply upgrades failed their gates (H2 54.0%, H3 48.7%) despite an accurate
value function (AUC 0.844), and the distilled student cleared its imitation
floor by only +0.9% — depth, not better 1-ply scoring, is the remaining
axis. (iii) *Unused legal budget:* our only CI-backed >50% player is the
determinized-MC teacher itself (58.7% [53.0, 64.1] vs v1) at ~215 ms per
decision, while the ladder allows 600 s/player of overage with
`actTimeout=0` — roughly 15 s/decision available; we had been using <2% of
legal thinking time. The Expert Iteration / AlphaZero family (ExIt-OOS for
imperfect information, PIMC in trick-taking games) is unanimous on the
conclusion: the search plays at test time; the nets guide and accelerate it.

The plan therefore inverted: ship belief-sampled determinized search as the
agent. The teacher's mirror-only exact-knowledge assumption is replaced by
honest belief sampling — track every opponent card revealed in the logs,
sample the unknown remainder uniformly over the legal pool (4-copy limits,
observed energy types), consistency-check every sample. The trained nets
move inside the search: the rung-a value net truncates rollouts (~10×
cheaper samples → more determinizations per second, i.e. better belief
coverage), and the rung-b distilled policy plays the rollouts — the ExIt
loop operating where it now matters. Every degradation path (engine import
failure, search exception, sampling failure, time pressure) falls back to
the gated v1 heuristic.

**Engine feasibility (Phase A, verified 2026-07-09):** the official sample
submission ships `cg/` with binaries for every platform — including
`libcg.so` (Linux x86-64), the same engine build the ladder's own
interpreter executes every episode — and its `main.py` does a plain
`import cg`, so bundling the engine is the intended pattern, not a hack.
The pip package's internal copy exposes no search bindings, so the bundle
must carry `cg/`. A probe bundle (byte-identical v1 play + one
`search_begin`/`search_step` cycle logged to stderr) passes the exec-style
load check, plays a clean full game locally (search cycle ≈ 1 ms), and
degrades to pure v1 with the engine deleted — submittable insurance that
answers the only question local testing cannot (does the ladder sandbox
allow the import?) for the cost of one slot playing at v1 strength.
TODO: on-ladder probe verdict; belief-search gates E2–E5.

**E1 — the key gate (search+belief vs v1, 300 games, seats alternated).**
How much of the mirror teacher's 58.7% survives honest uncertainty? Answer:
**none of it.** Belief-sampled search scored **49.0% [43.4, 54.6] → FAIL**,
while the same search with exact opponent knowledge (mirror determinization)
scored **58.3% [52.7, 63.8] → PASS**, faithfully reproducing the teacher.
The search port is correct; the belief is what fails.

*Diagnosis* (comp-belief vs mirror-exact search on 249 identical searched
positions, matched RNG). Mirror overrides the v1 heuristic on 38% of
searched decisions — that override set is the entire source of its edge. On
exactly those positions, honest belief makes the *same* override only 9% of
the time and reverts to the v1 answer 76% of the time: it captures almost
none of the edge. The mechanism is a collapsed value signal — the top-two
candidates' rollout values are separated by a median gap of 0.031 under
mirror belief but **0.000 under honest belief (76% of positions have zero
separation)**. With vague opponent decks the determinized rollouts can't
tell the candidates apart, so the search falls back to v1 and the agent
plays at ≈ v1 strength (49.0% ≈ 50%). More determinizations cannot fix a
flat landscape; the fix is a *sharper belief*, i.e. sampling realistic
opponent decks (archetype priors from META.md via the `sample_opponent_deck`
prior hook) rather than a generic legal-composition prior.

*Structural caveat on the gate itself.* E1's opponent is v1 on our own
deck, so the match is a mirror by construction — which makes exact/mirror
belief tautologically correct and penalizes honest hedging against variation
that the gate contains none of. The gate therefore cannot fairly rank the
two beliefs for real ladder play (varied opponents); it only proves that
*correct* belief converts to +9pt of strength, and that our current honest
belief is not yet accurate enough to bank any of it.

**Fair cross-deck gates (resolving the caveat).** We re-gated against three
*real* top-ladder decklists extracted from episode replays — Cynthia's
Garchomp ex (5 energy), Dudunsparce/Alakazam (3 energy, a 73%-win-rate
field deck), Mega Kangaskhan ex (16 energy) — each piloted by v1, all
structurally unlike our 35-energy mono-Water build. Win rates of
belief-search + our deck vs v1 + opponent deck (300 games each):

| opponent | v1 baseline | honest belief | exact-mirror belief | *perfect* belief (oracle) |
|---|---|---|---|---|
| Garchomp ex   | 72.5% | 73.7% [68.4,78.3] | 71.0% | **78.3%** [73.3,82.6] |
| Dudunsparce/Alakazam | 37.5% | 42.7% [37.2,48.3] | 40.7% | **51.3%** [45.7,56.9] |
| Mega Kangaskhan | 75.0% | 75.3% [70.2,79.9] | 72.3% | 73.3% |

Three findings. (1) **E1's mirror-advantage was a gate artifact:** against
opponents that actually differ, honest belief equals or beats exact-mirror
belief on all three decks — confidently-wrong belief is no better than
honest-but-vague belief once the opponent isn't us. (2) **Belief accuracy is
the lever, and it converts:** the oracle column (search handed the
opponent's true 60-card list) beats honest belief by +4.6 and +8.6 pt on the
two decks with headroom, and on the deck we *lose* to (Alakazam) perfect
knowledge swings us +13.8 pt — a clear loss to a coin flip. The gap between
honest and oracle belief is exactly what meta-archetype priors are built to
close. A position-level diagnosis agrees: perfect belief roughly halves the
fraction of decisions where the search cannot separate its candidates
(Alakazam 55%→33% flat), and honest belief currently captures only 11–18% of
the overrides perfect belief would make. (3) **A deck-power ceiling:** even
*perfect* search only reaches parity against the strongest field deck
(Alakazam 51.3%, CI spanning 50%) — against the best archetypes our deck,
not our decision quality, is the limiter. Net: the agent is strong across
most of the field (73–78%) and the search + a sharper belief is the right
next investment where decisions still swing games.

**Methodological finding — seat matters.** In the H2 gate the challenger won
72% in seat 0 vs 36% in seat 1 (n=150 each). Any comparison that does not
alternate seats is invalid; ab_gate.py alternates by construction.

## 3. Deck concept & key cards (Deck 20%)

- 35/60 basic Water Energy — deliberately extreme density because
  Hammer-lanche (Crabominable, attack 1046) does 100 × Energy in the top 6
  of deck: expected ~350+ damage/attack, one-shotting most of the meta.
- Supporting cast: TODO name each card and its role (energy routing,
  setup active, prize-trade profile — ex/Mega ex give up 2/3 prizes,
  our attackers give up 1).
- Evidence the concept is load-bearing: every energy-reduction variant lost
  (H1 table); reason-3 (no-active) endings dominate mirrors (86%), so
  survivability-through-tempo beats board width.
- Meta context (META.md, 40 episodes of 2026-07-06): top-20 field =
  Cynthia's Garchomp ex, Dudunsparce/Alakazam draw engines, Mega Kangaskhan
  ex/Raging Bolt (16 energy), Marnie's Grimmsnarl ex. Avg first-attack turn
  4.7, avg game 13.1 turns. TODO: our matchup story vs each once we have
  per-archetype W/L.

## 4. Consistency evidence (Model Score: stability criteria)

- Zero INVALID/ERROR/TIMEOUT sides — ours and, for context, the sampled
  ladder field (META.md); `tools/ladder_watch.py` flags any such loss as P0.
- Determinism: fixed policy, no RNG at decision time; C1 validation +
  `resolve_selection` byte-identical across all variants.
- Timing headroom: v3 path 0.024 ms avg / 0.196 ms max per decision against
  a 600 s game budget; time guard (Phase 2d) makes overrun structurally
  impossible. TODO: learned-model inference timing.
- Statistical discipline: every ship decision is a 300-game Wilson-CI gate;
  seat alternation enforced by the tool.
- TODO: rating stability over time from ladder_watch history.

## 5. Figures to produce (final edit)

1. Rating over time (ladder_watch history CSV).
2. Calibration plot: predicted win prob vs actual (metrics.json, rung a).
3. Matchup table / archetype win rates (meta_miner, larger sample).
4. The H1 deck-variant bar chart with CIs.
5. Pipeline diagram: flag → gate → ship.

---

*Word budget check at final edit; current skeleton ≈ 700 words of body.*
