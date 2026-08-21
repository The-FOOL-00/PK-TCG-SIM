# Does our generic policy pilot Archaludon ex / Cinderace well?

**Nothing submitted.** Header written and committed before any arm runs.

---

## Why this test

SANJAY_CURRENT.md's Step 4 could not cleanly separate his edge into "deck"
vs "rules" — both plausibly contribute. We now have his exact 60-card list
(reconstructed from replay data, `metaX_archaludon_sanjay.csv`, validated
clean against the live engine pool — 0 unknown ids). Running **our own
generic policy, unmodified, on his deck** isolates the deck variable exactly
the way DECK_SWITCH.md isolated Grimmsnarl vs Garchomp: same code, different
`deck.csv`.

**One relevant fact checked first:** Archaludon ex is the **only** ex card in
this deck too (Duraludon, Cinderace, Relicanth are not ex). So T1's
prize-value differentiator will face the same self-play mirror confound
documented in TARGET_FIX_SHIP.md — noted, not a reason to skip the test, since
T2 and the E1/E2 sequencing gates are unaffected by it.

## Arms — 100 games self-play each, `PILOT=""`

| arm | config | deck |
|---|---|---|
| **AR-v1** | v1-alone, no rules | Archaludon ex / Cinderace |
| **AR-full** | v1 + SEQ_E1 + SEQ_E2 + TARGET_T1 + TARGET_T2 (our current best build) | Archaludon ex / Cinderace |

## Comparators — already measured, same policy, Grimmsnarl deck

| arm | config | prize velocity |
|---|---|---|
| D1 (DECK_SWITCH.md) | v1-alone | **0.4574** |
| C2 (CONDITIONAL_BUILD.md, 300g) | v1 + E1+E2 | 0.4823 |
| T1T2 (TARGET_FIX_SHIP.md, 300g) | v1 + E1+E2+T1+T2 | **0.4953** |

## PRE-REGISTERED BANDS — fixed before running

**Primary counter: prize velocity, AR-full vs T1T2's 0.4953 (same full config,
different deck).**

| band | condition | reading |
|---|---|---|
| **PASS** | AR-full ≥ **0.60** | deck is structurally superior even under fully generic piloting — supports "mostly deck" |
| **MARGINAL** | 0.4953 ≤ AR-full < 0.60 | comparable to or modestly better than Grimmsnarl — deck helps some, not decisively |
| **FAIL** | AR-full < 0.4953 | deck alone, under our generic policy, does **not** beat what we already have — Sanjay's rule sophistication is doing the majority of the work, not the deck |

**Secondary: AR-v1 vs D1 (0.4574)** — the same comparison with rules stripped
from both sides, to see if the deck edge (if any) survives without E1/E2/T1/T2
riding along.

**Also reported, not verdict inputs:** own turns/game, first attack turn,
attack-when-legal, extra draws/turn — same shape as every other arm this
session.

**Bands are not revised after results.** If AR-full lands ambiguously close to
a boundary, the response is the same one used for T1T2: extend the sample
before deciding, not redraw the line.

---

## RESULTS

| arm | sides | prize velocity | own turns/game | attack-when-legal |
|---|---|---|---|---|
| **AR-v1** (no rules) | 200 | **0.2510** | 9.01 | 42.3% |
| AR + E1 only | 200 | 0.2248 | 8.70 | 37.8% |
| AR + T1 only | 200 | 0.2434 | 8.56 | 38.1% |
| **AR-full** (E1+E2+T1+T2) | 200 | **0.2207** | 9.43 | 36.9% |
| *(comparator)* T1T2, Grimmsnarl, same policy | 300 | *0.4953* | *7.00* | *87.5%* |
| *(comparator)* Sanjay's own real ladder | 69 eps | *0.4718* | *6.17* | *64.9%* |

### **FAIL, decisively — and the finding is stronger than a simple miss**

AR-full's velocity (0.2207) sits **far below the pre-registered FAIL
threshold (0.4953)** — not close, not marginal. More importantly: **AR-full
is worse than AR-v1 with no rules at all** (0.2207 vs 0.2510). Our own rules,
calibrated and shipped on Grimmsnarl, are **actively harmful** on this deck.

### Root cause, confirmed directly — not inferred

E1 vetoes attack in favour of any legal `PLAY`/`ATTACH`/`EVOLVE` option.
Checked directly against 40 games of replay: **in every single decision where
both an attack and a develop option were legal (n=1059), E1 deferred the
attack — 100.0% of the time.** That is E1 working exactly as designed.

**The design assumption breaks on this deck.** E1 was built on the Phase 1
finding that *"ATTACK is terminal; every other action is free"* — true for
every attack in Grimmsnarl's deck. It is **false for Cinderace's Turbo Flare**:
`"Search your deck for up to 3 Basic Energy cards and attach them to your
Benched Pokémon"` — Turbo Flare **is** a development action, just one that
also deals damage. Deferring it every time doesn't sequence around a terminal
action; it delays the exact ramp effect the deck's tempo plan depends on.
T1 (Boss prize-value targeting) adds a smaller additional decrement on top,
consistent with it being a narrower, lower-magnitude fix.

### What this settles from SANJAY_CURRENT.md's Step 4

**The deck alone does not explain his edge — his rule layer is not
optional.** Our generic policy, even with the best rules this project has
produced, cannot get within range of either our own Grimmsnarl numbers or
Sanjay's actual ladder figure (0.4718) on his deck. Whatever fraction of his
807 the deck construction contributes, it is **conditional on** — not
separable from — the ~1200 lines of matchup-aware, deck-specific logic that
pilots it. Deck choice was the 10× lever when moving from Garchomp to
Grimmsnarl (both piloted by rules mined *for* Grimmsnarl); it is not a
transferable shortcut to a deck we have not built comparable execution for.

## Recommendation — do not switch decks; the redirect is back to Grimmsnarl depth

1. **Do not adopt Archaludon ex / Cinderace.** Under present evidence it would
   *lower* our score relative to what we already have, not raise it.
2. **E1 and T1 are confirmed non-transferable as unconditional rules.** Both
   remain correctly scoped to Grimmsnarl (where they were mined and where E1/E2
   already show a real +0.085 ladder signal per SANJAY_CURRENT.md) — nothing
   here reduces confidence in TARGET_FIX_SHIP.md's shipped bundle, which is
   Grimmsnarl-only. It is a caution against reusing these specific rules
   unconditionally on any future deck without re-mining for that deck first.
3. **The path to closing more of the gap to 807/1000 is deck-specific rule
   depth on Grimmsnarl itself** — priority 3 from MATCHUP_MINING.md
   (per-archetype secondary-criterion tuning on Shadow Bullet targeting,
   already evidenced at n=287/162/47/41 for four opponent archetypes) is the
   next well-evidenced, buildable step, not a deck switch.

### Artifacts

| path | contents |
|---|---|
| `metaX_archaludon_sanjay.csv` | Sanjay's reconstructed decklist, validated |
| `scratchpad/s3/horizon_AR_{V1,FULL,E1_ONLY,T1_ONLY}/` | 100 games each |
