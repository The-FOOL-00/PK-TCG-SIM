# Closure: Measuring Whether an Agent Can Pilot a Deck

### Seven archetypes, one metric, and a catalogue of the ways local evaluation lied to us

---

## 1. The agent

A **deterministic heuristic pilot in one file of pure standard-library Python**.
No engine binary, no neural weights, no search. Median decision **0.10 ms**,
p99 **3 ms**. Its core is a fixed priority ladder over the legal option menu:
*lethal attack (100 000) > attach (3 000) > evolve (2 800) > item (2 400) >
bench (2 300) > ability (2 200) > non-lethal attack (~1 100) > terminal*, with a
separate context-keyed scorer for sub-decisions.

That simplicity is a **result**. We spent the project trying to beat it:

| intervention | offline metric | head-to-head | verdict |
|---|---|---|---|
| Deck redesign, 6 variants | — | 25–42% | KILL |
| Analytic 1-ply evaluator | tuned to 53% | 54.0% [48.3, 59.6] | KILL |
| Learned value net, 1.52M rows | **AUC 0.845** | 48.7% [43.1, 54.3] | KILL |
| Determinized Monte-Carlo search | 58.7% [53.0, 64.1] | ladder **μ548 vs μ614** | KILL |
| Behaviour cloning, MAIN-only | top-1 **69.4%** (floor 20.8) | 31.0% [26.0, 36.4] | KILL |
| Behaviour cloning, two-headed | sub-decision **76.1%** | **60.7% [55.0, 66.0]** | ship → μ697 |
| BC + anti-deckout brake | context acc. **96.8%** | 39.0% [33.7, 44.6] | KILL |
| Mined sequencing + targeting | — | §6 | **SHIP** |

Every offline proxy we trusted read excellent while head-to-head read 31–49%.

## 2. Measurement discipline

**≥300 games, seats alternated by construction, 95% Wilson CI, PASS only if the
lower bound clears 50%.** One variant read 48% at n=50 and **25% at n=150**; one
challenger won **72% in seat 0 and 36% in seat 1**. Later screens pre-register
PASS/FAIL bands in a file *before* the run and carry a fire counter — *a rule
that did not fire has not been tested.*

The discipline paid for itself concretely. An arm that looked best in an
exploratory sweep was **selected after seeing the numbers**; re-run under
pre-registration it regressed to the mean and was killed. Post-hoc selection is
the failure mode this protocol exists to catch, and it caught it.

## 3. Contribution 1 — envelope closure

Prize velocity (prizes ÷ own turns) isn't comparable across archetypes; each has
its own natural clock. So we normalise against **that deck's own top-10
envelope**, harvested from real top-10 replays of that archetype:

> **closure = our mirror prize velocity ÷ that archetype's top-10 velocity**

Same agent, same flags, **only `deck.csv` differs**; 100 games / 200 sides each:

| deck | attacker online via | velocity | **envelope** | **closure** |
|---|---|---|---|---|
| **Marnie's Grimmsnarl ex** | Stage-2 **+ Rare Candy** | **0.4574** | 0.5725 | **79.9%** |
| Cynthia's Garchomp | Stage-2, no Rare Candy | 0.2628 | 0.4950 | 53.1% |
| TR Mewtwo / Spidops | Basic, stall plan | 0.3303 | **0.6754** | 48.9% |
| Mega Kangaskhan / Raging Bolt | Basic + Mega evolution | 0.3025 | **0.6729** | 45.0% |
| Fezandipiti / Dudunsparce | Stage-1 engine | 0.2061 | 0.5084 | 40.5% |
| *Teal Mask Ogerpon ex* ᵃ | *Basic, no evolution* | *0.4726* | *0.5845* | *80.9%* |
| *Dragapult ex / Munkidori* ᵃ | *Stage-2, no Rare Candy* | *0.2324* | *0.5021* | *46.3%* |

<sub>ᵃ measured later with a second harness; ranking transfers, absolute values not directly comparable to rows 1–5.</sub>

**Three findings.**

**(i) Closure tracks how many turns the attacker needs, not deck strength.**
One-step decks — a Basic, or a Stage-2 collapsed by Rare Candy — close at
**79–81%**. Everything requiring a genuine multi-turn climb closes at **40–53%**.

**(ii) High envelope with low closure is the trap.** Mewtwo (0.6754) and
Kangaskhan (0.6729) have the **highest** envelopes we measured — top-10 pilots
extract *more* from them than from Grimmsnarl — and we convert the least of it.
Picking a deck by field strength selects exactly these. Dragapult ex is the
current meta's best archetype (76.5% pooled, 10–2 versus Grimmsnarl) and we
close 46.3% of it; adopting it would **lower** our rating.

**(iii) Card flow is not the bottleneck.** Fezandipiti draws **4.18 cards/turn
against our Grimmsnarl 1.63** and has the *worst* velocity of any deck measured.

**Mechanism: a fixed priority order *is* a plan.** Ours ranks
*attach > evolve > item > bench > attack*, which is precisely the Grimmsnarl
line — `attach → Rare Candy → Grimmsnarl ex` falls out of the tier order with no
planning. Garchomp requires *holding an attacker back* through a three-stage
climb; the same order produces slow, passive play.

> **The agent was never bad at piloting. It was piloting the wrong deck for its
> fixed priority order.**

**The decisive control.** We reconstructed a *strong player's own 60-card list*
and ran our unmodified agent on it. Velocity **0.2510** against our Grimmsnarl
**0.4953** — and our shipped rules made it **worse** (0.2207). A top deck is not
a transferable asset; it is conditional on execution built for it.

## 4. Contribution 2 — a catalogue of how local evaluation lies

Five documented instances, each with a mechanism:

| # | the lie | mechanism |
|---|---|---|
| 1 | A gate said a deck switch was worth **74.7% [69.5, 79.3]**; ladder gave **μ548 vs μ614** | the gate's opponent was *our own agent on our old deck*; **both sides mispiloted the new deck identically**, so it could not see the weakness they shared. The rank-1 player ran a **byte-identical list** |
| 2 | Mirror self-play showed our sequencing rules as **null** | a mirror is blind to a **strictly-dominated** fix: taking a free action before a terminal one is not a trade-off, so both sides gain equally. On ladder the same rules moved velocity **+0.0853**, far outside the 0.019–0.025 noise band |
| 3 | A search-quality metric read **0.938** | ties were broken by index, so the tie-break was voting with itself. Excluding non-discriminating worlds gave **0.667** — and 0.938 would have landed in the "do not rebuild" band on an artifact. *Caught before the run, not after* |
| 4 | Two diagnostic tools reported confident tempo numbers | they inserted the sample-submission directory ahead of ours on `sys.path` and had been driving the **38-line random agent**. Every historical run of both was random-vs-random. Gates were unaffected; the diagnostics were void |
| 5 | An "absolute" defect: a legal attack was excluded from the candidate set **1068 / 1068 times** | fixing it changed nothing. **A mechanically absolute defect can still be non-binding** |

Instance 4 forced a retraction against ourselves: re-measured, the agent that
attacks *earliest* (turn 4.6) is the one that **loses**. First-attack turn was
never the discriminator — sub-decision quality and consistency were. A second
retraction followed: a per-**decision** analysis concluded we attack *more* than
the top-10; recomputed per **turn**, the sign inverts (50.5% vs 74.6%), and the
gap decomposes to **willingness ~59%, setup capability ~28%.** We had ranked
them backwards and said so.

## 5. The deck — Marnie's Grimmsnarl ex / Munkidori

**Concept:** a 320-HP attacker that arrives early *because it pays its own
energy cost*, converts each attack into two-target prize pressure, and closes
with passive chip damage.

| n | key card | role |
|---|---|---|
| 3 | **Marnie's Grimmsnarl ex** (320 HP) | **Punk Up** — on evolving from hand, search **5 Basic {D} Energy** and attach freely. **Shadow Bullet** — 180 Active **+ 30 to a Bench** Pokémon |
| 3 | **Rare Candy** | collapses Impidimp → Grimmsnarl ex into one turn |
| 4 | **Munkidori** | **Adrena-Brain** — relocate 3 damage counters onto an opposing Pokémon, free, every turn |
| 2 | **Froslass** | **Freezing Shroud** — a counter on every Ability-holder each Checkup, ours excepted |
| 4 / 2 | Buddy-Buddy Poffin / Boss's Orders | Basic search / gust |
| 9 / 10 | Petrel, Lillie's Determination, Dawn / Basic {D} | draw engine / fuel |

**Alignment with the pilot, mechanically:**

- **Punk Up removes the phase our pilot handles worst.** A greedy scorer
  accumulates energy poorly across turns; one *evolve* delivers five at once.
  The ramp is an **event**, not a plan. This is why only 10 energy is needed.
- **Rare Candy is why this deck is pilotable at all** — the difference between
  79.9% closure and the 40–53% band every other multi-turn deck occupies.
- **Shadow Bullet + Adrena-Brain + Freezing Shroud stack chip damage**, so the
  prize race is won by *accumulation* — which a greedy pilot executes correctly.

**Key-card utilisation is where our two targeting rules live**, mined from
**1,770 top-10 decisions** on exactly these cards:

| decision | top-10 criterion | our scorer before |
|---|---|---|
| **Shadow Bullet** splash target (n=1538) | lowest **HP ratio**, 82.4% | lowest **raw HP** — scored a fresh 130-HP Basic identically to a half-dead 260-HP attacker |
| **Boss's Orders** target (n=232) | highest **prize value**, 84.1% | *the same formula used to promote our own Pokémon* — "prefer high HP + energy," which is backwards when choosing an **opponent's** Pokémon to drag out |

Both criteria are near **matchup-invariant** (70–100% across every archetype
with n≥28), so neither needs opponent detection.

## 6. Rules: mined, not invented

Record every MAIN decision's full state context, partition into cells, rank by
**leverage = cell frequency × total-variation distance** between top-10's action
distribution and ours — comparing **top-10 Grimmsnarl (504 sides, 19,323
decisions)** against **our agent on the identical 60 cards (200 sides, 6,692)**,
so every divergence is *piloting*, not deck.

The top cell was a **sequencing** problem:

| own turns containing an attack | top-10 | **ours** |
|---|---|---|
| turns using an ability | **80.2%** | 61.8% |
| actions before the attack | **5.87** | **2.97** |
| attacked as the **first** action | **2.0%** | **43.0%** |
| in "lethal available", share choosing ATTACK | 22% | **100%** |

**Attacking ends the turn; every other action is free.** `WEIGHT_LETHAL =
100 000` meant that the instant a KO appeared, the turn ended with cards
unplayed. **E1** (develop before a terminal action, capped at 12/turn) and
**E2** (fire an available Ability first) move attack-first **42.4% → 0.1%** and
ability-turns **59.5% → 89.5%**, both to field parity — the +0.0853 ladder
signal in §4.

**Two laws these produced.**

**Composition is not automatic.** Screened cross-deck, one free-ability rule
scored **39.0%** vs a 32.0% baseline (+7.0 pt, 695 fires); a second scored 36.4%
alone (385 fires); **stacked they collapsed to 33.3%**, the second firing **4
times instead of 385**. They compete for the same once-per-turn slot.

**Only unconditionally-valuable substitutions survive.** Four further mined
rules failed: promoting a Supporter before attacking (**−7.0 pt** — after it
resolves the pilot re-scores and never returns to the attack); a
dynamic-damage attack our scorer priced at its *printed* 0 damage, so we used it
**0 times in 200 games** (correct, but starved at 13 fires); redistributing
attachments (fired 164×, lifted the target attack **4.7×**, still **−3.5 pt** by
starving the primary attacker). A rule substituting a **free** action for a
terminal one succeeds — the menu is unchanged minus that action. A rule
**promoting an action the pilot would not otherwise take** fails: it shifts the
state into a line the pilot cannot continue. *Matching an expert's rate is not
matching their policy.*

## 7. Consistency and stability

- **Determinism** — no RNG at decision time; ties break on lowest index.
- **Legality** — **0 INVALID / ERROR / TIMEOUT** across every submission.
- **Crash-freedom** — 0 crashes, 0 fallbacks in every 300-game gate; a 19-episode
  ladder audit logged **0 tracebacks and 0 stderr bytes** over 1,301 calls.
- **Timing** — ladder p50 **0.1 ms**, p99 168 ms, max 280 ms against **600 s**.
- **Fault injection** — engine removed, card data removed, malformed option: all
  still legal, each degrading with one stderr line.
- **Deployment integrity** — no project-local module imports; data loads via a
  `__file__` → cwd → `/kaggle_simulations/agent` → `sys.path` probe. Every
  bundle is exec-loaded from a **bare temp directory** with `sys.path` stripped
  and each flag re-asserted — a gate that caught a flag baked off and a shadowed
  deck file. Ladder audit confirmed the correct deck in **20/20** sides, and card
  data was verified card-by-card against the official Kaggle CSV.
- **Matchup independence** — both targeting rules are near matchup-invariant by
  measurement (§5). The one archetype-conditional rule we built ships **off**:
  it fired on 69.7% of decisions instead of the rare near-ties it was designed
  for, because our scorer evaluates one candidate at a time and **cannot see
  sibling scores** — structurally incapable of being a tie-break.

## 8. Honest limits

**Best ladder result μ697; the top sits above μ1150.** We characterise the gap
precisely and did not close it. **Mirror self-play overstates our ladder
strength ~2×** (0.4574 → 0.2370 on the same build) — every self-play figure here
is an upper bound, and the §4 ladder comparison is observational (n<60).

**Deck fit is now exhausted as a lever.** We are at ~80% of the best available
envelope and the ladder score did not follow. Our worst matchup was diagnosed
from damage logs as **not a decision problem at all**: across 100 games our
damage dealt (26,470 vs 26,850) and attack count (372 vs 365) were unchanged
versus the mirror — the opposing roster is simply bulkier, so identical output
buys fewer knockouts. No rule fixes a stat mismatch.

Closure is validated on seven archetypes and predicts every failure on record.
That is evidence, not proof — and it is the thing we would hand to the next
team first.
