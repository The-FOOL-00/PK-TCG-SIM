# Kangaskhan/Raging Bolt Phase 1 — E1 sequencing test

**Nothing submitted.** Written before any arm below is run.

## Why this exists

Per ROSTER_DIFF_JUL31.md, Kangaskhan/Raging Bolt ex is the chosen build
target (most repeatedly-confirmed archetype edge over Grimmsnarl across 4
independent snapshots). `kangaskhan_mine.py` ran the same turn-state
conditional mining that originally found E1/E2 for Grimmsnarl, comparing 85
pooled top-10 Kangaskhan pilot sides (Jul26+Jul31 harvests, 3127 MAIN
decisions) against our own generic v1-alone piloting of the same decklist
(7864 decisions, from this session's `crossdeck_test.py` OPP-side data).

**Top finding, by a wide margin: the `can_KO` cell, TVD=0.720 (n=404
them / 342 us).** When a legal, certain-lethal attack is available: **we
attack 100.0% of the time; top-10 pilots attack only 28.0% of the time**
(PLAY 32.9%, ABILITY 24.0%, RETREAT 6.9%, ATTACH 6.9%, END 1.2%).

## Mechanism, verified against card_data.json before designing anything

**Mega Kangaskhan ex (756, 3 copies)**: ability *Run Errand* — "Once during
your turn, if this Pokemon is in the Active Spot, you may use this Ability.
Draw 2 cards." Free, no cost, usable once per turn, **does not end the
turn** (MAIN menu re-presents after an Ability just as after any other
non-terminal action). Its only attack, **Rapid-Fire Combo, is a pure damage
attack** (200 base + coin flips) with no development side-effect — this is
exactly E1's clean case: attack is terminal, ability is free, sequence
ability first, attack after. Example decisions confirm this pattern: pilots
take ABILITY (Run Errand) then, in a later MAIN decision the same turn with
Ability now exhausted, still sometimes decline the attack for PLAY/RETREAT —
worth watching but the dominant, cheap, obviously-correct piece is the
Ability-before-terminal-attack sequencing, identical in shape to E1's
original Grimmsnarl finding.

**Known risk, carried forward explicitly from ARCHALUDON_TEST.md**:
**Raging Bolt ex (63, 2 copies)**'s attack **Burst Roar deals 0 damage and
reads "Discard your hand and draw 6 cards"** — a hybrid attack+refresh
effect, structurally identical to Cinderace's Turbo Flare, which is exactly
what made E1 actively harmful on the Archaludon deck (100% of attack/develop
ties deferred the attack, delaying the deck's own ramp effect). E1 applied
unconditionally here risks the same failure mode on Raging Bolt specifically,
even if it helps on Mega Kangaskhan. This is not hypothetical — it is the
documented cause of the only clean negative-transfer result this project has
found.

**Net expectation, stated before running:** could go either way. Kangaskhan
is 3 copies / more central to the decklist than Raging Bolt's 2, so if E1
nets positive it's a real edge; if Burst Roar dominates when it matters
(e.g. late-game refuel turns), E1 could net negative exactly as it did on
Archaludon. This is why it's tested, not assumed.

## Arms — self-play mirror, `--deck metaX_kangaskhan_top10.csv`, 200 games each

| arm | config |
|---|---|
| **K0** | v1-alone, no rules (baseline) |
| **K1** | + SEQ_E1 |

## PRE-REGISTERED BANDS — fixed before running

**Primary: prize velocity, K1 vs K0.**

| band | condition | reading |
|---|---|---|
| **PASS** | K1 − K0 ≥ +0.03 | E1 transfers, proceed to design E2-equivalent + target-selection mining for this deck |
| **AMBIGUOUS** | −0.02 < delta < +0.03 | extend to 400 games before deciding, same rule as every prior test |
| **FAIL** | K1 − K0 ≤ −0.02 | Burst Roar's dual-purpose nature dominates, as in ARCHALUDON_TEST; E1 does not transfer here either; next step is a Kangaskhan-specific sequencing rule that exempts Burst Roar, not unconditional E1 |

**Guards, not verdict inputs:** own-turns must not increase; report
`e1_veto` fire count to confirm the mechanism actually engages on this deck.

**Bands are not revised after seeing results.**

---

## RESULTS

| n | K0 (baseline) | K1 (+E1) | delta | 95% CI | own-turns guard |
|---|---|---|---|---|---|
| 200g (400 sides) | 0.2957 | 0.2872 | −0.0085 | [−0.0414, +0.0242] | OK |
| **400g (800 sides)** | 0.2991 | 0.2850 | **−0.0141** | **[−0.0387, +0.0101]** | **BROKEN** (7.89 vs 7.75) |

`e1_veto` fired 165/game — the mechanism engages heavily, as expected given
how central Mega Kangaskhan's free Ability is to this deck.

Per the pre-registered protocol, the ambiguous 200g read was extended to
400g rather than decided early. At 400g the point estimate moved **further
negative** (−0.0085 → −0.0141), not toward the +0.03 PASS line, and the
own-turns guard — clean at 200g — broke at 400g (games got longer with E1
on, the opposite of the intended effect). The CI still technically spans
zero, so this doesn't clear the literal −0.02 FAIL line, but the direction,
the trend with more data, and the guard break all point the same way.

## VERDICT: E1 does not transfer to Kangaskhan/Raging Bolt either

**Second deck in a row where unconditional E1 fails to help**, for the same
class of reason flagged before running: Raging Bolt's Burst Roar (0 damage,
"discard hand draw 6") is a dual-purpose attack, structurally identical to
the Cinderace effect that made E1 actively harmful on Archaludon
(ARCHALUDON_TEST.md). Mega Kangaskhan's own case (free Ability before a
pure-damage attack) is exactly E1's clean scenario and likely *is* a real
win in isolation — but applied unconditionally across the whole 60-card deck,
whatever it gains on Kangaskhan's turns is offset or reversed by mishandling
Raging Bolt's turns.

**This generalizes the lesson beyond a single deck**: E1/E2/T1/T2 were mined
*for* Grimmsnarl and validated *on* Grimmsnarl; porting them wholesale to a
new deck is now 0-for-2 (Archaludon, Kangaskhan). A native build for a new
archetype needs a card-by-card audit of every attack/ability for hidden
dual-purpose effects before any sequencing rule is applied — not a port of
existing rules, and not a small addition on top of them. That is
substantially more work than tonight's remaining budget covers; it is
comparable in scope to the multi-week effort that produced Grimmsnarl's
current rule set.

**Not pursuing a Kangaskhan-specific exemption for Burst Roar tonight** —
that would be a new design-build-test cycle in its own right, and the
`can_KO` cell's real story likely has other components beyond just this one
attack (the mined data showed top-10 also choosing PLAY/RETREAT over the
attack in decisions *after* Mega Kangaskhan's Ability was already spent,
which E1 can't explain at all). Flagging as the next concrete step, not
completing it now.

