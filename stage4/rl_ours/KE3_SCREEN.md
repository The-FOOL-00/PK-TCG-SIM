# KE3 — Ogerpon Teal Dance free-attach ability rule, screen

**Nothing new submitted.** Screen-only; KE1-only bundle (already delivered)
remains the shipped Kangaskhan position.

## What KE3 is

Second Kangaskhan-native free-ability veto, targeting Teal Mask Ogerpon ex
(id 96, 3 copies in the Kangaskhan deck). Ability text: *"Teal Dance —
Once during your turn, you may attach a Basic {G} Energy card from your
hand to this Pokémon. If you attached Energy to a Pokémon in this way,
draw a card."* Once/turn, no discard cost, separate from the normal
per-turn energy attach action — strictly-dominated by the same argument
as KE1's Run Errand veto.

New helper: `_has_free_attach_ability` — matches *"once during your turn"*
+ *"attach"* + *"basic"* + *"energy"* + *"hand"* + *"this pok"* − *"discard"*.
Unlike KE1's helper, does not require active-spot (Teal Dance fires from
bench too). Correctly narrow — verified detects only Teal Mask Ogerpon
(rejects Wellspring Mask Ogerpon, Kangaskhan, Munkidori, Raging Bolt,
Fezandipiti, Meowth).

## Design fix mid-screen: trigger narrowed after first-run regression

Initial version triggered on {ATTACK, RETREAT, END, ATTACH}. First cross-
deck run showed KE13 (KE1 + KE3 combined) crashed to **31.2%** vs baseline
32.3% — the ATTACH trigger reproduced exactly the destructive interaction
KE2 had shown when combined with KE1. Root cause: swapping ATTACH → Ability
consumes the once-per-turn slot before KE1 gets its "Ability right before
terminal" moment.

**Fix**: narrowed trigger to {ATTACK, RETREAT, END} — matches KE1's shape
exactly, so KE1 and KE3 address disjoint decision types (KE1: Mega Kang;
KE3: Ogerpon). Re-ran both cross-deck arms.

## Results — 200 games each, cross-deck vs v1-alone Grimmsnarl

| arm | velocity | atk-when-legal | prizes/g | Win% | ke1_fires | ke3_fires |
|---|---|---|---|---|---|---|
| baseline (no rules) | 0.2858 | 54.8% | 2.19 | 32.3% | 0 | 0 |
| **KE1 alone** | **0.3350** | 55.9% | 2.64 | **39.2%** | 695 | 0 |
| KE3-narrow alone | 0.3156 | 58.0% | 2.44 | 36.4% | 0 | 385 |
| **KE1 + KE3-narrow** | 0.3156 | 55.2% | 2.44 | 33.3% | 507 | **4** |

## VERDICT: KE3 does not compound with KE1 as designed

**KE3 alone is a real positive** (+4pt over baseline) — the ability
detection and veto mechanism both work as intended. But **KE13 combined
delivers only +1pt over baseline**, dramatically underperforming KE1
alone's +7pt.

Fire counts explain why: in KE13, KE3 fires only **4 times per 200 games
(vs 385 alone, 99% suppressed).** KE1 fires first in the hook chain and
consumes the once-per-turn ability slot on our active — by the time KE3
checks, the engine no longer offers OT_ABILITY on the menu for the pattern
KE3 targets (because Run Errand already fired that turn, and Ogerpon's
Teal Dance is a separate ability but competes for the same MAIN-decision
opportunities in most sequences).

**Rule composition fails a second time.** Both KE12 and KE13 confirmed the
same shape of failure: adding a second free-ability veto on top of KE1
regresses toward or below baseline, because the two rules compete for the
same MAIN-decision slots rather than addressing genuinely disjoint states.

## What ships

**KE1-only bundle (`dist/kang/v1_kang_ke1.tar.gz`, sha `681fb6e7…122008`)
remains the shipped Kangaskhan position.** No rebuild. KE3's flag stays
in the codebase, default off, for the record.

## Broader methodology finding

Tonight's tests establish a firm rule for future work: **any second-rule
veto on this deck must fire on genuinely disjoint decision states**, not
just different Pokemon. Two rules that both divert v1's terminal action
to a free ability will always compete for the same MAIN slots, and only
the first-in-chain will fire. This means the KE1-family shape is
saturated — further ability-vetos won't compound.

The next-viable-shape for a stackable rule would need to address a
category KE1 does not (e.g., target selection like T1/T2 on Grimmsnarl,
or a completely different pattern like retreat-timing). That requires
mining specifically for cells where the ABILITY channel is not the
top-10-vs-us gap. Left as a next task, not started this session.
