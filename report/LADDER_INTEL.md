# Ladder Intelligence Report — 2026-07-09

Sources: 47 top-ladder episode replays + 2 of our own v2.1.0 agent logs
(`data/top_replays/`); our ladder verdict (v2.0.0 μ=614 / 25 games,
v2.1.0-alakazam μ=548 / 6 games); self-play piloting diagnostic
(`tools/diagnose_alakazam_piloting.py`).

**One-line finding:** we already ship the rank-1 player's exact deck. The
entire gap to the top is *piloting*, and our search architecture is
mismatched to the combo/control decks the top of the ladder is made of.

---

## §A1 — Majkel1337 (rank 1, μ=1260)

- **Deck: Dudunsparce / Alakazam, 3 basic energy.** ONE decklist across all
  14 sampled sides. **It is byte-identical to our `metaB_alakazam.csv`
  (19/19 card ids, 60/60 copies).** We are already shipping his exact deck.
- **Game plan: long denial-control grind.** Avg **44 turns/game**,
  first-attack **turn 4.1** (gets Dudunsparce's 90-damage attacker online
  early), then grinds — **4.0 denial plays/game** (Enhanced Hammer + Boss's
  Orders), 1.9 Rare Candy/game. Wins by attrition/deckout, not race.
- Record in sample: 9W/5L (a hard field of other top teams).

## §A2 — kashiwashira (rank 2, μ=1163)

- **Deck: Team Rocket's Mewtwo ex / Team Rocket's Spidops, 9 energy.** One
  decklist across all 11 sides. A different archetype from META.md's top
  cluster — a stall/control deck.
- **Game plan: extreme stall.** Avg **51.7 turns/game**, first-attack
  **turn 11.1** (very late), zero denial, zero Rare Candy. Wins the long
  game on prizes.
- Record in sample: 4W/7L — but 5 of those 7 losses are to Majkel's Alakazam
  by **deckout** (reason 2): the stall deck runs itself out of cards against
  the Alakazam grind. A clean rock-paper-scissors, not weakness.

## §A3 — Architecture signature (decisive)

Median decision time per team (from `remainingOverageTime` deltas; our own
agent logs give wall-clock `duration` directly):

| team | deck | median | p90 | p99 | max | read |
|---|---|---|---|---|---|---|
| kashiwashira (rank 2) | Mewtwo stall | **33ms** | 39ms | 87ms | 419ms | **fast policy** |
| nasuo445 (2-0 vs field) | Garchomp | **31ms** | 35ms | 271ms | 279ms | **fast policy** |
| Majkel1337 (rank 1) | Alakazam | **92ms** | 113ms | 244ms | 12s* | **fast policy** |
| Project Mew | Abomasnow E35 / Alakazam | 320ms | 1740ms | 2702ms | 2968ms | **search** |
| our v2.1.0 | Alakazam | 210ms** | 1925ms | — | 2661ms | **search** |

*single outlier (setup). **from our 2 agent logs (SLOW-decision warnings at
1.7–2.7s on turns 2–3).

**The top of the ladder runs fast policies (31–92ms) — trained nets or
deck-specific heuristics with at most light lookahead — not deep search.**
The one search team in the elite pool, Project Mew, goes 16-15 (≈50%): search
is *competitive* at a high level but is not how anyone reaches the top-2. Our
agent sits squarely in Project Mew's speed/architecture class.

## §A4 — What beats the top decks

A meta triangle in the sample:
- **Alakazam (Majkel)** decks out **Mewtwo stall (kashiwashira)** — 5-0 in
  head-to-heads (reason 2).
- **Mewtwo stall** out-prizes Alakazam in the very longest games (it takes
  games off Majkel too).
- **Cynthia's Garchomp (nasuo445)** went **2-0, beating BOTH** Majkel's
  Alakazam and kashiwashira's Mewtwo (reason 1, prizes) — a fast aggressive
  evolution deck that punishes the slow control decks before they set up.
- Garchomp is also META.md's highest-rated archetype (avg lb 1117).

Garchomp is the meta counter and the *simplest* of the three top decks to
pilot (one evolution line to a big attacker; no Rare-Candy-combo trainer
engine, no denial-timing game).

---

## §B1 — Our Alakazam (v2.1.0) failure, ranked

Direct loss transcripts vs top opponents were not available (only 2 of our
own agent logs, from a mirror/validation episode, are in the replay set — no
`data/loss_episodes/`). Root-cause is therefore from (a) our agent logs and
(b) a 20-game self-play piloting diagnostic vs Majkel's replay signature:

| metric | OURS (v2.1.0) | Majkel rank-1 |
|---|---|---|
| avg game length | 28.8 turns | 44 turns |
| **first-attack turn** | **11.2** | **4.1** |
| denial plays/game | 4.2 | 4.0 |
| Rare Candy/game | 1.4 | 1.9 |
| games where we NEVER attack | **6/20 (30%)** | — |

Ranked failure modes:
1. **Slow setup / late pressure (primary).** We first attack at turn 11 vs
   Majkel's turn 4, and 30% of games we never attack at all. We get the
   Dudunsparce attacker online far too late; Majkel pressures from turn 4
   while denying. This is a tempo/sequencing failure, not a denial failure
   (our denial rate matches his).
2. **Failure to close.** Even when set up, we don't convert to prizes
   efficiently — shorter games than Majkel but worse outcomes means we lose
   the ones we don't stall into.
3. **Slow, grinding decisions** (agent logs: repeated 1.7–2.7s SLOW warnings
   on turns 2–3). The governor holds (no timeouts), but the search is
   burning its budget on early setup decisions without producing Majkel's
   crisp early tempo.

Mechanistic root cause: **our search only searches MAIN single-select
decisions and rolls out with the generic v1 heuristic.** Alakazam's strength
lives in the *trainer sub-decisions* (Rare Candy targets, Boss's Orders
gust targeting, multi-select draw/search resolution) that the search skips
and the v1 rollout plays blindly. So the search literally cannot "see" the
combo lines that make the deck rank-1 — it optimizes the wrong 5% of the
decision tree. This is why the same architecture pilots our *simple* old deck
to μ=614 but this *combo* deck to only μ=548.

## §B2 — Where our decisions diverge from top play

- **Tempo:** top Alakazam attacks turn 4; we attack turn 11. The winning
  line is Rare-Candy → Dudunsparce fast, swing early, deny to stay ahead.
  We over-set-up and under-pressure.
- **Speed/architecture:** top teams decide in 31–92ms with deck-specific
  policies that know their lines; we spend 200ms–2.7s searching a tree whose
  decisive branches (trainers) we don't even enumerate.
- **Deckout race:** Majkel actively mills opponents into deckout over 44
  turns; our shorter games suggest we're not executing that plan.

---

## §RECOMMENDATION

**The methodological headline (for the writeup):** the v2.1.0 74.7%
feasibility gate did not "lie" randomly — it compared our-search+Alakazam
against our-search+old-deck, i.e. against an unrepresentative opponent, with
*both* sides mispiloting Alakazam symmetrically. A gate whose opponent is not
the ladder field, and which cannot expose a piloting weakness both sides
share, predicts nothing. **Every future deck gate must use strong,
representative opponents (the top-team decks) and be anchored to our known
ladder result (v2.0.0 = μ614), never to v1.**

**Immediate, free action (do first, independent of the option chosen):**
ensure the *live* submission is v2.0.0 (μ=614), not v2.1.0 (μ=548) — that
recovers ~66 rating for zero work while we build.

Ranked options:

| # | option | expected result (2-day) | effort | regression risk | clean-exec <2d |
|---|---|---|---|---|---|
| **1** | **C — Garchomp** | **beat v2.0.0, target μ ~650–750** | med | low (gated vs v2.0.0) | **likely** |
| 2 | B — fix Alakazam piloting | recover ~614–750; ceiling 1260 | high | low (gated) | uncertain |
| 3 | A — copy top deck | ~0 (we already ship it → 548) | low | n/a | n/a |
| 4 | D — fast-policy / RL | high, but **weeks** not days | very high | — | no |

**Primary recommendation: Option C (Cynthia's Garchomp).** Reasoning:
(1) it is the meta counter — it beat *both* top-2 decks in the sample (2-0);
(2) it is the **simplest** top deck to pilot (one evolution line to a big
attacker), the best fit for our search+heuristic, which we have direct
evidence *mishandles combo decks* (the v2.1.0 result); (3) our search already
handled Garchomp matchups well in earlier gates. Build the top-ladder
Garchomp list from replays, add minimal Garchomp evolution/attacker
heuristics, and **gate vs v2.0.0 AND vs the three top-team decks piloted by
our own agent** — ship only if CI-lower > 50% vs v2.0.0. This directly avoids
the v2.1.0 gate mistake.

**Second: Option B (fix Alakazam piloting)** has the single highest ceiling
(we already ship the rank-1 deck) and the failure is now localized (slow
setup, late attacks, no close-out). But the fixes fight our architecture's
structural blind spot — the trainer sub-decisions the search doesn't
enumerate — so reaching Majkel's level likely needs more than heuristic
tweaks (it needs the search to cover trainer selections, or a deck-specific
policy). High ceiling, high effort, uncertain in 2 days.

**Option D is the real long-term answer** (the entire top of the ladder runs
fast policies) but is a multi-week RL effort, out of scope for a 2-day ship;
its cheap sub-variant (value-truncation on v2.0.0) already gated neutral in
Phase F and will not move rating.

**Data request to complete §B:** please drop our actual v2.1.0 loss episodes
(vs Majkel / kashiwashira / Garchomp) into `data/loss_episodes/` — the
self-play diagnostic strongly implies the tempo/close-out root cause, but real
loss transcripts vs the top decks would confirm it and sharpen whichever
option you choose.
