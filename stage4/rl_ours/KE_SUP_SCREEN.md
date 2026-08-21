# KE_SUP — Kangaskhan-native "play supporter before attacking" rule, screen

**Nothing submitted.** Written before any arm below is run.

## Why this exists (in contrast to KE1/KE2/KE3)

The prior three rules (KE1/KE2/KE3) all target the once-per-turn *Ability*
slot. `KE3_SCREEN.md` closed with the finding that "the KE1-family shape is
saturated — further ability-vetos won't compound" and named the next-viable
shape as "a category KE1 does not." KE_SUP is that: it targets the once-per-
turn *Supporter* slot, which is a distinct engine resource. Two rules — one
per resource — cannot compete for the same MAIN slot the way KE1+KE2 and
KE1+KE3 did (both consumed OT_ABILITY).

## Mining source (kangaskhan_conditional_cells.json)

Cell **`atk_legal & supporter_pending`**: n_them=504, n_us=954, TVD=0.271,
freq=16.1%, leverage=0.044 (4th-highest cleanly-non-ABILITY-dominated cell
after the KE1-family ones).

|          | PLAY | ATTACH | ABILITY | RETREAT | ATTACK | END |
|----------|------|--------|---------|---------|--------|-----|
| top-10   | 46.8 |  5.0   |  28.4   |  2.8    | **15.9** | 1.2 |
| us       | 40.4 | 13.2   |  11.7   |  0.0    | **34.7** | 0.0 |
| us_gap   | −6.4 | +8.2   | −16.7   | −2.8    | **+18.8**| 0.0 |

**We over-ATTACK by 18.8pt when a supporter is still unplayed this turn.**
Top-10 plays the supporter first (46.8% PLAY, of which the supporter is one
of the higher-ranked options given `supporter_pending`), we skip it and hit
the attack menu.

Deck-verified against `card_data.json` and `metaX_kangaskhan_top10.csv`
(60 cards): 10 Supporter cards (cardType=3) — Boss's Orders ×2 (id 1182),
Xerosic's Machinations ×2 (1197), Crispin ×4 (1198), Cyrano ×2 (1205). All
four have strict-dominance texts over ending-turn-attacking-early:
- **Boss's Orders**: pulls an opp bench Pokemon to active (opens a SELECT,
  no immediate self-cost; even a random pick generally breaks opp setup).
- **Xerosic's Machinations**: opp discards hand to 3, no self-cost.
- **Crispin**: search 2 basic energies, put 1 in hand + attach 1 — pure
  resource gain.
- **Cyrano**: search up to 3 ex Pokemon, put in hand — pure resource gain.

There is no "trap supporter" in this deck; playing any of them ahead of
attacking is a resource gain except in a rare kill-or-die state where the
attack is our only path to survive (guard-band watches for that regression).

## What KE_SUP does, mechanically

New helper: `_playable_supporter_index(sel, cur, me)` — walks the option
list, returns the index of the first `OT_PLAY` option whose hand-card has
`cardType == CT_SUPPORTER` (3). Engine already gates OT_PLAY options for
Supporters when `supporterPlayed` is True (Supporter card cannot re-play in
the same turn), so the presence of such an OT_PLAY option confirms
playability. No new skill-text pattern matcher (unlike KE1/KE3) — the
Supporter category is a first-class engine flag, so we read it directly.

`_ke_sup_veto(result, sel, cur)` fires **only** when:
1. `KE_SUP_ATK_BEFORE_SUPPORTER` flag is on and `sel.type == ST_MAIN`.
2. Chosen action is `OT_ATTACK` (deliberately narrow — this is not KE1's
   ATTACK/RETREAT/END trigger set; ATTACK-only maps to the mined cell).
3. `cur.get("supporterPlayed")` is False.
4. `_playable_supporter_index` returns a valid index.

When those hold, swap the chosen index to the Supporter's PLAY option.
Otherwise return `result` unchanged. `_validate_result` and downstream
fallback untouched, same pattern as KE1/KE2/KE3.

**Substitution safety**: Supporters do not end the turn. After the swapped
PLAY resolves, the engine re-presents the MAIN menu; v1 picks again. If
the attack is still the right call, it fires next MAIN — one turn's
sequence delayed by one card play. If the resources the supporter revealed
change the picture (Crispin adds an attach), the follow-up decision is
better-informed.

## Orthogonality vs KE1 (why this is expected to compound)

KE1 substitutes `{ATTACK, RETREAT, END} → OT_ABILITY` (Mega Kang Run Errand
or, in the composed-KE3 case that failed, Teal Dance). Consumes the
once-per-turn Ability slot for our active/board.

KE_SUP substitutes `ATTACK → OT_PLAY(Supporter)`. Consumes the once-per-turn
Supporter slot.

The two slots are **independent engine resources** (a turn can, and top-10
typically does, use both). Contrast KE1+KE3, which both targeted OT_ABILITY
and starved each other 99% (KE3_SCREEN.md line 40-46). No slot competition
here by construction.

Hook order in `main.py` (per the block at line 3304-3322): KE1 → KE2 → KE3.
KE_SUP will slot in after KE3 (or before — order doesn't matter, since
the trigger types are disjoint: KE1/KE3 fire on ATTACK/RETREAT/END with
OT_ABILITY substitution, KE_SUP fires on ATTACK with OT_PLAY substitution).

## Unit tests (to be written before any self-play)

Following KE1/KE3 pattern, 6-8 synthetic assertions on
`_playable_supporter_index` and `_ke_sup_veto`:

1. Returns index of Crispin (1198) PLAY when hand has Crispin and
   supporterPlayed=False.
2. Returns index of Boss's Orders (1182) PLAY when hand has Boss's.
3. Abstains (returns None) when hand has no Supporter (only Ultra Ball
   1121, Energy Switch 1116, energies).
4. Abstains when `supporterPlayed=True` (engine won't expose OT_PLAY for
   Supporters in that state; helper never finds one).
5. `_ke_sup_veto` abstains when flag off.
6. `_ke_sup_veto` abstains when chosen action is not OT_ATTACK (RETREAT
   should NOT trigger — this is not KE1's set).
7. `_ke_sup_veto` swaps to the supporter index when all conditions hold.
8. `_ke_sup_veto` abstains when no OT_PLAY of a Supporter is on the menu
   (edge case: supporter in hand but engine refused to offer it, e.g.
   supporterPlayed already True).

## Arms — cross-deck, `crossdeck_kang.py --opp grimmsnarl`

Baseline and KE1-alone numbers from `KE3_SCREEN.md` (200g runs already on
disk, cited for the delta reference):

| arm | velocity | atk-when-legal | prizes/g | Win% |
|-----|----------|----------------|----------|------|
| baseline (no rules) | 0.2858 | 54.8% | 2.19 | 32.3% |
| KE1 alone           | 0.3350 | 55.9% | 2.64 | 39.2% |

New arms (200g each, seats alternated):

| arm       | config                              |
|-----------|-------------------------------------|
| KE_SUP    | v1-alone + KE_SUP_ATK_BEFORE_SUPPORTER |
| KE1+KE_SUP | v1-alone + KE1 + KE_SUP           |

## PRE-REGISTERED BANDS — fixed before running

**Primary metric: Win rate vs v1-alone Grimmsnarl, 200 games.**
Mirror self-play was shown by KE1_SCREEN.md (delta −0.007, CI spans zero)
to be the wrong instrument for strictly-dominated rules — cross-deck is
the standing measurement per KE12_CROSSDECK.md line 27-30.

### KE_SUP alone vs baseline (32.3%)

| band | condition | reading |
|------|-----------|---------|
| **PASS** | win% ≥ 35.0% (Δ ≥ +2.7pt over baseline) | rule engages; move to stacked test |
| **AMBIGUOUS** | 32.3% ≤ win% < 35.0% | non-negative but small; likely fire-rate mismatch or noise; do not proceed to stacked |
| **FAIL** | win% < 32.3% | rule regresses; do not ship, do not stack; document like KE12 did |

### KE1+KE_SUP stacked vs KE1-alone (39.2%)

**This is the load-bearing test** — it distinguishes "second orthogonal
rule that compounds" from "third variant of the same veto that competes."

| band | condition | reading |
|------|-----------|---------|
| **PASS** | win% ≥ 41.0% (Δ ≥ +1.8pt over KE1-alone) AND KE_SUP fire count in the stacked arm within ±30% of KE_SUP-alone arm | genuine compounding; ship KE1+KE_SUP bundle |
| **AMBIGUOUS** | 39.2% ≤ win% < 41.0% OR KE_SUP fires down 30-70% vs alone | mild interaction; extend to 400g before deciding |
| **FAIL** | win% < 39.2% OR KE_SUP fires down >70% vs alone | same failure shape as KE12/KE13 (rules compete despite different slots); ship KE1-only, keep KE_SUP flag in codebase default-off |

**Guards, not verdict inputs:**
- Own-turns within ±0.3 of KE1-alone's 7.68 (excessive turn count = looping).
- Atk-when-legal not down more than 5pt from KE1-alone's 55.9% (some drop
  is expected — we're replacing some ATTACKs with PLAYs by design — but
  a big drop means we're vetoing beyond the intended cell).
- KE_SUP fire count reported alongside KE1 fire count.

### Threshold reasoning

- KE_SUP-alone +2.7pt threshold: lower than KE1's +7pt because the cell
  has smaller leverage (0.044 vs KE1's `can_KO` at 0.093), so expected
  effect proportionally smaller (roughly 0.044/0.093 × 7pt ≈ +3.3pt).
  +2.7pt is 80% of that midpoint estimate.
- KE1+KE_SUP stacked +1.8pt threshold above KE1-alone: additivity would
  predict +2.7pt on top of KE1-alone; +1.8pt is 66% of that (allows some
  fraction of KE_SUP's effect to be non-additive without failing).

**Bands are not revised after seeing results.**

---

## RESULTS — 200 games each, cross-deck vs v1-alone Grimmsnarl

| arm | Win% | vel | ownT/g | atkWL | prz/g | KE1 fires | KE_SUP fires |
|-----|-----:|----:|-------:|------:|------:|----------:|-------------:|
| baseline (no rules) | 32.0% | 0.2858 | 7.68 | 54.8% | 2.19 | 0 | 0 |
| KE1 alone           | 39.0% | 0.3350 | 7.88 | 55.9% | 2.64 | 695 | 0 |
| **KE_SUP alone**    | **25.0%** | 0.2726 | 7.76 | **51.4%** | 2.12 | 0 | 123 |
| **KE1 + KE_SUP**    | **37.0%** | 0.3466 | 7.64 | **58.3%** | 2.65 | 627 | 190 |

Baseline and KE1 reproduced within 0.2pt of the numbers cited in
`KE3_SCREEN.md` (baseline 32.3% → 32.0%; KE1 39.2% → 39.0%). Screen build
is consistent with the shipped bundle.

## VERDICT — FAIL on both pre-registered bands

**KE_SUP alone: 25.0% vs baseline 32.0% (Δ = −7.0pt) — FAIL** (band was
<32.3%).

**KE1 + KE_SUP: 37.0% vs KE1-alone 39.0% (Δ = −2.0pt) — FAIL** (band was
<39.2%). Fire count went UP not down (190 stacked vs 123 alone), so this
is not the KE12/KE13-style hook-slot competition — the two rules do fire
on genuinely disjoint slots as designed. The regression is caused by
something else.

## Root cause — sequencing hole after supporter play

The mechanism engages: KE_SUP swaps ATTACK→PLAY(supporter) 123 times in
200 games as intended, and the unit tests confirm the swap is correct.
The failure mode is downstream.

Diagnostic — **atk-when-legal drops** in both arms:
- KE_SUP alone: baseline 54.8% → 51.4% (**−3.4pt**)
- KE1 + KE_SUP: KE1-alone 55.9% → 58.3% (+2.4pt; the compound with KE1's
  free-draw draws more attack-enabling energy, which masks the underlying
  drop that KE_SUP-alone made visible)

Interpretation: when KE_SUP swaps ATTACK → PLAY-supporter, the supporter
resolves and v1 gets a fresh MAIN decision. v1 does not have a hard
"supporter → attack" post-condition — it re-scores the new menu from
scratch and often picks something other than ATTACK (another PLAY, an
ATTACH, or END). The mined top-10 pattern presumes a pilot who knows
supporter-then-attack as a sequence; our v1's scorer treats each MAIN
decision independently, so removing one of its attacks does not guarantee
the attack comes back on the next MAIN this turn.

Contrast with KE1's shape: KE1 swaps `{ATTACK, RETREAT, END} → OT_ABILITY`
(Run Errand). Run Errand is a free draw with no game-state side effects
beyond hand size — the very next MAIN presents the same menu minus the
ability, and v1 re-picks the same ATTACK/RETREAT/END. Substitution is
neutral to sequence. KE_SUP substitutes to a Supporter play, which
*changes hand contents*, sometimes making the attack look less attractive
on the re-score (an Ultra Ball just added to hand outscores ATTACK in
v1's early-turn preferences). So the substitution is not sequence-neutral
in the same way KE1's is.

## What this closes and what it doesn't

**Closes:** the simplest form of the mined `atk_legal & supporter_pending`
signal. A rule that substitutes ATTACK→supporter without also gating
v1's post-supporter MAIN to re-select ATTACK does not translate to a win-
rate gain. Do not ship KE_SUP.

**Does not close:** the mining signal itself. The 18.8pt over-attack gap
in this cell is real; top-10 pilots do play supporter first and then
attack. A working rule would need to be **paired** — swap ATTACK→supporter
AND then gate the immediate follow-up MAIN to prefer ATTACK from the same
menu if ATTACK is still legal. That's a more invasive rule (multi-turn
state tracker) than what KE1/KE_SUP shape allows, and needs its own
mining/design cycle.

**Also does not close:** the broader Kangaskhan build. KE1-only remains
the shippable single-rule position. KE_BOLT (see `KE_BOLT_DESIGN.md`) is
the next candidate; its 0.4×/game Bellowing Thunder usage gap by top-10
is a larger and cleaner signal (we NEVER use it in 200g despite it being
offered 135 times), and the substitution shape is ATTACK→ATTACK which
does not have KE_SUP's sequence-hole failure mode.

## What ships

**KE1-only bundle (`dist/kang/v1_kang_ke1.tar.gz`, sha `681fb6e7…122008`)
remains the shipped Kangaskhan position, unchanged.** No rebuild. KE_SUP
flag stays in the codebase, default off, for the record.

