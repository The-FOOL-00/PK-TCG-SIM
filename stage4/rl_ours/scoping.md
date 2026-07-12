# Stage 4 RL — operational scoping & timeline (living doc)

Decision record lives in algorithm_survey.md (incl. binding sign-off
amendments); this file is the operational schedule. Update here first.

## Deadline (verified)

**Submission lock: 2026-08-16** — user verified from the competition rules
page on 2026-07-12. Supersedes the 08-14 date in Sanjay's report.

## Binding dates

| Date | Milestone |
|------|-----------|
| Jul 12 (tonight) | Tier 1 gates built + green: leakage audit (our encoder), torch mirror bit-match, lab packages ×2, checkpoint sync. Tier 2 (PPO trainer + validation run) best-effort. |
| Jul 13 (lab day 1) | 08:00 lab open. FIRST-ACTION checklist: nproc → leakage audit → bit-match → report. nproc fork gate picks config (≥16 central / 8–16 reduced / <8 go-no-go, kill <1,500 games/h combined). Tier 3 real run launches only after Tier 1 gates pass on lab hardware + validation run clean. |
| Jul 13–20 | Trainer hardening, first PPO iterations, search-off gates every lab day. |
| Jul 20–26 | Week-1 shakeout complete; sanity gates; K1 armed throughout. |
| Jul 26 – Aug 10 | Main training window (**+48h vs old plan**). K2 checkpoints: 150k games (≥44%), 300k (≥48%). Capacity-growth ladder on K2 fire: 128k → 256k nets before any Gumbel-AZ pivot. |
| Aug 10–12 | Ship battery G8a/b/c + speed class + pre-flight; user sign-off window; slack for one battery re-run. |
| **Aug 12** | Nothing trains after this date. Rescope trigger (was Aug 10). |
| **Aug 14** | Hard internal freeze — final bundle submitted by user, 48h ladder convergence buffer. |
| **Aug 16** | Competition submission lock. |

The 48h gained vs the Aug-14 plan is allocated: ~96 core-hours of extra
training compute (both labs) + one extra ship-battery re-run slot. No new
scope items.

## Kill criteria (armed, from survey §9 + amendments)

- **Leakage audit fail (our encoder/harness): immediate STOP, no training.**
- **Bit-match fail (numpy vs torch): STOP, no training.**
- **Validation run** (10–30k games, pre-Tier-3): training reward at 10k
  games below starting reward = Sanjay-pattern check fired → STOP, rediagnose.
- **K1 collapse:** two consecutive 200-game gates <29% vs v2.2.0 → halt,
  revert to prior checkpoint, diagnose (~2 lab-days budget).
- **K2 plateau:** no gate ≥44% by 150k games or ≥48% by 300k → capacity
  growth first (128k, then 256k), Gumbel-AZ only after both plateau.
  Capacity-limited signal (train reward ~p90 of small-net achievable, gates
  <44%) is logged distinctly from plateau signal.
- **K3:** one KL-halving retry only, if K2 fires with KL pinned.
- **nproc <8 at either lab:** go/no-go escalation to user; combined
  sustained <1,500 games/h → NO-GO on RL, ride v2.2.0.

## Standing guardrails

No Kaggle submissions by the agent, ever. report/WRITEUP_DRAFT.md untouched
(notes go to stage4/writeup_notes.md). main.py fallback chain preserved.
Gates are search-off (we ship the raw policy). Tier 3 does not launch from
the home box tonight.
