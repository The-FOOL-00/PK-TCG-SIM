# Sanjay's current submission — what actually changed

**Report only. Nothing built, nothing changed, nothing submitted.**

---

# STEP 1 — identifying the submission

Team submission history pulled via the Kaggle API (`pokemon-tcg-ai-battle`,
**not** `…-challenge-simulation` — the wrong slug is what caused earlier 403s
in this project, not a credentials problem).

| id | filename | uploaded | score | episodes |
|---|---|---|---|---|
| 55062389 | `submission_archaludon_v1.tar.gz` | 2026-07-28 18:28 | 745.4 | 60, 33W-28L |
| **55082948** | **`submission_archaludon_v2.tar.gz`** | **2026-07-29 13:18** | **807.2** | **69, 39W-31L** |
| 55084706 | `submission_archaludon_v3.tar.gz` | 2026-07-29 14:30 | 698.9 | 58, 35W-24L |

**The jump is v2 (55082948), 807.2.** v3 is newer and *lower* (698.9) — the
description ("4× Jumbo Ice Cream + Hand Trimmer…") indicates a deck change, and
it did not repeat v2's score.

**Current active pair for the team** (Kaggle's last-2-uploads rule is
team-wide): the two most recent uploads overall are **v3 (07-29 14:30)** and
**v2 (07-29 13:18)** — both Sanjay's. Our most recent upload
(`v1_grimm_seq_e1e2`, 07-28 05:55) is currently **displaced**, not active.

---

# STEP 2 — bundle access

**The team API does not expose teammate submission downloads** (both
`/competitions/submissions/download/{id}` and the per-competition variant
returned `404`). Sanjay supplied `submission_archaludon_v2.tar.gz` and
`submission_archaludon_v3.tar.gz` directly, placed in the repo root; both were
extracted and read.

## Bundle contents (identical structure, both versions)

```
main.py  deck.csv  archaludon_deck.csv (identical to deck.csv)  FROZEN.json  cg/*
```

`FROZEN.json` is **stale metadata** left over from an earlier baseline
(`baseline_trevenant_v6`, frozen 2026-07-20, `ladder_submission: 54851936`) —
it does not describe the current tree and should not be read as current.

**`main.py` is byte-identical between v2 and v3.** The only difference between
the two uploads is `deck.csv`.

## Deck — Archaludon ex / Cinderace (Metal)

**v2 (807.2), 15 unique cards:**

| n | id | card |
|---|---|---|
| 11 | 8 | Basic {M} Energy |
| 4 | 169 / 190 / 666 | Duraludon / **Archaludon ex** / Cinderace |
| 4 | 1121 / 1122 / 1147 / 1152 | Ultra Ball / Pokégear 3.0 / Jumbo Ice Cream / Poké Pad |
| 4 | 1182 / 1185 / 1227 | Boss's Orders / Explorer's Guidance / Lillie's Determination |
| 4 | 1244 | Full Metal Lab |
| 3 | 1097 | Night Stretcher |
| 1 | 57 / 1159 | Relicanth / Hero's Cape |

**v3 (698.9)** cuts one copy each of Archaludon ex and Cinderace (4→3) and adds
2× **Hand Trimmer** (1087, new), 1× non-ex **Archaludon** (170), 1×
**Psyduck** (858), plus 1× Larry's Skill and 1× Black Belt's Training —
thinning the core attacker count for a broader consistency/tech package. Both
validate cleanly against `card_data.json` (all 20 card ids in v3 resolve; no
unconstructible card).

## vs every deck we have tested

| deck | our closure (self-play, DECK_SWEEP.md) | shares with Archaludon? |
|---|---|---|
| Grimmsnarl | 79.9% | — |
| Garchomp | 53.1% | — |
| TR Mewtwo | 48.9% | — |
| Kangaskhan | 45.0% | — |
| Fezandipiti | 40.5% | — |

**No overlap.** Archaludon ex / Cinderace is a deck we have never tested, on
either agent.

## SEARCH / PILOT / BC — separate codebase, confirmed

| flag/mechanism | present? |
|---|---|
| `SEARCH`, `PILOT`, `BC`, `GOVERNOR` (our names) | **no — none of our flags exist in this file** |
| `search_begin` / `search_step` / MCTS / rollout / determinization | **grepped: zero occurrences** |
| decision-time budget / governor | **none found** — no budget check, no time-based degradation |

His own docstring states it plainly: *"Score-based greedy option ranking (no
MCTS)."* Confirmed by absence of any search API call and by measured decision
speed (Step 3). **This is a separate codebase**, not a fork of ours — different
`main.py` entirely, own `cg/` copy, own scoring architecture built from
`SelectContext`/`OptionType` primitives with per-card and per-matchup logic
(`detect_matchup`, `apply_overrides`, 4 named `_v2_ov_*` override functions).

---

# STEP 3 — behavioural profile from replays

69 episodes for v2 (55082948), all fetched (replays + agent logs). Same
methodology as everywhere else in this project: turn/prize/attack extraction
from the `visualize` transcript, seat resolved via the episode index (not
`info.TeamNames`, which is unreliable for this too).

| counter | **Sanjay v2 (807.2)** | Sanjay v3 (698.9) |
|---|---|---|
| decision speed, median | **0.43 ms** | — |
| decision speed, p99 / max | 127 ms / 287 ms | — |
| own turns / game | **6.17** | 7.34 |
| **prize velocity** | **0.4718** | 0.3662 |
| prizes / game | 2.91 | 2.69 |
| attack-when-legal / turn | 64.9% | 53.6% |
| attack share / turn | 55.2% | 41.5% |
| **first attack turn** | **2.78** | 3.50 |
| first evolution turn | 5.28 | 6.10 |
| turn of first prize | 6.87 | 8.79 |
| actions-before-attack | 3.62 | 3.32 |
| turns using ability (of attacking turns) | 0.0% | 0.0% |
| record, this profile | 39W-31L, n=69 | 35W-24L, n=58 |

## The 0%-ability figure is structural, not a design gap — checked directly

Ability options **do appear** on his menus (326/3328 MAIN decisions, 9.8%).
The only MAIN-selectable ability in this deck is Archaludon ex's **Assemble
Alloy** — *"When you play this Pokémon from your hand to evolve… you may
attach up to 2 Basic {M} Energy from your discard."* This fires **at the
moment of evolving**, and the engine's standard rule (a Pokémon cannot attack
the turn it evolved) makes ability-use and attacking **mutually exclusive by
game rule** for this specific card, not by agent choice. Comparing this figure
to our E2 finding (ability-turns 59.5% → 89.5%) would be invalid — his deck's
one ability is structurally incompatible with same-turn attacking; ours
(Munkidori's repeatable damage-shift) is not.

Separately, in `score_option`, `OptionType.ABILITY` has **no dispatch entry**
and falls through to a flat score of `1` — just above `END` (0), and far below
`ATTACK` (raw damage value, 30–260). So even when legal, his ability would lose
to any attack outright by score. This is the opposite polarity from our E2, and
it does not need to be otherwise: it is *never* offered alongside a legal
attack in the first place.

## Opponent archetypes faced (v2, n=69)

| opponent | n | W-L |
|---|---|---|
| Dudunsparce / Alakazam | 12 | 6-6 |
| Fezandipiti / Dudunsparce | 11 | 5-6 |
| **Archaludon / Cinderace (mirror)** | 10 | 5-5 |
| Marnie's Grimmsnarl / Munkidori | 10 | 6-4 |
| Mega Lucario / Hariyama | 7 | 5-2 |
| *(11 more archetypes, n≤4 each)* | 19 | 12-7 |

Mirror exposure 14.5% (10/69) — a genuinely mixed field, not a soft schedule.

---

# STEP 4 — the comparison that matters

## Full table, ladder-vs-ladder where possible (self-play flagged explicitly)

| | **Sanjay v2 (807.2, ladder n=69)** | our C0 self-play (0.4762) | our C2 self-play (0.4797) | **our C0-equiv ladder** `v1_grimmsnarl` (currently 440.5, n=43) | **our C2 ladder** `v1_grimm_seq_e1e2` (currently 482.5, n=38) | **v2.2.0-class BC ladder** (n=52, this resub 495.5) |
|---|---|---|---|---|---|---|
| **prize velocity** | **0.4718** | 0.4762 *(self-play)* | 0.4797 *(self-play)* | 0.3069 | **0.3922** | 0.2281 |
| own turns/game | 6.17 | 7.36 *(self-play)* | 7.38 *(self-play)* | 6.74 | 7.45 | 8.77 |
| attack-when-legal | 64.9% | 88.9% *(self-play)* | 88.8% *(self-play)* | 75.4% | 80.7% | 52.4% |
| first attack turn | **2.78** | 6.08 | 6.09 | 5.82 | 5.81 | 6.00 |
| actions-before-attack | 3.62 | 2.96 | 4.75 | 2.90 | **4.62** | 4.59 |
| decision speed (median) | 0.43 ms | — | — | 0.10 ms | 0.10 ms | ~0.1 ms (BC forward pass, established earlier) |

## The single largest divergence

**Sanjay's real-ladder prize velocity (0.4718) is nearly equal to our
self-play ceiling (0.476–0.480) — and it is 20–107% above every ladder number
we have ever produced** (0.31 / 0.39 / 0.23 across three of our own
submissions).

Everywhere else in this project, self-play has overstated ladder performance
by roughly 2× (0.4574 self-play → 0.2370 ladder for our own Grimmsnarl v1).
**Sanjay's agent shows essentially no such gap.** Whatever separates self-play
piloting-competence from real ladder strength for us, his design mostly avoids
it.

The second-largest divergence: **first attack turn 2.78**, faster than every
field band measured all session (4.1–5.6) and faster than any configuration
either of us has shipped.

## What the evidence supports — (a) **and** (b), not (c), and not disjoint

### (c) is ruled out directly
Zero search code, zero decision-time budget, decision speed sub-millisecond at
the median. Confirmed by source inspection and by measurement. **Nothing in
search explains this.**

### (a) deck choice — real, and mechanically specific
- **Cinderace: `retreatCost = 0`, and its attack Turbo Flare costs `{C}` (one
  Colorless energy) for 50 damage while also fetching up to 3 more Basic
  Energy onto the bench from the deck.** That is a legal turn-1/turn-2 attack
  *and* a ramp effect on the same card — no evolution required. Neither
  Grimmsnarl nor Garchomp has anything that cheap; both need a stage-1/ex line
  online before any attack exists. This is the direct mechanical cause of
  first-attack 2.78.
- Archaludon ex (retreat 2, HP300, +100 via Hero's Cape → HP400) is a slow,
  tank-class payoff attacker (Metal Defender, `{M}{M}{M}`=220, weakness-immune
  next turn) — Cinderace buys the time for it to come online.

### (b) a different — and considerably richer — rule structure
1200+ lines, no shared architecture with our `main.py`. Concretely different
from our fixed tier ladder in three ways his own code makes explicit:

- **Attack is scored by its literal damage value** (30–260), not a fixed
  weight tier — but the effect is the same "attack last" principle we derived
  independently in CONDITIONAL_MINING.md: his own docstring reads *"Attack:
  damage value (always last — attacking ends the turn)."* He arrived at the
  identical structural insight from a different codebase and shipped it.
- **`detect_matchup()` + per-opponent overrides.** Named handling for at least
  Crustle, Alakazam, and Hop archetypes: Crustle overrides 10+ specific scores
  (e.g. "Metal Defender does 0 damage vs this deck"); Alakazam gets a
  floor/ceiling damage estimate from partial information to decide whether to
  heal; Hop gets a Snorlax-targeting Boss line. **We have no opponent-aware
  logic of any kind** — our entire ladder is opponent-blind.
- **Boss's Orders is prize-optimal, not reflexive.** `score_play`'s `BOSS`
  branch computes whether the current Active is already lethal, checks every
  bench target for a lethal Boss-pull weighted by `prize_value` (accounting
  for `ex` = 2 prizes), and separately handles a stall sub-case when no lethal
  exists. This is a small search over legal Boss targets by outcome, executed
  by explicit code rather than rollout.

### Read: not "deck vs. rules" — the two compound

The deck supplies **structural speed** (a free-retreat, 1-energy attacker that
self-ramps); the rule layer supplies **surgical conversion** (matchup-aware
overrides, prize-optimal targeting). Attack-when-legal is *lower* than ours in
both self-play and ladder terms (64.9% vs 75–89%), yet prize velocity is
higher — consistent with fewer, better-chosen attacks rather than more
frequent ones. Neither factor alone plausibly produces a ladder prize velocity
matching self-play ceilings; the combination does.

## An unplanned finding worth flagging on our own side

Fetching our own two most recent ladder submissions for a fair comparison
surfaced a result outside this task's original scope: **our `v1_grimm_seq_e1e2`
(E1+E2, the C2 arm shipped in C2_SHIP.md) is measurably ahead of the plain
`v1_grimmsnarl` baseline on real ladder data**, not just in self-play:

| | ladder n | prize velocity | actions-before-attack | ability-turns |
|---|---|---|---|---|
| `v1_grimmsnarl` (C0-equiv) | 43 | 0.3069 | 2.90 | 41.3% |
| `v1_grimm_seq_e1e2` (C2) | 38 | **0.3922** | **4.62** | **72.9%** |

A **+0.0853** difference — well outside the 0.019–0.025 same-config noise band
established in CONDITIONAL_BUILD.md, and moving in the mechanism-predicted
direction on both diagnostic counters (toward top-10's 5.87 and 80.2%). This is
**observational, not a controlled A/B** — different opponent pools, ladder
matchmaking, n<60 on both sides — so it is not a re-opened verdict on E1/E2,
which remains recorded as **DROPPED** on the pre-registered self-play screen.
It is reported here because it surfaced during this task and bears directly on
Step 4's comparison; it was not sought out separately.

---

## Summary

| question | answer |
|---|---|
| which submission jumped | **`submission_archaludon_v2.tar.gz`, id 55082948, 807.2** |
| bundle accessible | not via API; **Sanjay supplied it directly** — fully inspected |
| deck | Archaludon ex / Cinderace (Metal) — untested by either of us |
| search present | **no** — confirmed by source and by decision-speed measurement |
| shares code with our `main.py` | **no** — separate codebase entirely |
| largest divergence | **ladder prize velocity (0.4718) ≈ our self-play ceiling**, while ours has always cost ~2× to cross into ladder |
| primary driver | **(a) + (b)**: a deck built for free 1-energy tempo, piloted by matchup-aware, prize-optimal rule logic — not search, not a simpler codebase |

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/sanjay_profile.py` | replay profiler (seat-mapped, reused for our own ladder subs too) |
| `scratchpad/sanjay_v2/`, `scratchpad/sanjay_v3/` | extracted bundles |
| `scratchpad/s3/sanjay_55082948/`, `sanjay_logs_55082948/` | 69 replays + logs |
| `scratchpad/s3/sanjay_55084706/` | 58 replays (v3) |
| `scratchpad/s3/ourgrimm_55033010/`, `ourgrimm_55046537/` | our own ladder replays, refetched for comparison |
| `scratchpad/s3/bc_55018207/` | v2.2.0-class BC ladder replays |
