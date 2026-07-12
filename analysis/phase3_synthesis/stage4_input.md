# Phase 3 — Synthesis for Stage 4 (diagnostic)

Inputs: Phase 1 (`analysis/phase1_v2_2_0_losses/inference.md`), Phase 2
(`analysis/phase2_meta_shift/*.md`), quantifications in `quantify.py` output,
teacher survey in `teacher_candidates.md`.

## 3.1 Loss clusters × current top-10 win patterns

| our loss mode | top-10 exploitation | verdict |
|---|---|---|
| C1 — lost damage races from an established board (44%) | Pattern 1: the rank-1/3/8 engine decks win exactly this way, closing by prizes at median T12–13; our losses hand 6 prizes over by T12–18 with ≤2 taken | **Direct hit.** The dominant top-10 style is a better executor of the thing that already beats us at μ700. Gets worse, not better, as μ rises |
| C2 — Crustle stall self-deckout (25%) | Pattern 2: Crustle shells now hold 5/10 top seats; 29% encounter rate at the top; deckout is 20% of top-10 wins as a deliberate condition | **Direct hit.** The hole scales with rating — the archetype we are 1W-8L against is twice as common at μ1150 as at μ700 |
| C3 — mirror losses (9%) | nasuo (the mirror's best pilot) is himself declining, 3W-12L vs the consensus engine | Low priority — the mirror pool shrinks as the deck fades |
| C4 — setup accidents (9%) | no pattern targets it; base-rate variance | **Idiosyncratic, ignore** |
| C1-specific archetype (Mega Lucario) | zero Lucario in top-10; ceiling observed μ~1034 | The *archetype* is a μ700–1030 phenomenon, but the *failure mode* (race conversion) transfers to the top's engine decks |

Nothing about our loss profile is idiosyncratic except C4. Both dominant
clusters are amplified, not diluted, in the current top-10 pool.

## 3.2 Teacher staleness — quantified

- nasuo445: rank 7 → 9, sample win rate 56% → 47% in two days.
- The collapse is **matchup-specific**: vs the new consensus engine
  (Fez/Alakazam list-0 family) he went **17W-16L → 3W-12L (20%)**. Vs
  everything else he is still 17W-11L. The deck that took ranks 1/3/8 farms
  him — and that archetype plus its neighbors is ~30% of the top-10 pool.
- What BC-full learned that gets punished: the deck's whole game plan (T6
  Garchomp, race from an established board) loses the race to the engine's
  T12 closure; and its anti-Crustle line demands mode-switching BC failed to
  express (below).
- **Correction to a Phase 2 hypothesis**: the 812-episode harvest was NOT
  missing anti-Crustle data — 16 of nasuo's 81 winning sides (20%) are vs
  Crustle, 7 of them no-active kills. BC had the examples and still produced
  0 no-active wins and 4 self-deckouts (twice while AHEAD on prizes). C2 is an
  **expression failure** (rare-mode behavior drowned by the dominant racing
  mode + compounding error over 20+ turn games), not pure data absence. This
  weakens any plan whose only ingredient is "add more of the same data."
- Ceiling: even perfect imitation now lands at a declining μ~1100 deck that
  the ruling archetype beats 80/20. **Yes — BC-full's ceiling is capped by
  teacher staleness, and the cap is deck-level, not just pilot-level.**

## 3.3 Behavioral gaps (v2.2.0 vs current top-10 median)

1. **No attrition mode.** Top-10 wins end deckout 20% of the time on purpose;
   our agent cannot bank resources, manage its own deck count, or pursue
   no-active as a win condition — it fires every draw ability every turn and
   deckouts itself. (nasuo with the same deck: 62% vs Crustle; us: 11%.)
2. **Slow prize closure.** Top winners convert an established board into 6
   prizes by median T12–13 (Boss's Orders timing, KO sequencing). We reach the
   same board state (first attack T6, Garchomp T6) and take ≤2 prizes by
   T12–15 in losses; our own wins take median 17.5 turns.
3. **Structurally countered matchup, ~30% of the top pool.** Against the
   consensus engine family our deck loses 80/20 in its best pilot's hands.
   No behavioral fix on this deck removes gap 3.

## 3.4 Honest read: RL fine-tune vs fresher teacher

RL fine-tune of BC-full (Branch A) can plausibly attack gaps 1–2 (they are
decision-quality problems on states we already visit). It cannot touch gap 3
— the deck itself is countered by the pool's ruling archetype — and our RL
opponent pool would be v1-piloted meta decks, i.e. weak pilots (the Alakazam
μ548 lesson: local pools built from our own piloting lie about the ladder).
Expected value: caps out around the teacher's own declining trajectory
(μ~850–950 optimistic). **The gap is a data-quality/teacher problem first**:
the top of the ladder just handed us a better teacher on a deck we already
have intel on (list-0 = metaB + 7 cards), with two pilots and ~85 win-sides/
day of fresh replays. Re-harvest is cheap (pipeline exists), the BC recipe is
gate-proven, and RL benefits more from the stronger warm start afterward.

## 3.6 Sanjay-stack strand check

Highest-μ Lucario team observed anywhere in the current top-10's opponent set:
**μ=1034** (ImANoob1122 1026, mitomeat823 1034, tomo11111 1014; 7 teams total,
all 986–1034). Zero Lucario above that band and zero in either top-10
snapshot. His frozen scores (751.9, 803.4) sit inside the archetype's observed
range; the archetype's empirical ceiling is ~μ1030, safely below the top-10
cut (~1125). **Strand-locked, with headroom to roughly μ1000 but no observed
path into the top-10.** Not a competitor to Stage 4; his μ751 sub is,
however, a useful sparring opponent for our C1 cluster (fighting aggro, 60
replays already on disk).

## 3.7 Branch recommendation: **B (re-harvest → BC-full-v2 → RL)**

- **Teacher/deck**: list-0 (metaB_alakazam + 7-card update), pilots Majkel1337
  (#1) and Yushin Ito (#3). Primary imitation target Majkel (fast policy,
  consistent); Yushin's sides as candidate augmentation — decided at data
  prep with pilot-tagged extraction stats.
- Why not A: gap 3 is deck-level; RL on a countered deck vs weak local pilots
  is optimizing the wrong thing against the wrong opponents.
- Why not C: BigBugginnings plays Dragapult/Fezandipiti — a different deck.
  Option encodings and decisions are deck-relative; his anti-Crustle behavior
  cannot be grafted onto a Garchomp policy. And 3.2's correction shows C2 was
  never primarily a coverage gap. The only same-deck augmentation source is
  nasuo himself (16 anti-Crustle wins — already in the data).
- Branch B *also* addresses C2 the way the new deck does: Majkel beats Crustle
  59% by racing to T12 — "always race" is a single-mode behavior BC
  demonstrably can imitate, unlike nasuo's mode-switch.
- Deck familiarity discount: list-0 is 53 of 60 cards identical to
  metaB_alakazam.csv, whose card interactions we already mapped in the v2.1.0
  era; encoder/context work is incremental.
- **Risks, stated**: (1) imitation gap — nasuo-BC landed ~430μ below its
  teacher; Majkel-BC starting from μ1231 may land μ800–900, an improvement
  but not top-8 by itself → RL fine-tune remains the second stage, now from a
  stronger start. (2) mixed-pilot data may blur the policy → resolve with
  pilot-tagged extraction + Majkel-only baseline. (3) list-0 could churn
  again — mitigated by re-checking list stability at data-prep stop point.

### Timeline (Branch B, target ≤18 days to G7a — projected ~9)

| dates | work |
|---|---|
| 07-12..13 | data prep: 340 list-0 sides already on disk; extraction + deck tables for list-0; daily harvest of new dailies; **stop point: dataset stats** |
| 07-14..16 | volume accumulates to ~400–600 win sides; train BC-v2 (two-head, PL, seed sweep); held-out C1/C2 eval; **stop point: training report** |
| 07-17..19 | piloting-signature check; G7a vs v2.2.0 (300g); **stop point: kill criterion** |
| 07-20..24 | G7b Crustle-heavy archetype pool + G7c ablation; speed check; **stop point: ship decision** |
| 07-25..08-08 | RL fine-tune on BC-v2 warm start (own gate battery, same stop points) |
| 08-09..16 | buffer; ship final; writeup notes |

Rescope trigger (Aug 10) has ~2.5 weeks of slack even if BC-v2 needs a second
training iteration.
