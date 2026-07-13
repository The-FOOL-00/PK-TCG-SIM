# Gumbel-AlphaZero pivot — scoping note (distant contingency)

**Status: NOT started, NOT authorized.** This branch triggers only if BOTH
capacity rungs fail — i.e. run2 (128k) AND run3 (256k) both read
`verdict.py = CAPACITY-LIMITED, HIGH-CONFIDENCE`. It is the designated pivot from
`algorithm_survey.md` (Rank 2, the best search-based option) once PPO capacity
growth is exhausted. This note exists so that IF we reach that branch we are not
scoping cold. Light effort only; revisit properly at trigger time.

## Why this is the pivot (one line)
PPO-from-BC optimizes the *raw policy head* we ship. If more capacity still can't
close the Alakazam-vs-Garchomp matchup, the ceiling is likely the **reactive
single-forward policy class**, not the parameter count — a *search* at decision
time (lookahead over determinized hidden state) is the next lever. Gumbel-AZ is
chosen over vanilla AZ because it keeps target quality valid at **low simulation
counts** (§4 of the survey: vanilla AZ's visit-count targets degrade at the 32–100
sims our throughput budget allows; Gumbel's completed-Q targets do not).

## Reusable from Sanjay's existing AlphaZero infrastructure
His stack (SANJAY_SESSION_REPORT.md) was built for vanilla/PUCT AZ and is
**validated** — the pivot is "cheap" precisely because most of the search
machinery already exists and was gatekept:

| Component | Reuse | Note |
|---|---|---|
| ISMCTS + determinization | **reuse directly** | Sampled-hidden-state search over the cabt obs; shelved by PPO, reactivated here. Already respawn-hardened + gatekept. His `n_det=2` was too few (target-noise floor); Gumbel tolerates more determinizations at fewer sims. |
| Engine-as-league-opponent wrapper | **reuse** | Same v2.2.0 / v1-archetype opponents; our league sampler (`rollout.make_league_wrapper`) already wraps these. |
| SL warm-start (policy + value) | **reuse pattern** | BC-v2 (`bc_weights_list0_b.npz`) warm-starts the policy prior; value from `value_weights_mlp`. Same weight-copy path as PPO. |
| Gatekeeping / worker respawn / Colab-lab packaging | **reuse** | Orthogonal to the algorithm; the driver/preflight/fork-gate carry over. |
| Leakage-audited encoder | **use OURS, not his** | Ours (`ppo/common.encode_*`, audited 6/6) differs from his; the search consumes the same 170-dim leak-free state we already ship. No re-port needed — this is already done. |

## What Gumbel-AZ needs *beyond* what's reused (the actual build)
1. **Gumbel root action selection** — sample top-k actions via Gumbel-top-k, then
   **sequential halving** the simulation budget across them (replaces PUCT at the
   root). This is the sample-efficiency mechanism; ~a self-contained root policy,
   not a rewrite of the tree search.
2. **Completed-Q value targets** — training target is the completed Q-value
   (mix of observed child Q and prior for unvisited actions), replacing AZ's
   visit-count distribution. Requires a new target-computation pass in the
   self-play → replay pipeline; the net's policy head is trained to the improved
   Gumbel policy, value head to the search return.
3. **Replay buffer + target regeneration** — AZ trains off a buffer of
   (state, improved-policy, return) tuples, not on-policy trajectories like PPO.
   Our PPO trainer is on-policy; this is a different data loop (buffer 200k+,
   the fix for Sanjay's 10k-buffer regression), needs building.
4. **Search-time serve path** — unlike PPO (raw argmax ships), a search artifact
   must run ISMCTS at serve. Confirm the ship/runtime budget allows N sims within
   cabt's per-move time; if not, the shipped artifact is the *distilled* policy
   head (search as a training-time teacher only). **Decision to make at trigger.**

## Rough time-to-first-loop from our current codebase
Assuming Sanjay's ISMCTS/determinization is handed over in working form and our
encoder/opponents/warm-start are reused as-is:

| Piece | Estimate |
|---|---|
| Wire our encoder + BC/value warm-start into his search | ~0.5 day |
| Gumbel-top-k + sequential-halving root | ~1 day |
| Completed-Q target pass + replay buffer loop | ~1.5–2 days |
| Self-play driver + leakage/bit-match gates on the new path | ~0.5 day |
| First smoke + throughput/nproc sanity | ~0.5 day |
| **Total to a first training loop** | **~4–5 focused days** |

Plus training time itself. Against the **Aug 12 train-stop freeze**, triggering
this pivot late is schedule-critical: it is only viable if both PPO rungs
conclusively plateau **early enough** to leave ~a week. If run2/run3 plateau
verdicts land after ~Aug 6–7, the honest call may be to **ship v2.2.0** rather
than start a 4–5 day build we can't finish + train. Flag that trade-off to the
user + advisor at trigger, do not auto-start.

See `algorithm_survey.md` §2.2 / §4 (Gumbel rationale + vanilla-AZ regression
diagnosis) and `LAB_RUNBOOK.md` run3 addendum (the trigger).
