# CONTEXT — Pokémon TCG AI agent: session log & current state

_Last updated: 2026-07-19 (rev 6 — §6h: deck is NOT the constraint, piloting is; Alakazam package built)._
_Companion docs: `agent/STAGE3_HANDOFF.md`,
`agent/design/alphazero_plan.md`, `rules/basic_rules.md`._

---

## 0. TL;DR — the two things that mattered

> **START HERE: read §6h, then §6g, then §6e's refutation table.** §6h has the
> current state and the one open defect; §6g corrects §6f; §6e lists 5 refuted
> hypotheses that will look compelling again if you don't.
>
> **The meta-lesson of 2026-07-19: 8 hypotheses tested, 7 refuted.** Every wrong
> turn came from reasoning off OUR data alone — our wins vs our losses cannot
> tell you whether 0.8 energy or 140 HP is *normal*. Both times the diagnosis
> inverted, it was because a top player's replays finally got pulled.
> **Pull the current #1's replays BEFORE any significant decision.** Also: never
> trust an arena run under n=60 for a win-rate call — hours went into 8–12 game
> runs that mathematically could not resolve the effects being chased.

> **The recurring lesson: two separate subsystems were present, plausible-looking
> and completely inert.** The V1 import bug (§0) and the belief-identification
> collapse (§6d) were both found by *testing whether the thing worked*, not by
> reading the code — which looked fine in both cases. Assume any unmeasured
> component is doing nothing.


**Our Kaggle submissions were never actually running.** Kaggle puts the agent
directory on `sys.path` while it `exec()`s `main.py`, then **removes it**. Every
subsequent `import mcts` raised `ModuleNotFoundError`, our never-crash
`except → random` fallback swallowed it, and we played **uniformly random for
entire games** while the deck phase still looked fine.

* Proof (production logs, ep 86825163):
  `SELFCHECK FAIL: ModuleNotFoundError: No module named 'mcts' -- WILL PLAY RANDOM`
* Proof (replay timing): **3.07 s of the 600 s bank across 93 decisions ≈ 33 ms
  each** = fallback speed. The ladder #1 uses ~285 ms/decision.
* Ladder result of that broken agent: **366**.

**Fix:** load our modules by explicit file path with
`importlib.util.spec_from_file_location`, which never consults `sys.path`.
**Confirmed working in production**: `SELFCHECK PASS`, 0 fallbacks,
1235–1626 ms/decision. Ladder record since the fix: **11W–9L** (see §6b).

> Implication: every previous search submission (`submission_search` 620,
> `mcts_iter100` 628, `search_metaB_alakazam` 622) almost certainly had this bug.
> Those scores are what a *random* agent scores — the search has never been
> evaluated on ladder before now.

---

## 1. Agent changes (in `agent/mcts.py`, mirrored into submissions)

Chronological; all measured against arenas unless noted.

| # | Change | Rationale / measured effect |
|---|---|---|
| 1 | **Develop-biased rollout** `_competent_choice` (EVOLVE > PLAY > ATTACH > ABILITY, then highest-damage ATTACK) replacing an attack-or-END-only policy | Old policy never benched/attached, so the rollout player was board-wiped in nearly every sim → every option's Q ≈ −1. Won-game best-Q **+0.10 → +0.95** |
| 2 | **Competent opponent model** in-tree + symmetric rollouts (was uniform-random) | A search that assumes the opponent may not take lethal walks into it. **vs strong_800: 0.20 → 0.60** |
| 3 | **Engine-exact lethal fast-path** `_find_lethal` — probe each ATTACK via `search_step`; if it terminates in a win in all probed worlds, take it | Engine computes exact damage (weakness/effects); no hand-modelled damage math |
| 4 | **Engine-probed multi-selects** `_choose_multiselect` (was random) | Discards / energy payments / fetch targets were being chosen at random — a permanent card-advantage leak |
| 5 | **Time-scaled worlds** (`max_worlds=16`, keep sampling while budget remains) | We were using ~10% of the affordable per-decision time |
| 6 | **Richer static eval** `_hand_eval`: prize lead, bench depth, HP fraction, energy, lone-active fragility | Old eval was prizes+bench only |
| 7 | **Truncated rollouts scored by static eval** | Unfinished deep rollouts returned 0.0 (wasted signal) |
| 8 | **Blunder veto** `_loses_immediately` | Defensive mirror of the lethal probe |
| 9 | **Tier-1**: opening bench rule, best-first expansion `_expansion_priority`, rollout retreat, adaptive budget | Board-wipe was 70%+ of vs-random losses |
| 10 | **`VALUE_NET` / `POLICY_NET` hooks** (blend weight `VALUE_NET_WEIGHT=0.5`) | Optional; **currently unused — both measured harmful, see §3** |
| 11 | **Rollout depth 100 → 24** | 63 → **185 visits/decision (3×)**. Win-rate effect under test |
| 12 | **Anti-dominated-move rule** | ATTACK and END both end the turn, so passing with a legal attack is dominated. Observed twice in real games |

### Reverted (documented so it isn't reintroduced)
**"Attack 65% of the time" rollout policy.** Added on the theory that we
under-attack. **That diagnosis was wrong.** Measured per *turn* (the correct
unit — attack is legal at every MAIN sub-decision but you attack once, at the
end of a turn):

| Agent | Turns containing an attack |
|---|---|
| Ladder #1 (Majkel1337, 40 games) | **24%** |
| Our agent | **30%** |

We attack *more* than the #1. The "12.4% of decisions" figure that motivated the
change was an artifact of counting sub-decisions.

---

## 2. Deployment robustness (`submission_*/main.py`)

| ID | Vulnerability | Status |
|---|---|---|
| **V1** | Kaggle strips agent dir from `sys.path` → all local imports fail → silent random play | ✅ `_bootstrap_modules()` — explicit file-path import, bypasses `sys.path` |
| **V2** | Module-level statements could raise (`from cg.api import…`, `MY_DECK = _read_deck_csv()`) → `agent` never defined → forfeit *everything*, worse than V1 | ✅ both guarded; `_raw_fallback()` works off the raw dict; FATAL logged |
| **V3** | Belief never reset if the harness doesn't send `select=None` between episodes → stale belief corrupts every determinization | ✅ `_looks_like_new_game()` (turn regression) |
| **V4** | Time-bank exhaustion | ✅ safe — governor caps at 0.75×600 s; measured 190 s for a 118-decision game |
| **V5** | `_find_lethal` / `_choose_multiselect` ran *before* the budget clock, unbounded | ✅ hard `probe_deadline` |
| **V6** | Determinizer couldn't predict a face-down opponent active → `search_begin` raises → whole decision goes random (~1/105) | ✅ `_any_basic_in_pool()` fallback |
| — | **Observability** | ✅ `SELFCHECK PASS/FAIL` + `FALLBACK #n` to stderr. **This is how V1 was caught — keep it.** |

> **Lesson: never let a broad `except` hide a startup failure.** Emit a loud
> one-time self-check. Also: `kaggle competitions logs <ep> <idx>` *downloads a
> JSON file*, it does not print — that's why logs looked "empty" for hours.

---

## 3. Learning components — built, measured, NOT shipped

Harvested **all 1000 episodes of ladder-#1 `Majkel1337`** (submission 54662660)
via `top_replays/download_all.sh`. They play **one fixed Alakazam list in all
999 parseable games** (`agent/deck_alakazam_top.csv`).

| Component | Offline metric | Arena result | Shipped? |
|---|---|---|---|
| Value net (63k top-player positions; mixed retrain on +120k self-play) | val sign-acc **0.78–0.81** (baseline 0.53) | value-only vs hand-eval **0.467** | ❌ |
| BC policy net (51k of the #1's decisions) | top-1 **0.388** (baseline ~0.11) | value+policy vs hand **0.367**; value-only vs full **0.769** | ❌ |

**Conclusion: the BC policy priors are actively harmful; the value net is
~neutral.** Root cause is representation — our card features are
identity-blind (7 dims: is_pokemon/is_basic/hp/is_energy/is_supporter/is_item/
best_damage). The net cannot distinguish Abra from Alakazam, which is exactly
what Alakazam's combo lines depend on. Independently confirmed by repo1, who
plateaued at top-1 0.529 and concluded *"the bottleneck is FEATURES, not rows."*

Pipeline files (all working, reusable): `build_topplayer_dataset.py`,
`build_policy_dataset.py`, `value_features.py`, `policy_features.py`,
`train_value.py`, `train_policy.py`, `value_net.py`, `policy_net.py`,
`az_selfplay.py`, `run_azgen.sh`.

---

## 4. Tooling built this session

| File | Purpose |
|---|---|
| `agent/vs_external.py` + `agent/agent_worker.py` | Head-to-head between two *submission packages*, each in its own process (avoids `main.py`/`cg` name collisions; each gets its own engine). Fresh workers per game |
| `agent/investigate_losses.py` | Per-decision trace capture (board, options, visits, Q), loss clustering, wins-vs-losses value-signal control |
| `agent/oracle_gap.py` | Same agent with the TRUE hidden state (`visualize_data`) → measures total belief-side headroom. Result: **30/30 vs random** (belief headroom ≈ 6.7 pts) |
| `agent/head2head_agents.py` | MCTS-vs-MCTS deck arena, per-side perspective-pinned belief |
| `top_replays/download_all.sh` | Idempotent bulk episode download (`kaggle competitions episodes` / `replay`) |
| `watch_submission.sh`, `verify_fix.sh` | Post-submission verification: pulls agent logs + measures ms/decision from the replay |
| `run_*.sh` | Detached, self-driving benchmark chains (survive Claude session ending) |

---

## 5. External intelligence (`Downloads/opp/`)

**repo1 `kaggle-pokemon-tcg`** — extensive prior work, key claims:
* **The one proven lever is META-COUNTERING, not mirroring.**
  Cycle: **Dragapult > Trevenant > Alakazam > Dragapult**.
  Countering the #1 scored **~900–978**; *mirroring* the #1's deck flopped at **460**.
* Exhausted (don't re-grind): policy plateau (features, not data); **forward
  search validated WORSE for them** (bad opponent determinization); self-play
  gate failed.
  → **Our validated determinizer + working search is our differentiator.**

**repo2 `ptcg-ai-battle-challenge-simulation`** — 146 logged submissions with
real Elo. **Byte-identical archives scored 600–955.**
→ **Ladder Elo variance is enormous; never re-plan on a single score.**
(This also explains `strong_code_submission`: 803.4 then 626.1 — same code.)

**Sparring partners staged:** `_opp_strong800` (heuristic Lucario),
`_opp_sundar` (BC net, Garchomp), `_opp_oshbocker`, `_opp_tuann`,
`_opp_lb950` (~950 Lucario), `_opp_repo2`.

---

## 6. Current state

| Submission | Contents | Result |
|---|---|---|
| `54799629` | pre-V1 Trevenant | **366** — agent never ran (random play) |
| `54822283` | AGENT_DIR fix only — still broken | 1W–3L, still 26 ms/decision |
| `54822768` | **V1 importlib fix** | 9W–5L — first genuinely searching agent |
| **`54824626`** (live) | + V2/V3/V5/V6, depth 24, anti-dominated | **11W–9L (55%)** — see §6b |

* **Candidate on disk:** `submission_trevenant/` — adds the `_anti_dominated`
  fallback-path fix and the anti-chip gate (§6c). Tarball
  `submission_trevenant_ship.tar.gz` (verified from the extracted archive under
  simulated Kaggle conditions: SELFCHECK PASS, 0 fallbacks).
  **Do not ship the gate until the arena approves it.**

---

## 6b. Ladder results — submission 54824626 (all fixes, live)

**11W–9L (55%)** over 20 real games. Agent verified genuinely searching every
game: `SELFCHECK PASS`, **0 fallbacks**, ~1.3 s/decision.

### By opponent archetype — the decisive cut
| Archetype | Record |
|---|---|
| **Dragapult** | **0W–4L** ← 4 of our 9 losses |
| Lucario | 3W–1L |
| Alakazam | 2W–0L |
| Kangaskhan | 2W–0L |
| TR-Spidops | 1W–1L |
| Abomasnow / Decidueye / Other | 0W–1L each |
| GreatTusk / Slowking / Eeveelution | 1W–0L each |

This reproduces repo1's cycle on live data: **Dragapult > Trevenant > Alakazam**
(we beat Alakazam 2–0, lose to Dragapult 0–4).

### Win/loss profile (n=20)
| Metric | Wins (9) | Losses (9→ now 9) |
|---|---|---|
| Prizes we took | 4.1 | **2.5** |
| Prizes they took | 2.1 | **5.0** |
| Game length | 20.6 turns | **15.8 turns** |
| Max energy ever on our active | 2.2 | 1.8 |

### THE STRUCTURAL PROBLEM: energy
Across **all 20 games** our active Pokemon never held more than **1–3 energy**.
Hop's Trevenant's real attack **Corner costs 3 energy** (90 dmg) — it essentially
never came online. We fought the entire ladder with the 1-energy 30-dmg
`Horrifying Revenge`, and sometimes 10-dmg filler, into 130–350 HP walls.
Cause: **9 energy in 60 cards**, and every KO takes its attached energy with it.

> The #1's Alakazam deck fixes exactly this: its attacker `Psychic` costs **1
> energy** and scales +50 per energy on the OPPONENT's Pokemon, plus 4× Enhanced
> Hammer / 3× Xerosic energy denial — which is *why* it counters Dragapult.

### Attack-TIMING finding (and a corrected earlier error)
Per-turn P(attack | attack legal), 20 games vs the #1's 150:

| Turn | #1 player | OUR WINS | OUR LOSSES |
|---|---|---|---|
| 0–3 | 69% | **60%** | **33%** |
| 4–7 | 43% | **47%** | **73%** |
| 8–11 | 24% | **25%** | **58%** |
| 12–15 | 23% | **17%** | **50%** |
| 16–19 | 24% | **21%** | **43%** |

**Our winning games track the #1 almost exactly; our losing games invert it** —
passive early, then chip-attacking a wall late. Data in `agent/_attack_profile.csv`.

⚠️ **Causality caveat:** in losing games we are behind, so late attacking is
partly a SYMPTOM (no development left, desperate) rather than a cause. The
early-game gap (33% vs 60%) is the cleaner signal. This is why the gate below
must win an arena before shipping — it is fitted to correlational data.

### Loss autopsies
| Opponent | Deck | Diagnosis |
|---|---|---|
| taka548 / tennogh / jarrett / zerotwo002 | **Dragapult** | Fast (9–15 turns), maxE 1–2. Blown out before setup |
| TABOUT MHAMED | Abomasnow ex (350 HP, 3 prizes) | Prize math + a real END-over-30-dmg-attack blunder (bug, fixed) |
| happyunhappy | TR-Spidops (130 HP) | Never powered Corner; chipped with 10-dmg attacks |
| yato higa | Decidueye | **Lost by one prize** (5–6), decked to 2 cards. Genuinely close |
| Mayu Takagi | Lucario | — |
| Toru59er | Other | — |

---

## 6c. Anti-chip gate (implemented, UNVALIDATED)

`_is_chip_attack()` + gate in `choose_action`:
* before turn 8 → **no restriction** (early attacks are near-free; #1 takes 43–69%)
* from turn 8 → veto an attack only if it **cannot KO** AND deals **<25% of the
  defender's remaining HP**, and a real development move is available
* never falls through to END (`_anti_dominated` still applies)
* damage estimate = base × weakness, ignoring scaling text → deliberately
  conservative, since it is only used to VETO

**Also fixed:** `_anti_dominated` was placed AFTER the `total_visits == 0`
early-return, so the no-search fallback bypassed it — that produced a real
END-over-a-30-damage-attack on ladder (ep 86844269 turn 10). Now extracted to a
helper and applied to **every** MAIN return path; unit-verified on that exact
position.

**Methodology note — do NOT "graph losses vs attack count to find the optimum".**
That curve is confounded (losing → more attacking). The valid form is an
*interventional* sweep (set the policy, measure win rate). And at n=30 the CI is
±18%, so only coarse points are resolvable — a fine grid would fit noise.

---

## 6d. Opponent-deck identification — a second silent failure (2026-07-19)

**The belief system was never identifying anything.** Same class of bug as §0:
present, plausible-looking, and inert. Found by testing it rather than trusting it.

**Root cause.** Hypotheses were matched by EXACT decklist. Real ladder lists are
variants, so on real replays the true archetype's own representative still took
**8–20 card violations** from tech-card differences, and `_CONTRADICTION_PENALTY
= 1e-6` per copy annihilated it. All six hypotheses died and **92–100% of the
belief mass fell to the "unknown" fallback by turn ~5, in 100% of games.** The
determinizer was sampling filler instead of the opponent's real attackers,
energy and gust effects — so every "belief-guided" search result up to this
point was substantially less belief-guided than assumed.

**Fixes (all three needed; the third is the one that mattered).**

| # | Where | Change |
|---|---|---|
| 1 | `decks_pool.identify()` | Bayesian archetype posterior: meta-share prior × `3^(signature-card hits)`. Each top-5 deck has a clean unique core, so tech cards can't eliminate the truth. |
| 2 | `main._reweight_by_archetype()` | Re-priors hypotheses from that posterior **every decision**; unknown mass shrinks as confidence rises, so off-meta decks still can't be confidently mis-identified. |
| 3 | `belief._FLEX_COPIES = 12.0` | Forgives 12 copies of variant slack, then dampens the rest sublinearly (`shortfall**0.5`). Without this, fix 2 got re-annihilated immediately. |

`_opponent_hypotheses()` now also consumes `decks_pool.WEIGHTS` (measured meta
share) instead of assigning uniform 1.0 — so the most likely matchup is played
correctly even *before* any reveal.

**Measured on real replays:**

| metric | before | after |
|---|---|---|
| mean unknown mass (midgame) | 92–100% | **28%** |
| games locking on (≤4% unknown) | 0/20 | **15/20** |
| early ID matches full-information verdict (turn ~8) | — | **87%** |

**Two caveats, recorded so they aren't cited as stronger than they are:**
- An earlier "100% correct at end" figure was **tautological** — ground truth was
  derived from the same signature function. The real number is the 87% early
  convergence.
- 5/20 games still collapse to unknown: those opponents play lists too far from
  our stored representatives. That needs a **decklist refresh, not more code**.

**Status: UNVALIDATED for win rate.** Arena run (n=12 vs Alakazam) was in flight
at time of writing. This touches the belief path in *every* decision, so it must
not ship on identification metrics alone — n=12 is thin; want a larger run first.

---

## 6e. Loss investigation, 2026-07-19 — 6 hypotheses, 5 refuted

Read this section before proposing any of these again. Each looked compelling
and each dissolved under test; the refutations cost more time than the one fix.

### Refuted — do NOT reintroduce

| # | Claim | Why it's wrong |
|---|---|---|
| R1 | "51.8% of our actions are ILLEGAL (`[]` when minCount>=1)" | `[]` is the engine's normal **pass/decline**. Disproof was in the same output: winning games showed 56–94 of them. |
| R2 | "We pass more when losing (47.5% W vs 58.7% L)" | Same root cause as R1. Those frames are `status=INACTIVE` — the **opponent's** turns, where the harness repeats the last observation and we emit nothing. In games we lose the opponent takes more turns, so the gap is pure artifact. |
| R3 | "Only 10 Basics is a construction error; +14 Basics ≈ +5–7% win rate" | **Luca (#1) runs 10 Basics. Majkel runs 9.** The best lists in the format run what we run. Projection withdrawn. |
| R4 | "The agent refuses to bench Basics" | In 4 of the 5 empty-bench losses it **never held a Basic** to bench. 1 decline in 2 opportunities total. |
| R5 | "Low energy causes losses" | Confounded by game length + KOs. At **fixed turns** the W/L difference is noise and alternates sign (−0.21, −0.07, +0.05, +0.29, −0.03, +0.17, −0.17). |

Also discarded: **KOs-suffered as a metric** — computed from the opponent's prize
count, which is definitionally entangled with losing. Circular, tells us nothing.

### Confirmed and FIXED

**We end the turn while one KO from losing, holding cards that could dig.**
Bench empty + no Basic in hand: 18 such decisions across eps 86862897 / 86824062
/ 86835128, 10 had a legal PLAY option, we played it **0 times**. Ep 86862897
turn 1 is the clean case — held 2x Pokegear 3.0 (free Item, digs) + Postwick,
all offered, chose END, lost on turn 1 with all 6 prizes intact.

Fix: `_dig_when_benchless()` + `_dig_value()` in `submission_trevenant/mcts.py`,
applied on every MAIN return path beside `_anti_dominated`. Ranks plays by what
they do (search-for-Basic 100 > search 80 > draw 60 > other 20 > Tool/Stadium 5)
rather than taking the first PLAY option, which would just as happily play a
Stadium. Verified: on ep 86862897 exactly one decision flips (END -> PLAY
Pokegear); all others unchanged. Smoke test 3W–5L, **0 errors**.

Scope: ~5 of 62 games, and it converts only *some* of them — 4 of those 5 games
also never drew a second Basic, which no code fix reaches.

### The open finding: we play ~3x too slow (energy PERSISTENCE)

Benchmarked against **522 Luca replays** — the first expert baseline we've had.
Every earlier metric compared our wins to our losses, which is blind to problems
affecting both.

| turn | energy: ours | energy: Luca | prizes: ours | prizes: Luca |
|---|---|---|---|---|
| 8 | 0.62 | **1.74** | 0.56 | **1.86** |
| 10 | 0.75 | **1.65** | 0.90 | **2.83** |
| 12 | 0.84 | **1.49** | 1.13 | **3.54** |
| 18 | 1.04 | 1.00 | 2.25 | **4.70** |

- Being **behind early is normal** — Luca is behind at turns 6–10 too. The
  earlier "systemic tempo deficit" framing is retracted.
- The real gap is **rate**: Luca has 2.83 prizes at turn 10, we have 0.90. Their
  games decide by turn 12–16; at turn 18 we're still in the early midgame.
  (Turn 16+ convergence is survivorship — their fast wins are already over.)
- Bench-empty share of decisions: ours **6.4%**, Luca **3.8%**.

**Mechanism — NOT attachment.** Attach-declined: ours **55.9%** (1122 offers),
**Luca 76.1%** (8322 offers). *We attach MORE than the #1 player.* Luca doesn't
need to: **energy persists because their Pokemon survive.** Grimmsnarl ex has
320 HP; our Trevenant attacker ~140. Ours dies and every KO resets the energy
investment to zero — we refill a leaking bucket. This explains the energy curve,
the prize rate, why we attach more, and why the 3-energy Corner never comes
online (the attacker never lives long enough). Our deck asks for 50% more energy
than Luca's while generating half as much.

**Status: UNVERIFIED.** Deck confound — Luca plays Grimmsnarl, our measured
games were Trevenant. Instrumented run in flight (`PTCG_CURVES` in
`agent/vs_external.py` -> `agent/_curves_grimm.json`) measuring OUR energy curve
on Luca's deck. If it climbs toward 1.5, durability transfers and the deck is
the fix; if it stays ~0.8, the deck is not the mechanism.

> Prior evidence against "just take their deck": the **Lucario mirror test**
> (we piloted the reference agent's own deck, won **31.5%** over 1000 games) and
> the current Grimmsnarl package (**33% / 42% / 37.5%** vs an expected 61%).
> Deck alone does not confer the result.

---

## 6g. ⚠️ CORRECTION TO §6f — the metric is DAMAGE PER ENERGY (read before §6f)

§6f concluded the bottleneck was **HP + energy acceleration** (get a 320 HP body
and Punk Up). **That conclusion is FALSIFIED.** The measurements in §6f are
correct; the inference from them was not. Two current top players:

| player | deck | energy t8/t10/t12 | prizes t8/t10/t12 | record |
|---|---|---|---|---|
| **#1 Yushin Ito** (54773249) | **Alakazam, 140 HP** | **0.89 / 0.86 / 0.91** | **1.55 / 2.53 / 2.85** | 72W–47L |
| #2/3 THIRD PTCG Club (54810671) | TR Mewtwo ex, 280 HP | 1.90 / 2.20 / 2.22 | 0.80 / 1.46 / 2.69 | 16W–9L |
| **us** (Trevenant, 140 HP) | | 0.62 / 0.75 / 0.84 | 0.56 / 0.90 / 1.13 | 35W–26L |

**The #1 player wins with a 140 HP body and UNDER 1 ENERGY** — the same
resources we have — and takes prizes ~3x faster. So HP and energy are NOT the
binding constraint. Big bodies and acceleration are *one* viable strategy
(Mewtwo), not *the* answer.

### The real metric

| deck | cost | damage | **dmg/energy** |
|---|---|---|---|
| Alakazam `Psychic` | **1** | 10 **+50 per energy on the DEFENDER** → 210–260 vs a charged target | **~230** |
| TR Mewtwo ex `Erasure Ball` | 3 | 160 | 53 |
| Marnie's Grimmsnarl ex `Shadow Bullet` | 2 | 180 | 90 |
| **our `Hop's Trevenant` `Corner`** | **3** | **90** | **30** |

**We are ~8x less energy-efficient than the #1 deck.** That single ratio explains
the 3x prize rate, "outpaced from midgame", and why the one game we reached 3
energy we won 5–2. Two viable curves exist — low-energy/high-efficiency
(Alakazam) or high-energy/high-power (Mewtwo) — and **we are on neither**: we
have Alakazam's energy with the worst damage/energy in the format.

### This REVERSES the Grimmsnarl recommendation

Alakazam's `Psychic` scales with **the defender's** attached energy. Punk Up
attaching 5 energy makes Grimmsnarl the *ideal* Alakazam target (210–260 for one
energy). **Shipping Grimmsnarl walks into the #1 player's best matchup.**
Do not ship Grimmsnarl on the strength of §6f.

### What to select a deck on (revised)

1. **Damage per energy at 1–2 energy cost**, NOT raw HP — that is the axis the
   #1 wins on and the axis we lose on.
2. Attacks that **scale off the opponent's board** (energy attached, damage
   counters) are the format's premium effects — they convert the opponent's
   development into our damage.
3. `agent/find_attackers.py --hp 100 --cost 1 --dmg 100` finds cheap attackers;
   note it reads *printed* damage, so scaling attacks like `Psychic` (dmg=10)
   are UNDER-stated and will not surface. Read attack text for scalers.

---

## 6f. Structural measurements (CONCLUSION SUPERSEDED BY §6g — read that first)

**Our losses are not tactical. The deck is outclassed on two axes at once.**

### Axis 1 — bodies

| | our best active | what we face |
|---|---|---|
| aggregate (62 games) | **145 HP** | **248 HP** |
| ep 86900376 (can_cam) | **70** (never got Trevenant out) | 320 Marnie's Grimmsnarl ex |
| ep 86900899 (Mih Zam) | 150 | 300 Archaludon ex |
| ep 86901976 (Sean Jones) | 150 | 320 |

### Axis 2 — energy acceleration (the real gap)

`Marnie's Grimmsnarl ex` ability **Punk Up**: *"When you play this Pokémon from
your hand to evolve 1 of your Pokémon, search your deck for up to **5 Basic {D}
Energy** and attach them to your Marnie's Pokémon in any way you like."*

**One evolution = 5 energy.** We attach 1/turn by hand. This single ability
explains everything measured earlier: their persistent energy, their 3x prize
rate, AND why they *decline* 76.1% of manual attaches vs our 55.9% — they don't
need them. We were never closing that with better search.

Direct evidence of the leak, ep 86900899 energy on our active by turn:
`1 → 2 → 2 → 0 → 1 → 0 → 0 → 0` — build, get KO'd, reset, repeat. Five actives
cycled for one prize.

### Submission 54832367 (dig+belief fixes, Trevenant) — 4W–3L

| ep | res | opp HP | max energy | prizes |
|---|---|---|---|---|
| 86901445 | **W** | 280 | **3** | **5–2** |
| 86898034 | W | 150 (mirror) | 2 | 5–4 |
| 86899266 / 86899810 | W | 350 / 240 | 1 | 0–3 / 4–5 |
| 86900376 / 86900899 / 86901976 | **L** | 320 / 300 / 320 | 1 / 2 / 1 | 2–5 / 1–5 / 0–5 |

**The only game where we reached 3 energy (Corner online) we won 5–2.** We get
there in ~14% of games. Everything hinges on it.

Belief fix CONFIRMED WORKING in production: identified `grimmsnarl` at **90%**
confidence in ep 86900376.

### ⚠️ THE #1 RISK FOR A GRIMMSNARL BUILD

**Our agent declines 58–60% of EVOLVE opportunities** (W 58.5% / L 60.5% — it
was neutral for Trevenant, which is why it never surfaced as a loss driver).

**With Grimmsnarl that is catastrophic: every declined evolution throws away 5
energy.** Punk Up only fires when evolving *from hand*. Our evaluator scores
evolution as an ordinary board improvement and has no concept of the
acceleration. A ~48-sim determinized search will not see it through hidden
information — the same blind spot that required the dig rule.

**Do not ship a Grimmsnarl package until evolve-priority is verified/forced.**
Likely fix: a rule in `mcts.py` beside `_dig_when_benchless` — with a Punk Up
line available, evolving dominates.

### Deck strategy — settled

- `agent/find_attackers.py` (NEW) searches the card DB by HP / energy cost /
  damage, and `--counters` finds Grass attackers (Grimmsnarl ex is weak to
  Grass, code 1). Caveats in its docstring: printed damage ignores conditional
  bonuses, `ex` gives up 2 prizes, evolution consistency not modelled.
- **Grimmsnarl is NOT the best raw attacker** — Palafin ex does 250 dmg for
  **1** energy (340 HP); Grimmsnarl does 180 for 2. It dominates because of
  Punk Up + the Marnie engine. **A big body alone is not the answer; the engine
  is.**
- **Grass counter-deck REJECTED.** Decidueye (150 HP, 1 energy, 170 dmg = 340
  into Grimmsnarl) is tempting, but Grimmsnarl is only 34.9% of the meta and
  Grass is weak to Fire. Rough EV `0.35×0.80 + 0.65×0.40 ≈ 54%` vs Grimmsnarl's
  measured **66% overall**. No rock-paper-scissors cycle exists in this format,
  so counter-teching loses to bringing the best deck. Grass is worth at most a
  searchable 1–2 tech card, now that belief identifies Grimmsnarl at 90%.

---

## 6h. FINAL RESULTS 2026-07-19 — the deck is NOT the constraint, WE are

### Decisive: durability does NOT transfer (clean Grimmsnarl curve test)

Our agent piloting **Luca's exact Grimmsnarl list** (`submission_grimm/`,
separate package; `agent/_curves_grimm2.json`, 696 samples, 3W–7L):

| turn | **US on Grimmsnarl** | us on Trevenant | **Luca on Grimmsnarl** |
|---|---|---|---|
| 6 | **0.00** | 0.81 | 1.39 |
| 8 | **0.44** | 0.62 | 1.74 |
| 10 | **0.85** | 0.75 | 1.65 |
| 12 | **0.33** | 0.84 | 1.49 |

**Given the identical deck we develop it at ~1/4 of Luca's rate — worse than our
own Trevenant.** This was the pre-registered falsification condition. The 320 HP
body and Punk Up do NOT rescue us. Cause is almost certainly the evolve decline
(Punk Up only fires on evolve-from-hand; we decline 58–60%).

Third independent confirmation that **piloting, not decklist, is the limit**:
Lucario mirror 31.5% · Grimmsnarl 33/42/37.5/30% · this curve test.

### The matchup split (submission 54832367, all 12 episodes, 6W–6L)

| opponent's biggest Pokemon | our record |
|---|---|
| **300+ HP (ex decks)** | **1W–5L (17%)** |
| under 300 HP | **5W–1L (83%)** |

Cross-check by energy reached: **3 energy → 2W–0L** (won 5–2 and 5–4); 2 energy
→ 2W–3L; 1 energy → 2W–3L. Corner does 90 for 3 energy, so a 320 HP ex needs
FOUR Corners — unreachable. Under 300 HP, 90 damage suffices and we win 83%.

**The 578.0 score is n=12 and UNSETTLED** (vs 766.9 at n=51). Not a regression
from the fixes — this build simply drew 6 big-ex opponents out of 12. Do not act
on a score before ~40 episodes.

### Why ALAKAZAM (revised, stronger argument)

Not merely damage/energy. **We are demonstrably bad at accumulating energy —
0.3–0.85 on every deck tried.** Alakazam's `Psychic` costs **1** energy and
scales off the DEFENDER's attached energy. It is the only top archetype whose
win condition survives our specific weakness, and it converts our worst matchup
(300+ HP charged ex, 1W–5L) into its best. Pick the deck robust to the flaw,
then fix the flaw.

**`submission_alakazam_ship.tar.gz` is BUILT AND VERIFIED** (60 cards, 19
Pokemon, 9 basics; SELFCHECK PASS, 0 fallbacks, verified from the *extracted*
tarball with `sys.path` stripped and no `__file__`).

### ⚠️ THE OPEN DEFECT — energy development

**Why does our agent accumulate energy at ~1/4 an expert's rate on the same
deck, while declining FEWER manual attaches than they do (55.9% vs 76.1%)?**
That contradiction is unresolved and is the highest-value open question.

Note what is NOT the answer: `_expansion_priority` already scores `_OPT_EVOLVE`
at 300 (highest) and `_DEVELOP_PRIORITY` puts it first — the search explores
evolution first and then *chooses* against it. Evolve decline is 58.5% in wins
vs 60.5% in losses = **noise**, so a blanket forced-evolve rule is NOT
evidence-backed. It is justified only for Punk-Up-style acceleration the
evaluator cannot see, which Alakazam does not have.

### Audit status (2026-07-19)

| area | state |
|---|---|
| Deployment V1–V6 | hardened; verified from shipped tarball |
| Belief identification | **confirmed live** (grimmsnarl 90%, ep 86900376) |
| Dig-when-benchless | fixed + verified |
| Evolve priority | already maximal in search; decline NOT proven harmful |
| **Energy development** | **UNEXPLAINED — chase this** |
| `agent/mcts.py` | **STALE HAZARD** — lacks every guard; already caused one bad test (resolved AGENT_DIR to it, returned a 0-card deck). Delete or rename. |

---

## 6i. CODE AUDIT 2026-07-19 (rev 7) — the evaluator is the whole agent

Full audit of the decision core (main.py + mcts.py). Logs:
`agent/_ab_audit_fixes.log`, `agent/_ab_audit_racebug.log`.

### The structural finding: this is not really an MCTS

Measured, n=4021 rollouts: **96% hit the depth cap, only 3.9% ever reached a
real win/loss.** The 24-step cap advanced a mean of **2.85 turns** (n=2995),
because `_competent_choice` exhausts every EVOLVE/PLAY/ATTACH/ABILITY before
attacking and development re-presents the MAIN menu.

So the backed-up value is `0.6*_hand_eval(t+3) + 0.4*_hand_eval(t)` — **hand_eval
on both sides of the blend.** PIMC, the belief system, the determinizer and the
archetype identification all ultimately deliver a 5-term linear evaluator applied
~3 turns out. **Tuning `_hand_eval` is tuning the agent.**

### D1 — energy was ~20x below the search's resolution (FIXED)

At weight 0.10/6, one attach moved the leaf value **0.0167** against a measured
leaf sigma of **0.325** → **SNR 0.051**, needing ~380 sims/option; we run 12–48.
**The agent could not see energy at all.** That resolves §6h's open defect and
explains the contradiction (we decline *fewer* attaches than Luca yet develop at
1/4 the rate) — our attach decisions were noise, not policy.
Fixed: weight 0.10→0.30, divisor 6→3. SNR 0.051 → **0.261**.

### D2 — REFUTED MY OWN FIX. Deeper rollouts are a losing trade

Deepening the horizon to catch more terminals is the obvious move and it is
WRONG at this budget — a longer rollout costs simulations one-for-one:

| turns | rollouts/decision | terminal % | effective energy resolution |
|---|---|---|---|
| 3 | 163.2 | 0.3% | **4.64** |
| 5 | 81.5 | 1.8% | 2.84 |
| 10 | 45.6 | 3.7% | 1.95 |

(resolution = per-rollout SNR x sqrt(n)). The old flat 24-step cap sat at ~2.85
turns — **near-optimal by accident**. Kept the turn-based formulation (principled,
predictable) at `_ROLLOUT_TURNS = 3`. Net behaviour ~unchanged.

### D3 — no damage-race term; and the printed-damage trap (IMPORTANT)

`_hand_eval` had prize/bench/hp/energy/fragility and **no term for "can I
actually break through this body"** — so chipping 30 off a 320 HP ex scored as
progress. That is the 1W–5L vs 300+ HP shape. Added `_race_term` (hits-to-KO
each way, charge time included).

**But it caused a 16-point regression first, and the reason is a PRE-EXISTING
defect worth more than the fix:** this codebase ranks attacks by **printed
damage** everywhere — `_attack_damage`, `_anti_dominated`, `_expansion_priority`,
`_find_lethal` ordering, `_est_damage`. **Alakazam's `Powerful Hand` is printed 0**
(2 counters per card in hand) and **Fezandipiti ex's `Cruel Arrow` is printed 0**
(does 100). The race term read our own win conditions as "deals 0 damage",
pinned itself at −1.0 all game, and A/B'd at **33% (9W–18L, n=27)**.
Fixed via `_has_scaling_attack()` → the term ABSTAINS when damage is not
readable from the printed number. **A confidently wrong term is far worse than
an absent one.**
⚠️ The same blindness still mis-ORDERS attacks elsewhere (`_anti_dominated` would
pick a printed-30 Super Psy Bolt over a lethal Powerful Hand). `_find_lethal` is
safe — it steps the engine — but the ranking paths are not. **OPEN.**

### D4–D8 (mechanical, fixed, no behavioural risk)

| id | defect | fix |
|---|---|---|
| D4 | `_loses_immediately` counted `losses >= max(1,worlds)` but `continue`d past failed worlds → **one engine hiccup silently disabled the blunder veto** | count over worlds that actually probed |
| D5 | `if action and ...` sent every deliberate empty/pass return to the random fallback | `action is not None`, + minCount/maxCount check |
| D6 | `_last_turn` not cleared in `_reset_game()` → spurious second reset each game | cleared |
| D7 | `_BANK_TOTAL` hardcoded 600.0; never read `remainingOverageTime` | `_observe_bank()` prefers the harness's number |
| D8 | stale `agent/mcts.py` | renamed `agent/_stale_mcts.py.disabled` |

### A/B RESULT: fixes are win-rate NEUTRAL

Fixed vs pre-fix tarball (`submission_alakazam_ctrl`), PTCG_BUDGET=0.15, seed 3:
**39W–41L = 48.75% (n=80, full run).** Readings along the way: 53% (n=15),
57% (n=28), 52% (n=42), 50% (n=70), 48.75% (n=80) — more evidence for the §0
lesson: **never trust an arena run under n=60**, and read the FINAL tally, not
an interim one (an interim 50.0% at n=70 was reported before the run finished).

Honest read: D4–D8 are correct regardless. D1/D3 provably change what the search
can SEE (5x SNR) but produce **no detectable win-rate change**, and per §0 a +5%
effect needs ~1500 games/arm to detect — so "neutral at n=70" does NOT mean
"worthless". It means unmeasured. Do not claim these as a gain.

---

## 6j. FEATURE LABORATORY 2026-07-20 (rev 8) — method, and two instrument bugs

`_hand_eval` is the agent's objective (§6i), so it is now treated as a feature
laboratory: **one feature per experiment, isolated behind its own switch.**
Bundling five weight changes with one new term produced an unattributable
16-point regression that had to be unpicked by hand. Never again.

Switches live at the top of mcts.py (`DECK_TERM_W`, env `PTCG_W_DECK`). Control
arms are a full package copy with the weight forced to 0.0 (`submission_deck0/`)
so the two directories differ in exactly one constant.

### ⚠️ INSTRUMENT BUG 1 — the action-flip test needs a NULL CONTROL

Proposed method (good): don't just check the eval moves, check the ACTION moves.
Run each real decision twice from an identical RNG state, term ON vs OFF, count
how often the chosen action differs. A feature can improve the number and never
change a move.

First result looked strong: **39.7% action flips.** It was meaningless.
* Every flip occurred at deck>=12, where the term is EXACTLY 0.0 by
  construction. A term contributing nothing cannot flip anything.
* **Null control (both arms W=0.0, identical config): 42.3% flips.**

**ALWAYS RUN THE NULL CONTROL.** Without it this would have been read as a
strong positive and shipped.

### ⚠️ FINDING — the policy is ~40% NONDETERMINISTIC

The null control is the finding: **asked the same question twice, the agent picks
a different move ~40% of the time.** Not just wall-clock (it persists with a
non-binding deadline, `time_budget_s=1e6`, fixed `max_worlds`) — it is engine
state carried across `search_begin`/`search_end`.

Consequences, both large:
1. The action-flip test is **unusable** until this is fixed — its noise floor
   (42%) swamps any plausible feature effect.
2. It inflates variance in **every arena A/B we have ever run**, and is a strong
   candidate for why n=80 cannot resolve anything. **Fixing this may be worth
   more than the next five features**, because it makes every later experiment
   cheaper.

### Deck-count feature — STAGE 1 PASS, A/B IN PROGRESS

`_deckout_urgency(n)`: 0 while deck >= 12, rising linearly to 1 at empty.
`deck_term = urgency(opp) - urgency(me)`, weight 0.20. Chosen as the first
experiment because `deckCount` is a scalar the observation carries directly --
unlike a damage model it **cannot be confidently wrong** (the §6i failure mode).

STAGE 1 (paired states, identical but for deckCount): direction CORRECT, gap
**+0.117** for deck 30 vs 5 -- larger than a whole prize (0.075) and 7x the
energy term. PASS.

Opportunity rate (25 COMPLETE games): **24% of decisions have deck<12; 24/25
games reach it**, mean minimum 1.2 cards. NB an earlier read of "207/209
decisions at deck>=12" was WRONG -- those games were truncated at 120 decisions
and never reached the late game. Measure on complete games.

**A/B IN PROGRESS** (`submission_alakazam` W=0.20 vs `submission_deck0` W=0.0).
Interim main run **24W-36L (40.0%) at n=60 -- NOT A RESULT, do not cite.**
Pooling with 5 disjoint-seed shards (21-25) for n~270.
Logs: `agent/_ab_deck*.log`.

### Corrected feature table

"Tested" means A/B'd IN ISOLATION. Most of the existing terms have never been.

| feature | observable? | can be *wrong*? | isolated A/B? | effect | keep |
|---|---|---|---|---|---|
| prize / bench / HP | yes | no | **NO — never isolated** | unknown | yes (original) |
| energy count | yes | no | no (bundled) | unknown; SNR 0.051 -> 0.261 | yes |
| race term | **parsed** | **YES — was** | bundled | **0** (bug cost 16, fix restored baseline) | yes |
| deck count | yes | no | **running** | ? | ? |
| hand / card advantage | yes (`handCount`) | no | pending | ? | ? |
| tempo | yes (turn) | no | pending | ? | ? |
| evolution potential | inferred | medium | pending | ? | ? |
| energy persistence | inferred | medium | pending | ? | ? |

**The race term did NOT gain +16.** The bug cost 16; fixing it returned to
baseline. Net isolated effect 0. Recording it as +16 would make a neutral
feature look like our best one.

**Lesson from §6i, generalised: FACTS are worth ~16 points, WEIGHTS ~0.** A term
reporting something false steers the search confidently wrong; a term merely
underweighted is ignored. So every new feature needs an explicit ABSTAIN path
for states it cannot read (cf. `_has_scaling_attack`), and coefficient tuning is
low-yield.

### Tooling — arena is now ~6x faster

`vs_external.py` plays games in a strict sequential loop on a 12-core box: we
were using **1 core**. Run N disjoint-seed shards in parallel and pool:

    for s in 21 22 23 24 25; do (PTCG_BUDGET=0.15 python agent/vs_external.py \
      A B --n 30 --seed $s > /tmp/ab_s$s.log 2>&1 &) ; done

Per-game time barely moved (43s -> 48s), confirming we were CPU-idle. Effective
throughput ~7.7s/game. **A feature test now costs ~20 min instead of ~90.**

### Process notes

* `pkill` kills the inner python but NOT the harness-tracked shell — use
  `TaskStop` on the task id. Four orphaned tasks accumulated this way.
* Never `until grep -q SENTINEL <log>` on a run you might kill: the sentinel is
  never written and the waiter spins forever. Bound every wait.
* Copy a log to `agent/` only AFTER confirming its `HEAD-TO-HEAD` line exists.
  A result was misreported as 50.0% (n=70) from a log copied before the run
  finished; the true final was 48.75% (n=80).

---

## 6k. D9 — A THIRD OF OUR OWN DECK WAS JUNK (rev 9, 2026-07-20)

**The most consequential defect found in the audit, and it was silent.**

`observer.my_remaining_deck()` subtracted a CUMULATIVE `_my_cards_left_deck` set
built from DRAW/MOVE_CARD logs, removing a serial only on an explicit
`toArea == 1`. But a **MULLIGAN** -- and any hand-shuffle effect (Iono, Marnie) --
returns the hand to the deck with **no per-card log**. Those serials stayed
"gone" forever.

Measured: **14 serials tracked as gone when only 7 cards had left the deck**,
growing all game. The determinizer then padded our OWN hidden zone with
untracked filler in **98.7% of worlds, mean 19.8 cards, max 33** -- i.e. a THIRD
of our simulated deck was inert junk, so every rollout drew cards that do
nothing. Prime suspect for the §6h energy-development gap.

**It never raised an error.** `search_begin` accepted 900/900 worlds before AND
after. It corrupted the CONTENT of the search, not its validity -- which is why
no amount of crash-hunting would ever have found it. Only instrumenting the
determinizer's own flags exposed it.

FIX: recompute from visible zones instead of accumulating --
`my_deck - hand - discard - board - stadium - looking - preEvolution stacks`.
Self-correcting; a missed log event can no longer compound.

| stage | our-deck padding | residual |
|---|---|---|
| before | **98.7%** | -20 cards |
| recompute from zones | 5.1% | -1..-2 |
| + stadium / looking (they live on STATE, not player) | 5.1% | -1..-2 |
| + preEvolution stacks (only the TOP card carries `id`) | **0.4%** | ±1 |

### FINAL A/B RESULTS -- every isolated test came back INCONCLUSIVE

| change | result | n | 95% CI |
|---|---|---|---|
| audit fixes D1-D8 bundle | 48.75% | 80 | — |
| deck-out term | 46.3% | 270 | [40.3, 52.2] |
| effective-damage ranking | 52.2% | 180 | [44.9, 59.5] |
| **observer fix (D9)** | **50.4%** | **240** | [44.1, 56.7] |

Logs: `agent/ablogs/`. Viewer: `.\ablog.ps1 [filter] [-Watch]`.

**Five isolated A/Bs, five inconclusive -- including a bug that made a third of
our deck inert.** Two readings, not yet separable:
1. **Mirror self-play is the wrong instrument.** Both arms play the SAME deck, so
   symmetric corruption cancels. The real loss shape (1W-5L vs 300+ HP, 5W-1L
   below) CANNOT be measured in a mirror.
2. The evaluator dominates so completely (96% of rollouts scored by `_hand_eval`,
   §6i) that rollout CONTENT barely matters.

Either way the action is the same: **stop measuring in the mirror; ship
correctness fixes and let the ladder measure.**

### Sizing: we were under-sampling, not under-powered

Paired/common-random-number testing is IMPOSSIBLE -- `random.seed()` does not
control the engine (verified: same seed -> different opening hands; cg has its
own internal RNG, no seed parameter). So brute force is the only lever:

| effect to resolve | games needed | wall @7.7s/g | @3.9s/g (12 cores) |
|---|---|---|---|
| 10% | 97 | 0.2 h | 0.1 h |
| 5% | 385 | 0.8 h | 0.4 h |
| **3%** | **1068** | 2.3 h | **1.2 h** |
| 2% | 2401 | 5.1 h | 2.6 h |

**A 200-game test can only see a ~7% effect.** No single evaluator term is worth
7%, so those tests were guaranteed to return "inconclusive". Either run ~1000
games or do not run the test.

### Still open

* `no_concrete_hypothesis` fires in **28%** of determinizations -- over a quarter
  of worlds have NO concrete opponent deck and use pure filler. Traces to the 5
  unidentified decklists (§6d). Refreshing `decks_pool.py` is worth real win
  rate, not tidiness.
* Archetype identification **works as a classifier** (42.6% prior -> 92.5% at 5
  revealed cards; ~8.5 cards revealed by turn 2) but has **never been A/B'd**.
  `PTCG_NO_ARCHETYPE` already exists as a control switch.
* `_effective_damage` mis-reads bench-targeting attacks (`Pinpoint Dive`, "60
  damage to a BENCHED Pokemon") as damage to the active. Second-order --
  `_anti_dominated` only fires versus END and any attack beats END. A naive
  "benched" guard would break `Cruel Arrow`, whose text mentions Benched only in
  a weakness parenthetical. Left deliberately unfixed.

### Tooling gotcha

`ablog.ps1` shipped broken first: **PowerShell variables are CASE-INSENSITIVE**,
so `$W += $w` compiles to `$w = $w + $w` -- every per-shard number doubled and
the pooled line showed only the last shard. It printed clean, plausible output.
Renamed to `$totW`/`$gw`. Same lesson as the whole session: **the wrong answer
looks exactly like the right one.**

---

## 6l. v4 LADDER LOSSES 2026-07-20 (rev 10) — NOT FIXED, and why

First two real-ladder episodes of **v4** (submission 54839296, Alakazam).
Replays/logs in `newloss_v4/`. **Both losses. Both BOARD WIPES.**

### Deployment is CLEAN — rule this out first, every time

`SELFCHECK PASS`, **0 FALLBACK**, `AGENT_DIR=/kaggle_simulations/agent`,
decisions 1.0-2.0s (real search; the fallback signature is ~26ms), 13s of the
600s bank used. The D9 observer rewrite did not break deployment.

### The two games

| | ep 86961085 | ep 86962694 |
|---|---|---|
| outcome | board wipe, turn 5 | board wipe, turn 3 |
| opponent | 340 HP | 330 HP Mega Starmie ex |
| **our max energy** | **1** | **0** |
| our max bench | 2 | 1 |
| prizes they needed | 2 | **1** |
| Poffin passed? | **YES, turn 1** | no |

**ep 86961085 turn 1 (st8)**: bench 1/5, hand held `Buddy-Buddy Poffin` offered
as PLAY option 0 -- and the search chose **END**. Opponent went to 4 benched
that same turn. -> new rule `_develop_before_end` (below).

### ⚠️ ANSWER: NO, WE HAVE NOT FIXED IT

Replaying BOTH games' decisions through v5's rule stack:

| episode | decisions checked | CHANGED by v5 |
|---|---|---|
| 86961085 | 23 | **1** (END -> Poffin) |
| 86962694 | 8 | **0** |

**31 decisions, 1 changed.** And even that one probably does not win the game --
two extra Basics does not fix 0-1 energy against a 340 HP body.

Nine real defects were fixed today (§6i, §6k). **The codebase is meaningfully
more correct; the agent is probably not meaningfully stronger.** Every isolated
A/B came back neutral because none of them addressed the actual cause.

**THE CAUSE IS UNCHANGED SINCE §6h: WE DO NOT DEVELOP ENERGY, SO WE CANNOT
DAMAGE 300+ HP BODIES.** Both losses are exactly that.

### What the measurements RULED OUT (do not re-litigate)

* **Not a deck-construction error.** Our `deck.csv` is **byte-identical** to the
  alakazam list mined from Majkel/Yushin's replays (verified by set-compare).
  9 Basics (4x Abra 50HP, 3x Dunsparce 70HP, Fezandipiti ex 210, Shaymin 80);
  P(no Basic in 7 cards) = **30%**. They win with this list. It is the archetype,
  not a botched reconstruction.
* **We do NOT decline to bench Basics.** Decisions with bench-not-full AND a
  Basic playable from hand: **2, passed on 0**. The bench is thin because we
  never HOLD Basics -- which is why Poffin (deck-search-to-bench) is the lever.
* **We do NOT systematically decline attaches.** END-with-ATTACH-available: 1 of
  9. n=9, and it contradicts the §6h measurement that we decline FEWER attaches
  than Luca (55.9% vs 76.1%). Do not build a rule on this.

### New rule: `_develop_before_end` (`PTCG_DEVELOP_END=0` to disable)

Never END with an unfull bench while holding a card that searches Basics ONTO
the bench (Poffin, Hop's Bag; 7 such cards in the DB). Strictly dominated --
a free Item converting deck Basics into board presence cannot be worse than
passing. Deliberately NOT a general "never pass while holding cards" rule, which
would be confidently wrong for situational cards.

**Honest scope: fires in 1 of 20 such decisions across available replays.
A correctness fix, NOT a win-rate lever.**

⚠️ **It shipped SILENTLY DEAD first.** I compared occupied bench against
`len(me.bench)` -- but that list holds only OCCUPIED slots, so a 1/5 bench read
as "full" and the rule never fired. Capacity is **`benchMax`**. It compiled, ran,
and did nothing; only replaying the real losing state caught it.

### ⚠️ R2 RE-LEARNED THE HARD WAY

ep 86962694's final frame for our seat showed "70 HP active, bench 1, 11 cards in
hand" -- which reads as *lost with a healthy board*, i.e. a harness failure. That
is a **stale INACTIVE frame**: the harness repeats our last observation during
the opponent's turn, so our view was frozen at turn 2 while the game moved on.
The opponent's LIVE frames showed the truth (active KO'd, bench 0, board wipe).

**ALWAYS read board state from frames where `status == ACTIVE` for that seat.**
This is refutation R2 in §6e and it was walked into again.

Also: `info.Agents[].submissionId` is **None** in these replays -- our seat is not
labelled and it ALTERNATES. Identify it by matching visible hand cards against
our own decklist (both episodes scored ~±200, unambiguous).

---

## 6m. v4 AT n=46 + THE DECK-vs-PILOT EXPERIMENT (rev 11, 2026-07-20)

### ⚠️ UNIT-OF-ANALYSIS RULE — READ BEFORE QUOTING ANY METRIC

**Every metric in this file MUST state its unit: per GAME / per TURN / per
DECISION / per SEARCH / per ROLLOUT.** Two separate false discoveries in this
project came from decision-level statistics where turn-level was correct (the
chip-attack analysis in §6e, and "71% evolve decline" below). A player takes
many sub-decisions per turn and the MAIN menu re-presents after every
development action, so per-decision rates systematically inflate "declines".

---

### CONFIRMED (repeatedly supported)

| finding | unit | n | value |
|---|---|---|---|
| **We are 30% vs 300+ HP decks**, 62-80% otherwise | per game | 46 | 6W-14L |
| **A strong pilot gets 55-57% with OUR EXACT DECK vs 300+ HP** | per game | **599 + 72** | 331W-268L / 41W-31L |
| Loss modes: prize race 12, board wipe 9, deck-out 2 | per game | 23 | — |
| Never getting Alakazam out vs 300+ HP = **0W-6L** | per game | 6 | perfect separation |
| `Powerful Hand` works once assembled: mean hand **12.3** -> **245 dmg**; 18% outright KO a 340 ex | per attack | 119 | — |
| We evolve into Alakazam in **92 of 103 turns** (11% decline) | **per turn** | 103 | — |
| Deployment healthy: SELFCHECK PASS, 0 fallbacks, 1-2s/decision | per episode | 46 | — |

### ⭐ THE DECISIVE EXPERIMENT — deck vs pilot

`agent/pilot_vs_deck.py`. Against 300+ HP archetypes, **with the same Alakazam
list**:

| pilot | record | win rate | n |
|---|---|---|---|
| top player (`top_replays/`) | 331W-268L | **55.3%** | 599 |
| #2/#3 player (`newtop2/`) | 41W-31L | **56.9%** | 72 |
| **our agent v4** | 6W-14L | **30.0%** | 20 |

**gap ~25 points, z=2.42, p~0.015 -> SIGNIFICANT.**

**HYPOTHESIS A (deck limitation) IS REFUTED.** The deck is not at its ceiling.
Two independent strong pilots reach 55-57% exactly where we reach 30%. This is
a PILOT problem. One comparison; it replaces weeks of speculation.

### REFUTED (do not re-run these)

| hypothesis | why it died | n |
|---|---|---|
| "The 300+ HP weakness is the deck" | strong pilots get 55-57% with the same list | 599+72 |
| "We never put Alakazam into play" | 3rd most common Pokemon in play; a 3-game artifact | 46 |
| "We don't develop energy" | **WRONG ARCHETYPE.** This deck runs 7 energy BY DESIGN; `Powerful Hand` costs 1. §6h measured energy against GRIMMSNARL (Punk Up wants 5) and it does not transfer | — |
| "We decline 71% of evolves" | **WRONG UNIT.** 71% per-decision = **11% per TURN** | 103 turns |
| "We play out our hand, weakening Powerful Hand" | mean hand at attack = 12.3 (245 dmg) | 119 |
| "Poffin passes are systematic" | 9 of 287 = 3% | 287 |
| "Deck has only 2 energy" | `cardType==5` MISSES Special Energy; real count is 7 | — |
| "body_term (absolute board HP) will fix evolve declines" | makes evolution visible (was literally invisible: Abra and Kadabra both scored -0.6000) but **NO behavioural effect**, 47% vs 44% over 64 paired trials | 64 |

### ⚠️ STRUCTURAL LIMIT ON EVALUATOR TERMS

`_DEVELOP_PRIORITY` puts **EVOLVE first** in the rollout policy, so both the
evolve-now and decline-now branches reach evolved leaves and any leaf term for
that action **washes out**. **Generalisation: a leaf-evaluator term for an
action the rollout policy also takes cannot change behaviour.** This is the best
available explanation for why five isolated A/Bs (§6j, §6k) all returned
neutral -- better than "n was too small". Fixes must be RULES or ROLLOUT-POLICY
changes, not evaluator weights.

### OPEN

1. **Is the 300+ HP weakness strategic or evaluative?** Deck is ruled out. Two
   live candidates:
   * **B — strategic weakness**: Boss's Orders timing, prize mapping, target
     prioritisation, bench pressure, resource conservation, sacrificial
     sequencing. None of these surface as "declined evolve"-style bugs.
   * **C — evaluation blind spot**: locally sensible play that misjudges
     long-term prize trades. Produces exactly "loses the prize race" with no
     silly individual decisions -- which is what 12 of 23 losses look like.
2. **Does the value function mis-evaluate prize trades vs bulky decks?**
   Alakazam is NOT an ex (140 HP, 1 prize); their 340 HP ex gives 2. That trade
   should favour us and evidently does not. `_hand_eval`'s prize_term counts
   prizes taken, NOT the prize VALUE of what is being traded.
3. **How does the top player's ACTION DISTRIBUTION differ from ours in the 300+
   matchup specifically?** We have 599 of their games and 20 of ours. Compare
   Boss's Orders usage, retreat rate, attack target choice, turn of first
   Alakazam. This is the obvious next experiment and the data already exists.

**Do NOT let "no obvious bug remains" become "nothing left to improve."** The
achievement of this pass is eliminating attractive wrong explanations; the
remaining gap is 25 points and is a piloting gap.

### v4 ladder status

Score **629.5 at n=46** (was 476 at n=2; trevenant 54832367 sits at 722.3).
v4 is BELOW the trevenant build. Do not over-read: different deck, still
converging.

---

## 6n. THE ABILITY GAP — right diagnosis, WRONG FIX (rev 12, 2026-07-20)

**⭐ THE FIRST STATISTICALLY SIGNIFICANT A/B OF THE PROJECT — AND IT IS NEGATIVE.**
Everything in §6j/§6k was inconclusive. This one is not. Logs: `agent/ablogs/`.

### The diagnosis (STANDS — measured against 599 top-player games)

`agent/compare_pilot.py`. Same deck (alakazam), same matchup (opponent max HP
>= 300). **UNIT: per TURN.**

| metric | top player | us (v4) |
|---|---|---|
| **ability used WHEN LEGAL** | **88%** | **61%** |
| hand size T3 / T4 / T5 | 7.9 / 9.3 / 10.3 | 6.1 / 6.5 / 7.0 |
| **first Alakazam in play** | **turn 4.7** | **turn 7.9** |
| turns where ATTACK is legal | 77% | 53% |
| attack taken WHEN LEGAL | 92% | 86% |
| evolve / attach / play / Boss / Candy / Poffin | — | **all within 5 pts** |

Everything except abilities matches. Causal chain: skipping abilities costs
~3.3 cards by T5 -> `Powerful Hand` is 20 dmg PER CARD IN HAND, so that is ~66
damage -- AND the missing draws are what assemble Alakazam, which lands 3.2
turns late, which is why ATTACK is only legal in half our turns, which is why we
lose the prize race (12 of 23 losses).

⚠️ The raw "attack per turn" gap looked like **-25.7 points** and reads as "we
are too passive". On the correct denominator (*when attack is legal*) it is
**-6 points**. Same unit trap as §6m. WE ARE NOT DECLINING ATTACKS -- WE ARE
RARELY IN A POSITION TO MAKE ONE.

### The intervention (REFUTED)

`_ability_before_end`: never END with an unused ABILITY legal (guard: bench>=2,
because `Run Away Draw` shuffles Dudunsparce BACK INTO THE DECK). Verified to
fire on all 26 real END-with-ability decisions.

**A/B vs identical control, 10 shards x 40, PTCG_BUDGET=0.15:**

| | record | win rate | 95% CI |
|---|---|---|---|
| ability rule ON | 174W-226L | **43.5%** | **[38.6%, 48.4%]** |

**n=400. Upper bound BELOW 50%. SIGNIFICANTLY WORSE (-6.5 points).**
8 of 10 shards under 50%. Reverted; `ABILITY_BEFORE_END` defaults False.

### WHY the fix failed (the transferable lesson)

**MATCHING A RATE IS NOT MATCHING A POLICY.** The top player uses abilities
EARLY IN THE TURN TO ENABLE OTHER PLAYS (draw -> then use what you drew). We
implemented "use it as the last act before passing" -- the same action at the
worst possible moment, when nothing can follow it. Plus `Run Away Draw` removes
a body we just developed, and board wipes are 9 of 23 losses.

**Do not convert an observed frequency gap into a forced-action rule.** Measure
WHEN and WHY the action is taken, not just HOW OFTEN.

### ⚠️ PROCESS FAILURE — I BUNDLED TWO CHANGES

The A/B contained BOTH the new rule AND `_expansion_priority` ABILITY 150->275.
So the -6.5 points CANNOT be attributed between them. 400 games spent and the
attribution question is still open. Both were reverted.
**ONE VARIABLE PER A/B. NO EXCEPTIONS -- including when the second change looks
"obviously harmless".**

### Shipped configuration after revert

`DEVELOP_BEFORE_END=True`, `EFF_DAMAGE=True`, D9 observer fix IN,
`BODY_TERM_W=0.0`, `DECK_TERM_W=0.0`, `ABILITY_BEFORE_END=False`.

---

## 6o. PROMOTION-AFTER-KO — CLOSED NEGATIVE (rev 13, 2026-07-20)

Full writeup: `research/reports/exp_001_002_promotion.md`. **Do not reopen.**

Real defect confirmed (n=290 promotions): after a KO we choose the highest-HP
body 31% and the LOWEST-HP body 30% -- random on HP. Mean promoted 92 HP vs 134
available. Cause: `_board()` uses hp FRACTIONS, so a full-health 60 HP and a
full-health 150 HP body both score 1.0.

**But the fix and the hypothesis both died in cheap staged checks:**

* **STAGE 1 (behaviour)** — raising `BODY_TERM_W` moved promoted HP the WRONG
  way, monotonically (85.7 -> 77.9 -> 74.5; null control 86.6). `body_term` sums
  maxHp over active+bench, so it is INVARIANT when a Pokemon moves bench->active.
  Downstream it rewards keeping big bodies safe and feeding cheap ones to die.
  Any future attempt must key on **ACTIVE HP**, not board total.
* **STAGE 2 (mechanism)** — vs 300+ HP opponents a 110-159 HP body survives
  **1.29 turns vs 1.50 for a 70-109 HP body**. Extra HP buys ZERO tempo where we
  lose; it helps only vs <300 HP opponents, which we already win.

**~15 minutes of checks; 400 ladder games saved.** Protocol: behaviour check ->
mechanism check -> outcome check, stopping at the first failure.

**Pattern now at 5 independent dead ends** on the 300+ HP matchup: energy ·
evolution · KO capture · attacker uptime · promotion. All symptom-level. The
remaining candidates are structural: deck, or the in-tree opponent model.

---

## 6p. v7 IS WORKING (rev 14, 2026-07-20)

**v7 (54855847) at n=25 episodes: score 927.8. v6 (54851936): 766.4. Δ +161.**

Largest single-submission jump in this project's history. Read cautiously -- n=25
is below the ~40-episode convergence rule -- but the gap is large enough that
noise alone is unlikely to explain it.

### The one change

Between v6 and v7: `REVENGE_FIX` enabled. `Horrifying Revenge` and 176 other DB
attacks with "+N more damage" conditional riders now report their true damage
to the ranking heuristics when the trigger is verifiable (opponent's prize
count rose since our previous decision -- they only gain prizes by KOing our
Pokemon). Was reading 30 instead of 130 for our own win condition.

Offline A/B measured this at 51.4% (n=399, CI [46.5%, 56.3%]) -- inconclusive.
Ladder shows +161 Elo. That gap is coherent: the offline A/B is
Trevenant-vs-Trevenant where both sides misread the same attack; on the ladder
we face different decks where the misread matters asymmetrically.

### Session recap (revised)

Today's session started with v6 at 750 and 14 hypotheses tested, all
inconclusive or worse. The ONE change with a mechanism that survived scrutiny
(revenge fix) was shipped as v7 despite an inconclusive A/B, on the argument
that it corrected a factual error regardless of measured win rate. That call
now looks right.

**Standing lesson:** correctness fixes with a clear mechanism beat every
strategic guess we made this session, even when the offline number was
inconclusive. D9 (mulligan-lost cards), effective damage on Powerful Hand, and
now revenge damage all share this pattern. Strategic rules -- ability forcing,
promotion, deck swaps -- all lost.

### v7 config

`REVENGE_FIX=True`, `EFF_DAMAGE=True`, `DEVELOP_BEFORE_END=True`, D9 observer
fix in, adaptive extension restored. `BODY_TERM_W=0`, `DECK_TERM_W=0`,
`ABILITY_*=False`, `USE_POLICY=False`, `USE_VALUENET=False`.

### Value net (Day 1-2 done, Day 3 running)

`research/policy/` contains a trained MLP value net (40 features, 40->64->32->1).
- 71,178 training rows from 999 top-player replays
- Val MSE 0.70 vs 0.98 baseline; Cohen d +1.26 (both gates passed)
- Runtime latency 24.7 us per evaluate (budget <100)
- 400-game A/B currently running: interim 52.0% at n=125 (uninformative)

Category-policy BC (exp_011) was refuted at -82 Elo -- do not revisit.
Value-head approach is architecturally different (scores leaves, does not
drive actions), which is why it may work where the policy did not.

### Do NOT resubmit yet

v7 has ~15 more episodes to converge. Wait for it. If the value-net A/B lands
positive, build v8 with both changes together; if not, v7 alone is the ship.

---

## 6q. v7 SETTLED, v8 SHIPPED, RULES QUEUE (rev 15, 2026-07-20)

### v7 final: 880.8 at n=61

Settled trajectory: 927 (n=25) -> 886 (n=36) -> 881 (n=61). This is the true
baseline for v8+. **+114 Elo over v6 (766.4) from a single-line correctness
fix** (revenge damage). Largest single-submission jump in project history.

v7 by opponent (n=61):

| threat | record | note |
|---|---|---|
| Mega Lucario ex | 7W-1L (88%) | weak to Psychic -> we double |
| Alakazam | 6W-2L (75%) | we beat expert-piloted Alakazam decks |
| Archaludon ex | 2W-3L (40%) | was 0/8 in v6 -- revenge fix opened it |
| Grimmsnarl ex | 0W-5L (0%) | Dark type, weak to Grass we don't run |
| Dragapult ex | 0W-4L (0%) | Dragon, no weakness at all |

**9 of 26 losses are structural matchup problems** (Grimmsnarl + Dragapult) with
no rule-level fix.

### v7 loss buckets (n=61)

| bucket | count | Rule 1 target? |
|---|---|---|
| matchup-locked (Grimm/Dragapult) | 9 | no |
| promotion-heavy (>=2 mistakes) | 12 | **YES** |
| partial matchup (300+ ex, promo 0-1) | 1 | partial |
| fast disaster (T<=10, 0-1 prizes) | 2 | no (draw luck) |
| other | 2 | investigate |

**74 promotion mistakes across all losses, mean 2.8 per game.** Much bigger
signal than the n=14 sample I was estimating from earlier (3 clean cases). This
is the +Elo lever for v8.

### Rule 1 (v8): Promotion by (maxHp + 30 * energy)

Function `_promote_charged` at `select.context == 4`. Reorders the search's
choice of which benched Pokemon to promote after a KO.

**Score:** `maxHp + 30 * energy_attached`. Rationale:
- Pure `(energy, maxHp)` tuple tried FIRST -- downgraded 140 HP Trevenant to
  60 HP Dunsparce in 19% of cases because +1 energy outranked -80 HP.
- Combined score requires 3+ energy to override a 90 HP gap. Almost never
  triggers a catastrophic downgrade.

**Behaviour check across all traced losses:** 108 changes (down from 110 in
the first version). 95 clear upgrades (HP same or higher), 13 defensible 60/70
HP swaps. Zero catastrophic downgrades. Verified against 5 explicit trace cases
(Hiro Nomo, banana, klog, Lior Toledano, Hibikisato0413).

**Shipped:** `submission_trevenant_v8.tar.gz` -> 54863817. At n=4: 611.2
provisional (2W-2L). Same noise-shape as v6's initial 578 (settled 766) and
v7's initial 927 (settled 881). **Wait ~20 episodes before drawing any read.**

### Rule 5: Preserve last Trevenant (BUILT, NOT SHIPPED)

Function `_preserve_last_trevenant`. Fires only when:
1. Attacking with Hop's Trevenant (id 879)
2. Opponent has 300+ HP body in play
3. This attack does NOT KO the defender (via `_effective_damage`)
4. No other Trevenant on bench or in hand
5. >= 2 Trevenants already in discard

**Action:** override to END the turn -- deliberately breaks `_anti_dominated`'s
"never pass with a legal attack" rule because in this narrow case the attack
costs a Trevenant for chip damage. The last Trevenant + 130 damage is worth
more preserved than spent.

**Behaviour check:** 10 fires in 3618 loss-game decisions (0.28%). Under the
1% target. Fires on the traced games where we spent 3 Trevenants without
KOing the big ex (klog vs Archaludon 400, Nguyen vs Archaludon 400).

**Not shipped** -- waits on v8's real settling. Ordering discipline: attribute
Rule 1 first, then add Rule 5.

### Value net build (Day 1-2 done, Day 3 REFUTED)

Attempted architectural change: replace `_hand_eval` with trained 40->64->32->1
tanh MLP fit to 71,178 (state, outcome) pairs from 999 top-player replays.

Training gates PASSED:
- val MSE 0.70 vs 0.98 baseline (-28%)
- Cohen d (win-state vs loss-state predictions): +1.26
- Runtime latency: 24.7us end-to-end (budget 100us)
- Feature parity training vs runtime: 0.0 diff verified

400-game A/B result: **-82 Elo. Rejected.**

Root cause diagnosis (best guess): value net used as leaf evaluator scores
positions in absolute win-probability terms, but the search backup expects a
value SCALED to rollout reward. Wrong scaling propagates through UCT selection
and destroys the tree's ability to compare siblings. This is a signal-shape
mismatch, not a training-quality issue -- the network learned real signal
(passed both gates) but the plumbing was wrong.

Would need proper integration into the rollout backup, not just static
replacement, to make a value net work here. Documented for future revisiting.

### Rules queue (evidence-ordered, post-v8)

| # | rule | evidence | status |
|---|---|---|---|
| 1 | promotion (maxHp + 30*energy) | 12/26 losses, 74 mistakes | **v8 shipped** |
| 5 | preserve last Trevenant | 3-4 losses (klog, Shoto, Nguyen) | **built, shelf** |
| 2 | bench refill before END | ~1-2 losses (Lior) | not built |
| 3 | KO capture on any opponent | 2-3 losses (banana, klog) | not built |

**Realistic terminal from rules-only work: 920-950 (rank 35-45).**
Grimmsnarl + Dragapult account for 9 of 26 losses at n=61 and are structural.
No rule I've proposed touches them.

### Key architectural findings from this arc

**1. Mirror-vs-ladder asymmetry.** Correctness fixes (revenge, promotion) measure
neutral/inconclusive offline in mirror A/Bs because both sides misread the same
signal. On ladder, only WE misread. Revenge fix: measured +10 offline, +161 on
ladder. New shipping rule: correctness fixes with a real mechanism ship even
when offline is inconclusive.

**2. Grimmsnarl is not a Trevenant-decksplash-fixable matchup.** Grimmsnarl ex
does 180 dmg for 2 energy, one-shotting our 140 HP Trevenant. Our Trevenant
Revenge with all stackers does 190. Two Revenges = 380 vs Grimmsnarl's 320 --
requires we not die once, which we do. Only Grass attackers double against
Grimmsnarl, no Stage-1 Grass card fits our energy curve.

**3. Fairy Zone (Lillie's Clefairy ex) is engine-implemented.** Verified via
damage measurement: 2.10 ratio for damage to Dragon Pokemon with vs without
Clefairy in play (n=50 games). Would flip Dragapult's weakness to Psychic.
But 0/190 expert Alakazam decks use it -- strong signal against.
Not adopted.

**4. Grimmsnarl deck in our agent's hands: 31.5% (n=1000, §6h).** Already
tested. The deck's requirements (Stage 2 chain, Punk Up energy acceleration,
Rare Candy planning) all sit in our agent's blind spots. Switching to
Grimmsnarl would drop us from 57% to ~32%, or roughly -200 Elo.

### Current state summary

- **v7 (54855847):** 881 at n=61, live
- **v8 (54863817):** 611 provisional at n=4, live
- **Baseline:** 881
- **v8 verdict window:** ~n=20-40 episodes from now
- **Rule 5 status:** built, verified, shelf until v8 resolves
- **Rules 2/3:** designed, not built

---

## 7. Next steps (evidence-ordered)

0. **DECK CHOICE IS THE OPEN QUESTION — see §6g.** Select on **damage per
   energy at 1-2 cost**, not HP. Our Corner is 30 dmg/energy vs the #1's ~230.
   **Do NOT ship Grimmsnarl** — Punk Up's 5 energy makes it the ideal target for
   the #1's Alakazam `Psychic` (scales off the DEFENDER's energy).
1. **If a Punk Up deck is ever used anyway: force EVOLVE priority first.** We
   decline 58-60% of evolves; each declined evolve there = 5 energy lost.
1. **Finish the clean Grimmsnarl curve test** — `submission_grimm/` (separate
   package so deck.csv can never collide with the shipping build again),
   `PTCG_CURVES=agent/_curves_grimm2.json`. Question: does OUR agent develop a
   320 HP body like Luca does, or stay flat at ~0.8 energy?
   NOTE an earlier run was invalidated by editing deck.csv mid-run — never
   test two decks out of one package directory.

2. **Explain the Grimmsnarl 33/42/37.5% gap** before shipping that package.
   Echoes the Lucario mirror (31.5% on the reference agent's own deck). Two
   independent signals that our piloting, not our list, is the limit.

1. **Refresh the 5 unidentified lists** (§6d) — highest-value, lowest-effort item:
   pure data, no code, directly raises the 15/20 lock-on rate.
2. **Meta-counter read** — repo1's proven playbook. Mine the current top-20
   submissions for the live archetype distribution and ship its counter.
   (Tooling already exists: `top_replays/download_all.sh`.)
   NB: 1200 real games showed **no rock-paper-scissors cycle** — Grimmsnarl beats
   everything measured (66%), so "bring the best deck" > "counter the meta".
   Deck is now Luca's Grimmsnarl list (60 cards, 10 energy, 10 basics, verified).
3. **Opponent model as the in-tree policy** — the single biggest measured jump
   this project (random → competent = 0.20 → 0.60); using a real ~950-Elo engine
   (`_opp_lb950`/`strong_800`) or a model fit to the 1000 replays should beat our
   hand-written stub. Errors average out over rollouts, so it needn't be accurate.
4. **Card-identity representation** (attribute + text embeddings, Set-Transformer
   at the *root* only, distilled to the in-tree MLPs) — the diagnosed fix for the
   policy net. Latency budget: policy fires at every node expansion, so in-tree
   models must stay µs-scale.
5. **Do NOT** chase small Elo deltas via submissions (variance 600–955), grind BC
   accuracy in isolation, or scale self-play (both repos: gate failed).
