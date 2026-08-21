# Matchup-conditioned mining — results, and a reframe

**Mining only. Nothing designed, built, or submitted.** Same evidence
discipline as CONDITIONAL_MINING.md: report first, stop for approval before
design.

---

## What was asked vs. what the evidence supports

The plan was to partition Phase-1-style decision cells by **opponent
archetype** instead of turn-state, then build per-matchup overrides on top of
Grimmsnarl + the shipped E1/E2 gates. That mining ran. **It found a weak
signal at the level requested, and a strong signal one level down — in WHICH
target gets picked, not WHETHER an action-type is favoured.** Reporting both,
honestly, because the second finding changes what should be built first.

---

## STEP 1 — action-type distribution by opponent archetype

Same source as Phase 1: top-10 Grimmsnarl sides (504, all three harvests),
28,323→19,323 MAIN decisions with an opponent archetype attached from
`steps[1][1-seat]`. Five archetypes clear a usable decision-count floor
(≥200):

| opponent archetype | sides | decisions | TVD vs pooled | leverage | WR vs field |
|---|---|---|---|---|---|
| Marnie's Grimmsnarl / Munkidori (mirror) | 175 | 7284 | 0.044 | 0.0166 | 58.9% |
| Fezandipiti ex / Dudunsparce | 109 | 4027 | 0.049 | 0.0103 | 63.3% |
| TR Mewtwo ex / TR Spidops | 65 | 2244 | 0.051 | 0.0059 | 58.5% |
| Mega Kangaskhan / Raging Bolt | 27 | 844 | 0.078 | 0.0034 | 29.6% *(n<60, not quotable)* |
| Cynthia's Garchomp / Roserade | 40 | 1522 | 0.017 | 0.0014 | 57.5% *(n<60, not quotable)* |

**These TVDs are small.** Compare to Phase 1's turn-state cells, where `can_KO`
alone had TVD **0.784**. The largest matchup-level TVD found here (0.078,
Kangaskhan) is **an order of magnitude smaller**. Pooled action-type
distribution: `PLAY=41.9% ATTACH=10.0% EVOLVE=11.0% ABILITY=23.1% RETREAT=2.0%
ATTACK=9.8% END=2.3%` — and no matchup moves this by more than ~5 points on any
single action type.

**Reading this plainly: top-10 Grimmsnarl pilots do not meaningfully change
*which type of action* they take based on who they're facing.** They PLAY,
ATTACH, EVOLVE, fire abilities, and attack at roughly the same rates against
the mirror, Fezandipiti, and TR Mewtwo alike. Whatever matchup awareness
exists in top play, it is not visible at this granularity.

**One quotable, unconditional fact from this pass:** top-10 Grimmsnarl has a
**winning or even record against all three archetypes with a quotable sample**
(58.9% / 63.3% / 58.5%, all n≥60) — no bad matchup shows up among its common
opponents. Sanjay's own Grimmsnarl-adjacent teammate history has flagged
Kangaskhan/Raging Bolt as a possible bad matchup (23W-10L one direction in
DECK_SWEEP.md), but that cell remains **n=33, below the quotability floor**,
and here too (n=27 sides) it doesn't clear the floor for a decision-level read.

---

## STEP 2 — target-*selection* mining. This is where the signal is.

Action-type frequency was the wrong resolution. Sanjay's own overrides
(`_v2_ov_boss_target_alakazam`, the Crustle-specific bench targeting, the
prize-weighted Boss scoring in `score_play`) all operate on **which specific
card gets picked**, not on how often an action type fires. Two decision
contexts in the engine carry exactly this shape and are common enough to mine:

- **`SC_DAMAGE` (context 15)** — Grimmsnarl ex's own Shadow Bullet: *"This
  attack also does 30 damage to 1 of your opponent's Benched Pokémon."* Fires
  on nearly every attacking turn.
- **`SC_SWITCH` (context 3)** — Boss's Orders / forced-switch targeting.

Both verified against `main.py`'s own `SC_` enum, not guessed.

### Shadow Bullet splash target — pooled n=1538

| criterion | pooled rate |
|---|---|
| **chose the lowest-HP-ratio target** | **82.4%** |
| chose the highest-prize-value target | 59.9% |
| chose the highest-energy target | 56.2% |

**Dominant and fairly matchup-invariant** — min-HP-ratio ranges 70.7–90.0%
across every archetype with n≥15. The clear primary heuristic: **snipe
whatever is closest to dying.**

By matchup, the *secondary* criteria do move:

| opponent | n | max-prize | max-energy | min-HP |
|---|---|---|---|---|
| Fezandipiti / Dudunsparce | 287 | **65.2%** | **66.6%** | 78.7% |
| TR Mewtwo / Spidops | 162 | 49.4% | 63.6% | 79.0% |
| Kangaskhan / Raging Bolt | 47 | **78.7%** | 53.2% | 89.4% |
| Kangaskhan / Crustle | 41 | **70.7%** | **70.7%** | 70.7% |
| pooled | 1538 | 59.9% | 56.2% | 82.4% |

### Boss's Orders target — pooled n=232

| criterion | pooled rate |
|---|---|
| **chose the highest-prize-value target** | **84.1%** |
| chose the highest-energy target | 59.1% |
| chose the lowest-HP-ratio target | 48.3% |

**Prize value dominates and is close to matchup-invariant** (70.0–100% across
every archetype with n≥28). The heuristic: **pull whatever is worth the most
prizes** — exactly the shape of Sanjay's own `pv * 200 + energy_count * 100`
Boss formula.

---

## ⚠️ What this exposed in our own scorer

Checked `_score_card`'s handling of these two contexts directly against
`main.py`:

```python
if ctx in (SC_SETUP_ACTIVE, SC_TO_ACTIVE, SC_SWITCH, SC_TO_FIELD):
    if LEARNED_VALUE and pk and opt.get("area") == AREA_BENCH \
            and opt.get("playerIndex") in (None, me):
        ...                                    # LEARNED_VALUE is off by default
    if PROMOTE_RULE and ctx == SC_TO_ACTIVE and pk:
        ...                                    # PROMOTE_RULE is off (killed gate)
    if pk:
        return (pk.get("hp") or 0) + 20.0 * len(pk.get("energies") or []) \
            + _best_attack_info(pk.get("id"))[0] / 10.0
```

**`SC_SWITCH` is bundled with `SC_TO_ACTIVE`/`SC_SETUP_ACTIVE` under one
formula, and the live fallback path never checks `opt.get("playerIndex")`.**
`LEARNED_VALUE` (off by default) is the only branch that restricts to our own
bench — confirmed `LEARNED_VALUE=False` at import. So **the exact same "prefer
high HP + energy + attack power" formula runs whether we are promoting our own
post-KO active or Boss-pulling the opponent's bench.**

That is backwards for the Boss case. Self-promotion correctly wants our
strongest Pokémon. Boss's Orders wants the **opponent's** highest-value target
— by the mined evidence, prize value (ex/mega worth more), not raw HP+energy,
which merely correlates with it. A non-ex attacker with more energy on board
would currently outscore a bench ex worth double the prizes.

For `SC_DAMAGE` (Shadow Bullet splash), the existing rule —
`s = 200.0 - (pk.get("hp") or 200)`, i.e. lower **raw** HP scores higher — is
already directionally aligned with the mined pattern (snipe low HP), but scores
by absolute HP rather than HP **ratio**, so a fresh 130-HP Basic and a
half-damaged 260-max-HP attacker at 130 HP score identically, when the mined
top-10 criterion (ratio) would treat them very differently.

**This is a confirmed scoring gap, not a hypothesis.** It is evidenced at
n=232 (Boss) and n=1538 (Shadow Bullet) pooled top-10 decisions, and it is
almost entirely **matchup-invariant** — it does not need per-archetype
detection to fix.

---

## Recommendation — reframe the next design step

The evidence changes the priority order from what was originally proposed:

| priority | what | confidence | matchup-specific? |
|---|---|---|---|
| **1** | **Prize-value + `playerIndex`-aware `SC_SWITCH` scoring** (Boss/forced-switch target) | **very high** — n=232, 84.1% pooled, confirmed live bug | **no — matchup-invariant** |
| **2** | **HP-ratio (not raw HP) `SC_DAMAGE` scoring** (splash target) | high — n=1538, 82.4% pooled, existing rule already half-right | mostly invariant |
| 3 | Fezandipiti/Kangaskhan secondary-criterion tuning on Shadow Bullet (max-prize/max-energy shift) | moderate — real but smaller deltas (49–79% range) on top of #2 | **yes** |
| 4 | Deep per-archetype action-type overrides as originally scoped | **low** — Step 1 found weak signal at this resolution | yes, but thin evidence |

**#1 and #2 are the actual highest-leverage next build**, and neither needs
opponent-archetype detection at all — they are corrections to context
handling that apply regardless of who is across the table. The originally-
requested matchup-specific override layer (#3/#4) is real but smaller, and
best attempted *after* #1/#2 are in, once the invariant-target-selection floor
is fixed and no longer confounding the matchup-specific reads.

I have not designed the fix. Per the phase discipline used throughout this
project (mine → design → build/screen → ship), this stops here for your call
on whether to proceed to design on #1+#2, on the originally-scoped
per-archetype layer, or both.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/matchup_mine.py` | Step 1 archetype-level action-type mining |
| `stage4/rl_ours/target_mine.py` | Step 2 target-selection mining (Shadow Bullet, Boss) |
| `scratchpad/s3/matchup_cells.json`, `target_cells.json` | raw counts |
