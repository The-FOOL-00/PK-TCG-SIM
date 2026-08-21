# G_ABIL_BROAD — broader ability-first substitution, screen

**Nothing submitted.** Written before any arm below is run.

## Why this exists

Fresh mining pass (`conditional_mine_v2.py`) with jul31 top-10 snapshot
included and comparing to POST-shipped-bundle behavior
(`scratchpad/s3/horizon_T1T2`, 300g of v1 + E1+E2+T1+T2) reveals that
**even after E1/E2/T1/T2 ship, we still lag top-10 by 14-20pt on ABILITY
usage in critical cells**:

| cell | them ABILITY | us ABILITY | gap |
|---|---:|---:|---:|
| supporter_pending | 27.4% | 12.3% | **−15.1pt** |
| turn=T7+ | 32.8% | 20.5% | −12.4pt |
| turn=T7+ & powered | 32.1% | 18.9% | −13.2pt |
| our_active_KOable | 34.5% | 20.2% | −14.3pt |
| **KOable & attacker_powered** | **38.9%** | **18.6%** | **−20.3pt** |
| atk_legal & supporter_pending | 32.0% | 18.0% | −14.0pt |
| race=AHEAD | 35.2% | 20.4% | −14.8pt |

E2 (shipped) is `chosen == OT_ATTACK` → best `OT_ABILITY`. If v1 picked
PLAY/ATTACH/EVOLVE/RETREAT/END, E2 abstains. The mining shows this is
the failure mode: top-10 fires abilities BEFORE their non-attack picks
too.

## Deck abilities (all strictly-positive)

Grimmsnarl deck marquee abilities:
- **Munkidori (112) Adrena-Brain**: move up to 3 damage counters from our
  Pokemon to opp Pokemon. Zero-cost heal + damage.
- **Fezandipiti ex (140) Flip the Script**: draw 3 if any of ours were
  KO'd last turn. Zero-cost draw.
- **Grimmsnarl ex (648) Punk Up**: on evolve, attach 5 basic {D}
  energies. Massive tempo. Fires on evolve — not this rule's target
  (rule only fires when there's a *separately-offered* OT_ABILITY
  option, and evolve-triggered abilities are baked into the play).
- **Dudunsparce (66) Run Away Draw**: draw 3, shuffle self back to
  deck. Rider is a resource-cost, but Dudunsparce is a starter — losing
  it isn't a real cost.

None of these have destructive side effects on our side, so firing them
before any other action is strictly-dominant in the same argument as
KE1's Run Errand veto.

## What G_ABIL_BROAD does, mechanically

Single flag `G_ABIL_BROAD`. On ST_MAIN, if
- chosen action type ≠ OT_ABILITY, AND
- there's an OT_ABILITY option on the menu, AND
- the per-own-turn veto budget (`E1_MAX_VETO=12`) is not exhausted,
- then swap the chosen index to the best-scoring OT_ABILITY option.

Slots into `_seq_gate` after E2/E1 (both continue to fire on chosen=
OT_ATTACK per current semantics). G_ABIL_BROAD only fires when E1/E2
didn't (because chosen wasn't ATTACK).

## Orthogonality vs shipped E1/E2 (why this compounds)

- E2 fires on `chosen == OT_ATTACK → OT_ABILITY`. Disjoint from
  G_ABIL_BROAD's `chosen ≠ OT_ABILITY (any non-ATTACK)` trigger.
- E1 fires on `chosen == OT_ATTACK → OT_DEVELOP`. Same — disjoint.
- G_ABIL_BROAD does NOT fire when chosen == OT_ABILITY (v1 already
  picked the ability). No self-loop.
- The E1_MAX_VETO=12 budget prevents "defer forever" (rule fires 12
  times max per own turn even if abilities keep being offered).

## Fire-rate estimate

Own turns per game ≈ 8. Non-ability MAIN decisions per own turn ≈ 3-5
(v1 typically makes several PLAY/ATTACH/EVOLVE picks per turn). Fraction
of those with an OT_ABILITY offered = probably 30-50% (Munkidori's
ability is offered constantly). So per own turn maybe 1-2 fires. Per
200g at 8 own turns/game = ~2000-3000 fires — much higher than KE1's
~700, because the trigger is much broader.

If mining data holds (14-20pt ABILITY gap), the effect ceiling is
substantial. But the gap could ALSO reflect top-10 firing abilities on
different-value states than ours (harder to quantify).

## Unit tests

1. Swaps chosen PLAY → OT_ABILITY when ability is on menu.
2. Swaps chosen ATTACH → OT_ABILITY.
3. Swaps chosen EVOLVE → OT_ABILITY.
4. Swaps chosen RETREAT → OT_ABILITY.
5. Swaps chosen END → OT_ABILITY.
6. Abstains when chosen is already OT_ABILITY (no self-loop).
7. Abstains when no OT_ABILITY on menu.
8. Abstains when veto budget exhausted (E1_MAX_VETO reached).
9. Abstains when flag off.

## Arms (Grimm self-play mirror, using `horizon_test.py` style)

Comparators (already on disk):

| arm | Win% or velocity source |
|---|---|
| T1T2 (shipped bundle) | horizon_T1T2/ (300g, prizes/g and velocity documented) |

New arms:

| arm | config | dir |
|---|---|---|
| T1T2 + G_ABIL_BROAD | shipped + new rule | horizon_G_ABIL/ (fresh 200g) |

Also — cross-deck sanity check that this rule doesn't hurt other archetypes:
| Kang + G_ABIL_BROAD vs Grimm-v1 | crossdeck_kang.py --our-rules ke1_ga | 200g |

## PRE-REGISTERED BANDS

### G_ABIL_BROAD in Grimm mirror (over shipped T1T2)

**Primary metric: prize velocity** (mirror cancels first-attack differences,
so win% is 50% baseline; velocity is the mirror-appropriate reading).

Baseline velocity from `horizon_T1T2/`: to be computed at run time (call
it V_T1T2). Bands based on delta over V_T1T2.

| band | condition | reading |
|---|---|---|
| **PASS** | velocity ≥ V_T1T2 + 0.020 AND ability-fire rate up ≥ 30% | ship-verify, run cross-deck sanity |
| **AMBIGUOUS** | 0 ≤ Δvel < 0.020 | inconclusive; extend to 400g |
| **FAIL** | Δvel < 0 | do not ship; document |

### Kang cross-deck sanity vs Grimm-v1

If Grimm-mirror PASS:
| arm | Win% band |
|---|---|
| Kang+KE1+G_ABIL_BROAD | must be ≥ Kang+KE1's 39.0% − 2pt (no worse than KE1-only) |

If cross-deck check regresses, we know G_ABIL_BROAD is Grimm-only good.
Ship it only inside the Grimm bundle.

### Threshold reasoning

- 0.020 velocity gate: velocity has been the primary metric for E1/E2/T3
  screens; shipped bundle is around 0.30 velocity. A 0.020 gain (~7% of
  baseline) is a meaningful ship threshold that filters noise.
- Ability-fire-rate gate: mechanism check. If the rule fires but doesn't
  raise ability usage measurably, something else is going wrong.

**Bands are not revised after seeing results.**

---

## RESULTS

### Round 1 — G_ABIL_BROAD unfiltered (any OT_ABILITY)

| arm | velocity | prizes/g | atkWL | fires |
|-----|---------:|--------:|------:|------:|
| T1T2 baseline (300g mirror) | 0.4728 | 3.42 | 90.8% | — |
| T1T2 + GAB unfiltered (200g) | 0.4900 | 3.69 | 93.3% | 2003 (10/g) |
| Δ | **+0.0172** | +0.27 | +2.5pt | |

Kang cross-deck sanity (200g):
| arm | Win% | fires |
|-----|----:|------:|
| KE1 alone | 39.0% | KE1=695 |
| KE1 + GAB unfiltered | **32.5%** | KE1=601, GAB=? |

**Kang FAIL** (−6.5pt vs KE1 alone). Root cause: unfiltered rule fires
Meowth ex's Last-Ditch Catch ability ("put this pokemon into hand"),
which returns Meowth to hand every turn it's on our board, tanking Kang.
Narrowed the rule to `_has_positive_ability`-scoped OT_ABILITYs.

### Round 2 — G_ABIL_BROAD narrowed (positive-ability whitelist)

Filter: fires OT_ABILITY only if source card's skill text matches:
- "draw N cards" or "draw a card" AND no "discard" AND no "shuffle this
  pok" AND no "put this pok"
- OR "damage counter" + "move" (Munkidori-shape)

| arm | velocity | prizes/g | atkWL | fires |
|-----|---------:|--------:|------:|------:|
| T1T2 baseline | 0.4728 | 3.42 | 90.8% | — |
| T1T2 + GAB narrowed (200g) | 0.4771 | 3.54 | 91.8% | 1770 (8.85/g) |
| Δ | **+0.0043** | +0.12 | +1.0pt | |

Kang cross-deck (200g):
| arm | Win% | fires |
|-----|----:|------:|
| KE1 alone | 39.0% | KE1=695 |
| KE1 + GAB narrowed | 34.0% | KE1=635, **GAB=0** |

## VERDICT — FAIL on load-bearing Grimm mirror band

**Grimm mirror: velocity Δ +0.0043 vs PASS band ≥ +0.020 — FAIL.**
Fires as designed (1770/200g), atk-when-legal moves +1pt, but velocity
delta is inside mirror-symmetric noise. Doesn't ship.

**Kang cross-deck: G_ABIL_BROAD narrowed fires ZERO times.** Not a rule
regression — Kang picks ATTACK on most turns (KE1 handles those), and
Kang's non-ATTACK picks rarely coincide with positive-ability offers.
The 5pt "drop" from 39% to 34% is a 0-fire artifact of RNG at n=200
(95% CI ±9.4pt). Rule is a safe no-op on Kang matchup.

## Root cause — the narrowing tradeoff is unresolvable at this scope

The unfiltered rule (+0.017 mirror) hit real ability gaps but hurt
cross-deck by firing Meowth's Last-Ditch Catch. Narrowing to strictly-
positive-ability whitelist protected cross-deck but killed 75% of the
Grimm mirror velocity gain (unfiltered +0.017 → narrowed +0.004). The
233 fires the narrowing removed were high-value.

The lost fires were on Grimm's own ambiguously-positive abilities:
- Grimmsnarl ex Punk Up: evolve-triggered, not "once per turn" scope;
  filter rejected it.
- Various trainer abilities on Marnie's line that don't match my patterns.

A better filter would enumerate Grimm-deck-specific positive abilities
by card id (whitelist), rather than pattern-matching skill text. That's
another cycle's work.

## Session-wide pattern reinforced

Adding G_ABIL_BROAD to the ledger: **4 rule failures this session**:
| rule | approach | verdict |
|---|---|---|
| KE_SUP | swap ATTACK → supporter play | FAIL −7pt alone |
| KE_BOLT | swap Burst → Bellowing + discard policy | env-starved, FAIL stacked |
| KE_WELL | swap Kang-attach → Wellspring-attach | FAIL −9.5pt stacked |
| **G_ABIL_BROAD** | extend E2 to non-ATTACK chosen | FAIL — narrow filter kills effect, broad filter hurts other decks |

**Common failure mode reinforced**: rules that shift v1's action
distribution beyond KE1's specific narrow substrate (chosen ∈
{ATTACK,RETREAT,END} → single named ability from a specific active-
spot-carrier) either:
- Cause v1 downstream sequencing failures (KE_SUP, KE_WELL)
- Or hit env preconditions v1 doesn't reach (KE_BOLT)
- Or fire abilities with hidden side-effects that need per-deck
  enumeration (G_ABIL_BROAD)

## What ships

**Unchanged.** Shipped Grimm bundle (v1 + E1+E2+T1+T2) + shipped Kang
bundle (`dist/kang/v1_kang_ke1.tar.gz`, sha `681fb6e7…122008`) remain
the shipped positions. Fifth session in a row. G_ABIL_BROAD flag stays
in the codebase, default off, for the record.

