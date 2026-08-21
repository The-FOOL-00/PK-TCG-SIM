# Official Kaggle dataset vs what we have been using

**Report only. Nothing built, nothing changed, nothing submitted.**

All three reference artifacts **are present on disk** in the repo root:

| artifact | path | size | dated |
|---|---|---|---|
| `EN_Card_Data.csv` | `./EN_Card_Data.csv` | 359 KB | Jul 7 10:04 |
| Card ID list (PDF) | `./Card_ID List_EN.pdf` *(space, not underscore)* | 137.7 MB | Jul 7 10:04 |
| reference engine | `./ptcg_engine/ptcgProgram 22/` | 45 files, C++ source | Jul 7 10:04 |

Also present: `JP_Card_Data.csv`, `Card_ID List_JP.pdf`. Nothing needed
downloading.

---

# 1. Card text — `EN_Card_Data.csv` vs `card_data.json` `skills[]`

**Card counts match exactly: 1267 in the CSV, 1267 in `card_data.json`.**

Checked every card referenced by R1/R2/R3 and by the SEQ ordering gates.

| card | referenced by | name | ability/attack text | damage |
|---|---|---|---|---|
| 380 Cynthia's Gabite — **Champion's Call** | R1 `_is_search_ability` | ✅ | ✅ **identical** | ✅ |
| 342 Cynthia's Roserade — **Cheer On to Glory** | R5 (proposed) | ✅ | ✅ **identical** | ✅ |
| 387 Cynthia's Spiritomb — **Raging Curse** | R3 `_attack_damage_est` | ✅ | ✅ **identical** | ⚠️ **DIFFERS** |
| 1173 **Cynthia's Power Weight** | STEP 0 §5 | ✅ | ✅ **identical** (+70 HP) | n/a |
| 381 Cynthia's Garchomp ex | R2, STEP 0 | ✅ | ✅ Corkscrew Dive / Draconic Buster | ✅ 100 / 260 |
| 379 Gible · 341 Roselia | R2 | ✅ | ✅ | ✅ |
| 648 Marnie's Grimmsnarl ex — Punk Up / Shadow Bullet | E1c/E3 threat proxy | ✅ | ✅ | ✅ 180 |
| 647 Morgrem · 646 Impidimp · 112 Munkidori · 104 Froslass · 860 Snorunt | E1c/E3, E2 | ✅ | ✅ | ✅ |

**12 of 13 cards: no discrepancy of any kind.** Every ability and Trainer text
we relied on is verbatim identical to the official CSV, including the two that
`card_data.json` only exposes inside `skills[]` (Champion's Call, Cheer On to
Glory) and the Power Weight `+70 HP` line.

## ⚠️ The one discrepancy — and it is the one R3 was built for

| | Raging Curse (attack 540) |
|---|---|
| official CSV `Damage` | **`10×`** |
| `card_data.json` `damage` | **`0`** |
| effect text | **identical in both** |

### This is systematic, not a one-off

Scanning the whole pool:

| | count |
|---|---|
| attacks whose official CSV damage is **non-numeric** (scaling, e.g. `30×`, `70×`, `120×`) | **112** |
| of those, `card_data.json` stores **`damage: 0`** | **110** |

Examples: Comet Punch `30×`, Double Hit `90×`, Cross Breaker `120×`, Slurp Slurp
`90×`, Bellowing Thunder `70×`.

**Our `_attack_score` prices all 110 of these at the `WEIGHT_ATTACK_BASE` floor
of 1000** — identical to a 0-damage whiff — because it reads the numeric field.

### Root cause, found in the engine source

`ptcg_engine/ptcgProgram 22/CreateCard.h:378-385`:

```cpp
int val = 0;
const std::string& s = at->damageText;
if (s.size() > 0) {
    if (!s.ends_with("×")) {
        val = std::stoi(s);
    }
}
at->damage = val;
```

**Any damage string ending in `×` is deliberately exported as `0`.** `Api.h`
then emits `attack.damage` straight into the JSON our `bake_card_data()`
consumes. So `card_data.json` is faithfully reproducing what the engine's API
exports — **this is not a corruption in our pipeline.**

### Crucially: the engine still deals the real damage

`CardImpl.h:4758-4766` for Spiritomb:

```cpp
.attack(540, u8"レイジングカース", …, "10×", { Colorless })
.textEn(u8"Raging Curse", u8"This attack does 10 damage for each damage counter …")
.preEffect(AttackDamageChangeDamageCounter, Me).eVal(10).targetBench()
    .targetCondition(TargetType::Cynthia)
.noTargetWeaknessOnly();
```

The scaling is implemented as a `preEffect` at resolution time. **The engine
computes the true damage; only the static `damage` field is 0.**

**This confirms R3's premise from the authoritative source.** The measured
"360-damage Raging Curse scored 1000" was a real mispricing in our estimator,
not an artifact of `card_data.json`.

### Blast radius on what we actually ship — **zero**

| deck | scaling-damage attacks it contains |
|---|---|
| **`metaG_grimmsnarl_top10.csv`** (shipped) | **0** |
| `metaC_garchomp_nasuo.csv` | 1 — Raging Curse (Spiritomb) |

**The shipped Grimmsnarl bundle is unaffected.** Its attacks — Frost Smash 60,
Mind Bend 60, Corkscrew Punch 10/60, Shadow Bullet 180, Chilly 10, Filch 0
(genuinely 0, a draw effect) — all carry numeric damage. The 110-attack
mispricing is a latent hazard for *other* decks, not a live defect in the
current agent.

---

# 2. Reference engine vs the `cg/` engine we run

**They are not the same kind of artifact, so there is no textual diff to take.**

| | `ptcg_engine/ptcgProgram 22/` | `sample_submission/…/cg/` |
|---|---|---|
| form | **C++ source** — 45 files: `.h`, `Export.cpp`, `game.sln`, `game.vcxproj` | **compiled binaries + Python bindings** |
| contents | `Api.h`, `CardImpl.h`, `CreateCard.h`, `Game.h`, `EffectProc.h`, … | `cg.dll` (1.5 MB), `libcg.so`, `libcg-arm64.so`, `libcg.dylib`, `api.py`, `game.py`, `sim.py`, `utils.py` |
| role | the reference implementation, human-readable | what the agent actually links against |

**No version string exists in either** — I grepped `Api.h` and `Export.cpp` for
`version`/`BUILD` markers and found none, and the binaries carry no exposed
version symbol. So a version equality claim cannot be made directly.

**Consistency evidence, which is what is available:**

- Both artifacts are dated **Jul 7 10:04**, the same competition drop.
- The source's `ApiAllAttack` / `ApiAllCard` JSON schema (`attackId`, `name`,
  `text`, `damage`, `energies`) **matches exactly** the shape
  `bake_card_data()` consumes from `cg.api.all_attack()` / `all_card_data()`.
- The `damage`-is-0-for-`×` behaviour predicted by `CreateCard.h` **is exactly
  what we observe** in `card_data.json` for 110 of 112 attacks. That is a
  strong behavioural match between source and binary.
- Card-count agreement: **1267 = 1267** across CSV, `card_data.json` (built
  from the binary), and therefore the source's `CardTable`.

**No behavioural difference found.** The two are consistent on every point I
could check without recompiling.

**What I did not do:** build `game.sln` and byte-compare a fresh binary against
`cg.dll`. That would be the only way to prove version equality, it requires
MSVC, and nothing in the evidence suggests a mismatch.

---

# 3. Summary of differences found

| # | difference | severity | affects the shipped agent? |
|---|---|---|---|
| 1 | **110 scaling attacks export `damage: 0`** while the CSV shows `30×`/`70×`/`120×` etc. | **systematic**, root-caused in `CreateCard.h` | **No** — 0 such attacks in the Grimmsnarl deck |
| 2 | Raging Curse specifically: CSV `10×` vs json `0` | instance of #1 | No (Garchomp deck only) |
| 3 | Ability / Trainer text for all 13 rule-referenced cards | **none — verbatim identical** | — |
| 4 | Card counts CSV vs `card_data.json` | **none — 1267 = 1267** | — |
| 5 | Reference engine vs `cg/` | none found; source vs binary, no version string in either | — |

## What this changes

**Nothing about the shipped bundle**, and nothing about any conclusion drawn so
far. Two things are now on firmer footing:

- **R3's premise is confirmed by the official source**, not just inferred from
  `card_data.json`. The engine genuinely deals `10 × counters` while exporting
  `0`.
- **`card_data.json` is faithful to the engine API.** Our card pipeline is not
  introducing errors; the `0` originates in the engine's own exporter by design.

**One latent hazard worth recording:** if any future deck contains one of the
110 scaling attacks, `_attack_score` will price it at the 1000 floor. The
generalised fix is to read `damageText` rather than `damage` — but that field is
**not exported by the API at all** (`Api.h` emits only the numeric `damage`), so
it would have to come from `EN_Card_Data.csv` at build time. That is a design
note, not a change I am making.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/official_diff.py` | the CSV-vs-json comparison |
