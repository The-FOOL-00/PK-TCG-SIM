# Card-specific piloting knowledge for the v1 heuristic ladder

**DIAGNOSIS AND PROPOSALS ONLY. Nothing built, nothing submitted.** Governor,
`cap=16`, `END_VETO`, `EVAL_FIX`, `PROMOTE_RULE`, `LETHAL_PROBE` and the
candidate-set arms all remain off and untouched.

---

# STEP 0 — **SIGN ERROR REFUTED.** The premise is wrong, but it found a real defect next door.

## 1. Draconic Buster's actual text — refutes the claim

```json
{"attackId": 532, "name": "Draconic Buster", "damage": 260,
 "energies": [6, 6], "text": "Discard all Energy from this Pokémon."}
```

**Flat 260 damage for two Fighting Energy, with an energy-discard drawback.
There is no scaling on damage counters, anywhere in the text.** Damage on our
own bench is not fuel for Draconic Buster. The published strategy is wrong for
this card, and `card_data.json` is authoritative.

## 2. The mechanic is real — it belongs to a different card, which we do run

Sweeping every attack whose text mentions damage counters and a bench:

```json
{"attackId": 540, "name": "Raging Curse", "damage": 0, "energies": [0],
 "text": "This attack does 10 damage for each damage counter on all of your
          Benched Cynthia's Pokémon. This attack's damage isn't affected by
          Weakness."}
```

That is **Cynthia's Spiritomb (387)** — and we run **2 copies**. So the
described mechanic exists in our deck, on a card the hypothesis did not name.

## 3. Does our eval penalise damage on our own bench? — **No. It does not see it at all.**

The active scorer is `_score_main`, a flat tier ladder with **no board-state
term of any kind** — no HP, no damage, no counters. There is no sign to get
wrong.

The only board-HP term in the file is in the **v3 evaluator**, which is
**off by default** (`V3_EVAL = os.environ.get("PTCG_V3_EVAL", "0") == "1"`):

```python
v += V3_W_BOARD_HP * (my_hp - their_hp)      # V3_W_BOARD_HP = +0.10
```

Sign is **positive on our own HP**, so damage on our bench *would* lower the
score — a genuine sign error against Raging Curse **if V3 were ever enabled.**
It is not, and has never shipped. Same for `LEARNED_VALUE`.

**Conclusion: the STOP condition is not met.** No sign error exists in any
shipped configuration, so I continued to Steps 1–3 as instructed.

## 4. The real defect: Raging Curse is priced at the floor

`_attack_score` uses printed damage, and Raging Curse's printed damage is **0**:

```python
def _attack_score(attack_id, cur, me):
    dmg = _attack_damage_est(attack_id, cur, me)
    ...
    return WEIGHT_ATTACK_BASE + min(dmg, 1900.0) * ATTACK_DAMAGE_SCALE
```

`_attack_damage_est` only special-cases `"riptide"` and `"hammer"` by name. The
Raging Curse scaling lives in `_SCALING_ATTACK_TAGS`, which is gated behind
`EVAL_FIX` — **killed, and off.** So:

| attack | true damage | **v1 score** |
|---|---|---|
| **Raging Curse** | 10 × counters (measured up to **360**) | **1000.0 — the exact floor** |
| Corkscrew Dive | 100 | 1050.0 |
| Draconic Buster | 260 | 1130.0 |

**A 360-damage Raging Curse scores identically to a 0-damage whiff.** This is a
magnitude error, not a sign error.

### Measured impact

| | H1 self-play (60 g) | VN ladder (25 eps, ship config) |
|---|---|---|
| MAIN decisions | 5032 | 979 |
| decisions with damage on our own bench | 1221 | 239 |
| **Raging Curse legal** | 132 | 7 |
| … taken | 29 (**22.0%**) | 2 (28.6%) |
| **legal WITH bench counters** | **48** | 7 |
| … **declined** | **39** | 5 |
| damage foregone (median / max / total) | **120 / 180 / 3770** | **360 / 360 / 1530** |

**Honest scope limit: Spiritomb is 2 copies, so ladder n is 7.** The ceiling on
this fix is small on its own — 0.8 opportunities per self-play game. It is worth
fixing because it is unambiguously wrong, not because it is large.

## 5. Cynthia's Power Weight — confirmed, in deck, and not the card the strategy implies

```json
{"name": "Cynthia's Power Weight", "cardType": 2,
 "skills": [{"text": "The Cynthia's Pokémon this card is attached to gets +70 HP."}]}
```

**In our deck: 3 copies. `cardType 2` = `CT_TOOL`**, so it scores
`WEIGHT_ATTACH_TOOL = 2100 + tgt × 0.5`. The +70 HP claim is confirmed. The
"survive while accumulating counters" rationale only pays off through **Raging
Curse**, not Draconic Buster — the same substitution as §1.

**Note `card_data.json` carries no free-text for Trainers or abilities in the
top-level fields — it is all in `skills[]`.** Everything below is verified from
there.

---

# STEP 1 — mined from our own top-10 replays

Source: `replays_top10_jul21/` + `replays_top10_jul22/`, restricted to the two
top-10 agents who pilot **this deck** — **junlee789** and **Yudai Ueno** — by
`info.TeamNames`. Cross-checked against an archetype-only filter (any Cynthia's
Garchomp side): the two agree within ~2 points on every rule, so contamination
from mirrored opponents is negligible.

All rows below are **per MAIN decision**, identically computed for both sides.
Every reported rule has **n ≥ 20**.

| rule | **top-10 jul22** (64 sides) | top-10 jul21 (34 sides) | **OURS H1** (120 sides) | OURS H3 v1-alone | gap |
|---|---|---|---|---|---|
| **ABILITY taken when available** | **36.3%** (438/1207) | 32.9% (243/738) | **16.8%** (192/1142) | 19.0% | **−19.5 pts** ⚠️ |
| **Raging Curse taken/available** | **61.9%** (39/63) | 50.0% (29/58) | **22.0%** (29/132) | 27.0% | **−39.9 pts** ⚠️ |
| **ATTACH to bench (vs active)** | **56.3%** (246/437) | 61.6% (149/242) | **37.5%** (348/929) | 4.7% | **−18.8 pts** ⚠️ |
| EVOLVE taken when available | 61.9% (490/791) | 53.7% (253/471) | 50.7% (703/1387) | 73.3% | −11.2 pts |
| PowerWeight played when in hand | 37.3% (107/287) | 36.5% (58/159) | 30.1% (197/654) | 22.3% | −7.2 pts |
| ATTACK taken when available | 18.4% (293/1591) | 17.0% (156/920) | **28.3%** (670/2369) | 33.9% | **+9.9 pts** |
| RETREAT taken when available | 7.9% | 7.9% | 9.7% | 9.5% | +1.8 |
| Corkscrew Dive taken/available | 14.2% (135/954) | 14.0% (79/565) | 27.0% (352/1304) | 30.5% | **+12.8 pts** |
| Draconic Buster taken/available | 36.7% (44/120) | 20.9% (23/110) | 40.1% (120/299) | 57.1% | +3.4 |
| both attacks legal → Buster : Dive | **44 : 6** | 23 : 8 | **120 : 17** | 137 : 0 | ✅ matches |
| first evolution turn (median) | **3** | 4 | 4 | 4 | −1 |
| first attack turn (median) | 4 | 4 | 5 | 3 | −1 |
| bench size at T3 (median) | 2 | 1 | 2 | 2 | ✅ matches |

## ⚠️ ~~The headline finding reframes the whole target~~ — **RETRACTED, see §A1**

> **This subsection is wrong and is superseded by [§A1](#a1-my-per-decision-headline-was-wrong-retracted).**
> It is computed per DECISION. Per TURN — the standing unit — the comparison
> **reverses**: we attack on 50.5% of attack-legal turns against the top-10's
> 74.6%. The "setup speed, not attack willingness" attribution below does not
> survive: willingness is ~59% of the gap, capability ~28%. Kept in place
> unedited as the record of the error.

**At decision level we attack MORE often than the top-10, not less** — 28.3% vs
18.4% when an attack is legal. That is the opposite of the per-turn gap
(attack-when-legal 50.5% vs field 86–92%).

Both are correct; they measure different things. The reconciliation:

| | top-10 jul22 | OURS H1 |
|---|---|---|
| fraction of MAIN decisions where an attack is legal | **55.6%** (1591/2862) | **47.1%** (2369/5032) |
| attack-legal decisions per side | **24.9** | 19.7 |

**They are attack-capable on a materially larger share of their decisions.** The
gap is not attack *willingness* — it is how fast and how reliably they reach a
board state where attacking is possible. Every earlier intervention (cap=16,
END-veto, A-INCLUDE, A-WEIGHT) tried to make the agent *choose* attacks more
often. **That was the wrong target, and it is consistent with all six failing.**

*Unit caution: these per-decision rates are not comparable to the per-turn
attack-when-legal figure, because one turn contains several MAIN decisions and
some ATTACK selections resolve through sub-selections. Both columns here are
computed identically, so the comparison is valid; the absolute values are not
the per-turn metric.*

## Rules with n ≥ 20 that the data supports

| # | rule | evidence |
|---|---|---|
| **S1-a** | **Use a deck-search ability the turn it is available.** Top-10 36.3%, ours 16.8%. Their ability *availability* is also 2× ours per side (18.9 vs 9.5), so it compounds: using Champion's Call fetches the next Cynthia's Pokémon, which benches another Gabite, which offers another Champion's Call. | n=1207 / 1142 |
| **S1-b** | **Attack with Raging Curse once the bench carries counters.** Top-10 61.9%, ours 22.0%. | n=63 / 132 |
| **S1-c** | **Attach energy to the bench, not reflexively to the active.** Top-10 put 56–62% of attachments on the bench; we put 37.5% (H1) and 4.7% (v1-alone). Garchomp ex has `retreatCost = 0`, so a bench-built attacker promotes for free — building on the bench costs nothing. | n=437 / 929 |
| **S1-d** | **Evolve on sight.** Top-10 61.9% vs our 50.7%, first evolution T3 vs our T4. | n=791 / 1387 |
| **S1-e** | **Prefer Draconic Buster when both attacks are legal.** Top-10 44:6, ours 120:17. **We already match this — no change needed.** | n=120 / 299 |

---

# STEP 2 — published claims vs `card_data.json`

Verified against `skills[]` and `attacks[]`, and against the actual deck list
(`metaC_garchomp_nasuo.csv`, 60 cards / 20 unique).

| published claim | `card_data.json` | in deck? | verdict |
|---|---|---|---|
| Draconic Buster scales off counters on our own benched Cynthia's Pokémon | 260 flat, `"Discard all Energy from this Pokémon."` | 3× Garchomp ex | ❌ **REFUTED** |
| Cynthia's Gabite / **Champion's Call** — deck-search for a Cynthia's Pokémon | `"Once during your turn, you may search your deck for a Cynthia's Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."` | **4× Gabite (380)** | ✅ **CONFIRMED** — free tutor, once/turn |
| Cynthia's Roserade / **Cheer On to Glory** — +30 damage | `"Attacks used by your Cynthia's Pokémon do 30 more damage to your opponent's Active Pokémon"` | **3× Roserade (342)** | ✅ **CONFIRMED** (name is "Cheer On to Glory", not "Cheer on the Glory") |
| Corkscrew Dive — 100 dmg for one Basic Fighting Energy + draw to six | `damage 100, energies [6], "You may draw cards until you have 6 cards in your hand."` | 3× Garchomp ex | ✅ **CONFIRMED** |
| Garchomp ex free retreat | `retreatCost: 0`, hp 330, stage2 | 3× | ✅ **CONFIRMED** |
| Cynthia's Power Weight — +HP tool | `cardType 2` (`CT_TOOL`), `"gets +70 HP"` | **3×** | ✅ **CONFIRMED** |
| Turn-1: multiple Basics down, Trainers low priority | not a card claim | Basics: 4× Gible, 4× Roselia, 2× Spiritomb | ⚠️ see S1-c/S3-R4 |

### Discrepancies found

1. **Draconic Buster** — the headline claim, refuted (§ STEP 0).
2. **Ability name** — "Cheer **On to** Glory", not "Cheer on the Glory". Cosmetic.
3. **Power Weight is a TOOL, not an Item** — `cardType 2` = `CT_TOOL`. It is
   scored at `WEIGHT_ATTACH_TOOL = 2100`, not `WEIGHT_PLAY_ITEM = 2400`. Any
   rule written against "Item" would silently miss it.
4. **Roserade's +30 aura is nowhere in our eval.** Grep confirms the only
   card-specific strings in the whole scorer are `"riptide"` and `"hammer"`.
   Roserade is benched at the generic `WEIGHT_BENCH = 2300` and protected at
   nothing.

### Contra-indicated by replay evidence

**Corkscrew Dive is NOT underpriced.** The card text is accurate, but the
top-10 take it on only **14.2%** of the decisions where it is legal, versus our
**27.0%** — they decline it roughly twice as often, and when both attacks are
legal they choose Buster 44:6. Raising its score would push us *further* from
the field. **This proposal is rejected on our own evidence.**

---

# STEP 3 — ranked proposals. **NOTHING BUILT.**

Every rule goes in the **always-active** path (`_score_main` /
`_score_option` / `_attack_damage_est`) — **never inside `_pilot_score_main`**,
which is dead code in every shipped bundle because `bake_ship_config()` never
bakes `PTCG_PILOT`.

| rank | rule | evidence | mechanism | expected effect | blast radius |
|---|---|---|---|---|---|
| **1** | **R1 — Deck-search abilities outrank setup** | **BOTH** (replay n=1207 @ 36.3% vs 16.8%; card text confirms tutor) | Classify abilities from `skills[].text` matching `"search your deck"`; score those above `WEIGHT_PLAY_ITEM` instead of the flat `WEIGHT_ABILITY = 2060`. Text-driven, not a card-id hardcode. | ABILITY uptake 16.8% → ~35%; more Cynthia's Pokémon in hand → faster bench → **first evolution 4.67 → ~4.0**, more attack-capable turns | **Medium.** All ABILITY options; only lifts search abilities. |
| **2** | **R2 — Attach to the evolving bench line** | **replay, strong** (n=437 vs 929, 56–62% vs 37.5%) | Cut `ACTIVE_TARGET_BONUS = 100` on ATTACH only, and raise `POWERING_UP_BONUS` for a bench Pokémon whose evolution completes an ex. Garchomp ex's `retreatCost = 0` makes bench-building free. | attack-legal share of decisions 47.1% → toward 55.6%; **the headline gap** | **Large.** Every ATTACH decision — the 2nd most common action (17.4%). |
| **3** | **R3 — Score Raging Curse's real damage** | **BOTH** (card text explicit; replay n=63 @ 61.9% vs 22.0%; 39 declines / 3770 dmg foregone) | In `_attack_damage_est`, compute `10 × counters on our benched Cynthia's Pokémon` for attack 540. **A new, narrowly-scoped rule — NOT re-enabling `EVAL_FIX`**, which stays off and killed. Single attack id, single verifiable condition. | Raging Curse uptake 22% → ~55%; small absolute (2 copies, 0.8 chances/game) | **Tiny.** One attack id. |
| **4** | **R4 — Turn 1–2 basic development first** | **BOTH** (18 ENDs holding a playable Basic-searcher; 2 turn-2 board-wipe losses; field bench@T3 matches but our T1–2 does not) | On turns ≤ 2 with `bench < benchMax`, lift Basic-searchers (Buddy-Buddy Poffin, Nest Ball…) and Basic Pokémon plays above Supporters/Stadiums. | removes the board-wipe loss mode; supports first-evolution and attack-capability | **Medium**, but turn-gated to ≤ 2. |
| **5** | **R5 — Represent Roserade's +30 aura** | **card text only** ⚠️ *no direct replay rule at n ≥ 20* | Add +30 to `_attack_damage_est` when a Cynthia's Roserade is on our bench; and raise benching Roserade above generic `WEIGHT_BENCH`. | corrects every Cynthia attack's damage estimate by +30 | **Medium** — touches all attack scoring. |
| — | ~~R6 — reprice Corkscrew Dive~~ | ❌ **contra-indicated** | — | would move us away from the field | **rejected** |

## Recommended first arm — R1 + R2 + R3

Three rules, chosen so the arm is interpretable:

- **R1** and **R3** are supported by *both* sources and have small-to-medium
  blast radius.
- **R2** is the one that targets the headline gap (attack-capability, not
  attack-willingness) and is the only rule with a plausible large effect.
- **R4** is held back for arm 2: it overlaps R2's mechanism (both accelerate
  board development), so bundling them makes attribution impossible.
- **R5** is held back because it is web-derived on the *behavioural* side, and
  because it changes every attack estimate — too large to debut alongside R2.

---

# MEASUREMENT PLAN — **stated, not run**

### Arms

| arm | config |
|---|---|
| **B0** | v1-alone baseline (`PTCG_SEARCH=0`), `PILOT=""` — **ship config** |
| **B1** | v1-alone + R1 + R2 + R3 |
| **B2** | search on (`SEARCH_CAP=0`) + R1 + R2 + R3 |
| *(reference)* | H1 / H3 existing 60-game runs |

**Every arm runs `PILOT=""`.** Prior arms used `PILOT="garchomp"`, which no
bundle has ever shipped; those baselines are re-run rather than reused.

≥ 60 self-play games per arm, Garchomp deck, `behavioral_profile_jul21.py`
units for field-comparable rows and `horizon_counters.py` for decision rows.

### PRE-REGISTERED BANDS — fixed before any arm runs

**Primary counter: attack-when-legal (per TURN).** Baseline to beat is
**B0 measured fresh at `PILOT=""`**, not H1's 50.5% (different config).

| band | verdict |
|---|---|
| **≥ +12 pts over B0**, no other counter regressing > 5 pts | **PASS** |
| +5 to +12 pts | **MARGINAL** |
| **< +5 pts** | **FAIL** |

**Secondary, reported against the field bands:**

| counter | field | H1 today |
|---|---|---|
| first attack turn | **4.1 – 5.6** | 6.52 |
| first evolution turn | **3.6 – 4.2** | 4.67 |
| extra draws / turn | **2.1 – 2.6** | 1.34 |
| attack share / own turn | **0.47 – 0.64** | 0.31 |

**Mechanism counters (must move, or the rule did not fire):** ABILITY uptake
(R1), bench-attach share (R2), Raging Curse uptake (R3).

**Suspect flag, carried over:** any arm improving attack-when-legal while
pushing **first attack later** is flagged, not shipped.

**Bands are not revised after results.**

### Ship verification — additional, mandatory

Beyond the five standard checks: **extract the built tarball and confirm each
rule is live under `PILOT=""`**, by asserting the new scoring branches are
reachable in the exec-loaded bundle. This is the specific failure that made the
A-WEIGHT arm unshippable, and it is now a gate.

---

## Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/step0_probe.py` | STEP 0 corrected measurement |
| `stage4/rl_ours/mine_pilot_rules.py` | STEP 1 replay miner (team- and archetype-filtered) |

---
---

# AMENDMENT — unit correction, and the build

Appended 2026-07-27. **Nothing submitted.**

## A1. My per-decision headline was WRONG. Retracted.

The earlier claim — *"at decision level we attack MORE often than the top-10,
28.3% vs 18.4%"* — was computed **per MAIN decision**. Recomputed **per own
turn**, the project's standing unit, using the `visualize` TurnStart/Attack
transcript (the same source `horizon_counters.py` uses):

| | sides | **own turns / game** | total game turns | **attack-share / own turn** | **attack-when-legal / own turn** | attack-legal turns / own turns | prizes / game | **turn of first prize** |
|---|---|---|---|---|---|---|---|---|
| **TOP-10 jul22** (junlee789, Yudai Ueno) | 64 | **6.5** | 12.8 | **55.3%** | **74.6%** | **74.2%** | 3.06 | **7.2** |
| **TOP-10 jul21** (same two) | 34 | **6.4** | 12.9 | **59.4%** | **76.0%** | **78.1%** | 3.32 | 8.0 |
| OURS H1 self-play | 120 | 11.3 | 22.6 | 30.7% | 50.5% | 60.6% | 2.72 | 12.6 |
| OURS H3 v1-alone | 120 | 11.3 | 22.7 | 31.0% | 49.7% | 62.3% | 2.75 | 11.5 |
| **OURS VN ladder** (real games) | 25 | **9.2** | 18.4 | 27.3% | 50.4% | 54.1% | 2.20 | 11.3 |

**Per turn we attack far LESS, not more: 50.5% vs 74.6%.** The per-decision
comparison inverted the sign of the real gap. It is retracted; the table above
supersedes it.

### Does "setup speed, not attack willingness" survive? — **No. Not as stated.**

`attack-share/turn = attack-when-legal x attack-legal-share`. Decomposing the
24.6-point gap (55.3% vs 30.7%):

| counterfactual | attack-share | share of gap closed |
|---|---|---|
| our willingness, **their** capability (0.505 x 0.742) | 37.5% | **+6.9 pts — 28%** |
| **their** willingness, our capability (0.746 x 0.606) | 45.2% | **+14.6 pts — 59%** |
| interaction | — | ~13% |

**Attack willingness is the larger factor (~59%), not setup speed (~28%).** My
conclusion is wrong on the attribution and I am withdrawing it. Both factors are
real — capability is a genuine 60.6% vs 74.2% gap — but I ranked them backwards.

### What the correction does confirm, and more strongly

**Turns-to-win is the dominant structural difference.** Top-10 finish in **6.5
own turns**; we take **11.3** in self-play and **9.2** on real ladder — and take
our first prize at **T12.6 vs their T7.2**, five turns later. Their prize count
per game (3.06) is barely above ours (2.72); they simply get there in half the
turns. The back-of-envelope estimate (~8 vs ~18) was directionally right;
measured is 6.5 vs 11.3, a **1.74x** ratio.

*Confound, stated: our self-play is a mirror, theirs is real ladder. The VN
ladder row controls for it — 9.2 own turns against real opponents, still far
above 6.5. The finding survives.*

**This makes `own turns per game` the counter to watch**, and it is added as a
reported secondary for every arm below.

---

## A2. Build — R1 + R2 + R3

All three sit in the **always-active** path and are default-off:

| rule | function touched | flag |
|---|---|---|
| **R1** search abilities outrank setup | `_score_main`, `OT_ABILITY` branch | `PTCG_CARD_R1` |
| **R2** attach to the evolving bench line | `_attach_target_score` | `PTCG_CARD_R2` |
| **R3** Raging Curse real damage | `_attack_damage_est` | `PTCG_CARD_R3` |

None is inside `_pilot_score_main`. `EVAL_FIX` remains off and untouched — R3 is
a separate branch keyed on the attack name, mirroring the existing
`"riptide"` / `"hammer"` handling.

### Unit tests

`_is_search_ability` reads `skills[].text` for `"search your deck"` + `"hand"`,
so it generalises rather than hardcoding a card id:

| card | classified as search ability |
|---|---|
| **Cynthia's Gabite** | **True** |
| Roserade / Garchomp ex / Spiritomb / Roselia | False |

`_can_evolve_further` (R2) against our actual `DECK`:

| Gible | Gabite | Roselia | Garchomp ex | Roserade | Spiritomb |
|---|---|---|---|---|---|
| True | True | True | False | False | False |

R3 arithmetic, bench = Gabite -40 hp, Roserade -30 hp, Roselia full → 4+3+0 = 7
counters:

| | damage | v1 attack score |
|---|---|---|
| R3 **off** | 0 | **1000** (the floor) |
| R3 **on** | **70** | 1035 |

### Arms — `PILOT=""` throughout, B0 measured fresh

`B2C` (search, no rules) was added because without it `B2` vs `B0` would
conflate the search layer with the rules.

## A3. Results — v1-alone arms (60 games / 120 sides each)

| arm | rules | **attack-when-legal** | delta vs B0 (95% CI) | band | attack-share | **first attack** | **own turns/game** | first prize | prizes/game |
|---|---|---|---|---|---|---|---|---|---|
| **B0** | none | 51.6% | — | — | 0.31 | **5.19** in band | **10.3** | 10.8 | 2.66 |
| **B1a** | R1 | 53.8% | +2.2 [-2.8, +7.2] | **FAIL** | 0.32 | **5.14** in band | 11.6 | 11.7 | 2.82 |
| **B1b** | R2 | **59.1%** | **+7.5 [+2.5, +12.5]** | **MARGINAL** | 0.37 | 6.19 | **10.5** | **10.9** | **2.98** |
| **B1c** | R3 | 53.9% | +2.3 [-2.8, +7.5] | **FAIL** | 0.33 | **4.94** in band | **10.0** | **10.3** | 2.56 |
| **B1** | **R1+R2+R3** | **59.9%** | **+8.3 [+3.4, +13.2]** | **MARGINAL** | 0.38 | **7.68** ⚠️ | **11.8** ⚠️ | **12.8** ⚠️ | 3.10 |

*(field bands: attack-share 0.47–0.64, first attack 4.1–5.6, first evolution
3.6–4.2, extra draws 2.1–2.6)*

### Verdict on the pre-registered arm B1: **MARGINAL, and the suspect flag FIRES. Do not ship.**

Primary counter +8.3 pts, statistically significant, lands in the pre-registered
**MARGINAL** band (+5 to +12). But the header rule states:

> an arm that improves attack-when-legal while pushing first attack **later** is
> suspect and must be flagged.

**B1 pushes first attack from 5.19 to 7.68 — 2.5 turns later, and out of a field
band B0 was already inside.** It also regresses both turns counters: own turns
10.3 → 11.8, first prize 10.8 → 12.8. Against the A1 finding that turns-to-win
is the dominant gap, an arm that lengthens our games is moving the wrong way.

### Two findings from the ablation

**1. B0 — plain v1-alone at ship config — is already inside the field's
first-attack band (5.19 vs 4.1–5.6).** No arm we have built beats it there
except B1c. This is the first time B0 has been measured at `PILOT=""`, and it is
a better baseline than the H1 numbers we have been quoting.

**2. R2 alone accounts for essentially all of B1's gain, without the damage.**
B1b reaches 59.1% against B1's 59.9% — 0.8 pts short — while keeping own turns
at 10.5 (vs 11.8), first prize at 10.9 (vs 12.8), first attack at 6.19 (vs
7.68), and taking **more** prizes than any other v1-alone arm (2.98).

**R1 is the delay.** Alone it is not significant (+2.2, CI spans 0) yet it costs
1.3 extra own turns and pushes first prize back 0.9 turns — it adds development
actions that lengthen the game without converting. In the bundle it is what
drags first attack to 7.68. This is exactly the trap A1 identified: optimising a
per-decision uptake counter (ABILITY 16.8% → 36.3%) while the per-turn clock
gets worse.

**R3 is small, clean, and directionally right**: not significant on the primary
(+2.3), but it produces **the best first-attack (4.94) and the best own-turns
(10.0) of any arm**, because pricing Raging Curse correctly lets the agent
attack instead of continuing to develop. Its ceiling is limited by Spiritomb
being a 2-card line.

### Discipline note

**B1b is not hereby promoted.** Selecting it after seeing the results is exactly
the post-hoc goalpost-moving that pre-registration exists to prevent, and I was
corrected on this before ("a redesigned rule is a different variable, not a
retry of the same one"). B1b is a **candidate for a new pre-registered arm**,
with `own turns per game` and `turn of first prize` promoted to primary
alongside attack-when-legal. That is a decision for you, not a verdict I record
here.

## A4. Results — search arms, and the full four-arm table

`B2C` is search with **no** rules; `B2` is search **with** R1+R2+R3. Without
B2C, `B2` vs `B0` would conflate the search layer with the rules.

| arm | config | **attack-when-legal** | delta vs B0 (95% CI) | **band** | attack-share | **first attack** | **own turns/game** | **turn of first prize** | prizes/game | median deliberation |
|---|---|---|---|---|---|---|---|---|---|---|
| **B0** | v1 alone | 51.6% | — | — | 0.31 | **5.19** in band | **10.3** | **10.8** | 2.66 | 0.09 ms |
| **B1** | v1 + R1R2R3 | **59.9%** | **+8.3 [+3.4, +13.2]** sig | **MARGINAL** | 0.38 | 7.68 | 11.8 | 12.8 | **3.10** | 0.09 ms |
| **B2C** | search, no rules | 56.0% | +4.4 [−0.6, +9.4] ns | **FAIL** | 0.36 | 7.11 | 10.5 | 11.1 | 2.69 | 524 ms |
| **B2** | search + R1R2R3 | 53.6% | +2.0 [−2.9, +7.0] ns | **FAIL** | 0.32 | 7.91 | **12.0** | **13.8** | 2.91 | 528 ms |
| *field* | top-10 | *74.6%* | — | — | *0.47–0.64* | *4.1–5.6* | ***6.5*** | ***7.2*** | *3.06* | *38–633 ms* |

### The rules do not transfer to the search configuration

**B2 − B2C = −2.4 pts [−7.2, +2.5].** Not significant, but the point estimate
is negative and every timing counter is worse: first attack 7.11 → 7.91, own
turns 10.5 → 12.0, first prize 11.1 → 13.8. The rules help v1-alone and mildly
hurt the search config.

That is the third time a change has behaved differently under search than under
v1 alone. The search re-ranks the top-4 by rollout value, so lifting an option's
v1 score changes which options it *considers* but not what it *believes about
them* — and its beliefs are what HORIZON_TEST.md and CANDIDATE_SET.md already
identified as the defect.

## A5. VERDICT — **no arm ships**

| arm | primary band | suspect flag | ship? |
|---|---|---|---|
| **B1** (pre-registered arm) | **MARGINAL** (+8.3, sig) | ⚠️ **FIRED** — first attack 5.19 → 7.68 | **no** |
| B2C | FAIL (+4.4, ns) | — | no |
| B2 | FAIL (+2.0, ns) | ⚠️ **FIRED** — 7.91, worst of all arms | no |

**B1 is the only arm to clear the MARGINAL floor, and it trips the suspect flag
hard.** It pushes first attack out of a field band that B0 was already inside,
and lengthens the game on both turn counters — against the A1 finding that
turns-to-win is the dominant gap. Per the pre-registered rules, it does not
ship.

**Reported honestly: nothing here reached PASS.** Seven interventions have now
been measured (cap=16, END-veto, A-INCLUDE, A-WEIGHT, R1, R2, R3) and none has
cleared its pre-registered band.

### The one arm that looks right is not claimable

**B1b (R2 alone)** reaches 59.1% while holding own turns at 10.5 and first prize
at 10.9, and takes more prizes than any other v1-alone arm (2.98). It was found
by ablation *after* the bands were set, so promoting it now would be exactly the
post-hoc selection pre-registration exists to prevent. It is a **candidate for a
new pre-registered arm**, not a result.

If that arm is run, the bands should change to reflect A1: **`own turns per
game` and `turn of first prize` become primary alongside attack-when-legal**,
because an arm can now be seen to improve attack uptake while making the game
longer, and the longer game is what actually loses.

---

## A6. SHIP VERIFICATION — the gate that would have caught A-WEIGHT

**A defect was found and fixed here, and it is the important outcome of this
section.** `bake_ship_config()` did not know about `CARD_R1/R2/R3`, so a bundle
built before this change would have shipped with **all three rules OFF** — the
A-WEIGHT failure repeating exactly. `tools/build_search_submission.py` now takes
`--card-rules r1,r2,r3` and bakes each flag's default from `"0"` to `"1"`.

Bundle built and gated:

| field | value |
|---|---|
| path | `dist/cardrules/cardrules_r123.tar.gz` |
| **sha256** | `c3186f4e43b473e85ade8a1488d938a091ea4cc24b2df295dd3a38ffb42239f0` |
| size / members | 2.12 MiB / 14 |
| `AGENT_VERSION` | `ptcg-search-cardrules-r123` |
| builder stages | **6/6** — exec-load OK, no-cg fallback OK, 20-game smoke 0 crash 0 fallback, decision max 3122 ms |

### The gate — extracted tarball, exec-loaded, `PILOT=""`

| check | result |
|---|---|
| `CARD_R1_SEARCH_ABILITY` in extracted `main.py` | **True** |
| `CARD_R2_BENCH_ATTACH` | **True** |
| `CARD_R3_RAGING_CURSE` | **True** |
| `PILOT` | **`""`** — the ship value |

Flags alone are not proof, so each rule was also **fired** inside the extracted
bundle at `PILOT=""`:

| rule | probe | result |
|---|---|---|
| **R1** | `_is_search_ability(380)` | **True** |
| **R1** | live `_score_option` on Gabite's ability | **2900.0** (2060 would mean dead) |
| **R2** | `_can_evolve_further(379)` | **True** |
| **R3** | `_attack_damage_est(540)` with 7 bench counters | **70.0** (0.0 would mean dead) |

**SHIP GATE: PASS — every rule is live in the shipped artifact.**

This gate is now reusable and should run on every future bundle. Had it existed
before END_VETO.md, it would have caught A-WEIGHT being unreachable before 60
games were spent measuring it.

---

## A7. Summary

| # | item | outcome |
|---|---|---|
| 1 | per-decision headline | **retracted** — per turn we attack 50.5% vs 74.6%, the opposite of what I reported |
| 2 | "setup speed not willingness" | **withdrawn** — willingness ~59% of the gap, capability ~28% |
| 3 | turns-to-win | **confirmed and strengthened** — 6.5 own turns vs our 11.3 (self-play) / 9.2 (ladder); first prize T7.2 vs T12.6 |
| 4 | B1 (R1+R2+R3) | **MARGINAL, suspect flag fired — no ship** |
| 5 | B2C / B2 | **FAIL**; rules are −2.4 pts under search |
| 6 | B0 at ship config | first attack **5.19, inside the field band** — a better baseline than the H1 figures previously quoted |
| 7 | builder could not ship these rules at all | **found and fixed** (`--card-rules`) |
| 8 | ship gate | **PASS**, and now reusable |

Governor untouched. `cap=16`, `END_VETO`, `EVAL_FIX`, `PROMOTE_RULE`,
`LETHAL_PROBE` and the candidate-set arms all remain off. All three card rules
remain **default-off** in the repo. **Nothing submitted.**

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/perturn_compare.py` | per-turn / own-turns / prize analyser |
| `stage4/rl_ours/mine_pilot_rules.py` | per-decision replay miner |
| `stage4/rl_ours/step0_probe.py` | STEP 0 measurement |
| `scratchpad/s3/horizon_B{0,1,1a,1b,1c,2C,2}/` | 60 games per arm |
| `dist/cardrules/cardrules_r123.tar.gz` | gated bundle (not submitted) |
