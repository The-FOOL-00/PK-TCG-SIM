# Restore the v2.2.0-class baseline — build + verification

**Nothing submitted.** No upload was made or attempted.

---

## ⚠️ READ FIRST — the build spec does not describe the agent that scored 697

You asked me to confirm by diff whether this is the same agent or a
near-relative, and to flag every difference. **It is neither: the configuration
in the BUILD spec is a different agent from the one that scored μ697.**

The authoritative record is
[analysis/phase1_v2_2_0_losses/inference.md](../../analysis/phase1_v2_2_0_losses/inference.md),
written from the 56 harvested ladder replays of that submission:

> Submission **54573192** (`submission_bc_metaC_garchomp_nasuo.tar.gz`,
> v2.2.0-bc-full-garchomp), submitted 2026-07-11 13:31 UTC … Final frozen score
> **μ=682.5** (peak ~797 at game 13)

I extracted that exact tarball. Its baked configuration is:

| flag | **v2.2.0 (μ697)** | **BUILD spec in this task** |
|---|---|---|
| `AGENT_VERSION` | `ptcg-bc-v2.2.0-full-garchomp` | `ptcg-search-*` |
| **`BC`** | **`"garchomp_full"` — behaviour cloning ON** | `""` — off |
| **`SEARCH`** | **`False` — no search at all** | `True` |
| `SEARCH_CAP` | n/a (search off) | 0 |
| governor | present but inert (never runs) | active |
| bundled weights | `bc_weights_garchomp_full.npz` | `value_weights.npz` |
| `cg/` engine | **absent** (not needed) | present, 9 files |
| members | 4 | 13 |

**v2.2.0 is a behaviour-cloning agent that never runs the search.** The spec's
config — search on, 400-step rollouts, governor active, `value_weights.npz` — is
the **H1 baseline**, which has never been on the ladder. Its nearest shipped
relative is VN at μ509.

So the honest answer to your question: **not the same agent, and not a near
relative either.** They are different policies that happen to share a file.

**This does not block the restore.** The μ697 artifact is intact on disk and
byte-identical to what was submitted, so restoring it needs no rebuild at all —
a rebuild could only introduce drift. §1 verifies that artifact. §2 delivers the
bundle the BUILD spec literally asked for, correctly built and labelled.

---

## ⚠️ SECOND FINDING — `PILOT` is never baked, so no shipped search bundle has ever had the Garchomp tempo layer

`bake_ship_config()` in `tools/build_search_submission.py` substitutes exactly
`SEARCH`, `GOVERNOR`, `ROLLOUT`, `SEARCH_CAP`, `AGENT_VERSION`, `END_VETO` and
(for BC ships) `BC`. **It never touches `PILOT`.** Confirmed by grep: the string
`PILOT` does not appear in the builder at all.

Every bundle therefore ships with the module default `PILOT = ""`. Verified
directly in all three shipped tarballs:

| bundle | baked `PILOT` |
|---|---|
| `endveto_narrow_vw.tar.gz` (VN, live, μ509.2) | `""` |
| `canary_cap16.tar.gz` (μ439.1) | `""` |
| `submission_bc_metaC_garchomp_nasuo.tar.gz` (μ697) | `""` |

`_pilot_score_main` — which holds `WEIGHT_TEMPO_LOADED = 2450` — is reached only
via `if PILOT == "garchomp"` ([main.py:1537](../../main.py:1537)). **On ladder it
is dead code.**

### This invalidates part of my own CANDIDATE_SET.md measurement

Every self-play arm I ran (H1, H2, H3, VN, VB, CI, CW, CIW) set
`agent_mod.PILOT = "garchomp"`. That is **not the shipped configuration.** Two
concrete consequences, both mine to own:

**1. A-WEIGHT could never have shipped as tested.** `CAND_ATK_W` lives inside
`_pilot_score_main`. With `PILOT = ""` it is unreachable. The CW and CIW arms
measured a code path that would have been inert in any bundle built by the
current builder. Their FAIL verdict stands — but for the record, they were never
shippable in that form.

**2. The ladder exclusion rate I reported was understated.** Re-measuring the 25
VN ladder replays under the true ship config:

| scorer | exclusion | tempo hook fires | attack chosen when excluded |
|---|---|---|---|
| `PILOT="garchomp"` (what I reported) | 32.4% | 35.9% | 0/130 |
| **`PILOT=""` (what actually shipped)** | **38.2%** | **14.5%** | **0/153** |

And the 14.5% is not the tempo hook at all — it is exactly the 58 lethal
attacks, which reach 2450 via `WEIGHT_LETHAL`. **With `PILOT=""` the tempo hook
fires zero times.** The live agent scores every non-lethal attack at
1000 + dmg/2 and nothing lifts it.

The core Step 1 finding is unchanged and in fact stronger — exclusion is *worse*
on ladder than reported, and still mechanically absolute (0 of 153).

**Recommendation: decide explicitly whether `PILOT=garchomp` should be baked.**
I have not changed it — the BUILD spec does not mention `PILOT`, and baking it
would be an unrequested behaviour change to a bundle you asked to be a clean
baseline. It is a real, live decision and it is yours.

---

## 1. The true restore — v2.2.0 artifact, verified

**No rebuild.** This is the byte-identical file that scored μ697/682.5.

| field | value |
|---|---|
| path | `submission_bc_metaC_garchomp_nasuo.tar.gz` |
| **sha256** | `b9b7bca0836f2c1996749ad5b59dab36dcadd2133065cf495d189e0a59192887` |
| size / members | **0.22 MiB / 4** |
| `AGENT_VERSION` | **`ptcg-bc-v2.2.0-full-garchomp`** |
| members | `main.py`, `deck.csv`, `card_data.json`, `bc_weights_garchomp_full.npz` |
| config | `BC='garchomp_full' SEARCH=False PILOT='' SEARCH_CAP=0 END_VETO='' GOVERNOR=True` |
| original submission | **54573192**, 2026-07-11 13:31 UTC |

### Check 1 — diff vs the current tree

`main.py` in the bundle is 2438 lines; committed `HEAD` is 2518. The diff is
**86 changed lines, and every one is accounted for**:

| change | category | behaviour impact |
|---|---|---|
| `AGENT_VERSION` string | identity | none |
| `BC` default `"garchomp_full"` → `""` | ship-config default | none when re-baked |
| `BC_BRAKE` flag + `BRAKE_DRAW_ACTIONS` + `_bc_brake_mask()` added | **new feature, default off** | **none** — `if not BC_BRAKE: return None` |
| `_bc_decide` wraps `_pol_choose` in the brake mask | **new feature, default off** | **none** — mask is `None`, `else` branch is the original line |

**Behaviour changes: zero.** The BC decision path is byte-equivalent whenever
`BC_BRAKE=0`, which is the default. The uncommitted working tree adds a further
~330 lines (the killed gates, END-veto, candidate-set arms, governor telemetry)
— all default-off and all in the *search* path, which v2.2.0 never enters.

**Consequence worth stating plainly: the current `main.py` could reproduce
v2.2.0 exactly** under `BC=garchomp_full, SEARCH=0, PILOT="", BC_BRAKE=0`. The
shipped artifact is still the safer restore, because it needs no re-baking and
carries no risk of drift.

### Check 2 — clean-env self-play, 20 games

Loaded by `exec` from the bundle, no `__file__`, cwd elsewhere, bundle dir on
`sys.path` — the platform's load path, not the repo's.

| | |
|---|---|
| games / agent calls | **20 / 3691** |
| `FALLBACK` | **0** |
| `Traceback` | **0** |
| `hook error` | **0** |
| `SELFCHECK FAIL` | **0** |

### Check 3 — fault injection, four scenarios

Search-specific scenarios (begin-raises, sampler-raises, budget-zero) are
**not applicable**: v2.2.0 has no search and no engine. Substituted the four
faults that can actually occur for this bundle. All return a **legal** answer:

| scenario | result |
|---|---|
| BC weights removed | ✅ legal `[0]` — falls back to v1 |
| `cg/` removed (already absent) | ✅ legal `[0]` |
| `card_data.json` removed | ✅ legal `[0]` |
| malformed option (unknown type, empty `current`) | ✅ legal `[1]` |

### Check 4 — wall-clock

| | local MAX | **×1.8 Kaggle projection** | % of 600 s bank |
|---|---|---|---|
| v2.2.0 (20 games, 40 sides) | **0.1 s** | **0.2 s** | **0.0%** |

BC is a single forward pass — four orders of magnitude cheaper than the search
bundles (VN: 148.8 s local MAX). **Timeout risk is nil.**

### Check 5 — weights load *and* are exercised

`_bc_model()` returns a model with both heads (`head`, `head_card`) under clean
exec. Presence alone is not proof it drives decisions, so I re-ran the Phase 1
behavioural test — if BC had silently fallen back, the agent *is* v1 and
agreement with v1 would be ~1.00:

| | |
|---|---|
| multi-option MAIN decisions | 685 |
| BC model available | 685 / 685 |
| **agreement with pure v1** | **0.323** |

Phase 1 measured MAIN agreement median 0.23 on ladder. **0.323 in self-play is
consistent, and far from 1.0 — BC is genuinely driving the policy.**

**§1 verdict: ALL CHECKS PASS.**

---

## 2. The bundle the BUILD spec asked for

Built exactly to spec. **This is the H1 search baseline, not v2.2.0** — see the
warning at the top. Labelled honestly so it cannot be mistaken for the μ697
agent on the ladder.

| field | value |
|---|---|
| path | `dist/baseline/baseline_c0_vw.tar.gz` |
| **sha256** | `0512323664cadcc5b011c662e255885560311dd852b297bc2fa3fb4dffd344fd` |
| size / members | **2.12 MiB / 14** |
| `AGENT_VERSION` | **`ptcg-search-baseline-c0-vw`** |
| deck | `metaC_garchomp_nasuo.csv` (Cynthia's Garchomp) |

Every flag in the spec, verified in the baked bundle:

| spec | baked value | ✓ |
|---|---|---|
| `SEARCH_CAP=0` (400-step) | `PTCG_SEARCH_CAP` default `"0"` | ✅ |
| `END_VETO` off | `PTCG_END_VETO` default `""` | ✅ |
| `CAND_INCLUDE_ATTACK` off | default `"0"` | ✅ |
| `CAND_ATK_W` off | default `"0"` | ✅ |
| `EVAL_FIX` off | default `"0"` | ✅ |
| `PROMOTE_RULE` off | default `"0"` | ✅ |
| `LETHAL_PROBE` off | default `"0"` | ✅ |
| governor on, unchanged | `PTCG_GOVERNOR` default `"1"`; `GOV_CAP_S=3.0`, `GOV_STICKY_S=0.2` untouched | ✅ |
| `value_weights.npz` packaged | present, 123042 B (via `--force-weights`) | ✅ |
| `[gov-snap]` telemetry | present | ✅ |
| `[gov]` decision counters | `end_veto= atk_legal= atk_in= cand_forced= cand_atk_w= changed=` | ✅ |

### Check 1 — diff

**vs the repo's working-tree `main.py`: exactly 2 lines**, both the intended
ship-config bake.

```
28c28  AGENT_VERSION = "ptcg-heuristic-v1.0.0"  ->  "ptcg-search-baseline-c0-vw"
123c123 SEARCH = os.environ.get("PTCG_SEARCH", "0")  ->  ("PTCG_SEARCH", "1")
```

**vs the live VN bundle (μ509.2): 51 changed lines, exactly one behavioural.**

| change | category | behaviour |
|---|---|---|
| `AGENT_VERSION` | identity | none |
| **`END_VETO` `"narrow"` → `""`** | **BEHAVIOUR** | **the intended change — veto removed** |
| `CAND_INCLUDE_ATTACK` / `CAND_ATK_W` / `CAND_ATK_MIN_DMG` flags | new, default off | none |
| A-WEIGHT branch in `_pilot_score_main` | new, default off | none — and doubly unreachable, since `PILOT=""` |
| candidate block in `_search_decide` | new, default off | none — `cands` is only reassigned under `elif CAND_INCLUDE_ATTACK`, which is False; the rest is `STATS` increments |
| `[gov]` format string + `STATS` args | telemetry | none |

**Behaviour changes vs live VN: exactly 1 (END_VETO off), which is what was
asked for. Behaviour changes vs the H1 configuration already measured over 60
self-play games: zero.**

### Check 2 — clean-env self-play, 20 games

| | |
|---|---|
| games / agent calls | **20 / 2481** |
| `FALLBACK` | **0** |
| `Traceback` | **0** |
| `hook error` | **0** |
| `SELFCHECK FAIL` | **0** |
| searches run | 1495 |
| decisions where search overrode v1 | 554 |

### Check 3 — fault injection, four scenarios

| scenario | result |
|---|---|
| `value_weights.npz` removed | ✅ legal `[1]` |
| `cg/` engine removed | ✅ legal `[1]` — heuristic-only mode |
| `card_data.json` removed | ✅ legal `[1]` |
| malformed option (unknown type, empty `current`) | ✅ legal `[1]` |

The builder's own suite additionally passed `[3/6] exec-load check OK
(cg=True pool=1267)` and `[4/6] no-cg fallback OK`.

### Check 4 — wall-clock

| source | local MAX | **×1.8 Kaggle projection** | % of 600 s bank |
|---|---|---|---|
| this bundle, 20 games / 40 sides | **60.1 s** | **108.3 s** | **18.0%** |
| *(H1, 60 games — binding reference)* | *71.9 s* | *129 s* | *21.6%* |
| *(measured VN ladder reality)* | *106.6 s* | — | *17.8%* |

Builder smoke over 30 games: decision p50 561 ms, p90 1893 ms, **max 3020 ms** —
consistent with `GOV_CAP_S = 3.0` (the budget is checked *between*
determinizations, so a single one may overshoot slightly). Take H1's 21.6% as
the binding figure. **Comfortable margin; timeout risk low.**

### Check 5 — `value_weights.npz`

| | |
|---|---|
| in tarball | ✅ 123042 B |
| `_find_file` locates it under clean exec | ✅ |
| `_lv_model()` loads | ✅ keys `['np', 'layers']` |
| "not found" warning emitted | ✅ **no** |
| **value-net evaluations** | **76 over 4 games — non-zero** |

At `cap=400` the value net is reached only when a rollout hits the step cap
without terminating (`_rollout`: `if steps >= cap: … _lv_model()`), so the count
is low by design but confirms the weights are genuinely exercised, not just
present.

**§2 verdict: ALL CHECKS PASS.**

---

## Summary

| | **§1 v2.2.0 (the μ697 agent)** | **§2 baseline (what the spec described)** |
|---|---|---|
| path | `submission_bc_metaC_garchomp_nasuo.tar.gz` | `dist/baseline/baseline_c0_vw.tar.gz` |
| sha256 | `b9b7bca0836f2c…9192887` | `0512323664cad…fd344fd` |
| members / size | 4 / 0.22 MiB | 14 / 2.12 MiB |
| `AGENT_VERSION` | `ptcg-bc-v2.2.0-full-garchomp` | `ptcg-search-baseline-c0-vw` |
| policy | **behaviour cloning, no search** | **determinized search, no BC** |
| ladder history | **μ697 / 682.5 (25W-32L)** | never submitted; nearest relative VN μ509 |
| wall-clock ×1.8 MAX | **0.2 s (0.0%)** | 108.3 s (18.0%) |
| all five checks | ✅ **PASS** | ✅ **PASS** |

**Both bundles are built and verified. Neither has been submitted — the upload
is yours.**

### What I'd flag before you choose

1. **Only §1 has ever scored 697.** §2 is a good, clean, well-verified agent
   with no ladder evidence behind it. If the goal is "restore the best honest
   agent", §1 is the one, and it needs no rebuild — it is the original bytes.
2. **`PILOT` is unbaked in §2**, so the Garchomp tempo layer is inactive, as it
   has been in every search bundle we have ever shipped. Baking it would be a
   real behaviour change that has **never been gated on ladder**. Your call; I
   did not make it.
3. **Slot arithmetic.** Uploading one bundle displaces the older of VN (509.2)
   and `grimmsnariex_v1` (391.9). Uploading both displaces both. The Kaggle
   last-2 rule is **team-level**, so any upload by Sanjay in the same window
   also counts.
4. **Scores reset on resubmission.** A re-uploaded v2.2.0 starts from the 600
   entry rating and must re-climb; it does not resume at 697. The n ≥ 40 rule
   applies before reading anything into its score.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/verify_bundle.py` | bundle verifier (exec-loads the tarball, not the repo) |
| `dist/baseline/baseline_c0_vw.tar.gz` | §2 bundle |
| `scratchpad/s3/verify_v220.json` | §1 raw results |
| `scratchpad/s3/verify_baseline.json` | §2 raw results |
| `scratchpad/s3/build_baseline.log` | builder log, 6/6 stages |
| `scratchpad/s3/candset_shipcfg.json` | ship-config (`PILOT=""`) exclusion re-measurement |
