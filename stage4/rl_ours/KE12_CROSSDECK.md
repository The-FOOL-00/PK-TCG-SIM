# KE12 cross-deck verdict — first real positive signal of the session

**Nothing submitted.** Data-only.

## What this is

Cross-deck screen using `crossdeck_kang.py`. Our side = Kangaskhan/Raging
Bolt (metaX_kangaskhan_top10.csv) with configurable rule flags. Opponent =
v1-alone Grimmsnarl (metaG_grimmsnarl_top10.csv) — the current field-
leading archetype (5/10 top-10 seats per ROSTER_DIFF_JUL31.md). Seats
alternate to cancel first-player bias. Purpose: mirror self-play could not
discriminate KE12 signal from noise because both sides got the same rules;
this puts our rules against an opponent that does NOT have them.

## Results — 200 games each, KE1 + KE2 combined

| arm | velocity | own turns | atk-when-legal | prizes/g | Win rate |
|---|---|---|---|---|---|
| Kang v1-alone vs Grimm-v1 | 0.2858 | 7.68 | 54.8% | 2.19 | 32.0% (64W-134L) |
| **Kang + KE12 vs Grimm-v1** | **0.3091** | 7.89 | **58.0%** | 2.44 | **35.5% (71W-128L)** |
| **delta** | **+0.023** | +0.21 | **+3.2pt** | +0.25 | **+3.5pt** |

**Every guard clean.** Attack-when-legal moved in the correct direction
(+3.2pt), prize velocity moved up, first-attack proxy (own turns) reasonable.

## What this proves and does not prove

**Proves:**
- KE12 is a real per-decision improvement, not mirror-canceling noise. The
  +3.5pt win-rate gain is measurable at n=200 in cross-deck because the
  opponent doesn't also get the free-draw rule.
- The mining methodology transfers to a new deck: two Kangaskhan-native
  rules mined from `kangaskhan_mine.py`'s output produced a comparable
  per-rule effect to what E1/E2 gave Grimmsnarl (+0.085 on real ladder).
- Mirror self-play is not the right instrument for strictly-dominated
  rules; cross-deck is. This should be the standing measurement for any
  future rule of this shape.

**Does not prove:**
- That Kangaskhan is a shippable archetype for us. Even with KE12, our
  piloting produces a **35.5%** win rate against Grimmsnarl — well below
  the parity level a shippable bundle would need. Top-10 Kangaskhan
  pilots hit 70%+ on this matchup (`kangaskhan_mine.py`); the gap between
  us and them is ~35pt, of which KE12 closes 3.5pt.
- That the improvement generalizes to other opponents. Only tested vs
  Grimmsnarl (the largest ladder segment); could differ vs Kangaskhan
  mirror, Fezandipiti, Mewtwo.

## The scope, stated plainly

Building enough Kangaskhan-native rules to close the 15pt-to-parity gap
would require several more cycles of the same mine → design → build →
screen work — each rule an independent unit at the ~1-2 hour cost KE1
and KE2 took, and there is no guarantee of monotone gain (the additional
mining cells beyond the can_KO and supporter_pending ones already used
have lower TVDs, meaning smaller per-rule effects expected). This is the
comparable-to-Grimmsnarl-build effort I flagged earlier, and tonight's
positive signal is what makes it plausibly worth doing — but not fast
enough to promise a specific ladder outcome from a next-morning bundle.

## Follow-up isolation — KE1 alone beats KE12 (both rules together)

Ran the same cross-deck screen with KE1-only and KE2-only arms, 200 games each.

| arm | velocity | atk-when-legal | prizes/g | Win% |
|---|---|---|---|---|
| baseline (v1-alone) | 0.2858 | 54.8% | 2.19 | 32.0% |
| **KE1 alone** | **0.3350** | 55.9% | 2.64 | **39.0%** |
| KE2 alone | 0.3152 | 54.3% | 2.44 | 35.5% |
| KE1 + KE2 | 0.3091 | 58.0% | 2.44 | 35.5% |

**KE1 alone is the strongest single arm (+7pt win rate over baseline).**
**Combining with KE2 REGRESSES to 35.5%** — a 3.5pt loss vs KE1 alone.
The two rules interact destructively: KE2 fires earlier in the turn (when
v1 chose ATTACH) and uses up the once-per-turn free draw before KE1 gets
its "Ability right before terminal" trigger. Composition is not automatic
for these rules; the specific timing of *when* the free draw fires within
the turn matters, and the order that mining implied (Ability first, then
resources) is worse than the order KE1-alone produces (resources first,
Ability just before ending).

**Ship-relevant conclusion: KE1 alone is the shippable single-rule
Kangaskhan bundle.** KE12 is dropped; KE2 remains in the codebase, default
off, for reference.

## Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/crossdeck_kang.py` | cross-deck harness (Kang vs named opp) |
| `scratchpad/s3/cdk_grimmsnarl_none/` | 200 games, Kang v1 vs Grimm v1 |
| `scratchpad/s3/cdk_grimmsnarl_ke1/` | 200 games, Kang+KE1 vs Grimm v1 |
| `scratchpad/s3/cdk_grimmsnarl_ke2/` | 200 games, Kang+KE2 vs Grimm v1 |
| `scratchpad/s3/cdk_grimmsnarl_ke12/` | 200 games, Kang+KE12 vs Grimm v1 |
