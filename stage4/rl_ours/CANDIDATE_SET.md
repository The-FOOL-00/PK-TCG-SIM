# Candidate-set diagnosis + two-arm fix

**Nothing submitted.** Governor untouched; `cap=16`, the promotion rule and the
lethal probe all remain off.

---

## PRE-REGISTERED READING (written before any arm was run)

**Primary counter: attack-when-legal (per TURN, Sanjay §6n unit).**
H1 baseline **50.5%**; field 86–92%.

| band | verdict |
|---|---|
| **≥ 65%** and no other counter regressing more than 5 points vs H1 | **PASS** |
| 57 – 65% | **MARGINAL** |
| **< 57%** | **FAIL** |

Also reported: **first-attack turn** against the field band **4.1–5.6**. An arm
that improves attack-when-legal while pushing first attack *later* is suspect
and is flagged as such.

Secondary counters, each reported per arm: attack share per own turn, first
evolution turn, extra draws per turn, hand size at T3/T5/T7, median
deliberation, wall-clock p50/p90/p99/max per player-game.

**Bands are fixed as of this commit and are not revised after results.**

### Arms (factorial, END_VETO off in all four)

| arm | `CAND_INCLUDE_ATTACK` | `CAND_ATK_W` |
|---|---|---|
| **H1** baseline | off | off |
| **CI** = A-INCLUDE | **on** | off |
| **CW** = A-WEIGHT | off | **2200** |
| **CIW** = both | **on** | **2200** |

≥ 60 self-play games per arm, Garchomp deck, identical instrumentation.
Field-unit rows come from the same `behavioral_profile_jul21.py` used for the
top-10 table; decision-level rows from `horizon_counters.py`.

---

> ### ⚠️ AMENDMENT 2026-07-27 — measured under a non-shipped `PILOT`
>
> Found while rebuilding the baseline ([RESTORE_V220.md](RESTORE_V220.md)):
> `tools/build_search_submission.py` **never bakes `PTCG_PILOT`**, so every
> shipped bundle runs with `PILOT = ""`. Every arm below set
> `agent_mod.PILOT = "garchomp"`.
>
> **Two consequences.** (1) `CAND_ATK_W` lives inside `_pilot_score_main`,
> reached only under `PILOT == "garchomp"` — **the CW and CIW arms tested a code
> path that would be inert in any bundle the current builder produces.** Their
> FAIL verdict stands; they were never shippable as tested. (2) The ladder
> exclusion rate below is understated. Re-measured on the same 25 VN replays
> with `PILOT=""`: **38.2% excluded (153/401), tempo hook fires 0 times**, and
> still **0 of 153** ended in an attack. The 14.5% "hook fired" reading at
> ship config is exactly the 58 lethal attacks reaching 2450 via
> `WEIGHT_LETHAL`.
>
> The Step 1 finding is unchanged in direction and **stronger in magnitude** on
> the configuration that actually shipped. The verdict (no arm ships) is
> unaffected.

## STEP 1 — the measurement, before anything was built

### `SEARCH_TOPK` is 4. The code, quoted

```python
SEARCH_TOPK = int(os.environ.get("PTCG_SEARCH_TOPK", "4"))   # candidates by v1 score
...
order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
cands = order[:SEARCH_TOPK]
```
[main.py:172](../../main.py:172), [main.py:2599](../../main.py:2599)

The v1 ladder that produces `scores`:

| tier | weight |
|---|---|
| lethal attack | 100000 |
| bench when 0–1 in play | 3500 |
| **energy attach** | **3000** |
| **evolve** | **2800** |
| **item** | **2400** |
| **bench** | **2300** |
| **supporter** | **2150** |
| **tool** | **2100** |
| **ability** | **2060** |
| **stadium** | **2030** |
| **non-lethal attack** | **1000 + min(dmg,1900) × 0.5** |
| retreat / END | −500 / −1000000 |

A non-lethal attack scores 1010–1130 for 20–260 damage — **below every setup
tier.** There is one existing mitigation: `_pilot_score_main` lifts an attack to
`WEIGHT_TEMPO_LOADED = 2450 + dmg×0.5`, but only when `turn ≥ 4` **and**
`dmg > 0` **and** `cur["supporterPlayed"]`.

### Result: the exclusion is real, and it is not rare

Measured over every attack-legal MAIN decision in three independent sources.
Ladder replays are restricted to **our own seat** using the episode index —
`info.TeamNames` in a Kaggle replay reports "Project Mew" for *both* seats and
is not usable for this.

| source | games | attack-legal decisions | **best attack excluded from `cands[0:4]`** | **attack chosen anyway when excluded** |
|---|---|---|---|---|
| **VN ladder** (sub 55003807) | 25 | 401 | **32.4%** (130) | **0.0%** (0/130) |
| **H1 self-play** | 60 | 2369 | **32.0%** (759) | **0.0%** (0/759) |
| **Canary ladder** (sub 54991680) | 28 | 551 | **32.5%** (179) | **0.0%** (0/179) |

**Pooled: 1068 decisions where the best attack was outside the candidate set,
and an attack was chosen in exactly 0 of them.** The exclusion is not a
tendency — it is mechanically absolute, exactly as the hypothesis predicted.

The rate is stable at ~32% across self-play and two different ladder
submissions, which is strong evidence it is a property of the scoring ladder
rather than of any one opponent field.

### When the attack IS in the candidate set, the search often declines it

| source | chose an attack when the best attack *was* a candidate |
|---|---|
| VN ladder | 38.0% (103/271) |
| H1 self-play | 41.6% (670/1610) |
| Canary ladder | 28.0% (104/372) |

So exclusion is **not the whole gap.** Even with the attack visible, the search
picks something else ~60% of the time. Fixing the candidate set raises the
ceiling; it does not by itself reach the field's 86–92%.

### Rank of the best attack in the v1 order (H1, n=2369)

| rank | 0 | 1 | 2 | 3 | **4** | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| share | 31.2% | 11.8% | 14.2% | 10.8% | **8.1%** | 6.0% | 5.1% | 3.2% | 2.4% | 2.2% | 1.1% | 0.6% | 3.5% |

Ranks 0–3 survive; everything from rank 4 out is invisible. The cut lands right
in the middle of the mass — 8.1% of decisions miss by a single slot.

### Two corrections to the brief's stated mechanism

**1. It is not "whenever ≥ 4 setup options are on the menu."** That would
predict near-total exclusion; measured is 32%. The `WEIGHT_TEMPO_LOADED` hook
already rescues the attack on 31.0% (H1) / 35.9% (VN) of attack-legal
decisions. The defect is narrower than stated but still large.

**2. The dominant blocker is the supporter gate, not the option count.**

| why the 2450 tempo hook did not lift the excluded attack | H1 | VN ladder |
|---|---|---|
| **`supporterPlayed` is False** | **75.6%** | **73.1%** |
| `turn < 4` | 14.9% | 23.1% |
| hook fired, still cut | 5.5% | 3.8% |
| `dmg == 0` | 4.0% | — |

**Three quarters of all exclusions are one condition:** the attack is worth
2450+ only *after* the turn's draw supporter has resolved. Before that it is
worth ~1100 and is invisible. This is what A-WEIGHT targets.

### The excluded attacks are real swings, not chip damage

| | p10 | p25 | median | p75 | p90 | max |
|---|---|---|---|---|---|---|
| **H1 excluded-attack damage** | 20 | 20 | **100** | 100 | 100 | 260 |
| VN ladder excluded-attack damage | 20 | 20 | 40 | 100 | 200 | 260 |

**52.3% of H1's excluded attacks do ≥ 100 damage** — the same median as the
attacks that *do* make the candidate set. This is not the search correctly
ignoring chip damage. `CAND_ATK_MIN_DMG = 100` is set from this distribution.

### Exclusion by turn (H1) — worst exactly where the brief predicted

| turn | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| excluded | 31.1% | **41.4%** | 30.7% | 26.7% | 23.2% | 37.4% | 26.8% |
| attack-when-legal | 19.6% | **11.1%** | 18.9% | 30.5% | 34.1% | 28.6% | 29.3% |

Turn 3 is the worst turn on both counters simultaneously, and the early turns
are where the first-attack-turn gap (6.52 vs field 4.1–5.6) is set. Consistent
with the hypothesis — though exclusion persists at 20–40% deep into the game,
so this is not purely an opening-phase defect.

### One thing that is *not* broken

**Lethal attacks are never excluded: 0 of 406 pooled.** `WEIGHT_LETHAL =
100000` puts a lethal attack at rank 0 unconditionally. Whatever is wrong here,
the agent is not missing visible lethal because of the candidate set.

### Verdict on Step 1

**The hypothesis is confirmed and the build proceeds.** Exclusion affects ~32%
of attack-legal decisions, is stable across three sources, and is mechanically
absolute (0/1068). Two corrections are folded into the arm design: the
supporter gate is the real driver, and the damage threshold is set from the
measured distribution rather than assumed.

---

## STEP 2 — the two arms

Both default **off**; verified `CAND_INCLUDE_ATTACK=False, CAND_ATK_W=0.0` at
import, so every existing config is byte-identical.

### A-INCLUDE (`CAND_INCLUDE_ATTACK=1`) — candidate set only

```python
atks = [i for i, o in enumerate(options) if (o or {}).get("type") == OT_ATTACK]
if atks:
    ba = max(atks, key=lambda i: (scores[i], -i))
    ...
    elif CAND_INCLUDE_ATTACK:
        cands = cands + [ba]
```

No v1 weight changes. No reordering. The forced attack is **appended**, so it
is last in `cands`, and the existing tie-break

```python
best = max(cands, key=lambda i: (totals[i] / n, -cands.index(i)))
```

still resolves ties to `cands[0]` — v1's own top pick. Tie-break logic is
untouched, as specified: the attack must win on rollout value outright, not on
a tie. `cands` grows to at most 5.

### A-WEIGHT (`CAND_ATK_W=2200`) — scoring only

Mirrors `WEIGHT_TEMPO_LOADED` as a second, lower tier that drops the
`supporterPlayed` requirement — the condition Step 1 identified as 75.6% of the
cause — and gates on damage instead:

```python
if CAND_ATK_W > 0 and dmg >= CAND_ATK_MIN_DMG:
    return max(base, CAND_ATK_W + min(dmg, 1900.0) * ATTACK_DAMAGE_SCALE)
```

At 2200, a 100-damage attack scores **2250** — above marginal setup (stadium
2030, ability 2060, tool 2100, supporter 2150) and below the actions that
build the board (bench 2300, item 2400, evolve 2800, energy attach 3000).
`turn ≥ 4` and the lethal short-circuit are inherited from the existing hook.
No forced inclusion in this arm.

### Telemetry (Step 4)

`[gov]` / `[gov-snap]` now carry
`end_veto= atk_legal= atk_in= cand_forced= cand_atk_w= changed=`.

All are incremented **once per real decision** inside `_search_decide`. The
first draft incremented `cand_atk_w` inside `_score_option`, which also runs
inside every rollout and reported **124987 in two games** — useless as ladder
telemetry. Moved to the decision path. This closes the VN_HEALTH_CHECK.md §6
gap: whether the veto and the candidate fix actually fire is now directly
readable from ladder logs.

---

## STEP 3 — results

60 self-play games per arm (**120 sides each**, both seats the same agent).
0 crashes, 0 exceptions, 0 fallbacks across all 180 games.

### Primary counter — attack-when-legal (per TURN)

| arm | attacks / attack-legal turns | rate | Wilson 95% CI | **vs pre-registered band** |
|---|---|---|---|---|
| **H1** baseline | 416 / 823 | **50.5%** | [47.1, 54.0] | — |
| **CI** A-INCLUDE | 443 / 821 | **54.0%** | [50.5, 57.3] | **FAIL** |
| **CW** A-WEIGHT | 463 / 912 | **50.8%** | [47.5, 54.0] | **FAIL** |
| **CIW** both | 433 / 836 | **51.8%** | [48.4, 55.2] | **FAIL** |

Bands were PASS ≥ 65%, MARGINAL 57–65%, FAIL < 57%. **All three arms fail.**
The best arm, CI, lands 3 points below the MARGINAL floor and 11 below PASS,
and the field sits at 86–92%.

**None of the three is statistically distinguishable from baseline.** 95% CI on
the difference vs H1:

| arm | Δ vs H1 | 95% CI on the difference | |
|---|---|---|---|
| CI | **+3.4 pts** | [−1.4, +8.2] | spans 0 — not significant |
| CW | +0.2 pts | [−4.5, +4.9] | spans 0 — not significant |
| CIW | +1.2 pts | [−3.6, +6.1] | spans 0 — not significant |

### First-attack turn — two arms flagged suspect

Field band **4.1 – 5.6**.

| arm | first attack | attack-when-legal | flag |
|---|---|---|---|
| H1 | 6.52 | 50.5% | — |
| **CI** | **6.42** | 54.0% | improves both — direction consistent |
| **CW** | **6.62** | 50.8% | ⚠️ **later** while nominally up |
| **CIW** | **7.22** | 51.8% | ⚠️ **0.7 turns later** while nominally up |

Per the pre-registered rule, an arm that improves attack-when-legal while
pushing first attack later is suspect. **CW and CIW both trip it.** CIW is the
worst first-attack figure of any arm ever measured here except H2's 8.19. The
weight change makes the agent attack *more often once it starts*, but *start
later* — the opposite of what the field profile needs.

### Full scorecard

| metric | field (top-10 07-26) | **H1** | **CI** | **CW** | **CIW** |
|---|---|---|---|---|---|
| **attack-when-legal / turn** | 86 – 92% | 50.5% | **54.0%** | 50.8% | 51.8% |
| attack share / own turn | 0.47 – 0.64 | 0.31 | **0.36** | 0.34 | 0.32 |
| **first attack turn** | **4.1 – 5.6** | 6.52 | **6.42** | 6.62 | 7.22 ⚠️ |
| first evolution turn | 3.6 – 4.2 | 4.67 | 5.01 | **4.60** | 4.76 |
| hand T3 | 5.4 – 7.8 | 5.62 | 5.39 | 5.32 | 5.45 |
| hand T5 | 4.6 – 8.2 | 5.19 | 5.30 | 4.95 | 5.32 |
| hand T7 | 4.7 – 10.3 | 5.29 | 5.21 | 5.28 | 5.74 |
| extra draws / turn | 2.1 – 2.6 | 1.34 | **1.40** | 1.27 | 1.28 |
| END + development available | — | 46.3% | 44.5% | **38.7%** | **38.1%** |
| END + bench<max & searcher (per game) | — | 0.50 | 0.40 | 0.48 | **0.28** |
| median deliberation | 38 – 633 ms | 166 ms | 288 ms | 247 ms | 251 ms |

### Wall-clock per player-game

| arm | p50 | p90 | p99 | max |
|---|---|---|---|---|
| H1 | 32.7 s | 56.6 s | 68.6 s | 71.9 s |
| CI | 42.3 s | 66.4 s | 81.5 s | **82.9 s** |
| CW | 41.8 s | 63.3 s | 81.8 s | 85.8 s |
| CIW | 39.9 s | 66.3 s | 79.2 s | **89.2 s** |

Every arm costs ~25–30% more wall-clock than H1 (CI's `cands` grows to 5, so it
runs 5 rollout sets instead of 4). Median deliberation rises 166 → 288 ms.
Affordable on the measured ladder budget — but bought nothing.

Win rate is 50% in every arm by construction (self-play mirror) and was **not**
a verdict input, as pre-registered.

---

## VERDICT — **no arm ships**

All three arms FAIL the primary counter and none separates from baseline at
95%. Step 4 ship verification is defined as running "on the winning arm only";
**there is no winning arm, so no ship verification was performed and no bundle
was built.**

### Why the fix didn't work — the candidate set was not the binding constraint

Step 1 was right about the mechanism and wrong about its importance. The
decisive number is the **conversion rate of a forced-in attack**:

| arm | attacks reaching the search that previously could not | chosen |
|---|---|---|
| **CI** | 848 forced in | **60 → 7.1%** |
| **CIW** | 564 forced in | **36 → 6.4%** |
| *(reference)* attacks that reach `cands` on their own merit | 1412 | **632 → 44.8%** |

**A forced-in attack is taken 7.1% of the time; a naturally-ranked one 44.8%.**
Opening the gate worked exactly as designed — 848 previously unreachable
attacks became reachable — and the search declined 93% of them.

That is the whole result. If forced attacks had converted at the natural 44.8%
rate, CI would have gained ~380 extra attacking turns instead of 60, and would
have cleared the PASS band comfortably. The gap between 380 and 60 is the size
of the real defect, and it is **not in the candidate set.**

**The binding constraint is the rollout evaluation.** When the search can see
an attack, it usually prefers setup — at *both* caps, and whether the attack
arrives by rank or by force. This is the same conclusion HORIZON_TEST.md
reached from the other direction (v1 alone ends a turn with development
available 0.0% of the time; adding search makes it 46.3%). Two independent
experiments now point at the evaluator rather than at what it is fed.

### Was A-WEIGHT's tier simply too low?

Partly, and it does not rescue the arm. Rescoring the played replays under each
arm's own scorer:

| arm | exclusion rate | vs H1's 32.0% |
|---|---|---|
| CW | 24.9% | −7.1 pts |
| CIW | 26.1% | −5.9 pts |

2200 removes about a fifth of the exclusions — a 100-damage attack at 2250
clears stadium/ability/tool/supporter but still loses to any four of bench
2300, item 2400, evolve 2800, energy attach 3000. Raising it further would
start outranking board development, which the horizon test already showed is
where this agent's value actually comes from. **Given a 7% conversion rate on
the attacks it does surface, a higher tier buys a rounding error at real risk.
Not recommended.**

### One genuinely positive side effect, outside the pre-registered counters

Both weight arms cut the END pathology substantially, with **END-veto off**:

| arm | END + development available | END + bench<max & searcher / game |
|---|---|---|
| H1 | 46.3% | 0.50 |
| **CW** | **38.7%** (−7.6) | 0.48 |
| **CIW** | **38.1%** (−8.2) | **0.28** (−44%) |

Lifting attacks in the scoring ladder gives the search a non-END option it
rates acceptably, so it passes less. This was **not** a pre-registered counter
and is **not** grounds to ship CW — it fails the primary counter and pushes
first attack later. Logged as a lead: it suggests the END pathology is partly a
symptom of a thin option ladder rather than a defect in END handling itself,
which is a different framing from the one END_VETO.md assumed.

---

## What shipped anyway: telemetry

The `[gov]` / `[gov-snap]` line now carries
`end_veto= atk_legal= atk_in= cand_forced= cand_atk_w= changed=`, all
decision-level. This closes the VN_HEALTH_CHECK.md §6 gap — whether the END
veto fires on ladder was previously **unobservable**, and is now directly
readable. Emission only; no decision path reads any of it.

Both arms remain in the codebase **default-off** and verified byte-identical
(`CAND_INCLUDE_ATTACK=False`, `CAND_ATK_W=0.0` at import).

The `SLOW decision` threshold is still 1000 ms and still produces ~25 benign
lines per ladder episode. Not changed here — it is unrelated to this task.

---

## Recommendation

1. **Ship nothing from this task.** Three arms, all FAIL, none significant.
2. **Stop attacking the candidate set and the scoring ladder.** Between this
   task and HORIZON_TEST.md, four separate interventions (cap=16, END-veto,
   A-INCLUDE, A-WEIGHT) have now failed to move behaviour toward the field.
   The 7.1%-vs-44.8% conversion gap localises the defect to the **rollout
   evaluation** — the search genuinely believes setup beats attacking.
3. **The next experiment should test that belief directly**, e.g. score a
   forced attack's rollout value against the setup option the search chose
   instead, and check it against realised game outcome. That is a diagnostic,
   not a fix, and I have not started it.
4. Carry forward for the writeup: *a mechanically absolute defect (0/1068) can
   still be a non-binding one.* Step 1's exclusion finding was correct,
   reproducible across three sources, and almost entirely irrelevant to
   strength. Worth stating plainly alongside the Gate 1 lesson.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/candset_measure.py` | Step 1 offline re-scoring + exclusion measurement |
| `scratchpad/s3/vn_replays/` | 25 VN ladder replays (fetched for Step 1) |
| `scratchpad/s3/horizon_C{I,W,IW}/` | 60 games per arm |
| `scratchpad/s3/candset_step1.json` | Step 1 raw counters |
| `scratchpad/s3/prof_C{I,W,IW}.json` | field-unit profiles |
