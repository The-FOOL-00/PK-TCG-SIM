# Kangaskhan + KE1 bundle — ship verification

**Nothing submitted.** Bundle built; delivered to user for upload.

## Bundle

| field | value |
|---|---|
| **Path** | `dist/kang/v1_kang_ke1.tar.gz` |
| Size | 144 KB, 3 members (main.py, deck.csv, card_data.json) |
| **sha256** | `681fb6e74991517c3da25abc67248a62b72ab9a44038e3e99bda678dc5122008` |
| **AGENT_VERSION** | `ptcg-v1-kang-ke1` |
| Deck | `metaX_kangaskhan_top10.csv` (validated: 60 cards, 24 unique, 0 unknown ids) |
| Config | v1-alone, no search, no engine, no weights, `KE1_FREE_DRAW=1` baked ON |

## Builder verification (5/6)

Standard checks from `tools/build_search_submission.py`:

| # | check | result |
|---|---|---|
| 1 | deck valid | ✅ 60 cards, 24 unique, no unknown ids |
| 2 | bundle assembled | ✅ `main.py + deck.csv + card_data.json` |
| 3 | exec-load in temp cwd | ✅ `EXEC-CHECK-V1-OK deck=60 energy=16` |
| 4 | no-card_data fallback | ✅ agent loads + answers legally without card_data.json |
| 5 | smoke (20 self-play games) | ✅ `SMOKE-OK 20 games 0 crash 0 fallback  p50 0ms p90 0ms p99 0ms max 2ms` |
| 6 | tarball emitted | ✅ 0.14 MiB, 3 members |

## A6 gate — extract-in-bare-cwd re-verification

Extracted the tarball into a bare temp directory (no repo files on `os.getcwd()`
path), stripped repo paths from `sys.path`, exec-loaded main.py with no
`__file__` — the exact load conditions Kaggle uses.

| check | result |
|---|---|
| `KE1_FREE_DRAW` after bake | **True** (default flipped `"0"` → `"1"` in bundled main.py:268) |
| `AGENT_VERSION` | `ptcg-v1-kang-ke1` |
| `_has_free_draw_ability(756)` (Mega Kangaskhan) | **True** |
| `_has_free_draw_ability(112)` (Munkidori) | False (correctly excluded — damage-move ability) |
| `_has_free_draw_ability(63)` (Raging Bolt) | False |
| `_has_free_draw_ability(1071)` (Meowth ex) | False (correctly excluded — has "discard") |
| `_has_free_draw_ability(140)` (Fezandipiti) | False (correctly excluded — has "if KO'd" conditional) |
| `_ke1_veto` firing on synthetic v1-chose-ATTACK state | ✅ swaps to Ability, `STATS["ke1_veto"]=1` |

**KE1 is live and correctly narrow.** The specific rule that produced the
+7pt cross-deck gain vs Grimmsnarl is what's baked into this bundle.

## Best offline evidence supporting this bundle

From [KE12_CROSSDECK.md](KE12_CROSSDECK.md), 200 games each cross-deck vs
v1-alone Grimmsnarl opponent, seats alternated:

| arm | velocity | atk-when-legal | prizes/g | Win% vs Grimm |
|---|---|---|---|---|
| Kangaskhan v1-alone | 0.2858 | 54.8% | 2.19 | 32.0% |
| **Kangaskhan + KE1 (this bundle)** | **0.3350** | 55.9% | 2.64 | **39.0%** |

The +7pt cross-deck gain is the largest per-rule improvement measured this
whole session. Whether it translates to a specific ladder score depends on
how the actual top-10 field is composed and how top-10 pilots specifically
counter Kangaskhan — those aren't measurable offline.

## Deployment note

Uploading this bundle displaces one of the two currently-active submission
slots. Current occupants:

| id | file | current score | n episodes |
|---|---|---|---|
| 55127151 | (Sanjay's newest, ~04:37 UTC) | 721.5 | 14 (unsettled) |
| 55115606 | our T1T2 Grimmsnarl | 472.3 | ~36 (still settling) |

Displacing 55115606 (T1T2) with this bundle is the natural trade — it
occupies the "our" slot. Displacing Sanjay's fresh submission would be a
team-visible decision and not recommended.

**Nothing submitted from this workstation. User uploads.**
