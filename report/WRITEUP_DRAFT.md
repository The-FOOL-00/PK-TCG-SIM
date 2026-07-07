# Strategy report — DRAFT skeleton

> **HARD LIMIT: < 2000 words.** Rubric-mapped; every claim carries an n and a
> CI or is flagged TODO. Figures produced at final edit (list in §5).

---

## 1. Approach & rationale (Model Score: clarity, originality)

- Deterministic heuristic agent (`ptcg-heuristic-v1.0.0`), pure stdlib at
  runtime, no engine dependency in the bundle; every candidate improvement is
  developed behind a feature flag and only ships after a statistical gate.
- Ladder-validated baseline: μ ≈ 600 (leaderboard median 674, top-20 cutoff
  1054, 4,500 teams as of 2026-07-07).
- Improvement ladder (rungs): (a) learned value model trained on self-play
  outcomes → (b) search distillation from `cg.api.search_begin` into a
  <100k-param option-scoring net. Analytic v3 evaluator was the non-learned
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
