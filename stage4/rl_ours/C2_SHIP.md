# C2 bundle — ship verification

**Nothing submitted.** The upload is yours.

---

## FRAMING — this is not a promotion

Recorded verbatim as instructed:

> C2 (E1+E2) was DROPPED under the pre-registered screen rule and stays recorded
> as DROPPED. Nothing below claims it works. It is being built because:
> - it is not worse than C0 on any guard (velocity +0.0035, own turns +0.02,
>   attack-when-legal −0.1)
> - our slot currently holds the C0-equivalent Grimmsnarl agent at mu 463
> - self-play cannot resolve differences of this size (run-to-run noise
>   0.019–0.025 at n=200); ladder is a different instrument
> - the upload displaces mu 392 / 463, not v2.2.0, so there is no downside

---

## ⚠️ BUILDER CHECK — the unbaked-flag failure, **fourth occurrence**

`bake_ship_config()` did **not** know about `PTCG_SEQ_E1` / `PTCG_SEQ_E2`.
A bundle built before this fix would have shipped **both gates dead** — the
A-WEIGHT failure repeating exactly.

**Fixed:** the builder now takes `--seq-rules e1,e2,e3,e4,e1b,e1c` and rewrites
each flag's default from `"0"` to `"1"`, alongside the `--card-rules` mechanism
added for R1/R2/R3.

**Running tally of flags that would have shipped inert:**

| # | flag | caught by |
|---|---|---|
| 1 | `PILOT` (never baked at all) | RESTORE_V220.md audit |
| 2 | `CAND_ATK_W` (A-WEIGHT — measured 60 games while unshippable) | PILOT_KNOWLEDGE.md §A1 |
| 3 | `CARD_R1/R2/R3` | PILOT_KNOWLEDGE.md §A6 |
| 4 | **`SEQ_E1/E2`** | **this build** |

The A6 extraction gate exists because of #1–#2 and has now caught #3 and #4
before upload. It should stay mandatory on every bundle.

---

## BUNDLE IDENTITY

| field | value |
|---|---|
| path | `dist/c2/v1_grimm_seq_e1e2.tar.gz` |
| **sha256** | **`c6c03ddd3154f7a1fb1acedac7e204720ba255058e7cab8d3b884345b779b272`** |
| size / **members** | 0.134 MiB / **3** (`main.py`, `deck.csv`, `card_data.json`) |
| **`AGENT_VERSION`** | **`ptcg-v1-grimm-seq-e1e2`** |
| deck | `metaG_grimmsnarl_top10.csv` (top-10 list #1) |
| config | v1-alone, `SEQ_E1=1`, `SEQ_E2=1`, everything else off |

Builder stages **6/6**:

```
[1/6] metaG_grimmsnarl_top10.csv valid (60 cards, 19 unique)
[2/6] bundle assembled: ['main.py','deck.csv','card_data.json']   (no cg/, no weights)
[3/6] exec-load check OK (EXEC-CHECK-V1-OK deck=60 energy=10)
[4/6] no-card_data fallback OK
[5/6] SMOKE-OK 30 games 0 crash 0 fallback  decision p50 0ms p90 0ms p99 0ms max 1ms
[6/6] 0.13 MiB, 3 members
```

---

## CHECK 1 — diff vs the shipped `v1_grimmsnarl` bundle

Every changed line, categorised. The shipped bundle predates the ordering-gate
code entirely, so the diff carries the whole new block.

| lines | change | category |
|---|---|---|
| 28 | `AGENT_VERSION` `ptcg-v1-grimmsnarl` → `ptcg-v1-grimm-seq-e1e2` | identity |
| 204–232 | new flag block: `SEQ_E1..E4`, `SEQ_E1B_LETHAL`, `SEQ_E1C_DOOMED`, `E1_MAX_VETO=12`, `_SEQ`, `DEVELOP_TYPES` + comment header | **new config** |
| 2695–2778 | new `_seq_gate()` function | **new behaviour** |
| 2999–3006 | hook: `if SEQ_E1 or SEQ_E2 or SEQ_E3: result = _seq_gate(...)`, wrapped in try/except | **new behaviour** |

**Baked flag values in the new block:**

```
SEQ_E1 = os.environ.get("PTCG_SEQ_E1", "1") == "1"     <- ON
SEQ_E2 = os.environ.get("PTCG_SEQ_E2", "1") == "1"     <- ON
SEQ_E3 = os.environ.get("PTCG_SEQ_E3", "0") == "1"     <- off
SEQ_E4 = os.environ.get("PTCG_SEQ_E4", "0") == "1"     <- off
SEQ_E1B_LETHAL = ... "0" ...                            <- off
SEQ_E1C_DOOMED = ... "0" ...                            <- off
```

**No v1 scoring constant is changed.** `_seq_gate` replaces the chosen index
only; it is an option-set override, which is the specific respect in which it
differs from A-WEIGHT.

## CHECK 2 — clean-env self-play, 20 games

| | |
|---|---|
| games / agent calls | **20 / 3606** |
| `FALLBACK` | **0** |
| `Traceback` | **0** |
| `hook error` (incl. `[seq]`) | **0** |
| `SELFCHECK FAIL` | **0** |

## CHECK 3 — fault injection, all scenarios legal under E1/E2 on

| scenario | result |
|---|---|
| `cg/` engine removed | ✅ legal `[1]` |
| `card_data.json` removed | ✅ legal `[1]` |
| malformed option (unknown type, empty `current`) | ✅ legal `[1]` |
| weights removed | ✅ n/a — bundle ships none |

## CHECK 4 — wall-clock

| | local MAX | ×1.8 projection | % of 600 s bank |
|---|---|---|---|
| 20-game verification | **0.1 s** | **0.2 s** | **0.0%** |
| builder 30-game smoke, per decision | **1 ms** max | — | — |

Confirmed trivial, as expected from C1/C2's p99 of 0.007 s. The gates add a
menu scan per decision and nothing else; there is no search and no governor
engagement.

## CHECK 5 — A6 EXTRACTION GATE — **PASS**

Extracted from the tarball and exec-loaded with **cwd in a bare temp dir**
(`C:\…\Temp\tmpz1bojuz4`), not the repo root — `_find_file` checks
`os.getcwd()` before `sys.path`, and the repo root holds its own `deck.csv`.

| flag in the extracted `main.py` | value | |
|---|---|---|
| **`SEQ_E1`** | **True** | ✅ |
| **`SEQ_E2`** | **True** | ✅ |
| `SEQ_E3` / `SEQ_E4` / `SEQ_E1B` / `SEQ_E1C` | False | ✅ |
| **`PILOT`** | **`''`** | ✅ |
| `SEARCH` / `BC` / `END_VETO` / `SEARCH_CAP` | False / `''` / `''` / 0 | ✅ |
| `EVAL_FIX` / `PROMOTE_RULE` / `LETHAL_PROBE` | all False | ✅ |
| `CAND_INCLUDE_ATTACK` / `CARD_R1` / `R2` / `R3` | all False | ✅ |

| deck check | result |
|---|---|
| 60 cards | ✅ |
| matches the harvested top-10 list exactly | ✅ |
| module `DECK` == bundled `deck.csv` | ✅ |
| `TOTAL_BASIC_ENERGY` == 10 | ✅ |

### Both gates FIRED inside the extracted bundle

Flags present is not proof, so each gate was driven on **real observations
replayed from the C0 run**:

| gate | trigger state | chosen → returned | counter |
|---|---|---|---|
| **E1** | develop on menu, **no ability** (isolates E1) | `1 → [0]`, `1 → [0]`, `4 → [3]` | **`e1_veto` +3** |
| **E2** | ability on menu | `5 → [4]`, `7 → [6]`, `6 → [5]` | **`e2_veto` +3** |

**`e1_veto` = 3, `e2_veto` = 3 — both live and firing in the shipped artifact.**

*Method note, recorded because the first attempt was misleading:* my initial
probe drew both sample sets from the same scan and got identical observations,
so **E2 consumed them all and `e1_veto` read 0**. That was a test-harness flaw,
not a bundle flaw — E2 is checked before E1 by design. Re-run with E1 isolated
to menus containing a develop option and **no** ability, both counters
increment.

---

## SUMMARY

| check | result |
|---|---|
| builder bakes `PTCG_SEQ_E1/E2` | ✅ **fixed — would have shipped dead** |
| 1. diff vs shipped bundle | ✅ version + flag block + `_seq_gate` + hook; no v1 constant changed |
| 2. clean-env self-play 20 games | ✅ 0 / 0 / 0 |
| 3. fault injection | ✅ all legal |
| 4. wall-clock | ✅ 0.0% of bank |
| 5. A6 extraction gate | ✅ **PASS — E1 and E2 live AND firing** |

```
sha256   c6c03ddd3154f7a1fb1acedac7e204720ba255058e7cab8d3b884345b779b272
members  3
version  ptcg-v1-grimm-seq-e1e2
path     dist/c2/v1_grimm_seq_e1e2.tar.gz
```

**Nothing submitted.** C2 remains **DROPPED** on the screen; this bundle exists
so the ladder — a different instrument from self-play — can measure it if you
choose to spend the slot.

Two things to weigh, neither of which I am deciding:

- The screen could not distinguish C2 from C0 (+0.0035, CI spanning zero, both
  inside 0.019–0.025 run-to-run noise). **Ladder will not resolve it quickly
  either** — the current slot took 19 episodes to reach n<40.
- **C2's behavioural profile is genuinely different** even though its outcome is
  not: attack-first 42.4% → 0.1%, ability-turns 59.5% → 89.5%. If the ladder
  moves, that is the mechanism to credit; if it does not, the behavioural
  hypothesis is disconfirmed at the outcome level and that is worth knowing.
