# Phase 2 — What the current top-10 does to win

Source: 883 current-top-10 sides (496 wins) from the 07-10/07-11 daily
datasets (`pop_current.json`). Win endings: **prizes 64%, deckout 20%,
no-active 15%**; median win length 15 turns.

## Pattern 1 — Fezandipiti/Dudunsparce engine race (ranks 1, 3, 8)

Majkel1337, Yushin Ito, LiamK. Turbo draw engine (Poffin/Poké Pad into
Dunsparce→Dudunsparce, Rare Candy stage-2) converting card advantage into a
prize race; median winning game ~12–13 turns, wins overwhelmingly by prizes
with a no-active side dish (opponent runs out of attackers before prizes run
out). This is the deck the previous Alakazam pilots (including Majkel himself)
migrated to — same engine, better attacker package.

## Pattern 2 — Crustle attrition shells (ranks 2, 5, 7, 10)

Budew, MPGaming, S4nkurero, Eduardo. Slow games (winning median 25–32 turns),
win by a mix of prizes-eventually, opponent deckout, and no-active. They tax
every non-attrition opponent with a sub-55% matchup (see subsection) and beat
each other on small edges. Budew (#2) is the best-performing pilot of the
shell (56% overall in sample).

## Pattern 3 — Dedicated stall (rank 4) and bench denial (rank 6)

- kashiwashira: Team Rocket's Mewtwo/Spidops stall at 30 ms/decision — the
  07-08-era rank-2 recipe is back in the top-5 unchanged.
- BigBugginnings (Dragapult/Fezandipiti): notable **no-active specialist** —
  7 of its 11 anti-Crustle wins end no-active (kills every attacker the
  opponent fields rather than racing prizes).

## Pattern 4 — The lone search agent is being squeezed

Yushin Ito (~1.5 s/decision) fell #1→#3 and has the *worst* anti-Crustle
record of the top teams (42%, with **34 of 45 losses by deckout**): search
optimizes the prize race and walks into attrition clocks. Evidence that raw
search without an attrition model tops out here — consistent with our own
v2.0.0/v2.1.0 history.

## Requested subsection: how the current top-10 handles Crustle stall

Context (Phase 1, C2): v2.2.0 went **1W-8L** vs Crustle decks, all 4 deckout
losses, BC looping Gabite's draw ability into its own deckout.

Encounter rate first: **top teams cannot avoid the matchup** — 254 of 883
current top-10 sides (29%) face a Crustle deck (5 of 10 top teams pilot one).
Population-wide they go 131W-123L (51.6%): even at μ1150+, Crustle is a
coin-flip tax. Per-team:

| team | vs Crustle | how they win | how they lose |
|---|---|---|---|
| Budew (#2, Crustle mirror) | 11W-4L (73%) | prizes 7, deckout 2, no-active 2; med T26 | rare, mixed |
| kashiwashira (#4, stall) | 17W-9L (65%) | prizes 12, no-active 5; med T15 | deckout 3, prizes 4 |
| nasuo445 (#9, our teacher) | 5W-3L (62%) | no-active 3, prizes 2; med T16 | **deckout 3 — all three losses** |
| Majkel1337 (#1) | 38W-26L (59%) | **prizes 26 fast (med T12)**, no-active 10 | prizes 15, deckout 9 |
| BigBugginnings (#6) | 11W-8L (58%) | **no-active 7**, prizes 4; med T13 | prizes 6 |
| S4nkurero (#7, Crustle mirror) | 3W-2L (60%) | deckout 2; med T32 | prizes |
| Yushin Ito (#3, search) | 33W-45L (42%) | prizes 24; med T13 | **deckout 34 of 45** |
| MPGaming (#5, Crustle mirror) | 6W-13L (32%) | mixed, med T25 | prizes 10 |
| LiamK (#8) | 7W-12L (37%) | mixed; med T29 | deckout 8 |

Three viable anti-Crustle lines exist in the data:

1. **Race it before the clock matters** (Majkel): win by prizes at median T12
   — end the game while stall is still setting up. Requires engine-deck speed
   our Garchomp list doesn't have.
2. **Bench denial / no-active** (BigBugginnings, and nasuo's own 3 no-active
   wins): don't chase 6 prizes — KO every attacker they field. Crustle shells
   run few attackers; the win condition is theirs to lose. Median T13-16, so
   it also dodges the deckout clock.
3. **Out-attrition it** (Budew/S4nkurero mirrors, kashiwashira): only works
   with a deck built for it (resource recovery, thin draw usage). Not
   available to a Garchomp list that must draw to function.

The instructive one is **nasuo himself: 62% vs Crustle with the exact deck we
pilot** — his wins are no-active/prize kills by T16, his only losses are the
same deckout death our BC suffers. So the deck has a legitimate anti-Crustle
line (line 2), the teacher plays it *most* of the time, and BC-full failed to
reproduce it (1W-8L, 0 no-active wins vs Crustle). Two non-exclusive reads,
for Phase 3: (a) the 812-episode harvest under-sampled Crustle matchups so BC
never learned the against-stall mode-switch (win-side-only extraction makes
this worse — we only trained on nasuo's ~62% winning games, and stall games
are his loss-heaviest segment); (b) the behavior needs game-length/deck-count
context the policy may not represent. Either way this is a data-coverage
question before it is an architecture question.
