# KE_BOLT — Bellowing Thunder engagement rule, design notes

**Nothing built yet.** Design-only, pending KE_SUP screen verdict + ST_ENERGY
handler review.

## Mining finding (much stronger than the original hypothesis)

Original hypothesis (shortlist entry #2): "adjust discard count on Bellowing
Thunder to secure KOs where opp HP falls in (current, current+70]."

**Actual finding is bigger.** In 200 crossdeck games (Kang v1-alone vs
Grimm), harvested from the OPP-seat replays:

| stat | count |
|---|---|
| games | 200 |
| Raging Bolt ex active turns | 1018 |
| Bellowing Thunder OFFERED (attackId=72 on menu) | 135 |
| Bellowing Thunder PICKED | **0** |
| Burst Roar OFFERED (attackId=71) | 789 |
| Burst Roar PICKED | 151 |

Top-10 uses Bellowing Thunder at **0.412 per game (35 fires / 85 games)**;
we use it **0 out of 200 games** despite it being on the menu 135 times.

**Almost certainly a scorer artifact**: Bellowing Thunder's `damage=0`
printed (dynamic — 70 dmg per discarded basic energy). v1's `_score_main`
almost certainly reads printed damage and rates the attack as ~worthless,
so Burst Roar (a 0-cost draw-6 attack) wins by default whenever both are
on the menu.

## Revised rule shape

**KE_BOLT_ENGAGE — actively PROMOTE Bellowing Thunder over Burst Roar (or
non-attacks) when it can meaningfully damage opp active.**

Not "adjust discard count" — the discard count is a separate ST_ENERGY
sub-decision that fires after the MAIN attack pick and is handled by
whatever `_pick_energy` logic exists downstream. What we need is to first
GET v1 to pick the ATTACK.

### Trigger conditions

`_ke_bolt_veto(result, sel, cur)` fires on a MAIN decision when:
1. Flag `KE_BOLT_ENGAGE` is on.
2. An OT_ATTACK option is on the menu with `attackId == 72` (Bellowing
   Thunder). Cost 1L + 1F is already met (engine only offers legal atks).
3. Our active is Raging Bolt ex (id 63).
4. Raging Bolt has at least K basic energies attached beyond attack cost,
   where K is chosen so `K * 70 >= opp_active_hp` (secures a KO).
5. Chosen action is NOT already Bellowing Thunder.

When satisfied: swap the chosen index to the Bellowing Thunder option.

### Guardrails (why NOT to fire)

- Do not fire if resulting KO would be irrelevant (opp active already at
  ~1 HP and something cheaper KOs) — but this is subsumed by (5): if v1
  chose a cheaper KO, its `attackId != 72`, but the alternative KO is
  already fine. In practice: only fire if no KO was going to happen
  otherwise. Simplification: fire unconditionally when (1)-(5) met and the
  chosen non-Bellowing action does NOT already KO opp.
- Do not fire if we'd need to discard energies that leave Raging Bolt
  unable to attack next turn — but that's what the sub-select handles; the
  MAIN swap alone doesn't commit specific energies.

### Fire-rate estimate

135 offered × fraction with enough energy on RB to KO × fraction where
chosen was non-KO — probably 30-60 fires per 200g. Lower than KE1's 695
and KE_SUP's estimated ~120, but each fire converts a whiff into a KO
which is high per-fire value.

## Open questions to resolve before building

1. **ST_ENERGY sub-select handler**: verify what current code picks when
   asked "how many basic energies to discard for Bellowing Thunder." If
   it picks 0, the KE_BOLT MAIN swap does nothing useful. Need to trace
   the `sel.type == ST_ENERGY` path and ensure it picks K = ceil(opp_hp/70)
   or defaults to "discard as many as possible if lethal is available".
2. **Interaction with KE1**: KE1 substitutes ATTACK → OT_ABILITY. If both
   are legal, KE1 fires FIRST in the hook chain and swaps ATTACK to
   OT_ABILITY (Run Errand). KE_BOLT never sees a MAIN with ATTACK chosen.
   **This could saturate KE_BOLT to zero fires when stacked with KE1**,
   same failure mode as KE3+KE1. Need to test carefully.
   - Mitigation: KE_BOLT would need to fire BEFORE KE1 in the hook chain,
     OR KE_BOLT should also fire when chosen is OT_ABILITY (Run Errand)
     if the Bellowing Thunder KO is on the menu (dominance: a lethal
     Bellowing beats a Run Errand draw every time). This complicates the
     unit-test surface.
3. **Cost of missing Burst Roar**: When Burst Roar was the "right" call
   (deck reset via draw-6), swapping to Bellowing costs the draw refresh.
   Not sure how often top-10 chooses each; needs a MAIN-decision compare.

## Path forward

1. Complete KE_SUP screen first (in progress). If KE_SUP is FAIL, dial
   confidence in this whole methodology down before committing more time
   to KE_BOLT.
2. If KE_SUP is PASS: investigate ST_ENERGY handler in main.py. Determine
   if current logic already picks a sensible discard count when we DID
   pick Bellowing Thunder in some universe where the MAIN scorer favored
   it. If not, KE_BOLT needs BOTH a MAIN veto AND an ST_ENERGY policy.
3. Design KE_BOLT with hook ordering explicit (before KE1) and unit-test
   the interaction cases.
4. Cross-deck screen KE_BOLT alone / KE_SUP+KE_BOLT / KE1+KE_BOLT /
   KE1+KE_SUP+KE_BOLT.
