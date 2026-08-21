# Real cross-deck matchup measurement — Grimmsnarl+rules vs actual opponent decks

**Nothing submitted.** Header committed before the full-sample runs below it.

## Why this exists

Every self-play measurement all session has been a **mirror** (Grimmsnarl vs
Grimmsnarl). A mirror can never test matchup-specific behaviour — the
opponent is always our own deck. This harness (`crossdeck_test.py`) runs our
Grimmsnarl side (with whatever rule flags) against an **actual different
decklist** — Kangaskhan/Raging Bolt, Fezandipiti/Dudunsparce, TR Mewtwo/
Spidops — piloted by v1-alone on that deck. Seats alternate per game to
cancel first-player bias.

**Scope of the claim, stated up front:** the opponent side is v1-alone, a
generic pilot, not a top-10-calibre one. This measures "how does our policy
perform against a plausible board from that archetype", not "how would we
fare against the actual top-10 pilot of that deck." It is still the first
time this session has measured our policy against a genuinely different
board at all.

## Arms — 100 games each, our side = Grimmsnarl (E1+E2+T1+T2, the shipped
## TARGET_FIX_SHIP.md build), opponent = v1-alone on the named deck

| matchup | opponent deck |
|---|---|
| **grimmsnarl_mirror** | Grimmsnarl (control — should reproduce the T1T2 self-play numbers, validating the harness) |
| **kangaskhan** | Mega Kangaskhan ex / Raging Bolt ex |
| **fezandipiti** | Fezandipiti ex / Dudunsparce |
| **mewtwo** | TR Mewtwo ex / TR Spidops |

## PRE-REGISTERED READING — fixed before running

**Harness validation, checked first:** `grimmsnarl_mirror` prize velocity
should land close to T1T2's established self-play figure (0.4953, 300g). A
large deviation would mean the harness itself is biased, not that anything
about the matchup differs — in that case the real-matchup numbers below are
not to be trusted until the harness is fixed.

**No pass/fail band on the real matchups.** These are point measurements, not
a screen — we have never had this data before, so there is nothing to compare
it to except itself and the mirror control. Reported plainly: prize velocity,
own turns/game, attack-when-legal, prizes/game, per matchup.

**What would flag a rule for review:** any matchup where velocity is
substantially *below* the mirror control despite T1 firing at comparable
rates — that would suggest T1's static prize-value weighting is miscalibrated
for that specific opponent board (e.g., if the opponent runs almost no ex
Pokémon on bench, T1 degenerates toward its energy/HP-ratio tie-breakers,
same structural point as the Archaludon test but for a real ladder opponent
rather than a deck we don't play).

---

## RESULTS

100 games each, our side = Grimmsnarl (E1+E2+T1+T2), seats alternated.

| matchup | n | velocity | own turns | attack-when-legal | prizes/game |
|---|---|---|---|---|---|
| **grimmsnarl_mirror** (control) | 100 | **0.4819** | 7.47 | 89.0% | 3.60 |
| Fezandipiti / Dudunsparce | 100 | 0.4694 | 6.71 | 86.3% | 3.15 |
| **TR Mewtwo / Spidops** | 100 | **0.6219** | 6.93 | 87.7% | 4.31 |
| **Kangaskhan / Raging Bolt** | 100 | **0.4026** | 7.55 | 83.9% | 3.04 |

### Harness validation — PASS

Mirror control (0.4819) sits close to T1T2's established self-play figure
(0.4953 at n=300, 0.5139 at n=100) — within the run-to-run variance already
characterised this session (0.019–0.025). **No harness bias detected; the
real-matchup numbers below are trustworthy.**

### The finding

**This is the first time this session has measured our policy against an
actual different board, and the three matchups are not alike.** vs TR
Mewtwo/Spidops we are **materially favoured** (0.62, +0.14 over our own
mirror ceiling). vs Fezandipiti we are roughly at parity with the mirror. **vs
Kangaskhan/Raging Bolt we are clearly worse (0.40, −0.08)** — the only
matchup below the mirror control by more than run-to-run noise.

**This corroborates two independent pieces of evidence already on record:**

1. DECK_SWEEP.md flagged a Kangaskhan-vs-Grimmsnarl cell at 23W-10L (one
   direction, n=33) as a *possible* bad matchup, explicitly non-quotable at
   that n and never confirmed. This cross-deck measurement, from an
   independent method (self-play against the actual decklist, not ladder
   win/loss counting), lands in the same direction.
2. MATCHUP_MINING.md's target-selection mining found Kangaskhan/Raging Bolt
   had the **single largest per-archetype deviation** on Shadow Bullet
   targeting of any matchup measured (max-prize 78.7% vs pooled 59.9%, a
   19-point gap — the largest in the table).

**Kangaskhan is simultaneously our worst-measured matchup and the matchup
where top-10 play diverges most from pooled behaviour. That is the highest-
leverage remaining target for a matchup-specific rule**, not a Fezandipiti or
TR Mewtwo tune — those are already fine or favourable.

Proceeding to design a narrow, single-matchup fix targeting exactly this.

### Artifacts

| path | contents |
|---|---|
| `stage4/rl_ours/crossdeck_test.py` | the cross-deck harness |
| `stage4/rl_ours/crossdeck_analyze.py` | our-side prize velocity, seat-alternation aware |
| `scratchpad/s3/crossdeck_{grimmsnarl_mirror,kangaskhan,fezandipiti,mewtwo}_full/` | 100 games each |
