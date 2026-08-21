# Stage 4 writeup notes (chapter-four material)

Running log of findings worth keeping for the competition writeup. Do not
edit report/WRITEUP_DRAFT.md from Stage 4 work — fold these in later.

## 1. The pathology that survived a 3× data upgrade (2026-07-12)

BC-full-Garchomp's C2 failure (self-deckout vs stall) was hypothesized in
Phase 2 to be data coverage. Phase 3 disproved that: 20% of its training diet
was anti-Crustle wins, including 7 no-active kills, and it still produced
zero no-active wins on the ladder. BC-v2 (list-0 Alakazam engine, 3× games,
2.9× sub-decisions, two pilots from ranks 1+3) reproduced the same failure
**4–5× worse**: 41–52 self-deckouts per 100 games vs a defensive opponent,
versus 10 for the Garchomp BC. Static accuracy sees nothing (Crustle-game
decision accuracy ≈ overall; prize-fetch context 96.8%): the policy knows
every individual decision and cannot execute the season-long behavior. Cause:
thin-deck states are structurally absent from win-side imitation data —
winners close by T12-15, so the states where a draw-brake matters are
precisely the states the expert never showed us. Imitation learns the
racing line superbly (C1 probe: 90% vs Lucario aggro, closure T12.5 vs the
old agent's T18) and cannot learn to STOP racing.

## 2. Local probes lie about stall, quantified (2026-07-12)

v2.2.0 scored 71% vs v1-piloted Kangaskhan/Crustle locally while going 1W-8L
vs ladder Crustle pilots — a ~60-point probe-vs-ladder gap. v1 pilots a stall
shell as a beatdown deck; the stall is the PILOT, not the list. Consequence
for methodology: win rate vs v1-piloted archetypes is not a valid anti-stall
metric; the opponent-independent signal is our own self-deckout rate. This
also forced a strengthened G7b design (Stage 4) — the standard
v1-piloted-archetype pool would have overstated anti-stall competence.
Echoes the Alakazam μ548 lesson: local pools built from our own piloting
lie about the ladder, third time this pattern has appeared.

## 3. The draw-brake decision (2026-07-12)

Chosen fix (user decision at Stop 2 boundary): inference-time draw-brake
over frozen BC-v2 weights, ablatable via PTCG_BC_BRAKE for G7c causal proof.
Trigger: own deckCount ≤ N AND strictly behind on prizes → exclude optional
self-draw/fetch options from the BC head's choice (empirically derived action
set; evolutions excluded — their deck consumption is triggered bonus draws;
Sacred Ash excluded — it refills). N chosen from 41 recorded self-deckout
trajectories: median deck 3-turns-before-death = 11, late-game burn 3.7
cards/turn; braking cuts burn to ~1.3/turn. Notable: encode_state already
feeds deckCount/60 to the network — the information was always visible;
27.8k parameters of win-side imitation simply never got a gradient for it.
An honest framing for the writeup: this is a one-rule prosthetic for a
behavior BC cannot learn from winners, and the ablation gate (G7c) exists to
prove the single rule — not the new teacher, not the new deck — is what
moves the anti-stall number.

## 3b. Trigger widening, the measurement caveat, and holding pre-set limits (2026-07-12)

Trigger widened at sign-off from strictly-behind to **not-ahead** (parity
brakes too): 11 of 41 recorded self-deckouts happened level-or-ahead, and
against stall archetypes prize parity is functionally losing on the deckout
clock. Verification before gating surfaced a measurement caveat worth
keeping: the N-selection analysis measured interference against its own
consumption-derived card set, while the shipped brake also lists Hilda,
Poké Pad and Enriching Energy — so the "3 decisions / 1 of 29 wins" baseline
was really 5 / 1 against the brake as implemented. Always re-measure against
the artifact you ship, not the analysis that motivated it.

Decision surface from the same 100-game diagnostic (29 wins / 41
self-deckouts), exact shipped set:

| N  | trigger         | won-side interference | deckout games touched / saved>=4 | fires <T10 |
|----|-----------------|-----------------------|----------------------------------|------------|
| 12 | not-ahead       | 8 dec, 4 games        | 34/41, 26/41                     | 6          |
| 10 | not-ahead       | 5 dec, 2 games        | 34/41, 20/41                     | 3          |
| 12 | strictly-behind | 5 dec, 1 game         | 27/41, 17/41                     | 1          |

Two structural findings: (1) the TRIGGER drives which games the brake
touches (34/41 vs 27/41), while N only sets how deep into each game it
bites (median cards saved 5.0 at N=12 vs 3.0 at N=10); (2) "early-game
decks stay >12" is false for this engine's worst games — the pathological
tail burns ~34 cards by our 4th-5th player-turn, so early fires were the
brake meeting the pathology early, not an initial-draw interaction.

N=12 not-ahead breached the pre-registered interference limits (>6
decisions or >3 of 29 wins). Decision: drop to N=10 not-ahead (5/2, within
limits; identical game coverage; early fires halved) rather than relax the
limits ex-post — the limits were set before the eval precisely so the eval
couldn't argue us out of them. The cost (brake engages ~1 turn later) is
testable on the strengthened stall gate rather than assumed away.

## 3c. G7a kill: the second BC head-to-head failure (2026-07-12)

G7a (BC-v2 + brake N=10 not-ahead on list-0, vs v2.2.0-bc-full-garchomp,
300 games, seats alternated): **39.0%, Wilson 95% CI [33.7%, 44.6%] — FAIL**,
and decisively so (the UPPER bound is below 50%). Kill criterion honored:
no G7b/G7c, no iteration.

This is the second consecutive BC of a top-meta Alakazam deck to fail the
same gate: the metaB Alakazam BC failed G6 at 44.7%, was diagnosed
(sub-decision blindness + compounding error), and BC-v2 fixed both diagnosed
causes — two-headed card model, 3x games from the rank-1+3 consensus list,
prize-fetch accuracy 96.8% — plus an anti-deckout brake. Head-to-head result
got slightly WORSE (39.0% vs 44.7%). Loss anatomy (183 losses): 107 lost
prize races (58%), 52 self-deckouts (28% — the economy failure persists
against a BEATDOWN opponent even with the brake armed), 24 no-active (13%).

Reading: the gate gap is not the specific defects we kept fixing. Remaining
candidates: (a) compounding piloting error vs human-teacher level that
static accuracy cannot see (consistent with ch. 1), and/or (b) structural
deck matchup — Garchomp fighting aggro may simply beat the psychic engine
head-to-head, and the C1 probe (90% vs Lucario) plus 3 Phase-1 v2.2.0
losses to ladder Dudunsparce/Alakazam pilots (two 0-6 races) show the
matchup axis is real but unquantified. A head-to-head gate against one
fixed incumbent deck cannot separate pilot quality from matchup structure
when challenger and incumbent play different decks.

## 4. Alternate not taken (yet)

Data-shape fix (adding expert LOSING long games / thin-deck states to
extraction) held as fallback if the brake underperforms. Would test whether
the "sees-it-can't-do-it" class is curable inside pure imitation.

## 5. Choosing PPO over AlphaZero (chapter-five seed, 2026-07-12)

After G7a killed the imitation line — chapter 1's pathology surviving every
within-paradigm fix, twice — the RL algorithm was chosen by survey
(stage4/rl_ours/algorithm_survey.md), not inherited. PPO league self-play,
warm-started by direct weight copy from BC-v2 and KL-anchored to it, was
chosen over the AlphaZero family our teammate had already built. Four
reasons, in the order they decided it:

(i) **Optimize the deployed objective.** The ladder artifact is a raw ~1ms
numpy policy. PPO's training objective is that object's win rate. This is
the direct repair of chapter 1's lesson: BC optimized static decision
accuracy — a proxy that read 82–97% while head-to-head strength read
39–45% — and AZ substitutes another proxy, a search-support net whose raw
head is a byproduct. Twice burned by proxy objectives, we picked the
algorithm with none.

(ii) **Failure-mode asymmetry, observed not theorized.** The teammate's AZ
run destroyed its own SL prior (34–35% → 5% vs its target in 20 iterations:
a replay buffer holding under two iterations of data, 40% adversarial
opponent games from iteration 1, two determinizations, no KL anchor).
Anchored PPO's characteristic failure is plateau at the warm start —
bounded, diagnosable, recoverable. Under a fixed deadline, bounded worst
case beat higher theoretical ceiling.

(iii) **Losses in the gradient.** G7a's loss anatomy: 52 of 300 games were
self-deckouts with the brake armed. Win-only imitation structurally cannot
see this failure (chapter 1); the brake only splints it (chapter 3).
On-policy RL makes every self-deckout a negative gradient — the first
training signal in the project that touches the pathology directly. It also
supersedes chapter 4's data-shape fallback: self-play generates the
thin-deck states the expert corpus never contained.

(iv) **CPU economics.** Search-free games are 3–10× cheaper and games are
the entire budget on unknown lab cores; self-play is CPU-bound (teammate's
Colab-verified finding).

Timeline note (2026-07-12): deadline verified from the competition rules
page as **2026-08-16** (teammate's report had said 08-14 — planning had
built to the earlier date per policy). Internal freeze moves Aug 12 → Aug 14,
train-stop Aug 10 → Aug 12: ~96 core-hours of extra training compute across
two labs, allocated to the main window and one ship-battery re-run slot,
not to new scope. Operational schedule: stage4/rl_ours/scoping.md.

## 6. Two-team reconciliation (2026-07-21, from CONTEXT.md rev 15)

The teammate's Jul 13–20 arc (his session log, CONTEXT.md: 8+ hypotheses
tested, 7 refuted, one +114-Elo correctness fix, two significant negative
A/Bs) now cross-references our Stage 1–4 evidence. The reconciliation
itself is chapter material because the two stacks are architecturally
disjoint (his: determinized-search engine, hand evaluator, replay-derived
rules; ours: BC/PPO fast policies, learned encoder) yet keep producing the
same findings independently. Items, with transfer verdicts:

**6a. "Piloting, not deck, is the limit" — now replicated FOUR ways across
two stacks and the live ladder.** (i) His §6m pilot-vs-deck: top pilots
55–57% with his exact Alakazam list where his agent gets 30% (n=599+72 vs
20, z=2.42). (ii) His mirror probes: 31.5% piloting the reference agent's
own Lucario deck (n=1000); 33–42% on Luca's Grimmsnarl list, developing the
same deck at 1/4 the expert's rate. (iii) Our Stage-3 lesson in the same
shape: BC of the rank-1 Alakazam list shipped at μ548 vs the list's own
pilots at μ1200+; Garchomp BC G7a 39.0% vs v2.2.0. (iv) NEW, ladder-level
(Phase B refresh 07-21): junlee789 pilots our exact Cynthia's Garchomp
archetype AT #5 (μ1152) with a ~1.1 s/decision search agent — the deck we
"couldn't ship above μ700" is top-5 under a better pilot. Combined license:
deck selection is a second-order lever for us; every remaining point is in
the pilot. No further deck-swap experiments are justified.

**6b. The BC contrast is a features result, not a BC refutation.** His BC
failed at the representation layer: 7-dim identity-blind card features
(cannot distinguish Abra from Alakazam), top-1 0.388, priors actively
harmful in-tree (0.367 vs hand rollout), category-policy BC −82 Elo.
Ours cleared that layer (deck-identity one-hot tables, two heads, top-1
68.9%/76.1% MAIN/ST_CARD) and failed one layer up: static accuracy 82–97%
coexisting with 39–45% head-to-head — compounding error + win-only
blindness. repo1 independently: "the bottleneck is FEATURES, not rows"
(plateaued 0.529 identity-blind). So the two failures COMPOSE rather than
contradict: identity features are necessary (his lesson) and not sufficient
(ours). Direct consequence: his §7 item 3 asks for a learned in-tree
opponent/rollout model fit to top replays and expects it to beat his
hand-written stub (which alone took him 0.20→0.60 vs strong_800); his
attempt at that model failed for exactly the deficiency our encoder does
not have. That synthesis — our identity-aware nets inside his validated
search shell — is the one experiment neither stack could run alone.

**6c. Proxy-objective failure, third and fourth instances.** His SL clone:
82.2% teacher-match → 34–35% vs its own teacher. His value net: passed both
training gates (val MSE −28%, Cohen d +1.26, 24.7 µs latency) → −82 Elo,
diagnosed as signal-shape mismatch (absolute win-prob leaf values vs
rollout-scaled backup expectations — the tree's sibling comparisons
destroyed). Ours: two BC gates (44.7%, 39.0%) despite 82–97% accuracy.
Four instances, two stacks: any offline metric that is not "win rate of the
artifact you ship, measured in the deployment configuration" has now
misled one of us every time it was leaned on. (Our G-gates being raw-policy
search-off, and PPO optimizing the shipped object directly, are the
project's structural answers; his value-net lesson adds: if a learned value
ever re-enters a search backup — e.g. a Gumbel-AZ pivot — its SCALE
contract with the rollout signal is a pre-registered gate, not an
assumption.)

**6d. The behavioral gap is one phenomenon seen from two instruments.**
His §6n per-turn diff (same deck, same matchup, n=599 top-player games):
ability-used-when-legal 88% vs 61%, hand T3/4/5 7.9/9.3/10.3 vs
6.1/6.5/7.0, first Alakazam T4.7 vs T7.9, everything else within 5 pts —
skipping the draw engine costs ~3.3 cards by T5, the attacker lands 3.2
turns late, the race is lost (12 of 23 losses). Our C1 anatomy from the
other side: 58% of G7a losses are lost prize races; our fresh Phase-B
harvest (07-21, independent metrics, no Ability log — extra-draws-per-turn
as engine proxy) shows the live agent at 2.1 extra draws/turn and 24%
attack-share vs the top-10's 2.2–4.6 and 46–64%, hand decaying to ~4.3 vs
their 5.5–9.3. Same deficit, two stacks, two measurement systems. And his
§6n intervention lesson bounds the fix space: forcing the RATE
(ability-before-END) measured −6.5 pts at n=400 — "matching a rate is not
matching a policy." Our draw-brake is the same lesson from the C2 side: a
mechanism-derived rate rule that left the self-deckout share at 28%.
Sequencing has to be learned (in-gradient or imitated with context), not
forced.

**6e. Honest audit of our own record against his methodology rules.**
(i) Unit-of-analysis: our headline metrics are per-game or per-turn, but
the Phase-1 cluster matchup claims rest on n≤14 per cluster (C1 5W–9L, C2
1W–8L, C3 0W–3L) — C2 was later confirmed at scale (41–52 deckouts/100
games, G7a n=300); C1's "worst matchup" ranking was never re-measured at
n≥60 and should not be cited as more than direction. (ii) One variable per
A/B: BC-v2 bundled two-headed architecture + 3× data + new deck + brake
into one G7a gate; when it failed at 39.0% we could not attribute between
pilot quality and deck matchup — the same violation he logs in §6n, paid
in the same coin (an unattributable result). (iii) n≥60: our formal gates
comply (200–300); his rule mainly indicts the early ladder reads (μ548 at
n<40, v8 at n=4) which standing policy already refuses to act on.
(iv) His wash-out generalisation — "a leaf-evaluator term for an action the
rollout policy also takes cannot change behaviour" — post-hoc explains why
our v3 evaluator tuning era (hill-climbed weights, 53% vs v1) produced so
little on the ladder, and is a standing argument for policy/rule-level
learning over evaluator-weight learning in any future search work.

**6f. Deployment-integrity contrast (his V1 vs our bundle).** His agent
played uniformly random on the ladder for its entire early history —
`import mcts` after Kaggle strips the agent dir from sys.path, swallowed by
a never-crash fallback; scored 366; caught only by a loud SELFCHECK line.
Audit of our shipped path (code inspection 07-21): the v2.2.0 bundle
contains NO project-local module imports — deck.csv, card_data.json and
the BC weights all load via `_find_file()` (which tries `__file__`, cwd,
a hardcoded `/kaggle_simulations/agent`, then sys.path entries) and plain
file reads. The single local import in main.py (`import cg.sim`) sits
behind PTCG_SEARCH=1 (not shipped in v2.2.0), executes eagerly at module
scope inside the exec window while sys.path is intact, re-inserts the
engine's parent dir into sys.path from a file-path probe first, and
degrades to the v1 heuristic with one stderr line if it fails. Verdict:
immune to the sys.path-strip class by construction, consistent with the
runtime evidence already logged (clean stderr, ~1–3 ms decisions ≠
fallback signature). His transferable rule stands for us as policy:
every bundle emits a one-time SELFCHECK line, and any unmeasured component
is presumed inert until a production log proves otherwise (his two silent
failures — the import bug and the belief system that identified nothing —
were both invisible to code reading).

**6g. Correctness-fixes-beat-strategy, quantified across both stacks.**
His ledger: 14 strategic hypotheses inconclusive-or-harmful in one session;
the one shipped change correcting a factual misread (revenge damage,
printed 30 vs actual 130) = +114 settled Elo, the largest single jump in
his project. His generalisation "FACTS are worth ~16 points, WEIGHTS ~0"
(a term reporting something false steers confidently wrong; an
underweighted term is merely ignored) matches our D9-class experience and
argues that any model we put inside a search must ABSTAIN where it cannot
read the state rather than guess.

**6h. The governor-ship coupling problem (recorded 2026-07-22, S3 arc).**
Three consecutive time-governor bugs surfaced across S3's A/B iterations —
(i) seed poisoning: `ema_det` initialized to None, an unlucky first
cold-cache search set it above the disengagement threshold and permanently
pinned the worker to no-search for the rest of its chunk; (ii) missing
input cap: no bound on per-update EMA input, single high sample inflated
the running estimate above the safe range; (iii) cold-run bias: first N
searches had no distributional grounding, so early estimates biased
subsequent decision authority even when they didn't fully poison. Each was
caught by a pre-registered engagement telemetry criterion that stripped
away another mode of confound. Each fix reduced the confound and revealed
the next. The pattern is a real methodology risk we cannot ship our way
out of: **the same adaptive time-budget governor that protects the ladder
time bank in production is the mechanism whose behavior we are gating on
offline.** If a rollout policy or in-tree model ever passes an offline
gate but underperforms on the ladder, we will not be able to cleanly
disambiguate "the model is worse in real-population matchups" from "the
governor engages differently under real ladder decision-cost distributions
that our mirror A/B did not sample" — and vice versa. Ship-vs-gate
isolation is *imperfect for adaptive infrastructure*. Named here so the
writeup can be explicit rather than pretending the two axes are separable.
Two shipped controls partially mitigate: (a) the seed+cap+warmstart(N=10)+
hysteresis(M=3) combination gives hard engagement guarantees independent
of EMA, so the shipped governor cannot silently disengage on the ladder;
(b) `SELFCHECK`+`[gov]` atexit lines log governor state per episode, giving
a per-game measurable of what the shipped governor is actually doing on
the ladder if the ship-vs-gate diagnostic ever needs to run empirically.
Neither eliminates the coupling — they make it observable.

## 7. Multi-architecture convergence on Cynthia's Garchomp (2026-07-22 evening)

Fresh top-10 harvest (`analysis/phase2_meta_shift/replays_top10_jul22/`, 261
episodes, unauth chain built when bearer expired) surfaced two seats on our
own Garchomp archetype simultaneously: **#2 Yudai Ueno at μ1147.8 running a
36 ms/decision fast policy**, and **#6 junlee789 at μ1119.6 running a
1208 ms/decision search agent**. Same deck, two architectural classes,
50+ Elo apart at the top of the ladder. Same day we shipped Garchomp at
μ548–697 across our own attempts.

Two things this establishes for the writeup:

(a) **Piloting-not-deck reaches its strongest form.** Not "same deck, two
teams" (that was already the §6a claim). Here it's "same deck, two
ARCHITECTURES, both top-10, both far above what we shipped it at." The
architectural class of the agent is NOT the constraint on Garchomp; the
per-turn decision quality within whichever architecture is chosen IS. This
generalises the §6a finding across the fast-vs-search dimension.

(b) **Named fallback direction, no action now.** If the Path-2 hardened-
search arc (FINAL_PATH_JUL21.md) kills early on measured-effect gates —
i.e. our search shell fails to reproduce Sanjay's arc's effect sizes on
this deck — the existence of Yudai's 36 ms fast-policy pilot at μ1147
demonstrates a fast-policy road to top-10 on this exact deck also exists.
Fallback would be: BC-v3 on Yudai's specific episodes (a fast-policy pilot,
not a search pilot's rollout dataset — the distinction that made junlee789's
training corpus a rollout candidate) as a pure ship policy, no search. Not
started, not committed; recorded here so we do not rediscover the option
under time pressure if the primary path fails.

## 8. Gate A trajectory: pre-registration honored in both directions (2026-07-22)

Gate A (eval-correctness fix: Raging Curse + Psychic scaling handlers with
ABSTAIN discipline) was the first shipped-recipe gate under FINAL_PATH_JUL21.md.
Its full two-run trajectory is a discipline chapter, not just a component
result.

**A/B trajectory (Garchomp mirror, single variable = EVAL_FIX flag, all
telemetry PASS on both runs):**

| run | W-L | rate | Wilson 95% CI | verdict |
|---|---|---|---|---|
| original | 209-191 | 52.2% | [47.4, 57.1] | FAIL (in RETRY band 46-54%) |
| retry | 203-197 | 50.7% | [45.9, 55.6] | FAIL (CI-low ≤ 50%) |
| **pooled** | **412-388** | **51.5%** | **[48.0, 55.0]** | still fails ADOPT bar even at doubled n |

Point estimate stable at +1.5–2.2 pts across independent 400-game draws;
neither CI clears 50%. Component **KILLED per pre-registered rule.**

**The discipline chapter, not the point-estimate chapter.** After Run 1
landed in the RETRY band, the natural argument was: point estimate is
positive, correctness fixes measure neutral in mirror by §6l, spending 5 h
on a retry that can't change the shipping decision costs the calendar. All
those arguments have individual merit. All are inadmissible under a
pre-registered read rule *precisely because they only ever appear after
seeing the result*. The retry ran anyway, landed 50.7%, cleared the
ambiguity — Gate A fails clean. The alternative timeline (adopt on Run 1
point estimate, proceed to Gate D on an eval-hardened base) would have
bundled one un-gate-passed variable into Gate D's read and repeated
Sanjay's own §6n bundling failure ("BUNDLED TWO CHANGES ... attribution
question is still open") with an extra step.

Rule-following worked in **both** directions inside one gate: first
rejecting a plausible point-estimate-adopt argument in favor of the
retry, then rejecting a plausible "just barely fail, ship it anyway" argument
in favor of clean revert. Rules that only hurt on one side are goalposts, not
rules.

**Methodology cross-reference to Sanjay's §6l.** Correctness fixes measure
neutral-or-marginal in mirror A/Bs because both sides misread the same
signal; only WE misread on ladder. His revenge fix — the direct analog of
our EVAL_FIX component — measured 51.4% [46.5, 56.3] offline (nearly
identical to our 51.5% pooled) and produced **+114 Elo on ladder**. Our
Gate A trajectory sits inside that documented pattern. This is precisely
what Gate H (consolidated hardened shell vs v2.2.0-Garchomp, distinct
pre-registered gate against an incumbent lacking the fix) is designed to
resolve — no post-hoc goalpost move required.

**Strategic implication for FINAL_PATH_JUL21.md μ expectations.** Gate A's
kill means Gates D–G compound onto the unchanged v2.0.0-class base, not
onto an eval-hardened base. Sanjay's arc bundled multiple correctness-class
fixes on top of each other; a chain missing its earliest component
integrates smaller total effect. Honest central-μ revision for Path 2:
**950–1080 → 900–1030**. Crossing μ1000 is now a stretch, not a base case.
Floor (v7 μ881) unchanged; Gate H's ladder canary rule (settled ≥908, else
revert) still guards it. Aug 8 hard writeup pivot unchanged.

**Two artifacts survive for the writeup regardless of Gates D–H outcomes:**
(a) EVAL_FIX code with unit-verified ABSTAIN discipline for Raging Curse /
Psychic patterns — a demonstrated *how* for §6j "facts vs weights" that we
can point to when the chapter argues correctness-with-abstain is the right
shape; (b) a two-run Gate-A trajectory that empirically instantiates
Sanjay's §6l mirror-vs-ladder asymmetry in our stack, on our deck.

## 9. Gate D trajectory: sophisticated retry-argument rejected (2026-07-24)

Gate D (promotion rule at SC_TO_ACTIVE: `maxHp + 30·energy`, Sanjay §6q v8
rule 1) landed 48.2% [43.4, 53.1] at n=400 with telemetry PASS. Point
estimate NEGATIVE (−1.8 pts vs Gate A's +2.2). CI-low 43.4% < 46% = KILL
band (not RETRY-ONCE 46–54% band). Combined with Gate A retry's 45.9%
CI-low, pre-registered kill criterion fired: two consecutive gates in
A-D set at <46%.

**Post-hoc mechanistic diagnosis** (identified after the kill, admissible
as diagnostic material but not as gate-argument): Sanjay's `maxHp + 30·E`
rule was tuned for Trevenant's deck geometry, where the specific failure
mode was 140 HP body → 60 HP weakling downgrade. On our Garchomp deck the
adjacent bench candidates (Roserade 130 vs Gabite 100 vs Roselia 70 vs
Spiritomb 70 vs Fezandipiti 210 HP but different role) don't cluster the
same way. The pure-maxHp scoring plausibly ties or inverts on
attacker-quality where our current `hp + 20·E + best_dmg/10` had it right.
This IS the exact class of bug Sanjay himself documented for pure
`(energy, maxHp)` scoring in his §6q first-version (which he then fixed by
weighted combination + attack term he DROPPED in his final rule but which
appears to matter on our deck).

**The discipline decision matters more here than at Gate A.** Gate A's
retry argument was "point estimate is positive, correctness fixes measure
neutral in mirror per §6l" — a general statistical/methodological
argument. Gate D's retry argument would be "we identified a specific
mechanistic bug in the rule; a redesigned rule with attacker-quality
tie-breaker is a defensible improvement." That's a *stronger* argument —
mechanism-based, deck-specific, matches Sanjay's own iteration pattern. It
is precisely at the point where an argument is mechanistically strong that
pre-registration protects against sophisticated goalpost-moving. Rules
that only apply when the argument is weak are decoration; rules that apply
when the argument is compelling are protection.

**Ruling per pre-registration:** PROMOTE_RULE reverts to 0. The redesigned
rule (D-prime: `maxHp + 20·energy + best_attack_dmg/10` — combines Sanjay's
maxHp-not-hp fix with retention of our attacker-quality term) is a
DIFFERENT variable, not the same variable's retry. Under RETRY-ONCE
budget, it does not qualify as reuse; it earns its own scheduled slot or
does not run.

**Placement decision:** D-prime slots as position 5 in sequence
(A → D → B → C → **D′** → E → F → H), replacing Gate G (rich eval terms).
Rationale chained to evidence: G has smallest expected effect per Sanjay's
own §6j "weights ≈ 0" wash-out finding; D-prime has larger expected effect
(fires on every post-KO promotion, mechanistically motivated); placing
D-prime at position 5 honors the largest-effect-first ordering from user's
Adjustment (1) which position 7 (the (a) placement) would violate.

**Base-rate signal.** Two-of-two of the first two A-D gates KILLED. Even
before overriding the pre-registered halt with a redesign path, this is
weak base-rate evidence for "Sanjay's arc transfers to our stack on our
deck." Gate B needs to LAND cleanly (CI-low > 50%) to move the base rate;
if Gate B also kills, the recipe-transferability question is answered
regardless of what D-prime does later. Named here so the ongoing arc has
a public prior against which subsequent gates are read.

**Two artifacts survive for the writeup:** (a) unit-verified promotion
scorer with correct SC_TO_ACTIVE scope (Sanjay's rule reproduces his
Trevenant-vs-Dunsparce failure fix on synthetic input — the fix works in
his deck geometry; deck-geometry-transfer is the empirical failure);
(b) explicit example of the strongest form of the retry argument being
rejected under pre-registration, a discipline chapter more useful than
another shipping win.
