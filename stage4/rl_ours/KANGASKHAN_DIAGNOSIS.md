# Kangaskhan/Raging Bolt deficit — root cause, not a targeting bug

Continuation of CROSSDECK_MATCHUP.md's open question: is the 0.4026 vs 0.4819
velocity deficit fixable by a targeting rule, or structural?

## Deck composition (checked first)

16 of 17 non-energy Pokemon slots in the Kangaskhan/Raging Bolt list are
ex/mega (HP 170-300); our own deck has one ex card. Bench is uniformly
high-value, which already predicts T1's prize-value criterion mostly *ties*
in this matchup rather than mis-targets — the opposite failure mode from the
one CROSSDECK_MATCHUP.md's pre-registration flagged.

## Damage/KO accounting, 100 games each (`HpChange` log, `putDamageCounter=True`)

| matchup | dmg dealt (by us) | dmg taken | our attacks | opp attacks | our board-wipe losses |
|---|---|---|---|---|---|
| mirror | 26850 | 30500 | 365 | 377 | — |
| kangaskhan | 26470 | 15660 | 372 | 359 | 5/100 |

**Our total damage output and attack volume are essentially unchanged between
matchups** (26470 vs 26850 dealt, 372 vs 365 attacks) — we are not attacking
less, or attacking worse. **We also take less damage** (15660 vs 30500) and
lose to board-wipe in only 5/100 games. What's different is prizes/game (3.04
vs 3.60): the same damage output buys fewer knockouts because the opposing
roster's HP pool is dramatically bulkier. This is a raw damage/HP mismatch,
not a decision-quality problem — confirmed directly from logs, not inferred.

## Conclusion

**No targeting or sequencing rule addresses this.** T1/T2 operate on *which*
target to hit or switch to; they don't change how much damage an attack does.
The deficit is the deck matchup itself — same lesson as ARCHALUDON_TEST.md
from the other direction: rule quality doesn't compensate for a raw stat
disadvantage, in either direction. A fix here would require deck-level damage
scaling (different attackers, energy acceleration) — out of scope for a rule,
and not something to build speculatively against a single archetype's generic
v1-alone proxy.

**Recommendation: do not pursue a Kangaskhan-specific rule.** It would very
likely repeat the negative-transfer surprise from AR-full — a rule assumption
built for a different HP profile applied where it doesn't hold — for a
correctly-diagnosed problem it cannot fix. This closes out
CROSSDECK_MATCHUP.md's open item with a negative result, reported plainly.
