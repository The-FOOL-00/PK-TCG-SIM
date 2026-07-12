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
