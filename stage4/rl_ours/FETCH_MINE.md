# F1 — the fetch scorer is the discard scorer, and it is near-inverted

**2026-08-02. Nothing submitted.** `PTCG_FETCH_F1` ships default-off.

## Why this slot, and why now

Today's screens established the constraint that rules out everything else:

| measurement | shipped Grimmsnarl build | top-10 field |
|---|---|---|
| MAIN actions / own turn | **5.82** | — |
| actions before attacking | **4.78** (v1-alone: 3.00) | **5.87** |
| prize velocity, mirror | 0.4860 | — |
| **prize velocity, ladder** | **0.2370** | **0.5725** |

**E1/E2 worked.** They closed 61% of the action-count gap; behaviourally we are
near field parity. And ladder velocity is still **41%** of the field's.

Same deck, same action count, 2.4× fewer prizes. The gap cannot be *how many*
actions — it is **which card, which target, which order**. That is the sub-action
layer, 30% of all decisions, and it is where both of this project's surviving
rules (T1, T2) live.

## The slot

Census over 287 top-10 replays, decisions with **more than one option**:

| context | n | rule? |
|---|---|---|
| MAIN menu (type 0) | 35,675 | E1/E2 |
| **`SC_TO_HAND` (7) — what a search retrieves** | **23,309** | **none** |
| `SC_DAMAGE` (15) — splash target | 6,232 | T2 |
| `SC_DMG_COUNTER` (13) — Munkidori | 1,694 | T2 |
| `SC_SWITCH` (3) — Boss's Orders | *(T1's slot)* | T1 |

`SC_TO_HAND` is the largest sub-action slot in the game — **3.7× T2's slot and
~100× T1's** — and nothing has ever been mined for it.

## The defect

```python
def _card_value(cid):
    """How much we mind losing this card (used for discard/keep choices)."""
    ...
    if ct == CT_BASIC_ENERGY:
        return 10.0      # lowest of any card type
```

`SC_TO_HAND` called `_card_value` directly. **Retrieving is not discarding.** The
scorer answers "what do I mind losing?", and for a fetch the right question is
"what do I need?" — so the cards it rates cheapest are exactly the ones you most
want to draw.

Measured: `_card_value(7)` Basic {D} Energy = **10.0**;
`_card_value(648)` Marnie's Grimmsnarl ex = **300.0**. A 30× inversion on the
most-fetched card in the deck.

This is T1's defect exactly — *"the same formula used to promote our own Pokémon,
which is backwards when choosing an opponent's Pokémon"* — on 100× the volume.

## The mine (`fetch_mine.py`)

Top-10 replays, Grimmsnarl sides, winning sides, single-select, resolvable
options: **n = 662**.

| criterion | agreement with top-10 |
|---|---|
| **shipped `_card_value`** | **36.0%** |
| **energy-first, then `_card_value`** | **68.3%** |
| always *lowest* `_card_value` | 66.5% |
| *(reference: T1 84.1%, T2 82.4%)* | |

What they take: **Basic Energy 55.6%**, Pokémon 30.1%, Supporter 14.4%. Basic
Energy is on the menu in 521/662 decisions and they take it **70.6%** of the time.

That "always lowest `_card_value` = 66.5%" line is the finding in one number: the
borrowed scorer is not merely wrong here, it is **approximately inverted**.

Mechanically right for this deck: 10 Basic {D} Energy in 60 cards. Punk Up
delivers 5 — once, on evolve. Energy is the binding resource; Grimmsnarl ex is a
3-of you draw anyway. Energy starvation caps how often attacking is *legal*,
which is how you get 89% attack-when-legal alongside 0.2370 ladder velocity.

## The rule

```python
if ctx == SC_TO_HAND:
    if FETCH_F1_ENERGY_FIRST and _card(cid).get("cardType") == CT_BASIC_ENERGY:
        STATS["f1_fired"] += 1
        return 1000.0 + _card_value(cid)
    return _card_value(cid) if cid is not None else 10.0   # unchanged
```

Same action, different index — the pure-substitution shape that survived for
T1/T2 and that `[[kang-rule-shape-lesson]]` says is the only shape that works.
Non-energy candidates keep their existing ordering exactly.

Flag wired into `horizon_test.py`'s application loop and printed in the arm
banner (`F1=True` verified) — the inert-flag bug has now bitten this project
five times and was avoided here by construction.

## What this is NOT — read before believing the 68.3%

**Agreement is not win rate, and this project has the scar to prove it.** BC
reached **69–97% static accuracy** and **31–49% head-to-head**, three times.
Writeup §4: *every offline proxy we trusted read excellent while head-to-head
read 31–49%.* A 68.3% agreement number is an offline proxy of exactly that kind.

The reason to think this differs from BC is structural, not statistical: BC
replaced the **whole policy**, so its errors compounded through states the expert
never visited. F1 changes **one context's ordering** and leaves every other
decision byte-identical. That is the T1/T2 shape, and T1/T2 are the two things in
this project that shipped and stuck.

**Do not screen this in the mirror.** Today established that the mirror inflates
2× (0.4574 → 0.2370) and that its noise floor (±0.019–0.025) exceeds nearly every
effect this project has produced. A fetch improvement is symmetric in a mirror —
both seats get it — so a mirror screen is expected to read null *by construction*,
exactly as it did for E1/E2, which then moved ladder velocity **+0.0853**.

**The correct instrument is the ladder**, one lever, slot protected to n ≥ 40.

## Limits

1. **n = 662 of 23,309** raw decisions, after filtering to Grimmsnarl + winning
   sides + single-select + resolvable card ids. Multi-selects and unresolved
   zones are dropped, not modelled; the criterion is mined on the subset.
2. **68.3% is well short of T1/T2's ~83%**, so the criterion is coarser than
   either shipped rule. There is likely a board-state condition on top of
   "prefer energy" (hand energy count, turn, whether the attacker is online)
   that this mine did not search for.
3. **Winning-sides-only** may bias toward the energy-hungry games.
4. Grimmsnarl-specific. The 10-energy-in-60 constraint is what makes energy the
   binding resource; the rule should not be assumed to port.
