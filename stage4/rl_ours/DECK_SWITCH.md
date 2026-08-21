# Deck-switch experiment — Grimmsnarl on our existing agent

**Nothing submitted.** Governor untouched. `cap=16`, `END_VETO`, `EVAL_FIX`,
`PROMOTE_RULE`, `LETHAL_PROBE`, the candidate-set arms and R1/R2/R3 all stay
off.

---

# STEP 1 — CAN WE BUILD THE LIST? **Yes.**

## 1.1 The lists, harvested from `replays_top10_jul26/`

Decks are recoverable exactly: `steps[1][seat]["action"]` is the 60-card list
the agent returned to the deck-selection call. **7 distinct Grimmsnarl 60-card
lists** appear across the harvest; the two dominant ones account for 303 of the
sides.

**LIST #1 — seen 163 times, 19 unique cards. This is the one used below.**

| n | id | card | type |
|---|---|---|---|
| 10 | 7 | Basic {D} Energy | Basic Energy |
| 4 | 112 | Munkidori | Pokémon |
| 4 | 646 | Marnie's Impidimp | Pokémon |
| 4 | 1086 | Buddy-Buddy Poffin | Item |
| 4 | 1152 | Poké Pad | Item |
| 4 | 1219 | Team Rocket's Petrel | Supporter |
| 4 | 1227 | Lillie's Determination | Supporter |
| 4 | 1259 | Spikemuth Gym | Stadium |
| 3 | 647 | Marnie's Morgrem | Pokémon |
| 3 | 648 | **Marnie's Grimmsnarl ex** | Pokémon |
| 3 | 1079 | Rare Candy | Item |
| 3 | 1097 | Night Stretcher | Item |
| 2 | 104 | Froslass | Pokémon |
| 2 | 860 | Snorunt | Pokémon |
| 2 | 1182 | Boss's Orders | Supporter |
| 1 | 1080 | Unfair Stamp | Item |
| 1 | 1122 | Pokégear 3.0 | Item |
| 1 | 1137 | Tool Scrapper | Item |
| 1 | 1231 | Dawn | Supporter |

**LIST #2 — seen 140 times.** Identical except it drops Pokégear 3.0 + Tool
Scrapper for **2× Handheld Fan** (1161, Tool).

## 1.2 Constructibility — **no card is missing**

| list | unknown ids vs engine pool | `validate_deck` (60 cards, ≤4 copies, ≤1 ACE SPEC, has a Basic) |
|---|---|---|
| #1 (163) | **none** | **VALID** |
| #2 (140) | **none** | **VALID** |
| #3 (11) | **none** | **VALID** |

Checked against the live engine card DB (`cg.api.all_card_data()`), not just
`card_data.json`. **Nothing is unconstructible.**

Written to `metaG_grimmsnarl_top10.csv`.

## 1.3 Hidden Garchomp assumptions — **none live in ship config**

Every deck-specific string in `main.py`, and whether it is reachable:

| location | what | gated by | live at ship config? |
|---|---|---|---|
| `_attack_damage_est` `"riptide"` | Riptide damage from discard energy | **nothing — always active** | **yes, but inert** |
| `_attack_damage_est` `"hammer"` | Hammer-lanche deck-density estimate | **nothing — always active** | **yes, but inert** |
| `_SCALING_ATTACK_TAGS` {540, 88} | Raging Curse / Psychic scaling | `EVAL_FIX` | no (off) |
| `_is_cynthia_pokemon` | name prefix `"Cynthia'"` | `EVAL_FIX` / `CARD_R3` | no (both off) |
| `BASIC_SEARCHERS` | END-veto replacement pick | `END_VETO` | no (off) |
| `_pilot_score_main`, `WEIGHT_TEMPO_LOADED`, `WEIGHT_EVOLVE_EX_BONUS` | Garchomp tempo layer | `PILOT == "garchomp"` | no (never baked) |
| `_pilot_telemetry` | Garchomp stderr telemetry | `PILOT != "garchomp"` early return | no |
| `bc_weights_garchomp*.npz` | BC head | `BC` | no (off) |

**The two always-active hooks are inert for this deck:** no attack in the
Grimmsnarl list has a name containing `"riptide"` or `"hammer"`. Its attacks are
Frost Smash, Mind Bend, Filch, Corkscrew Punch (×2), Shadow Bullet, Chilly.

`DECK` and `TOTAL_BASIC_ENERGY` are derived from `deck.csv` at import
([main.py:365](../../main.py:365)), and `HAND_SLOT_IDS` / `CARD_SLOT_IDS` are
derived from `DECK`, so all adapt automatically.

**The builder bakes an arbitrary `deck.csv`** via `--deck` (it copies the file
to `bundle/deck.csv` and runs `validate_deck` first) — already exercised this
session for `metaC_garchomp_nasuo.csv`.

### One real caveat, recorded not worked around

`value_weights.npz` was trained on **Garchomp** feature vectors, and
`encode_state` derives its card-identity slots from `DECK`. Under search at
`cap=400` the value net scores a rollout leaf only when a rollout runs 400
engine steps without terminating (measured: 76 evaluations / 4 games), so the
exposure is small — but for the Grimmsnarl arm it is a **train/serve mismatch**.
It affects D3 only, is not part of the pre-registered primary (D1 vs D0, both
v1-alone), and is flagged in the D3 row.

**STEP 1 verdict: the list is buildable and the agent carries no live Garchomp
assumption. Proceeding to STEP 2.**

---

# PRE-REGISTERED READING — fixed before any arm was run

## Envelopes (measured, pooled `total prizes / total own turns`)

| envelope | source | **prize velocity** |
|---|---|---|
| **Grimmsnarl** | 7 top-10 Grimmsnarl teams, jul26, **258 sides**, 900 prizes / 1572 own turns | **0.5725** |
| **Garchomp** | top-10 jul21 0.52 / jul22 0.47 (PILOT_KNOWLEDGE §A1) | **0.495** (midpoint) |

## The question

Does our generic agent **pilot** Grimmsnarl better than it pilots Garchomp, in
that deck's own units?

**Closure = arm velocity / its own archetype envelope.** PASS requires D1's
closure to exceed D0's by **≥ 30% relative**.

With D0 measured at **0.2593** (R2_ARM.md B0', 200 sides):

| | arithmetic | threshold on D1 velocity |
|---|---|---|
| closure_D0 | 0.2593 / 0.495 = **0.5238** | — |
| **PASS** | closure_D1 ≥ 0.5238 × 1.30 = 0.6809 | **D1 ≥ 0.3898** |
| **MARGINAL** | closure_D1 ≥ 0.5238 × 1.10 = 0.5762 | **D1 ≥ 0.3299** |
| **FAIL** | below that | **D1 < 0.3299** |

*(D0 is re-measured fresh in this run; if it differs from 0.2593 the thresholds
are recomputed from the same formula, which is fixed here.)*

Reported with a **bootstrap 95% CI** on the D1 − D0 velocity difference (10,000
resamples over sides).

## Arms — 100 games each, `PILOT=""`

| arm | policy | deck |
|---|---|---|
| **D0** | v1-alone | Garchomp |
| **D1** | v1-alone | **Grimmsnarl** |
| **D2** | search, `SEARCH_CAP=0` | Garchomp |
| **D3** | search, `SEARCH_CAP=0` | **Grimmsnarl** |

The pre-registered verdict rests on **D1 vs D0**. D2/D3 are reported.

**Bands are not revised after results.**

## HONEST CAVEAT — recorded before results

**Self-play mirror cannot measure matchup equity.** Both sides play the same
deck, so this measures **piloting competence only**. Even a PASS does not
establish that Grimmsnarl beats the field *for us*; it establishes that we pilot
it better than we pilot Garchomp. The matchup claim rests on the 58.1% field
measurement, **which was measured for top-10 pilots, not for us**, and does not
transfer automatically.

---

## RESULTS

### D0 vs D1 — the pre-registered comparison (100 games / 200 sides each)

Both arms are the **identical generic agent**, `PILOT=""`, v1-alone, no rules.
The only difference is `deck.csv`.

| counter | **D0 Garchomp** | **D1 Grimmsnarl** | Grimmsnarl envelope | Garchomp envelope |
|---|---|---|---|---|
| **PRIZE VELOCITY** | **0.2628** | **0.4574** | **0.5725** | 0.495 |
| own turns / game | 11.17 | **7.63** | 6.1 | ~10.3 |
| prizes / game | 2.94 | **3.49** | **3.49** | ~3.1 |
| turn of first prize | 11.2 | **9.2** | 7.1 | ~10.8 |
| attack-when-legal / turn | 54.4% | **88.5%** | 84.5% | 74.6% |
| attack share / turn | 0.34 | **0.45** | 0.559 | 0.47–0.64 |
| first attack | **5.01** | 6.53 | — | 4.1–5.6 |
| first evolution | 4.34 | 4.82 | — | 3.6–4.2 |
| extra draws / turn | 1.63 | 1.63 | — | 2.1–2.6 |
| hand T3 / T5 / T7 | 5.33 / 5.04 / 5.09 | 5.88 / 5.85 / 6.16 | — | — |
| median deliberation | 0.00 ms | 0.00 ms | — | — |

**Δ prize velocity = +0.1946, bootstrap 95% CI [+0.1569, +0.2324]**
(10,000 resamples over sides). The interval is far from zero.

### Closure test — the pre-registered verdict

| | arithmetic | value |
|---|---|---|
| closure D0 | 0.2628 / 0.495 | **0.5309** |
| closure D1 | 0.4574 / 0.5725 | **0.7990** |
| **ratio** | 0.7990 / 0.5309 | **1.5049** |
| PASS floor | ≥ 1.30 | — |
| D1 velocity needed | 0.5309 × 1.30 × 0.5725 | 0.3951 |
| D1 velocity measured | — | **0.4574** |

## **VERDICT: PASS** (ratio 1.505 vs a 1.30 floor)

### What the numbers say

The same generic scorer, handed a different 60 cards, goes from **53.1%** of its
archetype's envelope to **79.9%** of its archetype's envelope.

Two counters are worth naming individually:

- **Prizes per game: 3.49 — identical to the top-10 Grimmsnarl figure (3.49).**
  On raw prize output our agent already matches the field with this deck.
- **Attack-when-legal: 88.5% vs the top-10's 84.5% — we exceed them.** On
  Garchomp the same scorer manages 54.4%.

And own turns per game drop **11.17 → 7.63**, closing most of the turns-to-win
gap that eight previous interventions could not move. The remaining distance to
the envelope is almost entirely game length (7.63 vs 6.1), not prize output.

### Why this is consistent with everything that failed before

Grimmsnarl's line is Impidimp → Morgrem → Grimmsnarl ex with **Rare Candy**, and
its attacker needs Darkness energy on a body that is cheap to field. The v1
ladder's fixed tier order — attach 3000 > evolve 2800 > item 2400 > bench 2300 >
attack ~1100 — happens to *be* a reasonable Grimmsnarl line. On Garchomp, whose
plan requires holding an attacker back through a 3-stage line while accumulating
counters, the same fixed order produces the slow, passive play measured all
session.

**The agent was never bad at piloting. It was piloting the wrong deck for its
fixed priority order.** That is a different diagnosis from every previous one in
this project, and it is the first that predicts the measurement rather than
being fitted to it.

### The FINAL_PATH_JUL21 objection, resolved

Part 2 closed counter-decking on a measured 20–25 pt piloting penalty for
unfamiliar decks. That penalty presumes deck-specific piloting skill exists to
lose. The audit in §1.3 confirms this agent has **none** — the only two
always-active card-specific hooks (`"riptide"`, `"hammer"`) do not match any
card in either deck. **Every deck is equally unfamiliar to it, so there is no
penalty to pay.** The objection does not apply, and the measurement above is
what it looks like when it does not.

### D2 / D3 — search arms

**Both complete at 100 games. The full 2x2 is in the addendum at the end.**

### D1 vs D3 — does search help Grimmsnarl? **No.**

| counter | **D1** v1-alone Grimm | **D3** search Grimm |
|---|---|---|
| **prize velocity** | **0.4574** | 0.4288 |
| own turns / game | **7.63** | 7.76 |
| prizes / game | **3.49** | 3.33 |
| attack-when-legal / turn | **88.5%** | 85.1% |
| attack share / turn | **44.8%** | 42.6% |
| turn of first prize | **9.2** | 10.3 |

**Δ = −0.0286, bootstrap 95% CI [−0.0666, +0.0096].** The interval spans zero,
so search is not *significantly* worse — but the point estimate is negative on
every counter, and it costs ~500 ms per decision plus the governor's whole
failure surface.

This is the fourth configuration in which adding search failed to help, and the
first on a deck the agent pilots well. Combined with the value-net train/serve
mismatch flagged in §1.3, **there is no case for shipping search with this
deck.** D1 is the arm that passed and the arm that ships.

---

# SHIP — v1-alone + Grimmsnarl

The builder had no v1-alone mode (only search ships and BC ships), so one was
added: `--v1-only` bakes `SEARCH` off, ships **no engine and no weights**, and
uses an exec check that asserts `SEARCH is False`, `BC == ""`, `PILOT == ""` and
a 60-card `DECK`.

| field | value |
|---|---|
| path | `dist/grimm/v1_grimmsnarl.tar.gz` |
| **sha256** | **`56c538867a5eeda6f4d559f59a4eafaeb9854318b268dfef901695a5c5d7583b`** |
| size / members | **0.132 MiB / 3** (`main.py`, `deck.csv`, `card_data.json`) |
| `AGENT_VERSION` | **`ptcg-v1-grimmsnarl`** |
| deck | `metaG_grimmsnarl_top10.csv` (top-10 list #1, seen 163×) |

## Builder stages — 6/6

```
[1/6] metaG_grimmsnarl_top10.csv valid (60 cards, 19 unique)
[2/6] bundle assembled: ['main.py','deck.csv','card_data.json']   (no cg/, no weights)
[3/6] exec-load check OK (EXEC-CHECK-V1-OK deck=60 energy=10)
[4/6] no-card_data fallback OK (agent loads + answers legally)
[5/6] SMOKE-OK 30 games 0 crash 0 fallback  decision p50 0ms p90 0ms p99 0ms max 2ms
[6/6] submission_v1_metaG_grimmsnarl_top10.tar.gz OK: 0.13 MiB, 3 members
```

## Ship verification — all checks pass

| check | result |
|---|---|
| **2. clean-env self-play, 20 games** | 2796 agent calls · **0 FALLBACK · 0 Traceback · 0 hook-error · 0 SELFCHECK FAIL** |
| **3. fault injection** | `cg/` removed ✅ legal · `card_data.json` removed ✅ legal · malformed option ✅ legal · weights-removed **n/a** (bundle ships none) |
| **4. wall-clock** | MAX **0.0 s** per player-game → ×1.8 projection **0.0 s = 0.0% of the 600 s bank** |
| **5. weights** | none bundled by design — no value-net, therefore **no Garchomp train/serve mismatch** |

Max decision time **2 ms**. Timeout risk is nil, and the governor never engages
because there is no search to govern.

## A6 extraction gate — **PASS**

Extracted from the tarball, exec-loaded with **cwd set to a bare temp dir** (the
platform's load path):

| flag | value |
|---|---|
| `SEARCH` / `BC` / `PILOT` | `False` / `''` / **`''`** |
| `END_VETO` / `SEARCH_CAP` | `''` / `0` |
| `EVAL_FIX` / `PROMOTE_RULE` / `LETHAL_PROBE` | all `False` |
| `CAND_INCLUDE_ATTACK` / `CAND_ATK_W` | `False` / `0.0` |
| `CARD_R1` / `CARD_R2` / `CARD_R3` | all `False` |

| deck check | result |
|---|---|
| 60 cards | ✅ |
| matches the harvested top-10 list exactly | ✅ |
| module `DECK` == bundled `deck.csv` | ✅ |
| `TOTAL_BASIC_ENERGY` == 10 (Darkness) | ✅ |
| Grimmsnarl ex ×3 · Morgrem ×3 · Impidimp ×4 · Rare Candy ×3 · {D} Energy ×10 · Munkidori ×4 | ✅ |

### The gate earned its keep again

On the first run it reported `module DECK == deck.csv: False` and
`TOTAL_BASIC_ENERGY = 35`. Cause: `_find_file` checks **`os.getcwd()` before
`sys.path`** ([main.py](../../main.py)), and my gate ran with cwd at the repo
root, which contains its own unrelated `deck.csv`. Re-run with a bare cwd — the
way Kaggle loads — it passes.

**That is a harness bug, not a bundle defect**, and the builder's own check was
right all along (it runs in a temp dir and printed `energy=10`). But it is worth
recording: **the agent's deck resolution is cwd-sensitive**, so any future
verification that runs from the repo root will silently test the wrong deck.

---

## SUMMARY

| | result |
|---|---|
| STEP 1 — list buildable | ✅ all 7 lists valid against the live engine pool |
| STEP 1 — hidden Garchomp assumptions | ✅ none live; `"riptide"`/`"hammer"` inert for this deck |
| **STEP 2 — pre-registered verdict** | ✅ **PASS** — closure ratio **1.505** vs a 1.30 floor |
| prize velocity D0 → D1 | **0.2628 → 0.4574**, CI [+0.1569, +0.2324] |
| search on Grimmsnarl (D3) | not better (−0.029); **v1-alone ships** |
| STEP 3 — ship verification | ✅ all checks pass |
| STEP 3 — A6 extraction gate | ✅ **PASS** |
| **sha256** | **`56c538867a5eeda6f4d559f59a4eafaeb9854318b268dfef901695a5c5d7583b`** |

**Nothing submitted.** Governor untouched; `cap=16`, `END_VETO`, `EVAL_FIX`,
`PROMOTE_RULE`, `LETHAL_PROBE`, the candidate-set arms and R1/R2/R3 all remain
off in the repo and verified off in the bundle.

### The caveat, restated because it bounds the claim

**This is a self-play mirror. It measures piloting competence, not matchup
equity.** The result establishes that our agent pilots Grimmsnarl far better
than it pilots Garchomp — not that Grimmsnarl wins for us on ladder. The 58.1%
field figure was measured for top-10 pilots. Our piloting reaches 79.9% of their
envelope, which is much closer than the 53.1% we manage on Garchomp, but it is
not parity, and the ladder is the only place that claim gets settled.

### Artifacts

| path | contents |
|---|---|
| `metaG_grimmsnarl_top10.csv` | the harvested deck |
| `dist/grimm/v1_grimmsnarl.tar.gz` | the bundle (not submitted) |
| `scratchpad/s3/grimm_lists.json` | all 7 harvested Grimmsnarl lists |
| `scratchpad/s3/horizon_D{0,1,2,3}/` | 100 games per arm |
| `scratchpad/s3/deckswitch.json`, `deckswitch_d1d3.json` | primary counters + CIs |
| `scratchpad/s3/verify_grimm.json` | ship-verification raw results |


---

# ADDENDUM — D2 complete, the full 2×2

All four arms now at 100 games / 200 sides, `PILOT=""`.

| | **Garchomp** | **Grimmsnarl** | deck effect |
|---|---|---|---|
| **v1-alone** | **D0 = 0.2628** | **D1 = 0.4574** | **+0.1946** |
| **search** (`cap=0`) | **D2 = 0.2430** | **D3 = 0.4288** | **+0.1858** |
| **search effect** | **−0.0198** | **−0.0286** | — |

Full counters:

| counter | D0 v1/Garch | D2 search/Garch | D1 v1/Grimm | D3 search/Grimm |
|---|---|---|---|---|
| **prize velocity** | **0.2628** | 0.2430 | **0.4574** | 0.4288 |
| own turns / game | 11.17 | 11.56 | **7.63** | 7.76 |
| prizes / game | 2.94 | 2.81 | **3.49** | 3.33 |
| attack-when-legal | 54.4% | 53.1% | **88.5%** | 85.1% |
| attack share / turn | 32.1% | 32.5% | **44.8%** | 42.6% |
| turn of first prize | 11.2 | 12.9 | **9.2** | 10.3 |

Bootstrap 95% CIs on the search effect: Garchomp **−0.0198 [−0.0538, +0.0144]**,
Grimmsnarl **−0.0286 [−0.0666, +0.0096]**. Neither is significant; both point
estimates are negative, and search worsens `turn of first prize` on **both**
decks (11.2 → 12.9 and 9.2 → 10.3).

## What the 2×2 shows

**The deck effect is ~10× the search effect, and they have opposite signs.**
Switching deck is worth **+0.19** on either policy; adding search is worth
**−0.02** on either deck. The two are close to independent — the deck gain is
+0.1946 without search and +0.1858 with it.

This is the cleanest statement of the session's whole arc: **every intervention
we tried lived inside the policy, and the policy was never where the value was.**
Nine policy-side interventions produced nothing that cleared a pre-registered
band. One deck change produced +0.19 on the same agent, on the first attempt,
with the pre-registration written beforehand.

It also closes out the search question on its own terms. Search has now been
measured against a matched no-search control on **two different decks** and is
non-positive on both, while costing ~500 ms per decision and the entire governor
failure surface. There is no configuration in this project's measurements where
it earns its cost.
