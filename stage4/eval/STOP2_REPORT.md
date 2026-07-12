# Stage 4 / Branch B — Stop 2: BC-v2 training + held-out C1/C2 eval (2026-07-12)

**Verdict: C2 expression FAILURE → STOP before gating, per instruction.**
C1 shows a clean, large improvement. Details below; no gates were run.

## Training (3 variants × 2 seeds, trunk 170→80→48, two heads, 27,842 params)

| variant | MAIN train/val | own-val MAIN | own-val CARD | note |
|---|---|---|---|---|
| a majkel-only | 1,468 / 14 | (64.3%) | (52.2%) | **val = 1 game / 14 decisions — statistically void**; 33 games is too thin to train or judge |
| b majkel+yushin | 5,522 / 471 | **55.4%** (both seeds) | **69.2%** | floors: always-0 11.5%, v1-agree 29.3% |
| c +bono | 9,252 / 784 | 49.2–49.4% | 66.7% | bono (51% pilot) dilutes own-val; but see common holdout |

Curves/metrics: `stage4/runs/bc_v2_*/metrics_full_*.json`. Note MAIN accuracy
is well below BC-full-Garchomp's 68.9% — the engine deck + a search-class
pilot (Yushin) are harder to imitate. Meta-freshness flag (addition 2): not
triggered in the "high val / weak held-out" form — val is itself moderate.

## Common holdout (identical held-out games for all variants: 784 MAIN / 585 CARD, 20 games)

| variant | MAIN | CARD | MAIN crustle | MAIN aggro | CARD prize-fetch (n=94) |
|---|---|---|---|---|---|
| a | 36.9% | 57.8% | 37.9% | 45.0% | **96.8%** |
| b | 49.0% | 63.4% | 47.5% | 47.5% | **96.8%** |
| c | 49.2% | 66.7% | 46.5% | 50.0% | **96.8%** |

- **Prize-fetch diagnostic (addition 3): green.** 96.8% for every variant —
  the novel engine surface is learned near-perfectly at the decision level.
- **C1 static-gap check (addition 4): not triggered.** Aggro-class MAIN acc
  is within ~2 pts of overall for b/c (no >10-pt shortfall).

## Behavioral probes (100 games each, v1-piloted opponents, 0 crashes)

### C1 — vs Mega Lucario/Hariyama (Sanjay's list): **clear improvement**

| agent | win rate | median win turn | wins ≤T12 | self-deckouts |
|---|---|---|---|---|
| v2.2.0 baseline | 76% | T18 | 4 | 2 |
| BC-v2 b | **90%** | **T12.5** | **45** | 3 |
| BC-v2 c | 86% | T13 | 38 | 8 |

Survival + closure both present: BC-v2 races and finishes. C1 pathology fixed
on this probe.

### C2 — vs Mega Kangaskhan/Crustle (Budew's list): **expression failure**

| agent | win rate | self-deckout losses | deckouts while AHEAD/level | median win turn |
|---|---|---|---|---|
| v2.2.0 baseline | 71% | 10 | 2 / 0 | T19 |
| BC-v2 b | 23% | **41** | 7 / 4 | T19 |
| BC-v2 c | 35% | **52** | 10 / 9 | T12 |

Two findings, one per direction:

1. **The pathology is back and 4–5× worse.** Static accuracy sees no Crustle
   gap (47%/61% ≈ overall) and prize-fetch is 96.8% — yet in play the agent
   self-deckouts in ~half its games vs a defensive opponent. Same
   sees-it-can't-do-it class as BC-full, with a structural amplifier: list-0's
   speed is bought with aggressive self-draw (Alakazam engine, Poffin,
   Poké Pad, Nighttime Mine); its real pilots manage deck economy when the
   race stalls, and 27.8k params of win-side imitation do not. Mechanism per
   the prize-state data: most self-deckouts happen **behind** at T20-21 —
   closure fails against a defensive board, the policy keeps firing the draw
   engine with no brake, and the deck evaporates. Thin-deck states are
   near-absent from win-side training data (winners close by T12-15), so the
   exact states where the brake matters are the states BC never saw.
2. **The probe itself under-measures ladder stall (G7b design flag).**
   v2.2.0 scores 71% vs this v1-piloted Crustle yet went 1W-8L vs ladder
   Crustle pilots — v1 pilots Kangaskhan/Crustle as a beatdown deck, not a
   stall. So these numbers overstate everyone; the *self-deckout counts* (own
   behavior, opponent-independent) are the reliable signal. This also means
   G7b as specified (v1 piloting the meta archetypes) will overstate
   anti-stall competence — worth revisiting at gate time.

## Ship-candidate ranking (per addition 1: held-out C1/C2, not val)

None shippable as-is. If forced to rank: **c** (best C2 win rate 35%, race
line partially expressed — median win T12, 18 wins ≤T12 — but worst
self-deckout count) vs **b** (cleaner val, slower race, 41 self-deckouts).
Variant a is void.

## Diagnosis summary + options (user's call, per stop protocol)

The gap is one behavior: **no draw-brake / deck-economy management in
stalled games**. Candidate directions:

- **(i) Data-shape fix**: extend extraction beyond win-sides for this deck —
  include list-0 pilots' LOSING long games (their deckout losses encode
  thin-deck decision changes) and/or upweight T15+ / deck-thin states.
  Cheap to test; stays inside the BC recipe. Risk: losing-side imitation
  reintroduces the "imitate the loser" objection; mitigation is filtering to
  the pre-loss stretch where the pilot was still playing well, or weighting
  by per-decision deck-count context.
- **(ii) Serve-time draw-brake**: a small explicit rule (e.g., decline
  optional self-draw abilities when own deck ≤ N cards and not at match
  point) layered over BC-v2, ablatable — would slot naturally into G7c as
  "the specific Stage 4 addition." Fast to implement and test on the same
  probes. Risk: hand-crafted overrides on top of imitation have bitten us
  before (v1-prior recursion class of bugs); it is a design change to the
  policy path, so it needs your sign-off.
- **(iii) Both** — (ii) now as a stopgap measured by probes, (i) as the
  proper fix.
- Escalation option if all fail: revisit teacher choice (BigBugginnings'
  Dragapult, half the volume, restarts the clock ~1 week).

Timeline position: day 1 of the 9-day projection (training + eval ran same
day as data prep). Slack to Aug 10 remains ~4 weeks even with a diagnosis
loop.
