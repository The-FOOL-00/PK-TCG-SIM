# Writeup review request — Strategy track

**What I need from you:** a fact-check pass and a call on the four open decisions
at the bottom. Not a copy-edit — the numbers matter more than the prose.

---

## 1. First, a deadline correction

Every planning doc in our repo says **"2026-08-16 submission lock"** as if it
governed everything (`LAB_RUNBOOK.md`, `lab/FIRST_ACTION.md`, `scoping.md`,
`CANARY_SUBMISSION_LOG.md`, `STATUS_lab_day1.md`, `algorithm_survey.md` §11).
That is wrong. This is **two separate Kaggle competitions**:

| track | what it takes | entry / team merger | final submission |
|---|---|---|---|
| Simulation | the agent + ladder score | 2026-08-09 | **2026-08-16** |
| Strategy | this writeup | **2026-09-06** | **2026-09-13** |

So the agent freezes Aug 16, but the writeup has roughly four more weeks after
that. **Please confirm you are entered on the Strategy competition specifically
and that our team is merged there** — being teamed on Simulation does not carry
over, and that merger closes Sep 6.

## 2. What's in this package

| file | what it is |
|---|---|
| `WRITEUP_KAGGLE.md` | **the paste target.** 1,999 words of body text, under the 2000 limit. Candidate title/subtitle strings for the form fields sit above the `---` rule; those are scaffolding, not pasted. |
| `figures/fig1..4_*.png` | four media-gallery figures |
| `WRITEUP_SUBMIT.md` | the previous draft, for diffing |
| `WRITEUP_FULL.md` | ~7,700-word complete record — use this to fact-check any claim in the short version |

## 3. What changed from `WRITEUP_SUBMIT.md`

**Reordered.** The old draft opened on a table of seven KILLs and closed on
"μ697 vs μ1150." A judge reading only the first and last screen takes away
"didn't work." The judging criteria are *"originality of deck construction and
algorithmic ingenuity"* — so envelope closure, the deck, and the pilot now come
first (§2–4), and the negative results follow as method (§5–6). §8 Honest Limits
is unchanged, word for word. Nothing was softened; it was resequenced.

**Deck section promoted and given an explicit claim.** "Originality of deck
construction" is a named criterion and the deck was buried at §5 of 8. It is now
§3 and states the argument plainly: *the decklist is a derived quantity* — we
measured the pilot first, then picked 60 cards its priority order already
executes.

**Two tables deleted, because a figure now carries them.** The 7-row closure
table (→ Fig 1) and the sequencing table (→ Fig 3). The 8-row kill table shrank to
4 rows since Fig 4 covers the other five. That is where most of the ~540 words
came from; almost no claims were dropped.

**Claims that were cut** — flag if you want any restored:
- the dynamic-damage attack rule (one of the four failed mined rules)
- the `20/20` ladder deck-identity audit line
- exact tier weights for attach/evolve/item/bench/ability (order kept; only
  `WEIGHT_LETHAL = 100 000` still named, because §5 refers back to it)

## 4. Please fact-check these specifically

I transcribed every number from the existing writeups without recomputing any of
them. The ones I'd most want a second pair of eyes on:

1. **Fig 1 / §2 closure table.** Ogerpon 80.9% and Dragapult 46.3% came from the
   second harness. I marked them hatched in Fig 1 with "ranking transfers,
   absolutes not comparable" in the legend. Is that caveat strong enough, or
   should those two decks come out of the headline figure entirely?
2. **§5 sequencing numbers.** The writeups carry two slightly different pairs —
   61.8% / 43.0% in the leverage table, and 59.5%→89.5% / 42.4%→0.1% for the
   E1/E2 ablation. I used the leverage numbers in prose and the ablation numbers
   in Fig 3. Confirm those are measured on different sets and that mixing them
   this way is honest.
3. **§4 kill table**, "Five analytic / learned policies → 4 KILL, 1 ship → μ697."
   Check that count against your record.
4. **§6 lie #1**, the 74.7% gate versus μ548/μ614, and the byte-identical rank-1
   list claim.

## 5. Four open decisions — your call

1. **Which title and subtitle?** Options are at the top of `WRITEUP_KAGGLE.md`.
2. **Do we link the GitHub repo** (`The-FOOL-00/PK-TCG-SIM`) in Attachments?
   "Algorithmic ingenuity" reads better with code attached, but check the repo is
   public and carries no competition data we can't redistribute — the README says
   official assets are gitignored, worth verifying before we expose it.
3. **Media gallery order.** I'd lead with Fig 1 (closure across seven archetypes)
   since it is the thesis in one image. Alternative is Fig 4 (the trap scatter),
   which is more provocative but needs Fig 1's setup to land.
4. **Do we mention the RL/PPO work at all?** Right now the short version says
   nothing about Stage 4 — the capacity ladder, the K1/K2 gates, the
   function-preserving Net2Wider growth. It is real algorithmic work and
   "algorithmic ingenuity" is a named criterion, but it produced no shipped
   improvement (flat ~27% over 83k games) and there is no word budget left for it
   without cutting something above. My read: leave it out of the 2000 words and
   let the linked repo carry it. Overrule me if you disagree.

## 6. Heads-up on the form itself

The Kaggle writeup form warns *"Another editor recently updated this Writeup."*
Whoever pastes first should open the newest version and reconcile rather than
overwrite. As of this note the form is still empty — title, subtitle, description,
media, attachments all blank.
