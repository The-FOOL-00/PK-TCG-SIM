# PHASE 2 — conditional policy design

**DESIGN ONLY. Nothing built, nothing submitted.** v1-alone; governor,
`cap=16`, `END_VETO`, `EVAL_FIX`, `PROMOTE_RULE`, `LETHAL_PROBE`, the
candidate-set arms and R1/R2/R3 all stay off. Every rule below gets its own
flag, defaults off, and lives in the **always-active** path — never inside
`_pilot_score_main`, which no bundle bakes.

> **Screen calibration, restated up front.** Self-play overstates ladder by
> roughly **2×**: Grimmsnarl measured **0.4574** in self-play and **0.2370** on
> ladder (n=19). **A passing screen means "worth a ladder slot", not "this
> works."** No ship decision rests on a self-play margin smaller than 2× the
> effect we care about.

---

# 0. MANDATORY MEASUREMENT — the lethal split. **Hypothesis REFUTED.**

The brief required this before designing: partition the `can_KO` cell by whether
the KO takes the last prize. The expectation was that top-10's 22% ATTACK share
is "mostly the game-winning subset."

**It is not.**

| top-10 Grimmsnarl, inside `can_KO` | n | PLAY | ATTACH | EVOLVE | **ABILITY** | RETREAT | **ATTACK** |
|---|---|---|---|---|---|---|---|
| **GAME-WINNING KO** (takes last prize) | **595** | 23.7% | 8.1% | 3.7% | **37.8%** | 0.5% | **26.2%** |
| **NON-FINAL KO** | **4462** | 36.1% | 8.4% | 9.9% | 23.8% | 0.8% | **21.0%** |

**ATTACK share differs by 5.2 points, not by the margin the hypothesis needed.
Even holding a game-winning KO, top-10 attack on only 26.2% of those decisions —
and fire an ability on 37.8%.**

Game-winning decisions are 11.8% of their `can_KO` cell and 10.6% of ours, so
the two populations are comparable.

### Why they still act first when the KO ends the game

The most likely explanation, and it matters for the design: **`can_ko` is a
printed-damage proxy.** Munkidori's ability moves damage counters, and this deck
runs 4 copies. An ability fired before the swing is frequently *how the KO is
secured*, not value taken instead of it. Firing abilities first is therefore
correct even at lethal.

### Consequence for the design — stated plainly

**The game-winning carve-out the brief mandated is not supported by the
evidence.** I have not made it E1's default. It is implemented as a separate
sub-flag (**E1b**, default **off**) so the screen can test it directly rather
than assuming it.

The first-principles argument for it remains sound in the abstract — a
game-winning attack makes later actions worthless. The data says top-10 do not
play that way, most plausibly because the ability *is* part of reaching lethal.
Screening it is cheaper than arguing it.

---

# 1. THE SPINE — sequencing by reversibility

**ATTACK is terminal. Every other MAIN action is free.** A tier ladder answers
"which action scores highest?"; the operative question inside a turn is "which
action ends it?"

| | top-10 | ours |
|---|---|---|
| attacked as the FIRST action of the turn | **2.0%** | **43.0%** |
| actions before the attack | mean 5.87 | mean 2.97 |

**These rules are gates on ordering, not score changes.** A-WEIGHT already
failed by reweighting attack, and it failed while being unshippable. E1–E4
remove options from consideration under stated conditions and leave every v1
weight untouched.

## What I am NOT designing, and why

The brief's original Phase 2 sketch proposed six phases (SETUP / DEVELOP /
PRESSURE / CLOSING / BEHIND / STABILISE). **Phase 1 does not support a six-phase
taxonomy.** Most of those phases have no cell with a distinct action
distribution behind them: turn buckets diverge weakly (`turn=T7+` TVD 0.156),
race state diverges weakly (E4 below), and there is no cell at all
distinguishing "DEVELOP" from "PRESSURE". Building a taxonomy would mean
inventing five orderings from one or two cells.

**The evidenced structure is four discrete gates, not six phases.** I have
designed those and listed the unevidenced ideas separately in §6.

---

# 2. THE RULES

## E1 — TERMINALITY SEQUENCING *(rank 1)*

**Trigger.** At a MAIN decision where at least one ATTACK option is on the menu
**and** at least one *board-advancing card play* is also on the menu — option
type `PLAY`, `ATTACH` or `EVOLVE`.

**Action.** Exclude ATTACK options from selection for this decision. v1 then
picks its best free action from the unchanged score vector. Attack becomes
selectable as soon as no board-advancing play remains.

**Explicitly not a reweight.** No v1 constant changes. The option set shrinks;
the scoring function is byte-identical.

**Guards, both required:**
- **Turn budget.** Veto at most `E1_MAX_VETO = 12` times per own turn. Top-10's
  p90 is 9 actions before attacking, max 15; 12 sits above the mass without
  allowing an unbounded loop if a repeatable option never clears the menu.
- **Never leave an empty menu.** The veto only fires when a non-attack option
  exists by construction, and `WEIGHT_END = −1e6` keeps END unselected while
  anything else is available.

**Sub-flags:**
- **E1b `lethal exception`** — attack immediately when the KO takes our last
  prize. **Default OFF; §0 argues against it.** Screened separately.
- **E1c `doomed attacker`** — attack immediately when our active is KO-able by
  the opponent's best printed attack **and** it is our only powered attacker.
  Evidence is indirect (`KOable & attacker_powered`, n=2965/1063, TVD 0.266).
  Default OFF, screened after E1.

| | |
|---|---|
| **Evidence** | turn-sequence 2.0% vs 43.0% (n=1903/755 attacking turns); `can_KO` n=5057/451, TVD 0.784 |
| **Expected effect** | attack-when-legal per **turn** roughly unchanged (we still attack, just later in the turn); **actions per turn up**; prizes/game **up**; own turns/game **down or flat**; first attack turn **later by design** |
| **Blast radius** | **Large.** Touches every decision where attack and a card play coexist — 31.9% of decisions (`atk_legal & supporter_pending`) plus more. This is the highest-risk rule here. |
| **Falsified if** | prize velocity does not improve, or own turns/game rises (meaning we develop more but convert less), or attack-when-legal per turn *falls* (meaning the veto is eating attacks rather than deferring them) |

⚠️ **The specific failure mode to watch:** if free options never exhaust, the
veto defers the attack until the turn ends and we simply stop attacking. The
`E1_MAX_VETO` guard bounds it, and **attack-when-legal per turn is the counter
that detects it.** It must not fall.

## E2 — ABILITY-BEFORE-COMMIT *(rank 2)*

**Trigger.** ATTACK on the menu **and** at least one `ABILITY` option available.

**Action.** Exclude ATTACK options for this decision.

**Deliberately scoped to abilities only** so it is separable from E1 — see §3.

| | |
|---|---|
| **Evidence** | `atk_legal & supporter_pending` n=6170/1390: ABILITY **30.6% vs 4.5%** (−26.1). `turn=T7+ & powered` 30.9% vs 12.2%. `supporter_pending` 26.2% vs 5.9%. §0: 37.8% ability share even at lethal. |
| **Expected effect** | ability uptake up sharply; prizes/game up (Munkidori damage-shifting secures KOs the printed proxy misses); own turns flat |
| **Blast radius** | **Moderate.** Abilities are once-per-turn and self-clearing from the menu, so the loop risk is far lower than E1's. |
| **Falsified if** | ability uptake rises but prize velocity does not — meaning the abilities we fire are not the ones that matter |

**Note on R1.** PILOT_KNOWLEDGE's R1 raised ability priority globally in the
static ladder and failed (+2.2, CI spanning zero, and it cost 1.3 own turns).
E2 is a different intervention: the problem is not the global rank, it is that
abilities are skipped **specifically when attack is on the menu**, because
attack wins and ends the turn. R1's failure is not evidence against E2.

## E3 — RETREAT SUPPRESSION *(rank 3)*

**Trigger.** `RETREAT` on the menu **and** our active is **not** KO-able —
opponent's active's best printed attack damage < our active's current HP.

**Action.** Exclude RETREAT options.

| | |
|---|---|
| **Evidence** | `safe_active` n=14036/3912: retreat **8.6% vs 1.6%**. `supporter_done` n=7301/2493: **13.2% vs 2.5%**. |
| **Expected effect** | energy retained on the attacker; first attack **earlier**; own turns down slightly |
| **Blast radius** | **Small.** Retreat is 3.9–13.2% of our decisions and the rule only fires in the safe subset. |
| **Falsified if** | prize velocity flat and own turns rise, indicating we are stranding a bad active we should have swapped |

**Known limitation:** the threat estimate uses printed damage only — no
abilities, tools or weakness. It will misjudge some genuinely dangerous boards
as safe, which makes this rule slightly too aggressive. That is the honest
error direction and it is worth screening rather than hand-tuning.

## E4 — PRIZE-RACE CONDITIONING *(rank 4 — weakest evidence, stated as such)*

**Trigger.** Race state from prizes remaining: `BEHIND` = ours > theirs,
`AHEAD` = ours < theirs.

**Action.** When **BEHIND**, disable E1's veto (push damage, accept the tempo
cost). When **AHEAD**, apply E1 and E2 normally.

| | |
|---|---|
| **Evidence** | `can_KO & race=BEHIND` vs `can_KO & race=AHEAD`: their ABILITY share **23.4% → 33.0%**, PLAY 39.7% → 27.6%. Ours is **100% ATTACK in both** — we have no race-conditional behaviour at all. |
| **Expected effect** | small; mostly protects E1 from over-applying in losing positions |
| **Blast radius** | Small — it only modulates E1. |
| **Falsified if** | it changes nothing, which is the likely outcome |

**This is the weakest of the four and I am ranking it last deliberately.** The
evidence is a 10-point shift in one action's share across two sub-cells. It is a
real difference in *their* behaviour, but it is thin, and it is a modifier on
E1 rather than an independent effect. If E1 fails the screen, E4 is moot.

---

# 3. INTERACTION ANALYSIS *(required)*

## E1 and E2 — **overlapping; kept as two, scoped to be separable**

As first conceived, **E2 is a strict subset of E1**: abilities are free, so
"don't attack while free value remains" already covers "don't attack while an
ability is available." Bundled, they would be unattributable.

**Resolution: E1 is scoped to card plays only** (`PLAY`/`ATTACH`/`EVOLVE`) and
**E2 to abilities only** (`ABILITY`). The two triggers are then disjoint —
a decision can fire either, both, or neither — and each increment in the screen
is separately attributable.

This costs nothing in coverage: C2 = E1+E2 is exactly the "no attack while any
free value remains" rule, reached in two measurable steps instead of one
unmeasurable one.

**If they had to be bundled**, attribution would require a third arm with E2
alone, and I would report the pair as a single effect rather than claim a split.

## E3 and E4 — **independent, no overlap**

E3 gates RETREAT on a threat condition. E4 modulates E1's ATTACK gate on a race
condition. Different option types, different triggers, no shared state. They can
be screened in either order without confounding.

**One second-order interaction to note:** E3 keeps a weak active in play, which
makes `ko_able` true more often, which is E1c's trigger. If E1c is ever enabled,
E3 and E1c must be screened together or the interaction will be misattributed.
Since E1c defaults off, this does not affect the planned arms.

---

# 4. RANKING — (evidence strength × cell frequency) / implementation risk

| rank | rule | evidence strength | cell frequency | impl. risk | verdict |
|---|---|---|---|---|---|
| **1** | **E1** terminality sequencing | **very high** — 2.0% vs 43.0%, n=1903/755, plus TVD 0.784 | **very high** — attack+play coexist on ~32%+ of decisions | **high** — loop risk, needs the turn-budget guard | **schedule first** |
| **2** | **E2** ability-before-commit | **high** — −26.1 pts, n=6170/1390, replicated in 3 cells | high — 62.2% of decisions have a pending supporter | **low** — abilities self-clear | **schedule second** |
| **3** | **E3** retreat suppression | **moderate** — 8.6% vs 1.6%, n=14036/3912, replicated | moderate — 3.9–13.2% of decisions | **low** — pure exclusion | **schedule third** |
| **4** | **E4** prize-race conditioning | **weak** — one 10-pt shift across two sub-cells | low — modifier only | low | **schedule last; expect null** |

---

# 5. SCREEN PLAN *(stated, not run)*

**Arms**, in Phase-1 evidence order, 100 games self-play each, `PILOT=""`,
Grimmsnarl deck (`metaG_grimmsnarl_top10.csv`, highest measured closure 79.9%):

| arm | config |
|---|---|
| **C0** | current static ladder — baseline, expected ≈ **0.4574** |
| **C1** | + E1 |
| **C2** | + E2 |
| **C3** | + E3 |
| **C4** | + E4 |

Anchors: C0 ≈ 0.4574; Grimmsnarl top-10 envelope **0.5725**.

**Screen metric:** prize velocity (prizes per own turn).

**SCREEN RULE — fixed before running.** An increment is **KEPT** if it improves
prize velocity by **≥ +0.02** with a bootstrap 95% CI **excluding zero**, **and**
does not increase own turns/game. Otherwise it is **DROPPED** and the next
increment is screened on top of the last kept arm. **Every increment is
reported, kept or dropped, with its numbers.**

**Reported per arm:** prize velocity (with bootstrap 95% CI), own turns/game,
prizes/game, attack-when-legal per turn, first attack turn, first evolution
turn, turn of first prize, extra draws/turn, wall-clock p50/p99/max.

**Additional mechanism counters** — a rule that does not fire cannot be judged:
E1 vetoes/turn, E2 vetoes/turn, E3 vetoes/turn, and **actions-before-attack per
attacking turn** (the Phase 1 headline counter — target is movement from 2.97
toward top-10's 5.87).

**Optional ablations, only if C1 passes:** E1b (lethal exception) and E1c
(doomed attacker), each as a single-variable arm against the best kept config.

**This is a SCREEN, not a verdict.** Self-play overstates ~2×. A passing screen
earns a ladder slot and nothing more.

---

# 6. UNEVIDENCED — listed, NOT scheduled

Ideas with no Phase 1 cell behind them. Recorded so they are not silently
smuggled in later:

| idea | why not scheduled |
|---|---|
| Six-phase taxonomy (SETUP/DEVELOP/PRESSURE/CLOSING/BEHIND/STABILISE) | no cell distinguishes DEVELOP from PRESSURE, or CLOSING from AHEAD; would require inventing five orderings from two cells |
| "If opponent ≤2 prizes, prioritise damage over development" | `opp_le2 & can_KO` has n=754/66 — **our side is below the n≥30 floor for a reliable split**, and `opp_le2 & no_KO` did not rank |
| "If turn ≤2 and bench <3, development outranks everything" | `turn=T1/T2` cells did not reach the top-20 by leverage; our T1–T2 behaviour already matches theirs closely |
| Boss's Orders / gust targeting | not a MAIN action-type divergence; would need sub-action mining Phase 1 did not do |
| Energy-attachment target selection | `ATTACH` share diverges by only −3.1 pts in `attacker_powered`; the divergence is *when* we attach, not *where* |

---

## Summary

**The design is four ordering gates, not a phase machine.** E1 and E2 implement
"attack last" in two separately-attributable halves; E3 stops us retreating when
nothing threatens us; E4 modulates E1 by the prize race and is expected to be
null.

**Two things the mandated measurement changed:** the game-winning carve-out is
not supported and defaults off (§0), and the six-phase taxonomy is not supported
and is not being built (§1).

**The largest risk is E1's**, and it is a specific one: a veto that defers
attacks into oblivion rather than sequencing them. Attack-when-legal per turn is
the counter that catches it, and it is in the reported set.

**STOP — Phase 2 gate. Awaiting approval before Phase 3 build.**
