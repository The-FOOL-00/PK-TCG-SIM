# KE_WELL — Wellspring Ogerpon attach-priority rule, screen

**Nothing submitted.** Written before any arm below is run.

## Mining source (attach_mine.py)

Attach-target distribution over top-10 Kang pilots vs our v1-alone
(400 games) piloting the same 60-card deck:

| Target | top-10 | our v1 | gap |
|---|---:|---:|---:|
| Mega Kangaskhan (756) | 43.6% | 62.4% | us +18.8pt (over) |
| **Wellspring Ogerpon (108)** | **23.7%** | **4.6%** | **us −19.1pt (under)** |
| Teal Ogerpon (96) | 13.4% | 6.4% | us −7.0pt |
| Raging Bolt (63) | 10.4% | 15.6% | us +5.2pt |
| Latias (184) | (none) | 5.6% | us wastes |

**Downstream: Wellspring's Torrential Pump usage:**
| pilot | Sob | Torrential Pump | rate/game |
|---|---:|---:|---:|
| top-10 (85g) | 75 | 49 | **0.576** |
| our v1 (400g) | 108 | 14 | 0.035 |

**Top-10 uses Torrential Pump 16× more often per game than we do.**
Torrential Pump is a 100 dmg + 120 damage-to-bench swing attack requiring
3 energies on Wellspring (1W + 2 colorless). Wellspring never reaches 3
energies for us because we over-attach Kangaskhan, so the attack rarely
becomes legal.

## What KE_WELL does, mechanically

Single hook, gated on `KE_WELL_ATTACH_PRIORITY` flag:

**`_ke_well_attach_veto`** on ST_MAIN: if
- v1's chosen action is `OT_ATTACH` (type=8) AND
- the target of that attach is Mega Kangaskhan (id=756) AND
- Wellspring Ogerpon (id=108) is on our field (active OR bench) AND
- Wellspring has fewer than 3 total energies attached AND
- an `OT_ATTACH` option targeting Wellspring is on the menu,
- then swap the chosen index to the Wellspring attach option.

Only fires when v1 picks Kang as attach target. Non-Kang attach picks
(RB, Ogerpon, Latias, etc.) are left alone — this is a "cap Kang
attach when Wellspring is starved" rule, not a generic redistribution.
Wellspring's 3-energy cap prevents the rule from over-firing after
Wellspring is fed.

## Orthogonality vs KE1

KE1 fires on `{ATTACK, RETREAT, END} → OT_ABILITY(Run Errand)`. KE_WELL
fires on `OT_ATTACH → OT_ATTACH`. Different chosen-action precondition,
different substitution target. No hook-slot competition. Composes with
KE1 by construction.

If KE_WELL works, it should also indirectly help KE_BOLT: shifting attach
energy from Kang (over-fed) to Wellspring frees Raging Bolt's own attach
opportunities on later turns (we won't need to attach to Kang again once
Kang has enough, so RB gets subsequent attaches naturally). Fires
projection for KE_BOLT with KE_WELL in place: 20-50 in 200g (up from 13
without KE_WELL), which would unlock KE_BOLT's own effect.

## Unit tests

1. Swaps Kang attach → Wellspring attach when Wellspring has 0 energies.
2. Swaps when Wellspring has 2 energies (still below 3-cap).
3. Abstains when Wellspring has 3 energies (cap met).
4. Abstains when Wellspring is not on field (absent from active + bench).
5. Abstains when chosen is not an OT_ATTACH.
6. Abstains when chosen is OT_ATTACH to non-Kang target.
7. Abstains when no OT_ATTACH to Wellspring is on menu.
8. Abstains when flag is off.

## Arms (cross-deck, `crossdeck_kang.py --opp grimmsnarl`)

Comparators from prior screens on disk:

| arm | Win% | vel |
|---|---:|---:|
| baseline (no rules) | 32.0% | 0.2858 |
| KE1 alone | 39.0% | 0.3350 |

New arms:

| arm | config |
|---|---|
| KE_WELL alone | v1 + KE_WELL_ATTACH_PRIORITY |
| KE1 + KE_WELL | v1 + KE1 + KE_WELL |
| KE1 + KE_WELL + KE_BOLT | v1 + KE1 + KE_WELL + KE_BOLT (only run if KE1+KE_WELL passes) |

## PRE-REGISTERED BANDS — fixed before running

### KE_WELL alone vs baseline (32.0%)

| band | condition | reading |
|---|---|---|
| **PASS** | win% ≥ 35.0% (Δ ≥ +3.0pt) | ship-verify continue |
| **AMBIGUOUS** | 32.0% ≤ win% < 35.0% | extend to 400g |
| **FAIL** | win% < 32.0% | do not ship |

### KE1 + KE_WELL stacked vs KE1-alone (39.0%) — LOAD-BEARING

| band | condition | reading |
|---|---|---|
| **PASS** | win% ≥ 41.0% (Δ ≥ +2.0pt over KE1) AND Torrential Pump usage rate ≥ 0.2/game (up from 0.035) | ship KE1+KE_WELL bundle |
| **AMBIGUOUS** | 39.0% ≤ win% < 41.0% | extend to 400g |
| **FAIL** | win% < 39.0% OR TP rate < 0.1/game | ship KE1-only, keep flag default-off |

### KE1+KE_WELL+KE_BOLT triple (only if the above PASS) vs KE1+KE_WELL

| band | condition | reading |
|---|---|---|
| **PASS** | KE_BOLT fires ≥ 30 per 200g AND win% ≥ KE1+KE_WELL score + 1.5pt | ship the triple |
| **FAIL** | otherwise | ship the double |

### Threshold reasoning

- KE_WELL alone +3.0pt: attach-diversification affects downstream
  attacker readiness, which propagates to more attacks landing per game.
  Rough expectation: +0.5 Torrential Pump / game × ~0.05 win% per TP hit
  = ~2.5pt raw. Threshold at +3pt (16% above expected point estimate).
- KE1+KE_WELL +2.0pt over KE1: additivity would predict +3pt on top.
  +2pt (66% of that) allows some non-additivity.
- Torrential-Pump-rate guard: the rule fails silently if we attach to
  Wellspring but v1's scorer still never picks TP over Rapid-Fire. The
  guard catches this — 0.2/g is the midpoint between our current 0.035
  and top-10's 0.576, and PASS requires reaching at least that.

**Bands are not revised after seeing results.**

---

## RESULTS — 200 games each, cross-deck vs v1-alone Grimmsnarl

| arm | Win% | Δ | vel | atkWL | TP/g | fires |
|---|---:|---:|---:|---:|---:|---|
| baseline | 32.0% | — | 0.2858 | 54.8% | 0.030 | — |
| KE1 | 39.0% | — | 0.3350 | 55.9% | 0.040 | KE1=695 |
| **KE_WELL alone** | **28.5%** | **−3.5** vs baseline | 0.2517 | **47.6%** | 0.140 | KE_WELL=164 |
| **KE1 + KE_WELL** | **29.5%** | **−9.5** vs KE1 | 0.2865 | 53.7% | 0.100 | KE1=485, KE_WELL=136 |

## VERDICT — FAIL on both bands + TP guard

**KE_WELL alone: 28.5% vs baseline 32.0% (Δ = −3.5pt) — FAIL**
(pre-registered band was PASS ≥35.0%, AMBIGUOUS 32.0–35.0%).

**KE1 + KE_WELL: 29.5% vs KE1-alone 39.0% (Δ = −9.5pt) — HARD FAIL**
(pre-registered band was PASS ≥41.0%). Worst regression from a rule this
session. TP-rate guard also fails: 0.100/g vs the 0.2/g threshold.

## Root cause — diverting attaches breaks Kang's damage engine

The rule engaged robustly: 164 fires in 200g (0.82/g) — highest fire rate
of any non-KE1 rule tested this session. And the immediate downstream
effect happened: Torrential Pump rate jumped 0.030 → 0.140 (4.7× baseline)
alone-arm, matching the intended mechanism.

But atk-when-legal dropped 54.8% → 47.6% (**−7.2pt**, biggest drop of
any rule tested), and in the stacked arm KE1's fire count dropped 30%
(695 → 485). Interpretation:

- We were attaching to Kang for a reason: Kang's Rapid-Fire Combo (3
  colorless energies, expected ~150-200 dmg on coin flips) is our
  highest-tempo consistent attacker. Delaying Kang's power-up delays
  attacks entirely.
- KE_WELL captures the top-10 attach ratio but not the *reason* top-10
  can afford it — top-10 has better follow-up sequencing (they cycle
  through attackers via Meowth ex bounces, Prime Catcher promotions,
  strategic retreats) so a diverted attach doesn't tank tempo. Our v1
  doesn't do those things, so a diverted attach IS a tempo loss.
- KE1's fire count dropping in the stacked arm confirms this: Kang
  spends less time in the active spot (either not powered enough to
  attack, or bench slots occupied differently), so Run Errand fires
  less often.

Same failure shape as KE_SUP: rules that PROMOTE actions v1 wouldn't
take fail when v1's downstream decisions can't capitalize on the shifted
state.

## Session pattern — three-for-three fail, and what that says

This session tested three new-shape rules on Kangaskhan:
| rule | shape | verdict | root cause |
|---|---|---|---|
| KE_SUP | swap ATTACK → PLAY(supporter) | FAIL −7pt alone | v1's re-scored MAIN after supporter doesn't return to ATTACK |
| KE_BOLT | swap Burst → Bellowing (+ discard policy) | AMBIGUOUS alone, FAIL stacked | env-starved (13 fires/200g) — RB rarely powered |
| KE_WELL | swap Kang attach → Wellspring attach | FAIL −9.5pt stacked | breaks Kang's damage engine — v1 can't compensate for delayed Kang power |

Common thread: **all three rules PROMOTE actions v1 wouldn't take, and
all three fail because v1's downstream decisions aren't structured to
capitalize on the shifted state.**

Contrast with KE1 (the sole shipped success): KE1 substitutes a terminal
action for a *free* ability (Run Errand — draw 2, no side effect other
than +2 cards). The substitution is *unconditional value* — it doesn't
depend on v1 following up with any specific sequence, because the free
ability just runs and the very next MAIN re-presents the same menu
(minus the ability) for v1 to pick the terminal action again.

**Path-forward implication**: The mine→veto→screen methodology's remaining
head-room on this deck likely requires either:
1. Rules that inject *unconditional value* (like KE1). Candidates: Energy
   Switch reallocation (free move of a wasted bench energy to active
   attacker), Prime Catcher forced-switch when opp active has 3+ energies
   (disruption with no self-cost).
2. Or structural v1 scorer changes so downstream sequencing can capitalize
   on rule-induced state shifts. That's a much bigger investment than
   another single-rule cycle.

## What ships

**KE1-only bundle (`dist/kang/v1_kang_ke1.tar.gz`, sha `681fb6e7…122008`)
remains the shipped Kangaskhan position, unchanged for the fourth
session in a row.** KE_WELL flag stays in codebase, default off, for the
record.

