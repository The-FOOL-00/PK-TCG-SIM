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

## 4. Alternate not taken (yet)

Data-shape fix (adding expert LOSING long games / thin-deck states to
extraction) held as fallback if the brake underperforms. Would test whether
the "sees-it-can't-do-it" class is curable inside pure imitation.
