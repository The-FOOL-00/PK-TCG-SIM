# F1 submission log — `ptcg-v1-grimm-f1`

**Nothing submitted. The upload is the user's action.** Design and mining detail
in [FETCH_MINE.md](FETCH_MINE.md).

## 1. Bundle identity

| field | value |
|---|---|
| path | `submission_v1_grimm_f1.tar.gz` |
| sha256 | `c18313d9491743385defeed1aca9b198c7d851621f77fa41f87875d62089e1c0` |
| size / members | 148 KB / 3 (`main.py`, `deck.csv`, `card_data.json`) |
| version string | `ptcg-v1-grimm-f1` |
| deck | `metaG_grimmsnarl_top10.csv` (60 cards, 19 unique, 10 energy) |
| config | v1-alone — **no engine, no weights, no search** |
| **diff vs the shipped build** | **one flag: `PTCG_FETCH_F1` 0 → 1** |

> ⚠️ The builder wrote this as `submission_v1_metaG_grimmsnarl_top10.tar.gz`,
> **overwriting the Jul-30 non-F1 bundle of the same name.** Renamed to
> `submission_v1_grimm_f1.tar.gz`. The Jul-30 artifact is gone; it is
> reproducible from the same command minus `--fetch-rules f1`.

## 2. Build verification — all six gates passed

```
[1/6] deck valid (60 cards, 19 unique)        version=ptcg-v1-grimm-f1
[2/6] bundle assembled: main.py deck.csv card_data.json
[3/6] exec-load check OK (EXEC-CHECK-V1-OK deck=60 energy=10)
[4/6] no-card_data fallback OK (loads + answers legally)
[5/6] SMOKE-OK 30 games, 0 crash, 0 fallback, p50 0ms p90 0ms p99 0ms max 1ms
[6/6] 0.14 MiB, 3 members
```

## 3. A6 extraction gate — baked defaults read back OUT of the tarball

The unbaked-flag bug has now bitten this project **seven times**. Verified by
extracting the archive and reading `main.py`, not by trusting the builder:

| line | flag | baked | expected |
|---|---|---|---|
| 28 | `AGENT_VERSION` | `ptcg-v1-grimm-f1` | ✅ |
| 123 | `SEARCH` | `"0"` | ✅ v1-only |
| 222 | `SEQ_E1` | `"1"` | ✅ |
| 223 | `SEQ_E2` | `"1"` | ✅ |
| 247 | `TARGET_T1_BOSS_PRIZE` | `"1"` | ✅ |
| 248 | `TARGET_T2_SPLASH_RATIO` | `"1"` | ✅ |
| 269 | `TARGET_T4_LETHAL` | `"0"` | ✅ **killed rule stays off** |
| 281 | **`FETCH_F1_ENERGY_FIRST`** | **`"1"`** | ✅ **the one change** |
| 1748 | F1 branch present in `_score_card` | — | ✅ |

**Two occurrences caught during this build**, both of which would have shipped
F1 dead: (6) `TARGET_T4_LETHAL`/`FETCH_F1_ENERGY_FIRST` missing from
`horizon_test.py`'s flag-application loop; (7) `fetch_rules` threaded into
`bake_ship_config` but **not passed at the call site** — the positional argument
list stopped at `ke_rules`.

## 4. Mechanism telemetry — the rule fires

**246 fires over 30 games = 8.2 per game** (~2,460 at 300 games).

For scale, both starvation deaths in this project's record: T4 fired 1.21/game
and was killed; §6's dynamic-damage rule died at 13 fires total. F1 is two orders
of magnitude clear of that failure mode.

## 5. Slot state — TO BE FILLED BY USER

> **The Kaggle last-2 rule is TEAM-level.** Two uploads by anyone on the team
> displace this. Sanjay's own uploads are what displaced v7 (μ877.8) and then
> v2 (μ807.2). **Confirm with him that he is not uploading before this goes up.**

| item | value |
|---|---|
| Team's two active submissions BEFORE upload | `[ ]` `[ ]` |
| Sanjay notified not to upload while F1 settles | `[ ]` |
| Upload date/time (UTC) | `[ ]` |
| Kaggle submission id | `[ ]` |
| Date n ≥ 40 reached | `[ ]` |
| Settled score at first read | `[ ]` |

## 6. Read rule

**No score is read, quoted, or acted on before n ≥ 40 games.** Agents enter the
pool at 600 and climb; byte-identical archives have scored **600–955** on this
ladder. A low early number is the default expectation and carries no information.
Our last canary froze at n=28 and its 439.1 is permanently uninterpretable —
that is the outcome this rule exists to prevent.

## 7. What a result means

The comparator is the shipped build, which last read **μ~700**.

- **F1 converts** → the fetch scorer was the binding defect, and the same mining
  method should be run on the remaining unmined sub-action slots (`SC_DISCARD`,
  `SC_ATTACH_TO`, `SC_REMOVE_DMG`).
- **F1 is flat** → 68.3% agreement joins AUC 0.845, top-1 69.4% and context-acc
  96.8% in the writeup's catalogue of offline proxies that read excellent and did
  not convert. That is a publishable result, not a wasted upload.

Either way this is the **first clean ladder read this project will have had** on
its own build — the local instrument was established today to inflate 2×
(0.4574 mirror vs 0.2370 ladder) with a noise floor wider than nearly every
effect ever measured here.
