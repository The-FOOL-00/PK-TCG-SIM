# DECISION MEMO — 2026-07-21: path selection after the capacity ladder + Sanjay's Jul 13–20 arc

Inputs: `SANJAY_CONTEXT_JUL20.md` (read in full; reconciliation banked in
`stage4/writeup_notes.md` §6), Phase-B ladder refresh
(`analysis/phase2_meta_shift/roster_diff_jul21.md`, 277 fresh top-10 replays +
60 of our own), our capacity-ladder record (run1/run2/run3), and the verified
calendar: **train-stop Aug 12, internal freeze Aug 14, submission lock Aug 16**
(user-verified; Sanjay's docs still say Aug 14 — reconfirm with him, item R5).

## 0. Decision

**Portfolio: Path 3 primary (our policy nets inside his search shell) +
Path 1 as unattended lab background (finish run3 to verdict) + Path 5 as the
floor (v7-881 / v2.2.0 ship, writeup absorbs everything from ~Aug 8).**
Path 2 (Gumbel-AZ) is dropped-with-cause; Path 4 (BC-v3) survives only as
Path 3's stage-2 feeder, never as a standalone ship.

Nothing here is implemented yet — this memo stops at the decision per
instruction.

## 1. Where the two tracks actually stand (cross-referenced)

| asset | number | status |
|---|---|---|
| His v7 search agent (Trevenant, sub 54855847) | **μ877.8 settled, n=61** | holds team slot 1; the team's live score |
| His v8 (promotion rule, sub 54863817) | 723.3 at ~n=45, still converging | holds team slot 2; verdict window open |
| Our v2.2.0 BC (Garchomp) | μ697 frozen, displaced | resubmittable floor |
| Our PPO run1 (27.8k) | flat **27.1%** vs v2.2.0, capacity-limited high-conf | closed |
| Our PPO run2 (128k) | flat **27.6%**, capacity-limited high-conf | closed |
| Our PPO run3 (256k) | flat **28.1%** at ~iter 256; kl_anchor still climbing; `verdict.py` = **CONTINUE** | paused, unresolved |
| Current ladder top | Grimmsnarl/Munkidori ×4 incl. #1 Oshbocker; **2 search-class agents in top 5**, one piloting OUR Garchomp archetype at μ1152 | fresh 07-21 harvest |

The capacity ladder's own arithmetic: 4.6× params bought +0.5 pt, another 2×
bought +0.5 pt. Whatever the 256k verdict ends up saying, the reactive
single-forward policy class is not closing a 27→55% gap on this evidence.
Meanwhile his shell — the team's only artifact anyone has improved this month
(+114 Elo from one correctness fix) — has an explicitly documented, never-fired
learned-model hook and a §7 request for exactly the model class we own.

## 2. Path evaluations

### Path 1 — resume run3 (256k PPO) to its verdict
- **Expected μ:** none directly. 28.1% ≠ a shippable gate (needs 55–60%); the
  realistic best case for the KL-still-climbing tail is +1–3 pts, i.e. still
  ~30%. This path cannot produce a challenger.
- **Wall-clock:** ~1 lab overnight (≈14.5k games/h → asymptote + verdict).
  Zero engineer-hours beyond launch/collect.
- **Lab-dependency:** the only path that needs one; flexible any lab day
  through ~Aug 6.
- **Risk:** none operational; pure opportunity cost of a lab night.
- **Writeup value:** HIGH per hour — it completes the pre-registered K2
  capacity protocol cleanly ("all three rungs run to verdict, all flat")
  instead of leaving the last rung mid-air. Our methodology chapter is the
  poorer for an unresolved pre-registered gate.
- **Call:** run it in the background on the next lab day. If no lab day
  materializes by Aug 6, record honestly: "256k CONTINUE-at-stop; resolved
  flat at 27.8k/128k" — acceptable, not preferred.

### Path 2 — Gumbel-AZ from scratch — DROPPED (with cause)
- **Expected μ:** P(ships something > 881 by Aug 12) ≈ 10–15%. First loop
  ~Jul 26–27 at the scoped 4–5 build days, leaving one training window with
  zero re-run slack against the Aug 12 train-stop — precisely the
  ship-v2.2.0-instead condition already flagged in `gumbel_az_scoping.md`.
- **The redundancy argument (new since scoping):** its formal trigger (both
  128k and 256k capacity-limited) is not yet fired (run3 = CONTINUE), but even
  when/if it fires, the pivot's premise — "the next lever is decision-time
  search over determinized hidden state" — is now **already satisfied by the
  team's other stack**: his shell IS a validated, deployment-hardened,
  μ881 determinized search. Building a second search from scratch in 4–5 days
  to maybe match what the team already fields is dominated by improving the
  existing one (Path 3) on every axis: cost, risk, calendar, and writeup.
- **His negative search+learning evidence** (AZ prior-collapse; value net
  −82 Elo signal-shape; BC priors harmful in-tree) doesn't kill search — his
  own agent is search — but it does say search-*training* loops have eaten two
  teams' weeks without a positive. We keep the scoping note for the record and
  close the branch.

### Path 3 ⭐ — SYNTHESIS: our identity-aware nets inside his search shell (PRIMARY)
The one experiment neither stack can run alone, and the one he explicitly
asked for (§7 item 3: learned in-tree opponent model / rollout policy fit to
the top-1000 replays, expected to beat his hand-written stub).

**Why the priors favor it:**
- His single biggest measured jump is exactly this lever's class: rollout
  policy random → competent hand-stub = **0.20 → 0.60** vs strong_800.
- His attempt at the learned version failed with a diagnosed cause — 7-dim
  identity-blind card features (top-1 0.388, cannot tell Abra from Alakazam)
  — which our encoder does not have (deck-identity tables, two heads, top-1
  68.9%/76.1%). repo1 independently: "the bottleneck is FEATURES, not rows."
- Honest counterweight: "learned beats hand-stub" is unproven; from-competent
  deltas are far smaller than from-random; and his §6i finding (96% of
  rollouts scored by `_hand_eval` at ~3 turns) means rollout-policy quality
  has bounded influence per rollout. This is a real experiment, not a
  formality.

**Latency budget (measured today, not estimated):** `encode_state` 51.6 µs +
trunk forward 9.3 µs (3.9 µs batched); full decision with heads ≈ **60–80 µs**
— inside the <100 µs budget his value net passed at 24.7 µs.
- As **node-expansion prior / opponent-model at expansion** (his POLICY_NET
  blend hook): few hundred calls/decision ≈ 10–30 ms of his 1.3–2 s budget
  (~2%) — comfortably affordable.
- As **every-rollout-step policy**: ~5k calls/decision ≈ 350 ms ≈ 20–25% of
  budget → ~20% fewer visits. Borderline; testable (gate G-S0 below); fallback
  is expansion-prior-only or top-k gating (net ranks the option list once per
  node, hand rules break ties).

**The deck-identity constraint (the main engineering fact):** our weights are
deck-specific (list-0 Alakazam; hand-count block keyed to our deck.csv).
Therefore stage 1 targets **his `submission_alakazam` package** — the deck
family our nets already know, zero new training. His v7 ladder build is
Trevenant; porting the synthesis to it requires a stage-2 retrain (Path 4
machinery) on a fresh teacher harvest. Both staged below. As an in-tree
OPPONENT model our current ST_CARD head degrades off-deck (unknown-slot
one-hot) — full opponent-model generality is stage 2+, per-archetype nets
selected by his belief system (which IDs archetypes at ~90%).

**Hosting:** his repo hosts the experiment (the shell, harness, and ladder
slots are his); our repo ships the weights + a frozen copy of the adapter.
Both repos record the A/B logs.

**A/B design (pre-registered, his shard pattern):** one variable —
`POLICY_NET` on/off, identical package otherwise. n=400 (10 shards × 40,
PTCG_BUDGET=0.15, disjoint seeds), null control armed (his §6j lesson), arena
outcomes only — no action-flip metrics (his measured 40–42% nondeterminism
noise floor makes them unusable unless he has since fixed the engine-state
carryover; ask R4).

- **Expected μ:** floor 878 (nothing adopted; v7 rides — the gate structure
  makes shipping a regression nearly impossible). Central-if-adopted 900–950.
  Tail ~980–1000 if rollout + opponent-model both land. Capped: rollout
  quality does not fix weakness-structure matchups (his Grimmsnarl 0W–5L is
  typed, not tactical). P(some adopted improvement) ≈ 35–45%.
- **Wall-clock:** 1–2 days integration + ~1 day staged A/Bs (his 12-core
  arena ≈ 20–40 min per 400-game test); stage-2 retrain +1–2 days if taken.
- **Lab-dependency:** **none** — this is why it coexists with Path 1.
- **Risk:** low and bounded — offline-gated, ships only through his slot
  after beating the battery; worst case is a clean negative result.
- **Writeup value:** the marquee chapter either way. A pre-registered,
  one-variable, two-team synthesis where the second team's validated
  diagnosis (features) is the first team's validated fix — positive or
  negative, it is the strongest single piece of methodology evidence we have.

### Path 4 — targeted BC-v3 on the behavioral gap — feeder only
- The target is real and now measured from two independent instruments: his
  §6n (ability-when-legal 88% vs 61%, hand T5 10.3 vs 7.0, first Alakazam
  T4.7 vs 7.9) and our fresh harvest (attack-share 0.24 vs top-10 0.46–0.64,
  hand ~4.3 vs 5.5–9.3, extra-draws 2.1/turn vs 2.2–4.6). His failed rule
  (-6.5 pts, n=400) proves rate-forcing can't fix it; sequencing must be
  learned in context.
- **As a standalone fast-policy ship: killed on priors.** Two consecutive BC
  head-to-head kills (G6 44.7%, G7a 39.0%) with the diagnosed residual —
  compounding error off the expert distribution — untouched by better data
  weighting. P(passes a ship gate) < 10%. We do not spend the calendar on a
  third attempt at a dead gate.
- **As Path 3's stage 2: this is where it earns.** Retrain/fine-tune on the
  fresh top-1000 harvests (Phase B located them: Yushin 54773249 = 1000 eps,
  junlee789 54775633 = 1000, jiatu.l 779, 齐乐 639 — ids already in
  `_episodes_meta.json`) for whichever deck his shell ships, weighted toward
  the 300+HP-matchup and sequencing decisions (his 599-game subset + ours).
  Inside the shell, compounding error is bounded by search (the net proposes,
  rollouts and the engine dispose) — the exact failure mode that killed BC
  standalone is the one a search wrapper mitigates. 1–2 laptop days, no lab.

### Path 5 — hold and write (the floor, not a fork)
- Ship = his 881 (+v8 if its window resolves above it) with v2.2.0
  resubmittable. All paths above feed the Strategy writeup; from **Aug 8**
  writing becomes the primary activity regardless of Path 3's state.
- What the writeup gains per path: Path 1 closes the pre-registered ladder
  (cheap, high value/hour). Path 3 adds the two-team synthesis chapter —
  its *negative* form ("we removed his diagnosed cause and the learned model
  still didn't beat the hand stub") is itself a strong result. Path 2 adds
  nothing unless it wins (a half-built second search is a worse chapter than
  a finished A/B). Path 4 standalone would add a third BC kill — redundant;
  we already have two.
- Already-banked chapter assets (writeup_notes §6): piloting-not-deck
  replicated 4 ways across two stacks + the live ladder; the BC features
  contrast (necessary-not-sufficient composition); proxy-objective failure
  ×4; deployment-integrity contrast; correctness-beats-strategy quantified.

## 3. Timeline to Aug 14 (lab days marked ◆; all dates 2026)

| date | work | notes |
|---|---|---|
| **Jul 21** (today) | Memo done; user sends asks R1–R6 to Sanjay | blocking item is repo access + hook spec |
| Jul 22 | Speculative build while waiting: adapter stub (our npz contract → his `policy_net.py` interface, from CONTEXT.md's description); bulk-fetch full teacher harvests (Yushin/junlee789/齐乐) for stage 2 | no lab |
| Jul 23 | Integration day 1: net into his shell (expansion-prior placement first), G-S0 latency/integrity check, smoke 20 | needs his repo by here; slips day-for-day with access |
| Jul 24 | Placement variants (rollout-step vs prior-only), null-control run, shard scripts staged | |
| Jul 25–26 | **G-S1: pre-registered 400-game A/B** (alakazam package, POLICY_NET on/off) → adopt / one-retry / kill per §4 | his 12-core box or ours |
| Jul 27–28 | If G-S1 ≥ adopt-or-retry: stage-2 BC-v3 fine-tune on fresh teacher for HIS shipped deck (Trevenant line), re-run G-S1 on that package. If G-S1 killed: bank negative, decide stage-2 vs early-writeup with user | |
| ◆ next lab day (any, ≤Aug 6) | **run3 resume → asymptote → verdict.py**, unattended overnight; collect checkpoint + history | Path 1; one night |
| Jul 29–31 | If adopted: his offline battery on the candidate build + **his** ladder canary (his slot, his call), n≥40 before any read (variance 600–955 on identical bytes) | slot rule §5 |
| Aug 1–7 | One iteration loop max (opponent-model-per-archetype OR blend tuning — one variable at a time); v8 window resolves; keep/revert decision on v8 vs v7 | |
| **Aug 8** | Hard pivot: writeup becomes primary. Any unfinished experiment is recorded at its last gate state | pre-registered |
| Aug 8–11 | Writeup sprint: fold writeup_notes §1–6 + both teams' refutation tables into WRITEUP_DRAFT; Sanjay reviews his sections | |
| **Aug 12** | Train/experiment stop (standing). Final submission decision: challenger only if it beat the battery AND canary ≥ 881+30 settled; else v7 + best-of(v8, v2.2.0) | |
| Aug 13–14 | Ladder convergence buffer; freeze **Aug 14**; writeup final read | |
| Aug 16 | Submission lock | |

Slack: ~3 engineer-days and one battery re-run are unallocated inside
Jul 27–Aug 7 — absorbed by access delays or one extra iteration, not new scope.

## 4. Pre-registered gates & kill criteria (Path 3, standard format)

- **G-S0 (integrity/latency), before any A/B:** with the net in-tree,
  visits/decision ≥ 75% of control's on the same positions; SELFCHECK PASS;
  0 fallbacks over a 20-game smoke. FAIL → demote placement (rollout-step →
  expansion-prior → root-only); still failing at root-only → kill in-tree
  use, record, stop.
- **G-S1 (offline arena):** n=400, 10×40 shards, one variable, null control
  logged first (must read 50%±CI; if the null itself is biased, stop and
  debug the harness, not the feature). ADOPT: Wilson CI-low > 50%.
  RETRY-ONCE: 46–54% allows exactly one placement/blend change, then re-run
  is final. KILL: < 46%, or second inconclusive. No further iteration —
  his 14-hypotheses-one-win session is the cautionary base rate.
- **G-S2 (ladder canary, confirmatory only):** his slot, ≥ 40 episodes
  settled before any read. Keep if settled ≥ ~910 (881+30); revert < ~850.
  Margins are wide because byte-identical archives have scored 600–955.
- **Calendar kills:** no repo access by **Jul 25** → Path 3 degrades to
  weights-package + spec handoff for Sanjay to run solo, we shift to stage-2
  data prep + writeup. No adopted candidate by **Aug 8** → v7 rides, full
  writeup mode. (Standing: nothing trains after Aug 12; no Kaggle submission
  is ever made by the agent.)
- **Stage-2 gate (BC-v3 feeder):** held-out teacher-match ≥ current net's on
  the same split, THEN the identical G-S0/G-S1 chain on his package.
  BC-v3-as-standalone-ship: permanently killed (two prior gate kills).
- **Path 1 disposition rule:** run3 verdict is whatever `verdict.py` prints
  at asymptote — no post-hoc reinterpretation; both outcomes
  (capacity-limited / continue-but-flat) feed the same conclusion already
  drawn from run1+run2 unless winrate_incumbent exceeds **34%** (2σ above the
  flat band), which would reopen the PPO branch for a user decision.

## 5. Exact asks from Sanjay (R1–R6)

1. **R1 — Repo access** (or a tarball snapshot): `agent/mcts.py`, `main.py`,
   `vs_external.py` + `agent_worker.py`, `ablog.ps1`, the
   `submission_alakazam*` and `submission_trevenant_v8` packages, and
   `top_replays/` index files. Blocking item for Jul 23.
2. **R2 — POLICY_NET hook spec:** where the hook fires (node-expansion prior,
   rollout choice, or both), exact input it passes (raw obs dict vs
   features), output contract (per-option scores? distribution?), blend
   semantics of `VALUE_NET_WEIGHT=0.5`, and his failed `policy_net.py` as the
   interface reference. Also `policy_features.py` so we can map his call
   sites onto our `encode_options` contract.
3. **R3 — Package choice agreement:** we propose the A/B runs on
   `submission_alakazam` first (deck-matches our trained weights — zero new
   training, fastest clean signal), then port to the Trevenant v7 line via a
   stage-2 retrain only if positive. His veto/alternative welcome — it's his
   shell and his slots.
4. **R4 — Harness state:** shard conventions (seeds, PTCG_BUDGET), and the
   status of the ~40% engine-state nondeterminism (§6j) — fixed or standing?
   If standing, we run arena-outcome A/Bs only and skip all action-flip
   metrics; also ask for his null-control script.
5. **R5 — Slot + calendar coordination:** confirm v8's verdict window and
   the keep/revert rule vs v7; agree that any synthesis candidate ships
   through his slot only after G-S1 + battery; **reconfirm the deadline** —
   his docs plan to Aug 14, the user-verified lock is Aug 16 (freeze Aug 14).
6. **R6 — Data for stage 2:** the 599-game 300+HP top-player subset +
   `compare_pilot.py`, and his `decks_pool.py` archetype signatures (for
   per-archetype opponent nets selected by his belief ID later).

## 6. What was decided against, in one line each

- **Gumbel-AZ:** dominated by improving the team's existing validated search;
  calendar leaves no re-run slack; trigger not even formally fired.
- **BC-v3 standalone:** third attempt at a twice-killed gate with the killing
  cause unaddressed.
- **Deck swaps of any kind:** piloting-not-deck is now replicated four ways
  (writeup_notes §6a); junlee789 reaching #5 on our own archetype closes the
  question from the ladder side.
- **Acting on any single ladder read < 40 episodes:** both teams have now
  independently paid for this lesson; it is a standing rule, not advice.

— end of memo. No implementation begun, per instruction.
