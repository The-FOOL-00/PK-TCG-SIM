# Path decision — 2026-08-02, 14 days to submission lock

**Nothing submitted. No upload was made or attempted.** This is analysis and a
recommendation; every upload in it is the user's action.

Question asked: *what development path gets us past μ1000 by the Aug 16 lock?*

Answer, stated first: **no development path does, at better than ~1-in-7 odds.
The largest μ available in the next 14 days is not in code — it is a slot we
already own and are not using.** The ordering below is by expected μ per day
spent, and the first tier is not engineering.

---

## PART 1 — Where we actually stand

Live leaderboard, `analysis/phase2_meta_shift/leaderboard_2026-07-31.csv`,
6,002 teams:

| | |
|---|---|
| **Project Mew** | **rank 2,289 / 6,002 — μ700.1** (last submission Jul 30 17:24) |
| μ1000 | rank ~110 — **top 1.83%** |
| μ900 | rank ~337 — top 5.6% |
| field median | μ638.1 |

**μ1000 is not "a bit more than 700." It is 2,179 places.**

And the team's own best-ever is below it: **Sanjay's v7 search agent, submission
54855847, settled μ877.8 at n=61** (DECISION_JUL21.md §25). Reaching μ1000
means beating our historic ceiling by +122 in 14 days, on a stack where the last
seven learning experiments all read negative.

## PART 2 — The finding that outranks every development option

DECISION_JUL21 recorded v7 as *"holds team slot 1; the team's live score."*
CANARY_SUBMISSION_LOG §2 states the rule in bold:

> **The Kaggle last-2 rule is TEAM-level, not per-member.** The two most recent
> uploads by *anyone on the team* are the active pair.

**CORRECTION (this doc, first draft, was wrong on attribution).** I originally
wrote that *our* uploads displaced v7. They did not.
[CANARY_HEALTH_CHECK.md](CANARY_HEALTH_CHECK.md) §0 pulled the real submission
history and states it plainly: *"v7 (μ 881) is gone, and it was not our doing.
Sanjay's own uploads displaced it."*

The actual record:

| submitted (UTC) | id | file | score | status |
|---|---|---|---|---|
| 07-26 07:52 | 54995194 | `submission_grimmsnariex_v1.tar.gz` | **401.1** | ACTIVE (Sanjay) |
| 07-26 04:58 | 54991880 | `submission_trevenant_v21.tar.gz` | **725.9** | ACTIVE (Sanjay) |
| 07-26 04:45 | 54991680 | `canary_cap16.tar.gz` | 439.1 | DISPLACED — ours, after 13 min |
| 07-26 01:56 | 54988933 | `trevenant_v20` | 726.8 | inactive |
| 07-25 17:02 | 54980729 | `trevenant_v17` | 750.5 | inactive |
| 07-22 00:55 | 54890463 | `trevenant_v11` | 778.5 | inactive |

Two things this changes:

1. **Both slots are Sanjay's**, at 725.9 and 401.1 — consistent with the team's
   700.1 on the Jul-31 board. Our canary was displaced by *his* upload 13 minutes
   after it went up, froze at n=28, and its 439.1 is **INVALID** under the n≥40
   rule. We have had no valid ladder read of our own build since.
2. **His own line is declining**: v7 877.8 → v11 778.5 → v17 750.5 → v20 726.8 →
   v21 725.9 → grimmsnarl_v1 401.1. The team's downward trajectory is upload
   churn on his side, not a code regression on ours.

**The team is fielding 725.9 while holding a settled 877.8.** No component on any
build list has a measured effect that large. The action is unchanged — restore
v7 — but it is **Sanjay's call and Sanjay's upload**, and the thing to stop is
his churn, not ours. Nothing in 14 days of engineering plausibly does either.

### Action 0 — restore v7 (Sanjay's action, one upload)

- Re-upload submission **54855847** so an 877.8-class agent occupies a slot.
- Expected delta: **+~178 μ**, cost one upload, zero development.
- Caveat, stated honestly: byte-identical archives have scored **600–955** on
  this ladder (repo2, 146 submissions) and every agent re-enters the pool at 600
  and climbs. A re-upload re-rolls inside that band; it does not deterministically
  return 877.8. It is still the best-expected-value single action available.
- **Standing rule, reinstated:** v7 is never displaced. Candidates ship into the
  second slot only. Before any upload, re-read §2 of CANARY_SUBMISSION_LOG and
  fill in the slot-state table — it exists precisely to stop this, and it was
  left blank.

### Action 0b — stop putting experiments in live slots

Every one of our uploads consumes a team-wide slot. With 14 days left, the slot
budget is the scarce resource, not compute. One slot is v7. The other takes at
most **one** challenger, and only after it clears the gate chain.

## PART 3 — What the record says about development paths

Seven independent negatives, both stacks (FINAL_PATH_JUL21 Part 3):

| # | attempt | result |
|---|---|---|
| 1 | BC-Garchomp (G6a) | 31.0% — fail |
| 2 | BC-full two-headed (G6c) | 44.7% — fail |
| 3 | BC-v2 + brake (G7a) | 39.0% [33.7, 44.6] — kill |
| 4 | **PPO capacity ladder 27.8k → 128k → 256k** | **flat 27–28% vs v2.2.0, 83k+ games — every rung** |
| 5 | His BC priors in-tree | 0.367 — harmful |
| 6 | His value net | −82 Elo — harmful |
| 7 | BC-junlee as search rollout (S3) | 48.8% [43.9, 53.6] n=400 — null |

Against that, the only mechanism class that has ever produced either team's
best score is **search**: his 366 → 881 arc, our μ614. That is the whole basis
for Path 2, and it still holds.

### Dead on arrival — do not spend days here

**More RL.** All three capacity rungs flat. The Gumbel-AZ trigger condition
(`gumbel_az_scoping.md`: fire only if 128k AND 256k both plateau) is now
formally **met** — but that note itself scopes ~4–5 days to *first training
loop*, before any gate, canary, or n≥40 ladder settle. It cannot produce a
shippable, gated artifact inside 14 days. The trigger firing is a writeup fact,
not an Aug-16 plan.

**Deck switch to Kangaskhan/Raging Bolt or Dragapult.** The Jul-31 harvest is
the strongest counter-matchup evidence this project has found (Kangaskhan/Raging
Bolt 10W-1L vs Grimmsnarl, four concordant snapshots; Dragapult 10W-2L). It
still does not clear the bar. Our measured closure is **45.0%** and **46.3%** on
those two decks — bottom of the seven-archetype band. FINAL_PATH Part 2 closed
this with an EV calculation: ~51.5% before the piloting penalty, **~30% after**
the measured 20–25 pt penalty. `roster_diff_jul31.md` says so itself: *"It does
not reopen the deck-switch question on its own."* Reopening requires a
within-team n≥60 read of ≥50% on the candidate deck, which no candidate has ever
produced.

## PART 4 — The one cheap measurement nobody has run

FINAL_PATH_JUL21 durable fact 5 names the target explicitly:

> The top-10 per-turn behavioral envelope is stable: attack-share **0.44–0.64**
> of own turns, first evolution T3.5–4.1, hand held or grown T3→T7. Our live
> agent sits outside it in every snapshot. **This envelope — not any specific
> opponent — is the target.**

Both envelope reads we hold are from the **retired search+Garchomp stack**:
BEHAVIORAL_GAP_DIAGNOSIS (atk/t **0.18**, first attack **T7.91** vs field
4.1–5.6) and FINAL_PATH's live row (atk/t 0.24, FA 6.1).

**We have never measured the shipped Grimmsnarl E1+E2+T1+T2 build against that
envelope.** E1 and E2 were adopted on *mirror prize velocity*, a different
instrument — and §4-lie-2 of our own writeup says the mirror is blind to exactly
this class of effect.

This matters mechanically, not just procedurally. **E1 substitutes a free
developing action for a terminal one, capped at 12 per turn.** Its measured
effect was attack-first **42.4% → 0.1%** against a field rate of **2.0%** — an
overshoot past the field, in the direction of attacking *later*. Our worst
envelope deviation is that we attack too late and too seldom. E1 may be paying
mirror velocity to buy ladder tempo loss.

### The arms (running)

Added to `horizon_test.py`, deck `metaG_grimmsnarl_top10.csv`, 300 games each:

| arm | config |
|---|---|
| `TE_FULL` | shipped build — E1 + E2 + T1 + T2 |
| `TE_NOE1` | **E1 off** — E2 + T1 + T2 |

### PRE-REGISTERED BANDS — fixed before reading any output

Primary readout: **attack share per own turn** (`horizon_counters.py`
`atk_turns / own_turns`, the §6n unit), plus first-attack turn from the
transcripts. Field envelope: **0.44–0.64**.

| band | condition | action |
|---|---|---|
| **FIRES** | `TE_NOE1` atk/turn exceeds `TE_FULL` by **≥ 0.05** and moves toward 0.44 | E1 is a measured tempo cost. Escalate to a 300-game head-to-head A/B, `TE_NOE1` vs `TE_FULL`; ship only on CI-low > 50% |
| **AMBIGUOUS** | delta **0.02 – 0.05** | record, do not act — inside the 0.019–0.025 mirror noise band |
| **NULL** | delta **< 0.02**, or wrong sign | E1 is not the tempo cause. Close the hypothesis and move to Part 5 |

Secondary, reported either way and **not** used to trigger action: whether the
shipped build sits inside the field envelope at all. If `TE_FULL` reads ~0.2
against a field 0.44–0.64, that is a standing finding about the ship build
regardless of what E1 does, and it belongs in the writeup.

**Caveat that limits every conclusion here:** this is mirror self-play, the
instrument our own §4 catalogue documents as blind to strictly-dominated fixes
and as overstating ladder strength ~2×. It can measure *behaviour* (rates,
turns) honestly, because both seats are the same agent and the rates are
absolute, not relative. It cannot measure *strength*. Nothing ships off this
screen alone.

### RESULT — run 2026-08-02, 300 games per arm, `metaG_grimmsnarl_top10.csv`

`horizon_counters.py`, both seats pooled (same agent), 4,233 / 4,232 own turns:

| metric | `TE_FULL` (shipped) | `TE_NOE1` (E1 off) | delta |
|---|---|---|---|
| **attack share / own turn** | **45.0%** | **48.3%** | **+3.3 pt** |
| attack-when-legal uptake | 89.6% | 88.5% | −1.1 pt |
| first attack (own-turn ordinal) | 3.64 | 3.58 | −0.06 |
| ATTACK share of MAIN decisions | 8.4% | 9.9% | +1.5 pt |
| PLAY share of MAIN decisions | 41.1% | 37.7% | −3.4 pt |
| ENDs | 2,165 | 2,006 | — |
| ENDs with development available | 0.0% | 0.0% | — |

**Verdict: AMBIGUOUS — 0.033, inside the pre-registered 0.02–0.05 band. Record,
do not act.** E1 does shift the mix exactly as designed (PLAY up 3.4 pt, ATTACK
down 1.5 pt) and it does cost attack share, but the effect sits inside the
0.019–0.025 mirror noise band's neighbourhood and does not clear the 0.05 bar.
No escalation to A/B. No flag change.

### The premise was wrong, and that is the more useful finding

**`TE_FULL` reads atk/turn 0.450 — inside the field envelope 0.44–0.64**, at its
lower edge. The shipped Grimmsnarl build is **not** the 0.18-atk/turn agent that
motivated this screen.

Those readings — BEHAVIORAL_GAP_DIAGNOSIS 0.18 / FA T7.91, and FINAL_PATH's live
row 0.24 / FA 6.1 — belong to the **retired search+Garchomp canary**, and I
carried them onto the current build without checking. They are stack-specific,
not an agent-wide property. First attack lands on own-turn 3.6 in both arms;
there is no tempo collapse here to fix.

Two limits on how far that goes:

1. **Mirror ≠ ladder.** 0.450 is measured against ourselves; the 0.44–0.64 field
   band was measured on top-10 *ladder* replays against real opponents. Our own
   writeup §8 records mirror overstating ladder strength ~2×. This does **not**
   establish that the shipped build sits inside the envelope on ladder — it
   establishes that the 0.18 figure was never about this build.
2. **Unit ambiguity, flagged not resolved.** Our first-attack number is an
   *own-turn ordinal* (3.64). The field's 4.1–5.6 comes from
   `behavioral_profile_jul21.py` and may be an absolute game turn, in which case
   the two are not directly comparable. This project has already published one
   retraction from getting a per-decision/per-turn unit backwards; the
   comparison is not quotable until the field script's unit is confirmed.

**Consequence:** Part 4 closes. The E1-tempo hypothesis is dead, the envelope
premise behind it was mis-sourced, and the honest next step is Part 5 — with the
standing caveat that we still have **no ladder-unit envelope measurement of the
build we actually ship.** Getting one costs a canary and n≥40, not a code change.

## PART 5 — Part 4 read AMBIGUOUS, so this is the development path

Resume **Path 2** — harden our search shell toward the 881 recipe — but only the
components that are still untried. Three of the original eight are already dead
on our stack (`EVAL_FIX`, `PROMOTE_RULE`, `LETHAL_PROBE` are all present,
default-off, and verified inert), and END_VETO measured μ509 at n=26 on the
retired stack and "did not convert."

What is left, ranked by his measured effect size:

| component | his effect | our status | est |
|---|---|---|---|
| **Competent symmetric opponent model in rollouts** | **0.20 → 0.60 — his single largest jump** | partial (v1 both seats, asymmetric quality) | 1.5 d |
| Engine-probed multi-selects (card-advantage leak) | not isolated | missing — we score heuristically | 1 d |
| Richer eval terms with ABSTAIN discipline | "facts ≈ 16 pts, weights ≈ 0" | 3-term now | 1 d |
| Anti-dominated rule on every MAIN return path | not isolated | missing | 0.5 d |

The opponent model is the one to build first: it is the largest documented
effect in his arc, it is selection/evaluation-side (where Part 3 localizes all
the value), and it is the one slot where our S3 null does *not* apply — S3
tested the rollout *policy*, this is the rollout *opponent*.

**Honest prior:** Path 2's original central estimate was μ950–1080. That was
written when all eight components were live. With three dead and one
non-converting, the remaining four carry maybe half the arc. Revised central:
**μ880–960**, tail ~1030. That is a real improvement over 700 and it is
probably not 1000.

## PART 6 — The recommendation, in order

1. **Today — Sanjay re-uploads v7 (54855847).** Largest single delta available,
   +~178 μ expected, zero development, one upload. Fill in the slot-state table
   before and after.
2. **Today — freeze the second slot.** No experimental upload without the full
   gate chain. Slots, not compute, are the scarce resource now.
3. ~~Read the Part 4 screen.~~ **Done 2026-08-02 — AMBIGUOUS, no action.** E1 is
   not a tempo bug and the 0.18-atk/turn premise was mis-sourced from a retired
   stack. Cost: ~10 minutes. One standing gap remains from it: we have no
   ladder-unit envelope read of the build we ship.
4. **Aug 3–10 — Part 5**, opponent model first, one variable at a time, each
   behind its own flag with a fire counter.
5. **Aug 12 — train/experiment stop** (standing rule, DECISION_JUL21 §195).
   Final decision: challenger ships into slot 2 only if it beat the battery
   *and* canaried ≥ v7+30 settled at n≥40. Otherwise v7 rides alone.
6. **Aug 16 — lock.** Writeup continues to **Sep 13** (see
   `report/REVIEW_NOTE.md`); the agent freezing does not freeze the report.

**Expected outcome, stated plainly:** μ850–950 by the lock, with v7 restored as
the floor. **P(μ ≥ 1000) ≈ 10–15%**, concentrated in the upper tail of the
600–955 re-roll variance stacking with a converting opponent-model build. Anyone
promising better than that from this position is reading the mirror, not the
ladder.
