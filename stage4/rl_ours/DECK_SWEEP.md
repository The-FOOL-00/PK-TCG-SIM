# Live health check + deck-fit sweep

**Nothing submitted, nothing built.** v1-alone throughout; governor, `cap=16`,
`END_VETO`, `EVAL_FIX`, `PROMOTE_RULE`, `LETHAL_PROBE`, the candidate arms and
R1/R2/R3 all stay off.

---

# PART A — health check, `ptcg-v1-grimmsnarl` (sha `56c53886`)

Submission **55033010**, uploaded 2026-07-27 15:51 UTC. **19 episodes, 20 of our
sides** (one self-match). Score has moved **422.6 → 463.1** since the brief.

*Auth note: the competition slug is `pokemon-tcg-ai-battle`, not
`…-challenge-simulation`. That mismatch — not the credentials — was the 403 that
blocked the first attempts.*

## 1. Game count and record

| | |
|---|---|
| episodes | **19** (20 sides; 1 self-match) |
| record | **9W – 11L** (45.0%) |
| current score | **463.1** |

**n = 19 < 40, so no band applies.** This is a health check, not a strength read.

## 2. Deck loaded correctly on the platform — ✅ **confirmed**

The `_find_file` cwd-precedence risk found in verification **did not
materialise on Kaggle**:

| check | result |
|---|---|
| sides whose deck == the harvested Grimmsnarl list | **20 / 20** |
| mismatched | **0** |
| Basic {D} Energy per side | **10** (exactly as intended) |

The platform sets cwd to the agent directory, so `os.getcwd()` resolves the
bundled `deck.csv` first. The risk was real but repo-local.

## 3. Exceptions, illegal actions, timeouts — ✅ **none**

| check | count |
|---|---|
| `Traceback` / `Exception` | **0** |
| `FALLBACK` | **0** |
| `SELFCHECK FAIL` | **0** |
| `cg engine unavailable` | **0** |
| total stderr bytes across 19 episodes | **0** |

Agent-call durations over **1301 calls**: p50 **0.1 ms**, p99 168 ms, max
**280 ms**. Against a 600 s bank that is immeasurably small. Total stderr of
zero is the expected signature of v1-alone — no search, so no `[gov]`
telemetry, and no warnings fired.

## 4. Opponent archetypes — **the headline finding**

| opponent archetype | sides | share |
|---|---|---|
| Mega Starmie ex / Cinderace | 3 | 15.0% |
| Mega Abomasnow ex / Kyogre | 3 | 15.0% |
| Mega Lucario ex / Hariyama | 3 | 15.0% |
| **Marnie's Grimmsnarl ex / Munkidori (MIRROR)** | **2** | **10.0%** |
| Fezandipiti ex / Dudunsparce | 1 | 5.0% |
| Mega Kangaskhan ex / Koraidon ex | 1 | 5.0% |
| Marnie's Grimmsnarl ex / Meowth ex | 1 | 5.0% |
| Mega Lucario ex / Flygon ex | 1 | 5.0% |
| Gouging Fire ex / Ethan's Ho-Oh ex | 1 | 5.0% |
| Ethan's Typhlosion / Crustle | 1 | 5.0% |
| Lillie's Clefairy ex / Hop's Snorlax | 1 | 5.0% |
| Hydrapple ex / Teal Mask Ogerpon ex | 1 | 5.0% |
| Dragapult ex / Fezandipiti ex | 1 | 5.0% |

### **Mirror rate is 10%, not 66%.**

| split | record |
|---|---|
| **vs mirror** | **1W – 1L** (n=2) |
| **vs non-mirror** | **8W – 10L** (n=18) |

**13 distinct archetypes in 20 games, and most of them never appear in the
top-10 harvest at all** — Mega Starmie, Mega Abomasnow, Mega Lucario, Hydrapple,
Gouging Fire, Typhlosion, Clefairy. The field at **μ≈450** is not the field at
μ1120–1185.

This matters for Part C: **the 66% Grimmsnarl seat share is a top-10
phenomenon.** Mirror-saturation is not a cost we are currently paying.

Both W/L splits are far below n=60 and are **not quotable**.

## 5. End reasons and game length

*(reason 1 = prizes, 2 = deckout, 3 = no-active)*

| | prizes | no-active | deckout |
|---|---|---|---|
| **wins** (9) | 4 | 4 | 1 |
| **losses** (11) | **8** | 3 | 0 |

| | ladder | self-play (D1) |
|---|---|---|
| own turns / game | **6.75** | 7.63 |
| prizes / game | **1.60** | **3.49** |

## 6. Prize velocity — **it did not transfer**

| | prize velocity |
|---|---|
| **ladder (19 episodes)** | **0.2370** |
| self-play D1 | **0.4574** |
| Grimmsnarl top-10 envelope | 0.5725 |

**Ladder velocity is 52% of the self-play figure.**

### Reading this correctly — low own-turns is ambiguous

Own turns *fell* (7.63 → 6.75) while prizes *collapsed* (3.49 → 1.60). Short
games are not automatically good: **in self-play 7.63 turns with 3.49 prizes is
winning pace; on ladder 6.75 turns with 1.60 prizes is losing fast.** 8 of 11
losses are prize losses — the opponent races to six while we take fewer than two.

This is exactly the caveat recorded in DECK_SWITCH.md before the result was
known: *self-play mirror measures piloting competence, not matchup equity.* The
piloting gain was real and reproduced (own turns are in the same range); the
strength it was hoped to imply has not appeared at n=19.

**For context, not part of this task:** the team's own history has
`trevenant_v17` at **750.5**, `v20` at 726.8, `v21` at 700.9 — all far above
anything our agent has produced. That is worth weighing separately.

---

# PART B — deck-fit sweep, v1-alone, `PILOT=""`

## Archetypes available

Every top-10 archetype in `replays_top10_jul26/` with a recoverable 60-card
list, restricted to the 10 top-10 teams (391 seats):

| archetype | top-10 seats | share | distinct lists | engine-pool validation |
|---|---|---|---|---|
| Marnie's Grimmsnarl ex / Munkidori | 258 | 66.0% | 2 | **VALID** |
| Mega Kangaskhan ex / Raging Bolt ex | 49 | 12.5% | 1 | **VALID** |
| Fezandipiti ex / Dudunsparce | 45 | 11.5% | 1 | **VALID** |
| Team Rocket's Mewtwo ex / TR Spidops | 39 | 10.0% | 1 | **VALID** |

**All four buildable — no unconstructible card in any list.** Garchomp holds
**zero** top-10 seats on 07-26, so its envelope is carried over from the
jul21/jul22 harvests (0.495).

## Results — 100 games / 200 sides per deck

| deck | **velocity** | envelope | **CLOSURE** | own turns | prizes/game | attack-when-legal | first attack | first evolve | first prize | draws/turn |
|---|---|---|---|---|---|---|---|---|---|---|
| **Grimmsnarl** | **0.4574** | 0.5725 | **79.9%** | 7.63 | **3.49** | **88.5%** | 6.53 | 4.82 | 9.2 | 1.63 |
| **Garchomp** | 0.2628 | 0.495 | **53.1%** | 11.17 | 2.94 | 54.4% | **5.01** | 4.34 | 11.2 | 1.63 |
| **TR Mewtwo / Spidops** | 0.3303 | **0.6754** | **48.9%** | 10.40 | 3.44 | 68.1% | 8.71 | 4.70 | 13.0 | 2.97 |
| **Kangaskhan / Raging Bolt** | 0.3025 | **0.6729** | **45.0%** | 7.74 | 2.34 | 38.5% | 7.51 | n/a | 11.5 | 1.64 |
| **Fezandipiti / Dudunsparce** | 0.2061 | 0.5084 | **40.5%** | 7.06 | 1.46 | 66.9% | 5.96 | 4.19 | 10.2 | **4.18** |

*Kangaskhan shows no first-evolution turn: Mega Kangaskhan is not reached
through the ordinary evolve path the profiler counts.*

### Notes

- **Mewtwo and Kangaskhan have the highest envelopes (0.675, 0.673)** — top-10
  pilots get more out of them than out of Grimmsnarl — but we convert the least
  of it. High envelope with low closure is a deck we cannot pilot.
- **Fezandipiti draws the most cards by far (4.18/turn vs 1.63)** and still has
  the worst velocity. Card flow is not our bottleneck.
- **Kangaskhan's attack-when-legal is 38.5%**, the worst of any deck measured
  including Garchomp. Its plan does not fit a fixed tier ladder at all.

---

# PART C — field position (reported separately, not merged)

| deck | top-10 seat share | WR vs pooled field | n | **as-us vs Grimmsnarl** | n | quotable? |
|---|---|---|---|---|---|---|
| Grimmsnarl | **66.0%** | 53.3% | **317** | — | — | WR yes |
| Kangaskhan / Raging Bolt | 12.5% | 67.3% | 49 | **23W – 10L** | **33** | ❌ **both n<60** |
| Fezandipiti / Dudunsparce | 11.5% | 41.0% | **78** | 18W – 32L | 50 | WR yes; h2h ❌ |
| TR Mewtwo / Spidops | 10.0% | 50.9% | 55 | 20W – 21L | 41 | ❌ **both n<60** |

**Only Grimmsnarl (n=317) and Fezandipiti (n=78) have quotable win rates. No
head-to-head cell reaches n=60.**

## Correction to the brief's Kangaskhan cell

The brief cites "23W-10L and 8W-19L, 60 combined". Measured:

- **as-Kangaskhan vs Grimmsnarl: 23W – 10L, n = 33**
- Grimmsnarl side of those same games: 10W – 23L, n = 33

**The two directions are the same 33 games viewed from opposite seats, not two
independent samples.** "60 combined" double-counts; the honest n is **33**.
I also measure 10W–23L on the Grimmsnarl side, not the 8W–19L quoted.

**Per the standing n≥60 rule this cell is not quotable, and it is a hypothesis,
not an established counter** — exactly as the brief instructed it be flagged.

## The mirror-exposure premise does not hold at our rating

The brief's trade-off — *"a deck we pilot at 80% of envelope but face in 70% of
games is worse than one we pilot at 70% and rarely mirror"* — is sound in the
abstract. But Part A measured our **actual** mirror exposure at **10%**, not
66%. The 66% figure describes the top-10 population; we play at μ≈450 against
13 different archetypes, most of which never appear in the top-10 harvest.

**So the mirror-saturation penalty is currently hypothetical for us.** It would
become real only if this agent climbed into the top-10 band, which nothing in
the evidence suggests is imminent.

---

# RANKING

## By closure (piloting fit) — the Part B question

| rank | deck | closure |
|---|---|---|
| **1** | **Grimmsnarl** | **79.9%** |
| 2 | Garchomp | 53.1% |
| 3 | TR Mewtwo / Spidops | 48.9% |
| 4 | Kangaskhan / Raging Bolt | 45.0% |
| 5 | Fezandipiti / Dudunsparce | 40.5% |

**Grimmsnarl leads by 26.8 points.** No other deck is close.

## By field position — reported separately, as instructed

| deck | high closure? | low mirror exposure (actual)? | non-negative vs Grimmsnarl? |
|---|---|---|---|
| **Grimmsnarl** | ✅ 79.9% | ✅ **10% measured** | n/a (is the mirror) |
| Kangaskhan | ❌ 45.0% | ✅ | ⚠️ 23W-10L but **n=33, not quotable** |
| TR Mewtwo | ❌ 48.9% | ✅ | ⚠️ 20W-21L, n=41, not quotable |
| Fezandipiti | ❌ 40.5% | ✅ | ❌ 18W-32L (n=50, not quotable, and negative) |

**No deck has both high closure and a quotable field advantage.** Kangaskhan is
the only candidate with a favourable-looking head-to-head, and both its win rate
(n=49) and its head-to-head (n=33) fall below the quotable floor.

---

# RECOMMENDATION — **keep Grimmsnarl. Do not switch.**

1. **Closure dominates.** 79.9% vs 53.1% for the next-best. Switching to
   Kangaskhan would trade 27 points of measured piloting fit for a head-to-head
   edge that our own standing rule says is not quotable at n=33.
2. **The mirror objection does not currently apply.** Measured exposure is
   **10%**, not 66%, and our mirror record (1W-1L) is not the problem — the 8
   prize-losses to non-mirror decks are.
3. **The alternatives are worse on the thing that transfers.** Mewtwo and
   Kangaskhan have the highest envelopes and the lowest closure: top-10 pilots
   extract value from them that our fixed tier ladder cannot.

### But hold the expectation down

**Ladder prize velocity is 0.2370, barely half the 0.4574 self-play figure**,
and the score sits at 463.1 with 9W-11L at n=19. The deck switch delivered the
piloting gain it promised and that gain has not converted into ladder strength.
Since the self-play→ladder shortfall should apply to every deck roughly alike,
the *ranking* above is probably sound while the *absolute* closure numbers
overstate what any of these decks will do on ladder.

**The honest read is that deck fit was the right variable and is now largely
exhausted** — we are at 80% of the best available envelope and still at 463.
Further gains have to come from somewhere other than the deck list or the
policy, both of which have now been swept.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/grimm_health.py` | Part A health check |
| `stage4/rl_ours/archetype_field.py` | envelopes + field position |
| `scratchpad/s3/eps_55033010.json`, `grimm_logs/`, `grimm_replays/` | 19 episodes, logs + replays |
| `metaX_{kangaskhan,fezandipiti,mewtwo}_top10.csv` | harvested lists |
| `scratchpad/s3/horizon_SW_{KANG,FEZ,MEW}/` | 100 games per deck |
| `scratchpad/s3/archetype_field.json`, `sweep_velocity.json` | raw numbers |
