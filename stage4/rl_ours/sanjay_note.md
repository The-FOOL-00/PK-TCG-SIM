# Note to Sanjay — algorithm decision + lab-visit ask (2026-07-12)

Draft for the user to send. ~200 words.

---

Sanjay — we ran a full algorithm survey after our BC line failed its gate
(39.0% vs v2.2.0, 300 games). Decision: **PPO league self-play** on list-0,
warm-started from our BC-v2 weights with a KL anchor, shipping the raw
policy head. Core reasons: we ship a 1ms search-free policy, so PPO trains
the exact deployed artifact; and its worst case is plateau-at-warm-start,
not prior destruction.

On your az_v3_run1 regression (34→5%), our diagnosis, four causes in order:
(1) 10k buffer = under 2 iterations of data — prior overwritten by ~it 4;
(2) opp_frac=0.4 vs a 65%-winning engine from iteration 1 — value head
poisoned before search targets mean anything; (3) n_det=2 — huge
hidden-info target variance; (4) no KL anchor to the SL prior (and lr
unlogged). Also: your gates measure at 30 sims; the ladder artifact is the
raw net — worth gating search-off.

We're keeping most of your infra: worker respawn, gatekeeping, leakage-audit
methodology, torch→numpy export, lab packaging. Replacing only the MCTS
core (shelved as our pivot) and the encoder (ours carries the warm start).

The ask: would you redirect tomorrow's 24h lab slot to a PPO run on list-0
with our BC-v2 warm start and corrected config, rather than continuing AZ
on the strand-locked deck? Two labs on one algorithm gives comparable
data; two algorithms on two decks gives anecdotes. Timing caveat: our
trainer lands this week — if it isn't ready when you arrive, the interim
option is your AZ with the four fixes applied as a control arm. Your call.
