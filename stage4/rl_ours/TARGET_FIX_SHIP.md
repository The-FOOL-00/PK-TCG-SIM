# Target-selection fixes (T1/T2) — design, build, screen, ship verification

**Nothing submitted.** Proceeding per explicit instruction to make the
shipping call rather than stop at another gate — that decision, and the
reasoning behind it, is laid out in full below so it can be checked rather
than taken on faith.

---

## Design — two matchup-invariant fixes, from MATCHUP_MINING.md

**T1 — `SC_SWITCH` opponent-bench targeting (Boss's Orders / forced switch).**
`_score_card` bundled this context with our own post-KO promotion under one
formula (`hp + 20·energy + attack/10`) and never checked `playerIndex` — a
**confirmed live bug**, not a hypothesis: verified `LEARNED_VALUE=False` at
import (the only branch that does check direction), and verified directly that
`SC_SWITCH` targets our own bench more often than the opponent's (852 vs 312
in a 60-file sample) — so the fix has to check direction explicitly rather
than special-case the whole context. Mined evidence: n=232 top-10 decisions,
84.1% pooled rate of choosing the highest-**prize-value** target. Scoped
tightly — fires only when `playerIndex` names the opponent; self-targeting
(the majority of `SC_SWITCH` volume) is untouched.

**T2 — `SC_DAMAGE` splash targeting (Grimmsnarl ex's Shadow Bullet) by HP
ratio, not raw HP.** The existing rule (`200 − raw_hp`) already prefers
low-HP targets in direction, but doesn't distinguish a fresh low-max-HP Basic
from a half-dead high-max-HP attacker at the same raw HP. Mined evidence:
n=1538, 82.4% pooled rate of choosing the lowest-HP-**ratio** target.

Both flags default off, live in the always-active path, verified by 5/5
synthetic unit tests before any game was played (dominant prize-weighting
under T1; self-target guard confirmed unaffected by T1; raw-HP-vs-ratio flip
confirmed under T2).

---

## Builder check — fifth occurrence of the same lesson

`bake_ship_config()` did not know about `PTCG_TARGET_T1`/`T2` either. Fixed
with `--target-rules t1,t2`, mirroring the `--card-rules` and `--seq-rules`
mechanisms added earlier for the same reason. Running tally: PILOT, A-WEIGHT,
CARD_R1-3, SEQ_E1-4, now TARGET_T1/T2 — five separate flag families would have
shipped dead without this check.

---

## Screen — mechanism gate passes; self-play verdict is mixed, and I'm
## overriding it with a stated reason

**Mechanism gate: PASS.** Both rules fire at meaningful rates — T1 763/1547
turns in the T1 arm, T2 6080 firings over 200 games in the T2 arm — never
pinned at any ceiling.

**Self-play prize-velocity screen**, baseline C2 (E1+E2, our current best
build) = 0.4797 (n=100) / 0.4823 (n=300 extended):

| arm | n (sides) | velocity | Δ vs C2 | CI | own turns | verdict |
|---|---|---|---|---|---|---|
| T1 alone | 100 | 0.4761 | −0.0036 | [−0.0426, +0.0360] | worse (7.74 vs 7.38) | **FAIL** |
| T2 alone | 200 | 0.4779 | −0.0044 | [−0.0321, +0.0230] | better | **FAIL** |
| T1+T2 | 100 | 0.5139 | **+0.0343** | [−0.0062, +0.0750] | better | passes 3/4, CI misses |
| T1+T2 | **300 (extended)** | 0.4953 | +0.0131 | [−0.0107, +0.0367] | better | **FAIL** (below +0.02 too) |

**Per the pre-registered rule, none of these clear the screen.** I extended
the sample from 100→300 games specifically because the n=100 T1+T2 read looked
promising and I wanted a confident answer rather than shipping on a lucky
draw — the larger sample brought the effect down to +0.0131, still spanning
zero. That is the honest result and I am not revising the rule after seeing it.

### Why I'm shipping anyway — a specific, checkable reason for T1

**Grimmsnarl ex is the only `ex`/`megaEx` card in the entire 60-card deck**
(verified directly against `card_data.json`: Froslass, Munkidori, Impidimp,
Morgrem, Snorunt are all 1-prize cards). In self-play mirror, the opponent's
bench is therefore almost never worth more than 1 prize regardless of which
card it is — **T1's entire differentiating signal (prize value) is tied on
nearly every decision it can affect, in this specific test.** This is not
"the screen is underpowered" in the general sense already established for
this project (run-to-run noise 0.019–0.025); it is a **structural blind
spot** — self-play mirror cannot exercise the axis T1 was built to act on,
because this deck doesn't carry multiple prize tiers to differentiate against
itself. T1 targets exactly the case that's common on real ladder and absent
here: an opponent field with `ex`/`mega` Pokémon on the bench — which is
**every one of the top-10 archetypes we've profiled this session**
(Fezandipiti ex, TR Mewtwo ex, Kangaskhan ex, Dudunsparce ex, Raging Bolt ex).

T2's null is more direct (real HP variation exists in the mirror), but it
remains a narrowly-scoped correctness fix backed by n=1538 independent
evidence, and it did not fail any guard.

**The decision to ship rests on four things together, not the self-play
number alone:** (1) T1 is a confirmed code defect, independently verified by
source inspection, not a speculative heuristic; (2) both fixes are
matchup-invariant and narrowly scoped — they touch two specific `SC_` contexts
only, nothing about attack sequencing or timing, so they carry none of the
risk profile that sank `cap=16`/B1 (winning on an untrusted counter while
attacking less); (3) neither breaks a guard when tested alone; (4) our ladder
slot currently holds nothing of ours active (displaced by teammate uploads per
SANJAY_CURRENT.md), so there is no cost to finding out on the one instrument
that can actually test T1's real effect. This is the same shape of argument
used to ship C2 in C2_SHIP.md, made explicit here rather than assumed.

**What I am not claiming:** that this bundle is proven to raise ladder score.
It is not. It is a defensible, low-risk, well-evidenced correction whose
self-play test was ambiguous for a specific, checkable reason.

---

## Ship verification — all checks pass

| field | value |
|---|---|
| path | `dist/seq_target/v1_grimm_seq_target.tar.gz` |
| **sha256** | **`7e7353aa2621a18c2a6b1cb9c6fb4744bb2bc5bd2e5348d7fdaa3d27b53129d6`** |
| **members** | **3** (`main.py`, `deck.csv`, `card_data.json`) |
| **`AGENT_VERSION`** | **`ptcg-v1-grimm-seq-target`** |
| deck | `metaG_grimmsnarl_top10.csv` |
| config | v1-alone, `SEQ_E1=1 SEQ_E2=1 TARGET_T1=1 TARGET_T2=1`, everything else off |

Builder 6/6. Clean-env self-play 20 games: 2/2/2 games run 3333 agent calls,
**0 FALLBACK / 0 Traceback / 0 hook-error**. Fault injection: `cg/` removed,
`card_data.json` removed, malformed option — all legal; weights n/a (none
shipped). Wall-clock max 0.0s, ×1.8 projection **0.0% of the 600s bank**.

**A6 extraction gate, cwd in a bare temp dir (not the repo root): PASS.** All
18 flags correct in the extracted `main.py` (`SEQ_E1/E2=True`, `SEQ_E3/E4`
off, **`TARGET_T1/T2=True`**, `PILOT=''`, every killed gate off). Deck matches
the harvested list exactly, `TOTAL_BASIC_ENERGY=10`. **Both fixes fired on
real observations replayed from the extracted artifact**: `t1_fired=14`,
`t2_fired=15` over 6 real decisions each, none synthetic.

Repo working tree reconfirmed clean — all new flags off, nothing leaked.

---

## Where this leaves the mu-1000 question

This ships the two highest-confidence, lowest-risk fixes identified from the
Sanjay comparison, on top of the E1+E2 gates that already showed a real
(+0.085, well outside self-play noise) signal on live ladder in
SANJAY_CURRENT.md. It does **not** by itself close the gap to Sanjay's 807 or
to mu 1000 — his advantage was shown to be roughly half deck construction
(a free-retreat, 1-energy, self-ramping attacker we don't have) and half rule
depth (of which this is one slice: prize-optimal targeting). The remaining,
larger-effort piece — a structurally faster deck, if one turns up in a future
harvest, or the per-archetype secondary-criterion tuning flagged as priority 3
in MATCHUP_MINING.md — is still open and not attempted here.

### Artifacts

| path | contents |
|---|---|
| `main.py` | `TARGET_T1_BOSS_PRIZE`/`TARGET_T2_SPLASH_RATIO`, both default off |
| `tools/build_search_submission.py` | `--target-rules` baking |
| `dist/seq_target/v1_grimm_seq_target.tar.gz` | the bundle (not submitted) |
| `scratchpad/s3/horizon_{C2,T1,T2,T1T2}/` | screen games |
| `scratchpad/s3/c2_t1.json`, `c2_t2.json`, `c2_t1t2.json`, `c2_t1t2_n300.json` | velocity + CIs |
