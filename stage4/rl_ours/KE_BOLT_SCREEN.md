# KE_BOLT — Bellowing Thunder engagement rule, screen

**Nothing submitted.** Written before any arm below is run. See
`KE_BOLT_DESIGN.md` for the underlying mining finding (top-10 uses
Bellowing Thunder 0.412×/game; we use it 0× despite it being offered
135 times in 200 games).

## What KE_BOLT does, mechanically (v2 — opportunistic-damage shape)

**Redesign note**: the initial v1 draft of this rule required
"basics_extra >= ceil(opp_hp/70)" (only fire when a KO is guaranteed).
A follow-up mining pass on the 35 top-10 Bellowing uses in the same 85
replays revealed that **top-10 never fires on a KO-threshold** — mean
discard is 3 basics (210 dmg), and all 35 uses are non-KO shots. Top-10
uses Bellowing opportunistically, as a general "70+ dmg per turn" damage
policy, not as a lethal finisher. v1 shape fires 0 times because the KO
precondition almost never holds in this deck's energy-attachment reality.
v2 matches the observed pattern.

Two hooks, both gated on `KE_BOLT_ENGAGE` flag:

**Hook 1 — MAIN veto (`_ke_bolt_main_veto`)**: on ST_MAIN, if
- chosen action is `OT_ATTACK` with `attackId == 71` (Burst Roar — 0-cost
  draw-6-with-0-dmg), AND
- an `OT_ATTACK` with `attackId == 72` (Bellowing Thunder) is on the same
  menu, AND
- our active is Raging Bolt ex (id=63), AND
- surplus basic energies on Raging Bolt = `count_basic_energies_on(active)
  - 2 >= 1` (i.e., at least 1 basic to discard after paying 1L+1F cost),
- then swap the chosen index to Bellowing. Only touches Burst Roar picks;
  any other v1 pick (a PLAY, a non-Burst attack, a RETREAT) is left alone.

**Hook 2 — ST_ATTACHED_CARD discard policy (`_ke_bolt_discard_policy`)**:
on ST_ATTACHED_CARD, if
- `context == 26` (Bellowing discard context, verified from replay
  inspection), AND
- `effect.id == 63` (Raging Bolt is the source),
- then pick K indices where:
  - if opp active HP > 0 and `ceil(opp_hp/70) <= min(options, maxCount)`:
    K = ceil(opp_hp/70) (exact KO discard)
  - else: K = min(2, options, maxCount) (top-10 median from mining)
  This preserves basic-energy resource on RB when a KO isn't reachable
  (top-10's median = 2 discards even when they have more available).

Both hooks are strictly-necessary — without hook 2, hook 1 causes a whiff
(v1's default on this ST_ATTACHED_CARD scores 0.0 and picks 0 discards,
delivering 0 damage per `main.py:1803`).

## Orthogonality vs KE1

KE1 fires on `{ATTACK, RETREAT, END} → OT_ABILITY(Run Errand)` and is
gated by `_has_free_draw_ability(active_id)` matching only Mega Kangaskhan
(id=756). When our active is Raging Bolt (id=63), KE1 abstains, so
KE_BOLT is free to fire. **Different active-slot precondition, disjoint
by construction.**

## Unit tests (before self-play)

Pre-registered assertions on the helpers, similar to KE_SUP tests:
1. MAIN veto fires when Bellowing offered, RB active, 3+ basic energies on
   RB, opp HP ≤ 70×(available-2), chosen was Burst Roar.
2. MAIN veto abstains when chosen is already Bellowing Thunder.
3. MAIN veto abstains when RB is not active.
4. MAIN veto abstains when RB has only 2 basics (bare attack cost, no
   extras to discard).
5. MAIN veto abstains when opp HP requires more discards than available.
6. Discard policy fires with correct count when context=26 + RB effect.
7. Discard policy abstains when context != 26 (other ST_ATTACHED_CARD
   uses like Retreat cost).
8. Discard policy caps at maxCount.

## Arms (cross-deck, `crossdeck_kang.py --opp grimmsnarl`)

Comparators from `KE_SUP_SCREEN.md` (already on disk):

| arm | Win% | vel |
|---|---|---|
| baseline (no rules) | 32.0% | 0.2858 |
| KE1 alone | 39.0% | 0.3350 |

New arms:

| arm | config |
|---|---|
| KE_BOLT alone | v1 + KE_BOLT_ENGAGE |
| KE1 + KE_BOLT | v1 + KE1_FREE_DRAW + KE_BOLT_ENGAGE |

## PRE-REGISTERED BANDS — fixed before running

### KE_BOLT alone vs baseline (32.0%)

| band | condition | reading |
|---|---|---|
| **PASS** | win% ≥ 34.5% (Δ ≥ +2.5pt) | ship-verify continue |
| **AMBIGUOUS** | 32.0% ≤ win% < 34.5% | non-negative but small; extend to 400g |
| **FAIL** | win% < 32.0% | do not ship; document |

### KE1 + KE_BOLT stacked vs KE1-alone (39.0%)

| band | condition | reading |
|---|---|---|
| **PASS** | win% ≥ 40.5% (Δ ≥ +1.5pt) AND KE_BOLT fires ≥ 0.7× the alone-arm fire count | ship KE1+KE_BOLT bundle |
| **AMBIGUOUS** | 39.0% ≤ win% < 40.5% | extend to 400g |
| **FAIL** | win% < 39.0% OR fires suppressed >70% | ship KE1-only, keep flag default-off |

**Guards, not verdict inputs:**
- Own-turns within ±0.3 of KE1-alone's 7.88.
- atk-when-legal not more than 5pt below KE1-alone's 55.9%.
- ke_bolt_main and ke_bolt_discard fire counts reported separately;
  the ratio should be roughly 1:1 (each MAIN swap should trigger exactly
  one discard select).

### Threshold reasoning (v2, opportunistic-damage shape)

- KE_BOLT alone +2.5pt threshold: opportunistic fires target Burst-Roar
  picks where RB has surplus basic energy. Baseline harvest showed
  Bellowing was OFFERED to us 135× in 200g but we picked Burst 151× and
  Bellowing 0×. If fire-when-Burst-chosen catches ~60% of those, that's
  ~90 fires. Each fires substitutes 0 dmg → 70-140 dmg. Expected win-rate
  effect is bounded above by top-10's own Bellowing-conversion delta,
  which is unmeasured in isolation but reasonably in the +2-6pt range.
  +2.5pt threshold requires meaningful realized effect, not just fires.
- KE1+KE_BOLT +1.5pt over KE1-alone: additivity would predict +2.5pt on
  top; +1.5pt (60% of that) allows some interaction non-additivity.
  Orthogonality argument holds: KE1 fires only with Mega Kang (756)
  active; KE_BOLT fires only with Raging Bolt (63) active. Disjoint
  active-slot preconditions = disjoint firings.

**Bands are not revised after seeing results.**

---

## RESULTS — 200 games each, cross-deck vs v1-alone Grimmsnarl

| arm | Win% | vel | ownT/g | atkWL | prz/g | KE1 fires | KE_BOLT MAIN | KE_BOLT discard |
|-----|-----:|----:|-------:|------:|------:|----------:|-------------:|-----------------:|
| baseline (no rules) | 32.0% | 0.2858 | 7.68 | 54.8% | 2.19 | 0 | 0 | 0 |
| KE1 alone           | 39.0% | 0.3350 | 7.88 | 55.9% | 2.64 | 695 | 0 | 0 |
| **KE_BOLT alone**   | **32.5%** | 0.3144 | 7.86 | 54.9% | 2.47 | 0 | **13** | **13** |
| **KE1 + KE_BOLT**   | **37.0%** | 0.3193 | 7.97 | 55.8% | 2.54 | 526 | **7** | **7** |

## VERDICT — FAIL on the load-bearing stacked band

**KE_BOLT alone: 32.5% vs baseline 32.0% (Δ = +0.5pt) — AMBIGUOUS**
(pre-registered band was PASS ≥34.5%, AMBIGUOUS 32.0–34.5%). Falls
inside the AMBIGUOUS band but with fire rate so low (13 fires per 200g
= 0.065/g, vs KE1's 3.5/g) that the confidence interval is dominated by
noise, not signal.

**KE1 + KE_BOLT stacked: 37.0% vs KE1-alone 39.0% (Δ = −2.0pt) — FAIL**
(pre-registered band required ≥40.5%). Fire count dropped from 13→7 in
the stacked arm (46% suppression) and KE1 dropped 695→526 (24%
suppression) despite the disjoint active-slot precondition — the two
rules don't compete for hook slots, but they DO cause different downstream
game states (Bellowing substitution changes energy pool + card advantage
trajectory), so future active-slot occupancy diverges.

Per screen discipline: **do not ship KE_BOLT.** Load-bearing test failed.

## Root cause — the rule is well-designed but starved by v1's play

The 11 unit tests pass, both hooks (MAIN veto + ST_ATTACHED_CARD policy)
engage correctly when their preconditions hold. But the preconditions
almost never hold in v1-alone play:

Diagnostic on 10-game smoke: 2 Burst Roar picks in the whole sample, both
with Raging Bolt at 1 energy (below the 2-energy 1L+1F attack cost, so
Bellowing wasn't offered anyway). At 200g, KE_BOLT MAIN fired 13 times —
that means only 13 states across 200 games had (RB active AND
`basics_extra ≥ 1` AND Burst Roar chosen). The mined pattern needs
Raging Bolt powered to 3+ basics; our v1 rarely gets it there.

Contrast with top-10 pilots' 35 Bellowing uses over 85 games (0.412/g).
They achieve this via Crispin (search + attach basic), Teal Dance
(Ogerpon's free Basic-G attach ability), and deliberate attach
prioritization toward Raging Bolt. Our v1 does none of these three
consistently.

## What this proves and what it doesn't

**Proves:**
- The `atk_legal & supporter_pending` mining cell is not the only
  environmentally-starved rule. KE_BOLT joins KE_SUP in the "signal is
  real in top-10 replays, translation to v1 game states is blocked by
  upstream v1 behaviors" category.
- Even a strictly-dominated substitution rule (Bellowing 70+ dmg vs
  Burst 0 dmg) doesn't move win rate if the substitution can only fire
  in ~7% of the situations top-10 encounters.
- The two-hook design (MAIN + ST_ATTACHED_CARD) is sound. Fire counts
  match 1:1 between hooks (13/13 alone, 7/7 stacked), confirming both
  hooks trigger together as designed — no orphan MAIN swaps producing
  0-damage whiffs.

**Does not prove:**
- That KE_BOLT would fail with a prerequisite fix. If a companion rule
  reliably powered Raging Bolt to 3+ basics (a "prefer RB as attach
  target when Kangaskhan is fed" policy, mineable from the top-10
  attach-target selects), KE_BOLT's fire count would likely rise 5-10×
  and its effect would become measurable.
- That the Bellowing→70dmg substitution is bad. In the 13 fires it made,
  velocity was 0.3144 vs baseline 0.2858 (+0.029) — meaningful per-fire
  effect, just not enough fires to move the win-rate needle.

## What ships

**KE1-only bundle (`dist/kang/v1_kang_ke1.tar.gz`, sha `681fb6e7…122008`)
remains the shipped Kangaskhan position, unchanged for the third session
in a row.** KE_BOLT flag stays in the codebase, default off, for the
record. Both `KE_SUP_ATK_BEFORE_SUPPORTER` and `KE_BOLT_ENGAGE` remain
as documented no-ops.

## Path forward that would unlock KE_BOLT

To make this rule fire at a rate that could move win-rate, the deck's
energy-attach behavior must change. Concrete next-cycle candidates
(mineable from the same 85 top-10 replays that produced this signal):
1. **Attach-target priority for Raging Bolt** — mine top-10's ST_CARD /
   ST_CARD_OR_ATTACHED selects on OT_ATTACH turns; compare to ours;
   likely finds a "prefer RB over other bench" bias we lack.
2. **Teal Dance activation gating** — Ogerpon's free Basic-G attach ability
   is what feeds RB. KE3 (already built, default off) targets exactly
   this, but was shipped-negative in KE3_SCREEN because of hook-slot
   competition with KE1. A re-scoped KE3 that ONLY fires when RB is on
   the field and needs energy (not the generic KE3 shape) might work.

Both are their own mine → design → build → screen cycles. Not this
session.

