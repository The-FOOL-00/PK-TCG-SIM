# Piloting Is the Product

*Paste target for the Kaggle Strategy-track writeup form. Same evidence as
`WRITEUP_SUBMIT.md`, reordered so the two named judging criteria — originality of
deck construction, algorithmic ingenuity — land before the negative results, and
trimmed to the 2000-word limit. Figures in `report/figures/`, regenerate with
`tools/make_writeup_figures.py`.*

**Everything above the rule below is scaffolding — paste only what follows it.**

---

## Title / subtitle options for the form

**Title** (80 char limit):

1. `Piloting Is the Product: Measuring Whether an Agent Can Pilot a Deck` — 67
2. `Envelope Closure: A Deck-Pilot Fit Metric, and Seven Archetypes of Evidence` — 75
3. `The Deck Is Not the Asset: Falsification-Driven Agent Design for the PTCG` — 72

**Subtitle** (140 char limit):

1. `A metric that predicts, before a single match, whether a given agent can pilot a given deck — validated on seven archetypes.` — 122
2. `We spent the project trying to beat a 0.1 ms heuristic. What survived: one deck-fit metric, two sequencing rules, two targeting rules.` — 133

---
---

## 1. What this is

We built a deterministic, sub-millisecond heuristic pilot, then spent the project
trying to beat it. Across ~20 pre-registered experiments we killed nine policy-side
interventions, two behaviour-cloning generations, one runtime search architecture
and four mined rule families.

Our most valuable output is not a win rate. It is a **measurement** — a deck–pilot
fit metric we call **envelope closure**, which predicts, before a single match is
played, whether a given agent can pilot a given deck. It explains every
architectural failure here retroactively, and it is why our decklist is what it is.

## 2. Contribution — envelope closure

Prize velocity (prizes ÷ own turns) is not comparable across archetypes; each deck
has its own clock. So we normalise against **that deck's own top-10 envelope**,
harvested from real top-10 replays of the archetype:

> **closure = our mirror prize velocity ÷ that archetype's top-10 velocity**

Same agent, same flags, **only `deck.csv` differs**; 100 games / 200 sides each,
across seven archetypes *(Figure 1)*.

**(i) Closure tracks how many turns the attacker needs, not deck strength.**
One-step decks — a Basic, or a Stage-2 collapsed by Rare Candy — close at
**79–81%**. Every deck requiring a genuine multi-turn climb closes at **40–53%**.
There is nothing in between.

**(ii) High envelope with low closure is the trap** *(Figure 2)*. TR Mewtwo
(0.6754) and Mega Kangaskhan (0.6729) are the **highest** envelopes we measured,
and we convert the least of them — 48.9% and 45.0%. Picking a deck by field
strength selects exactly these. Dragapult ex is the meta's best archetype (76.5%
pooled, 10–2 versus Grimmsnarl); we close 46.3% of it, so adopting it would
**lower** our rating.

**(iii) Card flow is not the bottleneck.** Fezandipiti draws **4.18 cards/turn
against our Grimmsnarl 1.63** and has the *worst* velocity of any deck measured.

**Mechanism: a fixed priority order *is* a plan.** Ours ranks *attach > evolve >
item > bench > attack* — precisely the Grimmsnarl line, so `attach → Rare Candy →
Grimmsnarl ex` falls out of the tier order with no planning. Garchomp requires
*holding an attacker back* through a three-stage climb; the same order produces
slow, passive play.

> **The agent was never bad at piloting. It was piloting the wrong deck for its
> fixed priority order.**

**The decisive control.** We reconstructed a strong player's own 60-card list and
ran our unmodified agent on it: velocity **0.2510** against our Grimmsnarl
**0.4953** — and our shipped rules made it **worse** (0.2207). A top deck is not a
transferable asset; it is conditional on execution built for it.

## 3. The deck — Marnie's Grimmsnarl ex / Munkidori

A 320-HP attacker that arrives early *because it pays its own energy cost*,
converts each attack into two-target prize pressure, and closes with chip damage.

| n | key card | role |
|---|---|---|
| 3 | **Marnie's Grimmsnarl ex** (320 HP) | **Punk Up** — on evolving from hand, search **5 Basic {D} Energy** and attach freely. **Shadow Bullet** — 180 Active **+ 30 to a Bench** Pokémon |
| 3 | **Rare Candy** | collapses Impidimp → Grimmsnarl ex into one turn |
| 4 | **Munkidori** | **Adrena-Brain** — relocate 3 damage counters onto an opposing Pokémon, free, every turn |
| 2 | **Froslass** | **Freezing Shroud** — a counter on every Ability-holder each Checkup, ours excepted |
| 4 / 2 | Buddy-Buddy Poffin / Boss's Orders | Basic search / gust |
| 9 / 10 | Petrel, Lillie's Determination, Dawn / Basic {D} | draw engine / fuel |

By our own measurement this list does **not** have the strongest envelope in the
field. It was chosen because every card aligns with the one thing our pilot does
well:

- **Punk Up removes the phase our pilot handles worst.** A greedy scorer
  accumulates energy poorly across turns; one *evolve* delivers five at once. The
  ramp becomes an **event**, not a plan — which is why only 10 energy is needed.
- **Rare Candy is why this deck is pilotable at all** — the difference between
  79.9% closure and the 40–53% band every other multi-turn deck occupies.
- **Shadow Bullet + Adrena-Brain + Freezing Shroud stack chip damage**, so the
  prize race is won by *accumulation*, which a greedy pilot executes correctly.

This is the originality claim we defend: **the decklist is a derived quantity.** We
measured the pilot first, then picked 60 cards its priority order already executes.

## 4. The pilot

One file of pure standard-library Python. No engine binary, no neural weights, no
search in the shipped path. Median decision **0.10 ms**, p99 **3 ms** — the speed
class the top-10 ladder pilots occupy (31–92 ms measured), ~1000× faster than our
search prototype. Its core is a fixed priority ladder over the legal option
menu — *lethal attack (100 000) > attach > evolve > item > bench > ability >
non-lethal attack > terminal* — plus a context-keyed scorer for sub-decisions.

That simplicity is a **result**, not a starting point:

| intervention | result | verdict |
|---|---|---|
| Deck redesign, 6 variants | 25–42% head-to-head | KILL |
| Determinized Monte-Carlo search | gate 58.7% [53.0, 64.1] → ladder **μ548 vs μ614** | KILL |
| Five analytic / learned policies | *Figure 4* | 4 KILL, 1 ship → μ697 |
| Mined sequencing + targeting | §5 | **SHIP** |

## 5. Rules: mined, not invented

We record every MAIN decision's state context, partition into cells, and rank by
**leverage = cell frequency × total-variation distance** between the top-10's
action distribution and ours — **top-10 Grimmsnarl (504 sides, 19,323 decisions)**
against **our agent on the identical 60 cards (200 sides, 6,692)**, so every
divergence is *piloting*, not deck.

The top cell was **sequencing**. Top-10 pilots used an ability on 80.2% of their
attacking turns and took 5.87 actions before attacking; we managed 61.8% and 2.97,
and attacked as the turn's *first* action 43.0% of the time against their 2.0%.
**Attacking ends the turn; every other action is free** — `WEIGHT_LETHAL = 100 000`
ended the turn the instant a KO appeared, cards unplayed. **E1** (develop before a
terminal action, capped at 12/turn) and **E2** (fire an available Ability first)
close both gaps to field parity *(Figure 3)*.

**Targeting** is the second shipped family, mined from **1,770 top-10 decisions**
on exactly these cards:

| decision | top-10 criterion | our scorer before |
|---|---|---|
| **Shadow Bullet** splash (n=1538) | lowest **HP ratio**, 82.4% | lowest **raw HP** — a fresh 130-HP Basic scored identically to a half-dead 260-HP attacker |
| **Boss's Orders** target (n=232) | highest **prize value**, 84.1% | *the formula for promoting our **own** Pokémon* — "prefer high HP + energy," backwards for choosing an opponent's |

Both criteria are near **matchup-invariant** (70–100% across every archetype with
n≥28), so neither needs opponent detection.

**Two laws these produced.**

**Composition is not automatic.** One free-ability rule scored **39.0%** against a
32.0% baseline (+7.0 pt, 695 fires); a second scored 36.4% alone (385 fires);
**stacked they collapsed to 33.3%**, the second firing **4 times instead of 385**.
They compete for the same once-per-turn slot.

**Only unconditionally-valuable substitutions survive.** Four further mined rules
failed — promoting a Supporter before attacking (**−7.0 pt**: after it resolves the
pilot re-scores and never returns to the attack), and redistributing attachments
(fired 164×, lifted the target attack **4.7×**, still **−3.5 pt** by starving the
primary attacker). A rule substituting a **free** action for a terminal one
succeeds: the menu is unchanged minus that action. A rule **promoting an action
the pilot would not otherwise take** fails — it shifts the state into a line the
pilot cannot continue. *Matching an expert's rate is not matching their policy.*

## 6. Measurement discipline — and five ways it still lied

**≥300 games, seats alternated by construction, 95% Wilson CI, PASS only if the
lower bound clears 50%.** One variant read 48% at n=50 and **25% at n=150**; one
challenger won **72% in seat 0 and 36% in seat 1**. Later screens pre-register
PASS/FAIL bands *before* the run and carry a fire counter — *a rule that did not
fire has not been tested.* It caught a real post-hoc selection: an arm picked
after an exploratory sweep regressed to the mean under pre-registration and died.

It was still not enough. Every offline proxy we trusted read excellent while
head-to-head read 31–61% *(Figure 4)*. Five documented lies, each with a mechanism:

| # | the lie | mechanism |
|---|---|---|
| 1 | A gate valued a deck switch at **74.7%**; ladder gave **μ548 vs μ614** | its opponent was *our own agent on our old deck* — **both sides mispiloted the new deck identically**, so the gate could not see the weakness they shared. The rank-1 player ran a **byte-identical list** |
| 2 | Mirror self-play scored our sequencing rules **null** | a mirror is blind to a **strictly-dominated** fix: a free action before a terminal one is no trade-off, so both sides gain equally. On ladder they moved velocity **+0.0853**, outside the 0.019–0.025 noise band |
| 3 | A search-quality metric read **0.938** | ties broke by index — the tie-break was voting with itself. Excluding non-discriminating worlds gave **0.667**, and 0.938 sits in the "do not rebuild" band. *Caught before the run* |
| 4 | Two diagnostics reported confident tempo numbers | they put the sample submission ahead of ours on `sys.path` and had been driving the **38-line random agent** — every historical run was random-vs-random |
| 5 | A legal attack was excluded from the candidate set **1068 / 1068 times** | fixing it changed nothing. **A mechanically absolute defect can still be non-binding** |

Instance 4 forced a retraction against ourselves: re-measured, the agent that
attacks *earliest* (turn 4.6) is the one that **loses**. A second followed — a
per-**decision** analysis said we attack *more* than the top-10; recomputed per
**turn** the sign inverts (50.5% vs 74.6%), decomposing to **willingness ~59%,
setup capability ~28%**. We had ranked them backwards, and said so.

## 7. Reliability

**0 INVALID / ERROR / TIMEOUT across every submission.** No RNG at decision time;
ties break on lowest index. 0 crashes and 0 fallbacks in every 300-game gate; a
19-episode ladder audit logged **0 tracebacks and 0 stderr bytes** over 1,301
calls. Timing p50 **0.1 ms**, p99 168 ms, max 280 ms against a 600 s budget. Under
fault injection — engine removed, card data removed, malformed option — play stays
legal, degrading with one stderr line.

**Deployment integrity:** every bundle is exec-loaded from a bare temp directory
with `sys.path` stripped and each flag re-asserted — a gate that caught a flag
baked off and a shadowed deck file.

The one archetype-conditional rule we built ships **off**: it fired on 69.7% of
decisions instead of the rare near-ties it targeted, because our scorer evaluates
one candidate at a time and **cannot see sibling scores** — structurally incapable
of being a tie-break.

## 8. Honest limits

**Best ladder result μ697; the top sits above μ1150.** We characterise the gap
precisely and did not close it. **Mirror self-play overstates our ladder strength
~2×** (0.4574 → 0.2370 on the same build) — every self-play figure here is an upper
bound, and the §6 ladder comparison is observational (n<60).

**Deck fit is now exhausted as a lever.** We are at ~80% of the best available
envelope and the ladder score did not follow. Our worst matchup proved from damage
logs to be **not a decision problem at all**: across 100 games our damage dealt
(26,470 vs 26,850) and attack count (372 vs 365) were unchanged versus the mirror —
the opposing roster is simply bulkier, so identical output buys fewer knockouts. No
rule fixes a stat mismatch.

Closure is validated on seven archetypes and predicts every failure on record. That
is evidence, not proof — and it is what we would hand the next team first.
