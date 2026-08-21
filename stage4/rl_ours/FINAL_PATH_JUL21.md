# FINAL PATH — committed decision to Aug 14 (analysis run 2026-07-22 evening)

Sources, read in full before any conclusion: [SANJAY_CONTEXT_JUL20.md](SANJAY_CONTEXT_JUL20.md)
(rev 15), [HANDOFF.md](../../HANDOFF.md) (PPO capacity-ladder handoff),
[report/HANDOFF.md](../../report/HANDOFF.md) (Stage-3 handoff),
[stage4/writeup_notes.md](../writeup_notes.md) §1–§6h.

Replay evidence: FOUR top-10 snapshots — 07-12 (Phase 2, 883 sides),
07-19/20 (teammate's §6n measurements, 599+1200 games), 07-21 morning
(277 eps, 350 sides, `replays_top10_jul21/`), **07-22 evening (261 eps,
337 sides, `replays_top10_jul22/`, harvested ~1 h ago via
`harvest_jul22_evening.py`)**. Team-best live: v7 μ~878–881. Target:
**cross μ1000 by Aug 14 freeze**. Effective runway from Jul 23: 22 days,
lab intermittent, laptop A/B = 4–6 h per 400 games.

---

## PART 1 — Current top-10 (fresh) and the durable/volatile split

### The board as of 2026-07-22 evening (read live; replays harvested same hour)

| # | team | μ | archetype (from 30 fresh replays each) | dtime med | FA | FE | hand T3/T5/T7 | xDr/t | atk/t |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Luca | 1211.6 | Grimmsnarl ex / Munkidori | 162 ms | 4.9 | 3.6 | 5.7/5.3/5.5 | 2.5 | 0.60 |
| 2 | Yudai Ueno | 1147.8 | **Cynthia's Garchomp (our deck!)** | **36 ms fast** | 4.7 | 3.6 | 5.1/3.9/6.0 | 2.4 | 0.56 |
| 3 | Eduardo R. de A. | 1129.5 | Grimmsnarl / Munkidori | 45 ms | 4.3 | 3.5 | 6.2/5.9/5.2 | 2.9 | 0.62 |
| 4 | Majkel1337 | 1122.7 | Fezandipiti / Dudunsparce | 186 ms | 4.4 | 3.9 | 6.5/9.2/8.3 | 4.9 | 0.53 |
| 5 | kashiwashira | 1120.4 | TR Mewtwo stall | 29 ms | 4.7 | 4.1 | 5.9/5.7/6.2 | 3.3 | 0.58 |
| 6 | junlee789 | 1119.6 | **Cynthia's Garchomp** | **1208 ms search** | 4.8 | 3.6 | 5.1/4.2/5.4 | 2.1 | 0.53 |
| 7 | LumenLiquidity | 1115.6 | Dragapult / Fezandipiti | 61 ms | 5.5 | 3.7 | 6.0/5.3/5.1 | 3.0 | 0.44 |
| 8 | Yushin Ito | 1115.5 | Fezandipiti / Dudunsparce | 236 ms | 3.7 | 3.7 | 6.8/8.2/9.3 | 5.2 | 0.64 |
| 9 | Rmy | 1112.9 | Grimmsnarl / Munkidori | 60 ms | 5.4 | 3.7 | 5.5/5.2/4.9 | 2.0 | 0.52 |
| 10 | Budew | 1112.7 | Mega Kangaskhan / Crustle | 49 ms | 9.2 | 3.9 | 7.4/7.3/7.4 | 2.6 | 0.29 |

(Per-TURN units throughout, §6m rule. No `Ability` log exists in this replay
schema; `xDr/t` = extra draws per own turn is the draw-engine proxy. New-list
flag: Yudai Ueno's Garchomp and Rmy's Grimmsnarl are variant lists not yet
diffed card-by-card against our stored `metaC_garchomp_nasuo.csv` /
`deck_alakazam_top.csv` intel — flagged for card-intel refresh, low priority.)

Our live row for contrast (61 sides, morning harvest): **atk/t 0.24, FA 6.1,
hand 4.5/4.2/4.3** — outside the top-10 envelope on every per-turn metric.

### VOLATILE — true this week, useless to build on

- **Who is #1: four different teams in four snapshots** (Majkel 07-12 →
  Yushin 07-19 per teammate → Oshbocker 07-21 09:37 → Luca 07-22 evening).
- Intra-DAY churn measured today: Oshbocker μ1212 #1 at 09:37 → **out of the
  top 20 by evening**; Yudai Ueno rank 174 → #2 in one day; THIRD PTCG Club
  1186 → 1088. This is the byte-identical-variance band (600–955, repo2)
  acting on live scores.
- Archetype seat counts: Crustle 5 seats (07-12) → 0 (07-21) → 1 (07-22).
  Grimmsnarl 4 → 3. Alakazam 1 → 0.
- Any single team's μ below the top ~3.

### DURABLE — held across all four snapshots (build only on these)

1. **Piloting, not deck, decides rating.** Strongest form yet tonight: the
   SAME Garchomp archetype holds #2 (fast policy, 36 ms) and #6 (search,
   1208 ms) simultaneously, while we shipped it at μ548–697. Within-archetype
   spread across pilots ≫ between-archetype spread. (Chain: §6m pilot-vs-deck
   z=2.42; Lucario mirror 31.5% n=1000; Grimmsnarl curve test; our μ548
   Alakazam; tonight's two-seats-one-deck.)
2. **Grimmsnarl/Munkidori is the strongest archetype and holds a top-3 seat
   in every snapshot** — measured 65.7% vs field tonight (n=102), replicating
   the teammate's 66% (n=1200) to within 0.3 pts, on a different week and
   different pilots. No archetype beats it at any quotable n.
3. **No RPS cycle** (tonight's matrix below; his 1200-game null; repo1's
   cycle claim dead for weeks).
4. **Both speed classes coexist at the top; neither excludes the other.**
   Tonight: 6 fast seats (29–61 ms), 4 deliberate seats (162–1208 ms).
   The morning read ("search-class rising") was over-fit to one snapshot —
   corrected here. What IS durable: every route WE have tried to a top-tier
   fast policy has failed at n≥300 (six imitation negatives, PPO capacity
   ladder flat at 27–28% across 27.8k/128k/256k), while both teams' search
   agents produced their teams' best-ever scores (his 881; our 614 pre-fix).
5. **The top-10 per-turn behavioral envelope is stable**: attack-share
   0.44–0.64 of own turns (Budew's 0.29 stall excepted), first evolution
   T3.5–4.1, hand held or grown from T3→T7. Our live agent (0.24 atk/t,
   hand decaying) sits outside it in every snapshot. This envelope — not any
   specific opponent — is the target.
6. **Correctness fixes beat strategy** (his +114 revenge fix vs 14 refuted
   strategy hypotheses; our D9/governor arc same shape).
7. **Ladder Elo variance is enormous**; no read below n≈40 episodes, ever.

---

## PART 2 — Counter-deck question: CLOSED, permanently, with tonight's numbers

Cross-archetype matrix from tonight's 337 top-10 sides. n≥60 rule enforced —
only pooled-opponent rows qualify; every per-cell rate is below n=60 and is
therefore directional-only:

| archetype (top-10 pilots) | vs pooled field | n | quotable? |
|---|---|---|---|
| Grimmsnarl / Munkidori | **65.7%** | 102 | yes |
| Fezandipiti / Dudunsparce | 52.7% | 74 | yes |
| **Cynthia's Garchomp (ours)** | **54.7%** | 64 | yes — first n≥60 read we have ever had on our own archetype |
| TR Mewtwo stall | 75.0% | 36 | no (n<60) |
| Dragapult / Fezandipiti | 45.2% | 31 | no |
| Kangaskhan / Crustle | 50.0% | 30 | no |

Directional cells (n=20–30, NOT quotable): Garchomp vs Grimmsnarl 15W–12L;
Fez/Dudu vs Grimmsnarl 10W–20L; Grimmsnarl mirror, top-10 pilot vs any
Grimmsnarl, 16W–6L — that last one is *within-archetype pilot spread*, i.e.
more durable-fact-1, not a matchup fact.

**EV of a counter-deck ship.** Best case in the data: nothing beats
Grimmsnarl at quotable n. Take the directional Garchomp-beats-Grimmsnarl 55%
at face value and a 30% Grimmsnarl encounter share:
EV = 0.55×0.30 + 0.50×0.70 ≈ **51.5%** before piloting penalty. Our measured
penalty for piloting an unfamiliar deck is 20–25 pts (31.5% Lucario mirror
n=1000; 1/4 Grimmsnarl development rate; μ548 Alakazam ship). Net ≈ **30%** —
strictly dominated by doing nothing (v7 rides at an implied ~55%).

**CLOSED.** Reopening requires a within-team n≥60 measurement of ≥50% on the
candidate deck by our own agent — which no candidate has ever produced. The
deck question for this team is settled: **Garchomp**, which we already hold,
now field-validated at 54.7% (n=64) and carrying two top-10 seats.

---

## PART 3 — Why imitation failed: one finding

Seven independent negatives across two stacks (was six; our S3 rollout null
completed the set):

| # | attempt | result |
|---|---|---|
| 1 | Our BC-Garchomp (G6a) | 31.0% vs v2.0.0 — fail |
| 2 | Our BC-full two-headed (G6c) | 44.7% — fail |
| 3 | Our BC-v2 + brake (G7a) | 39.0% [33.7, 44.6] — kill |
| 4 | Our PPO capacity ladder 27.8k→128k→256k | flat 27–28% vs v2.2.0, 83k+ games — capacity-limited at every rung |
| 5 | His BC priors in-tree | 0.367 vs hand rollout — harmful |
| 6 | His value net (gates passed) | −82 Elo — harmful (signal-shape) |
| 7 | Our BC-junlee as search rollout (S3) | 48.8% [43.9, 53.6] n=400, three configs — null |

**The unified finding.** Top-ladder strength is *per-turn decision quality
inside the durable behavioral envelope* (fact 5), and that quality is
computed, not recalled. The evidence localizes it precisely:

- **Replays are the wrong supervision signal**: static accuracy 69–97%
  coexisted with 31–49% head-to-head in every BC attempt, both stacks. The
  expert's replay shows WHAT was chosen, never the counterfactual structure
  (what would have lost) that made it right. Both teams fit the surface and
  missed the computation.
- **The computation that matters is selection/evaluation/probing, NOT
  rollouts**: our S3 null (48.8%, n=400, engagement-verified) shows rollout
  policy quality is not binding at ~13-det truncated-MC depth. His arc says
  the same from the positive side — his biggest measured jumps were the
  in-tree opponent model (0.20→0.60), engine-exact lethal probes, blunder
  veto, and one evaluation-correctness fix worth +114 Elo. All
  selection/evaluation-side. His §6i: 96% of rollouts hit the depth cap and
  are scored by the evaluator — the evaluator and what the tree chooses to
  expand ARE the agent.
- **Fast policies at the top do not contradict this** — they are the same
  decision quality reached by a longer engineering road (or better learning
  than we have achieved; six negatives say we don't have that road at
  current model class inside 3 weeks). The 285 ms/dec #1 of his era and the
  162–1208 ms top seats tonight show deliberate computation is one proven
  road; our own 366→881 observation of his arc shows it is walkable in days,
  not months.

**Therefore the winning path must attack search selection/evaluation/probe
quality on our own stack.** That is the differentiator the evidence names.

---

## PART 4 — Paths, evaluated, then the commitment

### Path 1 — our identity-aware nets into HIS 881 shell (root prior / in-tree selection)

The G-S1 null does NOT refute this: G-S1 tested the ROLLOUT slot (what a
playout returns); a root prior biases WHICH branches get the search budget —
a selection-side mechanism, exactly where Part 3 localizes the value. But the
null does lower the prior: both slots consume the same per-option preference
quality, and ours was indistinguishable from v1's ordering where we measured
it. Downgrade central by ~15 pts vs a no-null world.
- **Expected μ:** floor 878 (gate structure prevents regression); central
  900–950; tail ~1000. Chain: his 0.20→0.60 opponent-model jump bounds the
  mechanism's potency; his BC-prior failure was feature-caused (0.388 top-1
  identity-blind) and ours are 0.61–0.69 — the diagnosed defect is removed,
  but "removes his failure cause" ≠ "beats his hand stub" (S3 taught exactly
  that lesson one slot over).
- **Cost:** 3–4 days integration + 1 day A/B — IF his repo lands.
- **Dependency: HIS repo/coordination. Silent since Jul 20.** P(usable by
  Jul 25) subjectively 30–50%.
- **Kill:** no repo by Jul 25 → drop; A/B <50% CI-low → drop.
- **Verdict: opportunistic add-on only. Cannot be the committed path — its
  start condition is outside our control.**

### Path 2 ⭐ COMMITTED — harden OUR search shell to his 881 recipe, on Garchomp

His doc is a build guide with measured effect sizes AND a refutation table
(7 dead ends we get to skip). Our shell already has: working belief tracker +
determinizer (CardTracker), governor (fixed and telemetry-verified this
week, seed+cap+warmstart+hysteresis), C1-validated fallback chain, V1-immune
deployment. What it lacks is precisely his list:

| component (his measured effect) | our status | build est |
|---|---|---|
| Engine-exact lethal probe `_find_lethal` | missing | 1 d |
| Blunder veto `_loses_immediately` (+ D4-class world-count guard) | missing | 0.5 d |
| Anti-dominated rule on every MAIN return path | missing | 0.5 d |
| Competent symmetric opponent model in rollouts (his 0.20→0.60) | partial (v1 both seats, asymmetric quality) | 1.5 d |
| Engine-probed multi-selects (card-advantage leak) | missing — ours scores heuristically | 1 d |
| Evaluation correctness audit: scaling/conditional attacks reading printed damage (his +114 Elo class) | unaudited in `_attack_damage_est` | 0.5 d audit + fix |
| Richer eval terms w/ ABSTAIN discipline (his §6j "facts ≈ 16 pts, weights ≈ 0") | 3-term now | 1 d |
| Promotion rule (maxHp + 30·energy) | missing | 0.5 d |

~7–8 build days ≈ 12–15 calendar days at 3–5 h/day, leaving gate + canary
room. Skipped via his refutation tables: attack-rate forcing, ability-rate
forcing, energy-cause theories, deck swaps, KO-metric circularity, promotion
raw-HP form, action-flip testing without null control.
- **Expected μ:** floor 878; **central 950–1080**; tail ~1150. Chain:
  (i) his 366→881 arc = +515 from exactly this component list on a WORSE
  deck (Trevenant, 30 dmg/energy); (ii) our shell starts from a working
  μ614-class search, not from random-play 366, so we're buying the top half
  of his arc, not all of it; (iii) the deck we run it on is field-validated
  54.7% (n=64) with two top-10 seats, and the search seat (junlee789,
  1208 ms — our speed class) sits at μ1120–1152 across the day = the
  demonstrated ceiling for "search pilot + this deck"; (iv) haircut for
  3-week execution and for his lesson that most fixes measure neutral
  offline (mirror A/Bs cancel — hence ladder-facing gates below).
- **Dependencies: none external.** Lab optional (A/B nights).
- **Writeup value:** high both ways — a reproduction study of an
  independently-documented hardening arc, with pre-registered gates, on a
  second stack. Methodology-chapter gold even if the ladder result is flat.

### Path 3 — depth/throughput attack — DOMINATED
Part 3 localizes value to selection/evaluation, not depth; 6 of tonight's
top-10 run at 29–61 ms (depth is manifestly not the axis); and his D2
finding showed deeper rollouts are a *losing* trade at fixed budget. Dead
unless Path 2's profiling (incidental) reveals we're leaving >2× budget
unused — even then it's a tuning knob inside Path 2, not a path.

### Path 4 — counter-deck ship — CLOSED by Part 2 (net ≈30% after piloting penalty). Never reopens without a within-team n≥60 ≥50% measurement.

### Path 5 — hold 881 + writeup — THE FLOOR
Every experimental path risks exactly one thing vs this floor: displacing a
converged v7 with a mid-convergence candidate inside a 600–955 variance
band. Mitigation is structural, not hopeful: **v7 is never displaced; any
candidate ships into the v8 slot only** (Kaggle keeps latest-2; re-submit v7
first if needed per the standing slot rule), and only after the full gate
chain below.

### THE COMMITMENT

**Path 2, on Garchomp, starting Jul 23. Path 5 is the floor. Path 1 folds in
as a stage-2 add-on ONLY if his repo arrives before Jul 28 (its payload —
our nets as selection prior — then runs on OUR hardened shell through the
same gates). Paths 3 and 4 are dead.**

One committed path; everything else is conditioned, gated, or closed.

---

## PART 5 — Day-by-day, gates, kills

Calendar: Jul 23 → Aug 14. My assumptions: 3–5 h/day engineer time; lab days
unknown — every 400-game A/B below runs fine overnight on the laptop (4–6 h);
a lab day, when one lands, compresses that day's gate from overnight to ~1 h
(◆ = nice-to-have, never blocking).

| dates | work | gate / decision point |
|---|---|---|
| Jul 23 | Evaluation-correctness audit (`_attack_damage_est` vs scaling/conditional attacks — his +114 class) + fix; unit tests on known cards | — |
| Jul 24–25 | `_find_lethal` engine probe + blunder veto + anti-dominated, all on every MAIN return path; smoke 20 | — |
| Jul 25→26 (overnight) | **GATE A**: 400 g, single variable = {audit fix + probes + veto + anti-dominated} vs current shell | CI-low>50% ADOPT; 46–54% one mechanism-fix retry; <46% component-wise bisect before proceeding |
| Jul 26–27 | Engine-probed multi-selects | — |
| Jul 27→28 (overnight) | **GATE B**: 400 g, single variable = multi-select probing | same rule |
| Jul 28–30 | Competent symmetric opponent model in rollouts + retreat/bench rollout competence (his items 1–2) | Path-1 fold-in decision point: repo arrived? |
| Jul 30→31 (overnight) | **GATE C**: 400 g, single variable = opponent model | same rule |
| Jul 31–Aug 1 | Eval terms (+ABSTAIN discipline) + promotion rule | — |
| Aug 1→2 (overnight) | **GATE D**: 400 g, single variable = eval+promotion bundle *(bundle allowed here only because each term carries an ABSTAIN path; if D fails, bisect)* | same rule |
| Aug 2→3 | **GATE E (consolidated)**: hardened shell vs v2.2.0-Garchomp AND vs the v1-archetype pool, 400 g each | **ship-consider bar: CI-low > 55% vs v2.2.0** |
| Aug 3–4 | Bundle pre-flight (V1 sim, SELFCHECK, fault suite, 30-game zero-crash, <190 MiB, deck validate) | — |
| Aug 4–5 | **User ships canary into the v8 SLOT ONLY** (v7 untouched; re-submit v7 first if slot order requires) | — |
| Aug 5–8 | Canary convergence — **no read before n≥40 episodes** (durable fact 7) | keep if settled ≥ 908; revert slot to v7 backup if < 850 |
| **Aug 8** | **HARD PIVOT to writeup regardless of state.** Any component not yet gated is recorded at its last gate state | pre-registered, no exceptions |
| Aug 8–13 | Writeup: S1–S3 arc, governor§6h coupling, this memo's 4-snapshot analysis, reproduction-study chapter | — |
| Aug 14 | Freeze. Ship state = whatever passed; floor = v7 + v2.2.0 | — |

**Pre-registered discipline (all gates):** 400 games, seats alternated,
single variable per A/B (Gate D's exception documented above), Wilson 95%,
governor engagement telemetry (ema/max_ema/avg_dets/warmN/hystM) checked
BEFORE reading any win rate — an unhealthy-engagement run is void, not
reinterpreted; no quoted rate below n=60; per-TURN units for all behavioral
claims; ladder reads at n≥40 episodes only.

**Kill criteria with dates:**
- Any two consecutive gates (A–D) at <46% CI-low → the recipe is not
  transferring; halt build, Path 5 immediately (earliest possible: Jul 28).
- Gate E < 55% CI-low by Aug 3 → do not ship; Path 5 (writeup gets a
  completed reproduction study with a negative transfer result — still a
  chapter).
- No canary ≥908 by Aug 8 → v7 rides; writeup mode.
- Governor telemetry unhealthy in any gate → fix before interpreting;
  the §6h coupling paragraph in writeup_notes already names this risk.

**Path-1 fold-in (only if his repo lands ≤ Jul 28):** our MAIN-head net as
expansion/selection prior in OUR shell, blend-weighted, one variable,
its own 400-game gate slotted after C. The message to send him now:

> Sanjay — committed path is hardening our search shell to your 366→881
> recipe on Garchomp (two top-10 seats on that deck tonight; junlee789's
> search pilot at ~1120–1150 is the ceiling proof). Your doc + refutation
> tables are the build guide — thank you, it's a map. One optional ask: if
> you can share agent/mcts.py (or the whole repo) by Jul 28, we'll also gate
> OUR identity-aware net as a selection prior inside our hardened shell —
> your §7-item-3 experiment, run on our stack, one variable, n=400. After
> our rollout-slot null (48.8% [43.9,53.6], n=400, engagement-verified) the
> selection slot is the remaining untested mechanism. No slot coordination
> needed; nothing we ship touches v7.

---

**STOP.** Memo complete. Implementation begins on your sign-off only.
