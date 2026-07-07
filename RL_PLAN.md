# RL groundwork plan (WS3 — design only, no training)

Written 2026-07-07 against the actual cabt API (`cg/api.py` dataclasses, verified
observations from kaggle-environments 1.30.1) and throughput measured on this
machine. Nothing here is implemented; waiting for go.

## 1. State encoding: fixed-size vector from `Observation.current`

Card-ID-free per-Pokémon features (generalize to any opponent deck; the engine
DB has 1,267 cards, so one-hot card IDs are out). All features scaled to ~[0, 1].

**Per-Pokémon slot** — 12 slots: my active, my bench ×5, opp active, opp bench ×5
(bench padded with zeros to `benchMax`=5). 11 features per slot:

| feature | source | scale |
|---|---|---|
| present | slot occupied | {0,1} |
| hp | `Pokemon.hp` | /350 |
| maxHp | `Pokemon.maxHp` | /350 |
| damage taken | maxHp − hp | /350 |
| energy attached | `len(energies)` | /5 |
| is_ex / is_megaEx | card db | {0,1} ×2 |
| best attack damage | card db, static | /400 |
| energy still needed for best attack | cost − attached, clipped ≥0 | /4 |
| retreat cost | card db | /4 |
| weakness matches opposing active's type | card db | {0,1} |

12 × 11 = **132**

**Globals (23):** turn/20; my/opp prizes remaining /6 (2); my/opp deckCount /60
(2); my hand count /10; opp handCount /10; my/opp discard basic-energy count /35
(2); `supporterPlayed`, `energyAttached`, `retreated` flags (3); active special
conditions both sides (poisoned/burned/asleep/paralyzed/confused ×2 = 10 —
available as `PlayerState` booleans); `firstPlayer==yourIndex` (1).

**My hand as card-ID multiset (15):** counts/4 over OUR deck's ≤15 distinct card
IDs. Our own hand is fully visible and our deck list is fixed, so an exact
multiset is cheap and only needed for our side.

**Total ≈ 132 + 23 + 15 = 170 dims.** Encoder is pure feature extraction from
`Observation.current` + the baked `card_data.json` — no engine calls, stdlib-safe.

## 2. Action space: score-each-option (recommended) vs fixed taxonomy

Options lists are variable-length and heterogeneous (17 `OptionType`s ×
~30 `SelectContext`s; MAIN turns see 5–25 options, card-pick phases up to ~60).

- **(a) (state, option-features) scoring network** — embed the state once per
  decision, score each option with a shared MLP head:
  `score = MLP(state_emb ⊕ option_features)`. Option features (~45 dims):
  OptionType one-hot (17), SelectContext bucket one-hot (~12), target-slot
  features (the 11-dim block above for `area`/`index`/`inPlayArea`), estimated
  attack damage /400, KO-if-used flag, card value of the referenced card.
- **(b) fixed action taxonomy** — enumerate (type × target-bucket) cells with
  masking. Breaks on card-pick contexts (deck/discard selections have no stable
  cell identity) and wastes capacity on cells that never co-occur.

**Recommendation: (a).** It is a drop-in replacement for `_score_option` —
`resolve_selection`, multi-select handling (`minCount`/`maxCount`, score>0
padding), C1 validation and the fallback path all stay exactly as shipped.
Multi-select keeps the existing semantics: score options independently, take
top-k. This also means the RL net and the heuristic can be A/B'd per phase.

## 3. Self-play throughput on this machine (measured 2026-07-07)

`tools/throughput_bench.py`, v1 heuristic both sides, 12 logical cores
(measurement ran while a tuning job used ~1 core, so these are conservative):

| workers | games/min | games/s |
|---|---|---|
| 1 | 510 | 8.5 |
| 4 | 636 | 10.6 |
| 8 | **845** | 14.1 |

Clean-machine estimate ~1,000/min at 8 workers. Note: heuristic decisions are
~0.03 ms; an MLP policy at ~1 ms/decision × ~35 decisions/game adds ~4% — the
engine dominates. Budgets at 845/min: **~50k games/hour, ~1.2M games/day.**
**Verdict: local training is viable** for rungs (a) and (b) below; even PPO's
typical 1–5M-game appetite fits in days, not weeks. Cloud not required.

## 4. Inference budget on Kaggle (CPU-only, 2 vCPU)

- Hard limits: `remainingOverageTime` = 600 s per player per game, `actTimeout`
  = 0 → effectively ~17 s/decision available; our internal target stays
  ≤50 ms/decision to leave room for sampling/rollouts later.
- **UNCONFIRMED:** whether the Kaggle cabt image ships numpy. Very likely (the
  `kaggle_environments` package itself imports numpy), but record the check at
  our next Validation Episode before shipping any .npz-dependent bundle.
- Proposed net: MLP **170 → 128 → 64 → shared 64-dim state embedding**, option
  head **(64+45) → 64 → 1** ≈ 40k params. Weights as `.npz` in the bundle
  (~160 KB), inference = 2 numpy matmuls per decision batched over options →
  well under 1 ms.
- Numpy-absent fallback: distill to 170→32 + (32+45)→1 (~7k params) with
  weights as Python lists baked into a `.py`; pure-python matmul ≈ a few ms per
  option batch — still far inside budget. Either way the bundle stays DLL-free.

## 5. Training approaches ranked (≈4-week window), lowest risk first

1. **(a) Learn `evaluate_state` / option-score weights from self-play outcomes**
   — logistic regression (or 1-hidden-layer MLP) on (state features, eventual
   win) pairs; plug the learned value into the existing v3 tier structure.
   Cost: hours. Risk: minimal (falls back to hand weights). Payoff: moderate —
   replaces 6 hand-tuned weights with ~170 fitted ones and end-to-end tests the
   whole pipeline (encoder → training → bundle → A/B harness).
2. **(b) Policy distillation from deeper search** — locally, use
   `cg.api.search_begin/search_step` (cg.dll) as a teacher: determinize hidden
   info (sample opponent hand/deck/prizes consistent with observed counts,
   which `search_begin` requires as explicit predictions), run short
   expectimax/MCTS, imitate the improved policy with the §2 network. Runtime
   ships only the student net — DLL-free. Risk: medium (search plumbing,
   determinization quality). Payoff: high — this is where play strength beyond
   1-ply comes from.
3. **(c) Full policy-gradient/PPO self-play** — highest variance: sparse
   ±1 reward, self-play collapse risk, hyperparameter search on a single
   machine. Throughput says it's *feasible*, but at 4 weeks it competes with
   (b) for time while being strictly riskier.

**Recommended starting rung: (a) now, (b) as the main event, (c) only if (b)
plateaus early.** (a)'s dataset (self-play games with per-decision state
features + outcome) is also exactly the imitation buffer (b) needs, so no work
is thrown away.

## Known constraints carried over

- Bundle must stay DLL-free at runtime; `cg/` is local-tooling only
  ([[cabt-engine-contract]]: exec/no-`__file__` load, INVALID = instant loss).
- The C1 validation / `resolve_selection` / fallback guarantees in `main.py`
  wrap ANY policy — the RL net only ever replaces `_score_option`.
- WS2's mirror-tuning lesson applies to training too: the old deck + v1 policy
  are co-adapted; evaluate candidate policies against a *pool* (v1 policy, v3
  policy, random) rather than a single opponent to avoid overfitting the mirror.
