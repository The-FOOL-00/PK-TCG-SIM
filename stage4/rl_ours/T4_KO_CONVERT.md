# T4 — KO-conversion in the damage-target scorer

**Written 2026-08-02 BEFORE any arm was run. Nothing built, nothing submitted.**

## The defect, located

`main.py:1720`, `SC_DMG_COUNTER / SC_DMG_COUNTER_ANY / SC_DAMAGE` — the scorer
for **every damage-placement target** we choose:

```python
if TARGET_T2_SPLASH_RATIO:
    ratio = (pk.get("hp") or 0) / max(1.0, maxhp)
    s = 200.0 * (1.0 - ratio)          # prefer proportionally most damaged
```

**It never checks whether the damage about to be placed would knock the target
out.** A 320-HP Grimmsnarl at 48 HP (ratio 0.15 → score 170) outranks a 70-HP
Impidimp at 30 HP (ratio 0.43 → score 114) — but 30 damage *kills the Impidimp*
and leaves the Grimmsnarl alive. We place the counters, the target survives, the
damage strands.

T2 fixed *raw HP → HP ratio*. It never introduced the concept of **lethal**.

## The measurement that motivates it

Damage-to-KO conversion, computed from the 300-game replay sets already on disk
(`HpChange` events keyed by engine serial, versus each card's `hp`):

| build | damage dealt | KOs | **stranded** | dmg/KO |
|---|---|---|---|---|
| **Grimmsnarl, shipped (E1+E2+T1+T2)** | 451,830 | 1,997 | **29.4%** | 226.3 |
| Grimmsnarl, v1-alone | 415,520 | 1,949 | 28.3% | 213.2 |
| Ogerpon, E1+E2 | 303,590 | 1,382 | **4.4%** | 219.7 |

**29.4% of all damage we deal never becomes a knockout.** Ogerpon — a
single-target deck with no splash, no Munkidori, no Froslass — strands 4.4%. The
gap is structural to a damage-spreading deck, and it is exactly the mechanism
behind writeup §8:

> across 100 games our damage dealt (26,470 vs 26,850) and attack count
> (372 vs 365) were unchanged versus the mirror … identical output buys fewer
> knockouts.

§8 concluded "no rule fixes a stat mismatch." That conclusion is wrong on this
evidence: identical damage and identical attacks yielding fewer KOs is a
**conversion** gap, and conversion is decided at the target-selection slot.

Note the shipped rules made stranding slightly *worse* (29.4% vs 28.3%) while
raising both damage and KOs — T2 aims damage better without aiming it at *kills*.

## Why this rule shape is the one that survives

`[[kang-rule-shape-lesson]]` and writeup §6: *"A rule substituting a free action
for a terminal one succeeds — the menu is unchanged minus that action. A rule
promoting an action the pilot would not otherwise take fails."*

T4 is **safer than that shape**: it is the *same action*, a different target
index. The pilot was always going to place this damage. T4 only changes where.
It cannot shift the state into a line the pilot cannot continue, so the failure
mode that killed KE_SUP / KE_BOLT / KE_WELL and the four mined rules of §6 does
not apply.

## Implementation — the inputs exist

Verified against 40 games of replay:

| context | source | decisions / 40 games | damage |
|---|---|---|---|
| `13` `SC_DMG_COUNTER` | `effect.id = 112` (**Munkidori**, Adrena-Brain) | 56 | 3 counters = **30** |
| `15` `SC_DAMAGE` | Shadow Bullet splash | **787** | **30** |

- The scorer already receives `pk` with live `hp` / `maxHp` — it reads them today.
- The scorer already receives `effect`, which names the **source card id**.
- **`remainDamageCounter` is unusable** — present in the schema, but measured 0
  at every one of these decisions across 40 games, and referenced nowhere in
  `main.py`. Damage amount must come from a source-card map, not this field.

Rule, behind `PTCG_TARGET_T4_LETHAL`, default off:

```
amount = DMG_BY_SOURCE.get(effect.id)        # Munkidori 112 -> 30; splash -> 30
if amount and pk.hp <= amount:               # this placement KOs the target
    return LETHAL_TARGET_SCORE               # above any ratio score
# else fall through to the existing T2 ratio scorer, unchanged
```

Fire counter `STATS["t4_fired"]` mandatory — *a rule that did not fire has not
been tested*, and §6's dynamic-damage rule died starved at 13 fires. Expected
volume here is ~20 opportunities/game, so starvation is not the risk.

## PRE-REGISTERED BANDS — fixed before any arm runs

Arms, 300 games, `metaG_grimmsnarl_top10.csv`, mirror:

| arm | config |
|---|---|
| `ZG_SHIP` | shipped E1+E2+T1+T2 — **already measured**, velocity 0.4860, stranded 29.4% |
| `T4` | shipped **+ T4** |

**Primary: prize velocity.** Guard: stranded-damage share.

| band | condition | action |
|---|---|---|
| **PASS** | velocity delta ≥ **+0.026** (above the 0.019–0.025 same-config noise band) **and** stranded share falls | escalate to 300-game A/B; ship only on CI-low > 50%, slot 2 only |
| **MECHANISM-ONLY** | stranded share falls ≥ 3 pt but velocity delta < +0.026 | the rule does what it claims and does not convert. **Record, do not ship.** This is the §4-lie-2 signature and the honest outcome to expect |
| **FAIL** | stranded share does not fall, or `t4_fired` < 500 | defect mis-diagnosed or rule inert. Kill |

## Build log — two process failures, recorded

**1. The inert-flag bug, FIFTH occurrence.** `TARGET_T4_LETHAL` was missing from
`horizon_test.py`'s flag-application loop (line ~200). The arm would have run
with T4 dead and produced a null that looked like a refutation. Caught before
launch by checking the loop, not by the result.

Running tally (C2_SHIP.md §"BUILDER CHECK"): `PILOT` → `CAND_ATK_W` →
`CARD_R1/R2/R3` → `SEQ_E1/E2` → **`TARGET_T4_LETHAL`**. Mitigation added: the
arm banner now prints `T1=/T2=/T4=` so a dead flag is visible at launch.
Confirmed `T4=True` before the run.

**2. I corrupted two runs and discarded them.** `t4_fired` was not captured in
the replay `_seq` block, so the pre-registered fire-count kill condition was
unfalsifiable. I added the capture and restarted — but ran `rm -rf` on the
output directory while the first run was still writing to it, which crashed the
second with `FileNotFoundError`. Both aborted at ~33 games. No data from either
is used. The reported result comes from a single clean run.

**3. Fire-rate observation from the aborted data, and a threshold I am NOT
moving.** The aborted run showed **~36 fires over 33 games ≈ 1.1/game**, which
extrapolates to ~330 over 300 games — **below the 500 threshold pre-registered
above.**

The threshold was mis-derived: I set it from ~20 damage-placement *decisions*
per game (contexts 13+15), but T4 fires only when a candidate target is actually
*lethal* (`hp ≤ 30`), which is a small subset of those. The right denominator
was never "damage placements", it was "damage placements with a killable target
on the menu."

**The threshold stays at 500 as written.** Relaxing a pre-registered kill
condition after seeing data is precisely the post-hoc selection this protocol
exists to catch — writeup §6 records us catching it once already. If the clean
run lands near 330, T4 **FAILS on fire count** and the honest report is: the
rule is sound, the screen was mis-powered, and a correctly-powered re-run is a
*new* screen with its own pre-registration.

## RESULT — 2026-08-02, one clean 300-game run. **KILL. All three bands FAIL.**

| band | required | measured | verdict |
|---|---|---|---|
| **primary** velocity | ≥ **+0.026** | **−0.0001**, CI [−0.0241, +0.0246] | **FAIL** |
| **guard** stranded share | fall ≥ **3 pt** for MECHANISM-ONLY | **29.4% → 29.2%** (0.2 pt) | **FAIL** |
| **fire count** | ≥ **500** | **363** (1.21/game) | **FAIL** |

| | `ZG_SHIP` | `T4` |
|---|---|---|
| prize velocity | 0.4860 | 0.4858 |
| damage dealt | 451,830 | 451,890 |
| KOs | 1,997 | **2,019** (+22) |
| stranded | 29.4% | 29.2% |
| own turns / side | 7.13 | 7.23 |

**The rule works and does not matter.** It fires, it converts — KOs rise by 22
over 300 games (+1.1%) on identical damage, which is the mechanism doing exactly
what it was built to do. The effect is simply too small to see: at **1.21
lethal-target opportunities per game**, T4 can only touch a sliver of the
stranded 29.4%.

`t4_fired = 363 < 500` fires the pre-registered kill on its own, independent of
the other two. As recorded in the build log above, that threshold was
mis-derived and I left it unchanged rather than move it after seeing data. It
does not matter here: velocity and the guard both fail on their own terms, so no
reading of the fire threshold rescues this.

### What the KILL actually establishes

**The 29.4% diagnosis was right; the intervention was aimed at the wrong slice.**
Stranded damage is dominated by two sources a lethal check cannot reach:

1. **Froslass Freezing Shroud** — a counter on every Ability holder each Checkup.
   No decision attached, so no rule can retarget it.
2. **Splash onto targets nowhere near death.** Shadow Bullet's 30 lands on a
   full-HP bench Pokémon ~19 times for every 1 time it lands on a killable one.

Converting the bulk would require placing damage so it *accumulates toward a
future KO* — choosing the target you will finish two turns from now. That is not
a local substitution; it is planning, and this pilot has none. It is the same
wall as writeup §3: *a fixed priority order is a plan, and only for lines that
fall out of the order.*

**Consequence: KO-conversion is closed as a rule-shaped lever.** The stranding is
structural to a damage-spreading deck piloted by a greedy scorer. `PTCG_TARGET_T4`
stays default-off. The measurement itself (`ko_conversion.py`, 29.4% vs Ogerpon's
4.4%) is worth keeping — it is a real, previously-unmeasured property of the ship
build and it corrects writeup §8's "no rule fixes a stat mismatch" to the sharper
"this is a conversion gap, and conversion needs planning we do not have."

## Limits, before the numbers exist

1. **Mirror self-play.** Measures conversion honestly (both counts are absolute)
   but not strength. Our §8 records mirror overstating ladder strength ~2×.
   PASS escalates; it does not ship.
2. **Not all 29.4% is addressable.** Froslass's Freezing Shroud places a counter
   on *every* Ability holder each Checkup with no decision attached. That share
   is structural and T4 cannot touch it. The addressable slice is the ~843
   decisions/40 games in contexts 13 and 15.
3. **This does not reach μ1000.** Team level is μ~700, now confirmed empirically:
   re-uploading the 807.2 archive returned ~700, so 807.2 and 877.8 were
   upper-tail draws inside the documented 600–955 byte-identical band, not skill.
   T4 is the best-evidenced remaining lever, not a 300-point one.
