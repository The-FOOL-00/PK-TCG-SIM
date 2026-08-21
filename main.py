"""Pokemon TCG AI Battle Challenge agent (cabt engine).

Deterministic heuristic agent. Never crashes, never returns an illegal
selection: every path is validated and falls back to a legal index list,
with the failure logged to stderr (visible in Kaggle agent logs).

Protocol (derived from the sample submission and kaggle_environments source):
- Deck-selection call: obs["select"] is None -> return the 60 card IDs
  from deck.csv.
- Decision call: obs["select"]["option"] is the legal option list; return a
  list of option indices, length within [minCount, maxCount], no duplicates.

Kaggle loads this file with exec() and uses the LAST callable defined in it
as the agent, so `agent` must stay the final def in this module. __file__ is
NOT defined under that exec(), so all file access goes through _find_file().
"""

import atexit
import ctypes
import json
import math
import os
import random
import sys
import time
from collections import Counter

AGENT_VERSION = "ptcg-heuristic-v1.0.0"

# ---------------------------------------------------------------------------
# v3 feature flag: 1-ply analytic state evaluation for MAIN-phase decisions.
# Off by default so the shipped bundle behaves exactly like v1 unless enabled.
# Toggle via env var (bundle-time) or module attribute (local A/B harness).
# Runtime stays DLL-free: option scores use analytic deltas from
# card_data.json only; full engine simulation is a local-tuning-only tool.
# ---------------------------------------------------------------------------
V3_EVAL = os.environ.get("PTCG_V3_EVAL", "0") == "1"

# ---------------------------------------------------------------------------
# Learned value model (rung a): MLP win-probability from the 170-dim
# encode_state features, trained on self-play outcomes (training/train_value.py).
# Off by default. When on, MAIN-phase and attach/promote selections are scored
# tier + LV_SCALE * (P(win|after) - P(win|now)), the "after" feature vector
# built analytically — same 1-ply philosophy as v3, learned value instead of
# hand-tuned weights. Tiers are kept so turn structure (setup before attack)
# survives; deltas are clipped so they cannot cross the setup/attack boundary.
# Inference is numpy matmuls with a pure-python .npz reader + matmul fallback
# when numpy is missing. Missing/corrupt weights file: one stderr warning,
# then permanent fallback to the heuristic tiers. C1 validation,
# resolve_selection, and the fallback chain are untouched.
# ---------------------------------------------------------------------------
LEARNED_VALUE = os.environ.get("PTCG_LEARNED_VALUE", "0") == "1"
LV_WEIGHTS_FILE = "value_weights.npz"
LV_SCALE = 400.0        # score points per unit of win-prob delta (within-tier)
LV_DELTA_CLIP = 0.25    # |delta| cap: LV_SCALE*CLIP=100 < every tier gap that matters
LV_TRACE = False        # A/B harness only: append P(win|now) per decision
VALUE_TRACE = []

# ---------------------------------------------------------------------------
# Runtime belief-sampled determinized search (Phase B/C/D pivot, 2026-07-09).
# When SEARCH is on, MAIN-phase single-selects are decided by flat
# determinized Monte Carlo on the engine's search_begin/search_step API
# (bundled cg/), with the opponent's hidden zones sampled from a belief
# maintained by CardTracker. Everything else stays on the v1 path, and every
# failure mode (no engine, search exception, sampling inconsistency, time
# pressure) independently degrades to v1 with one stderr line. C1 validation,
# resolve_selection and the fallback chain are untouched — the search can
# only substitute WHICH legal option is preferred, never bypass validation.
#   SEARCH_CAP > 0 truncates rollouts at that many engine steps and scores
# the leaf with the rung-a value net (Phase C1); 0 = roll to terminal.
#   ROLLOUT selects the rollout policy: "v1" heuristic or "s1" distilled
# policy net from policy_weights.npz (Phase C2).
#   GOVERNOR enables the per-decision time budget (Phase D).
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Deck-specific piloting (Stage 1: Garchomp). PILOT="" reproduces v2.0.0
# byte-for-byte; PILOT="garchomp" adds tempo scoring traced to nasuo445's
# rank-6 replays (attacks 93% of turns once loaded, first-attack turn 4).
# The heuristics only touch MAIN scoring and emit stderr telemetry; C1
# validation / resolve_selection / the fallback chain are untouched.
# ---------------------------------------------------------------------------
PILOT = os.environ.get("PTCG_PILOT", "")

# ---------------------------------------------------------------------------
# Behavior-cloned pilot (Stage 3B): a small policy net imitating a named
# top-ladder player's decisions (training/train_bc.py / train_bc_full.py;
# weights follow the policy_weights.npz contract). BC="" keeps every path
# byte-identical; BC=<tag> loads bc_weights_<tag>.npz. Single-head weights
# answer MAIN single-selects only (sub-decisions stay on the v1 heuristic).
# Two-headed BC-full weights (e.g. BC="garchomp_full") additionally answer
# ST_CARD-family sub-decisions (fetch/bench/promote/discard picks) with a
# card head over encode_card_option features; multi-selects are picked by
# iterative argmax, mirroring the Plackett-Luce training decomposition.
# Missing weights or numpy: one stderr line, v1 behavior. C1 validation and
# resolve_selection untouched.
# ---------------------------------------------------------------------------
BC = os.environ.get("PTCG_BC", "")
# Draw-brake (Stage 4, ablatable): BC-v2 on the list-0 Alakazam engine
# self-deckouts in stalled games — it keeps firing optional self-draw/fetch
# actions with no deck-economy model (thin-deck states are absent from
# win-side training data; winners close by T12-15). BC_BRAKE=N (cards)
# arms an inference-time rule on the BC MAIN path only: when OUR deckCount
# <= N and we are not ahead on prizes (parity included), optional self-draw/fetch
# options (BRAKE_DRAW_ACTIONS below, derived empirically from deck-count
# deltas in stage4/eval/brake_analyze.py) are excluded from the BC head's
# choice. 0 (default) = off, byte-identical. Weights untouched; the picked
# index is always a legal option, so C1 validation / resolve_selection /
# fallback chain are unaffected. G7c ablates this flag.
BC_BRAKE = int(os.environ.get("PTCG_BC_BRAKE", "0") or "0")
# BC_CARD_ONLY: when 1, BC is used ONLY for ST_CARD-family sub-decisions
# (trainer card targets, bench fetches, discard picks) where val accuracy is
# 71% vs v1's 38.6% — but v1 handles all MAIN single-selects unchanged.
# This is the hybrid mode: preserves v1's strong MAIN policy (878 Elo source)
# while adding the proven card-head advantage. Set via PTCG_BC_CARD_ONLY=1.
BC_CARD_ONLY = os.environ.get("PTCG_BC_CARD_ONLY", "0") == "1"
BS_CEI = os.environ.get("PTCG_BS_CEI", "1") == "1"
BS_CEI_2PLY = os.environ.get("PTCG_BS_CEI_2PLY", "1") == "1"
BS_CEI_3PLY = os.environ.get("PTCG_BS_CEI_3PLY", "0") == "1"
BS_CEI_DETS = int(os.environ.get("PTCG_BS_CEI_DETS", "2"))
BS_CEI_PROB_OPP = os.environ.get("PTCG_BS_CEI_PROB_OPP", "0") == "1"
_BS_CEI_EVAL = None

Q_POLICY = os.environ.get("PTCG_Q_POLICY", "0") == "1"
Q_DEPTH = int(os.environ.get("PTCG_Q_DEPTH", "0"))
Q_DETS = int(os.environ.get("PTCG_Q_DETS", "1"))
_Q_POLICY_EVAL = None

# Deck-identity tables (HAND_SLOT_IDS / CARD_SLOT_IDS) are frozen at import
# from deck.csv. When a harness swaps DECK at runtime (ab_gate non-default
# decks, BC extraction) those tables silently describe the WRONG deck — the
# prior BC trained with a hand-count block that could only ever see 1 of the
# Garchomp deck's 20 ids. DYN_DECK_TABLES=1 re-derives both tables from the
# CURRENT DECK (cached); default 0 keeps every existing config byte-identical.
# On-ladder bundles ship deck.csv = the piloted deck, so both settings agree.
DYN_DECK_TABLES = os.environ.get("PTCG_DYN_DECK_TABLES", "0") == "1"
WEIGHT_TEMPO_LOADED = 2450.0   # loaded attack outranks marginal setup after the
                               # turn's draw supporter has resolved (see below)
WEIGHT_EVOLVE_EX_BONUS = 150.0  # evolving toward an ex (win condition) over a
                                # side-line evolve; stays within the evolve tier

SEARCH = os.environ.get("PTCG_SEARCH", "0") == "1"
# Gate A (2026-07-22): eval-correctness fix. Sanjay's §6p revenge-class:
# attacks with "+N more damage" / "N damage for each" scaling read printed 0
# and were harmful weights. Fix: parse attack text for KNOWN-VERIFIABLE
# scaling patterns; ABSTAIN (return printed damage) when unverifiable per
# §6j "facts ≈ 16 pts, weights ≈ 0". Off by default (byte-identical); flip
# EVAL_FIX=1 on the challenger for A/B.
EVAL_FIX = os.environ.get("PTCG_EVAL_FIX", "0") == "1"
# Gate D (2026-07-22): promotion-after-KO rule. Sanjay's §6q (v8 rule 1):
# at select.context == SC_TO_ACTIVE (post-KO promote), score benched
# candidates by `maxHp + 30 * energy_attached` instead of current
# `hp + 20*energy + best_attack_dmg/10`. Rationale (his measurement):
# - `hp` picks damaged tanks correctly but also picks the low-hp benchwarmer
# - `maxHp` avoids downgrading a damaged big body to a full-hp weakling
# - `+30*energy` requires 3+ energy to override a 90-hp gap (~never triggers
#   a catastrophic downgrade in his 108 traced decisions).
# Scope: SC_TO_ACTIVE only. SC_SETUP_ACTIVE / SC_SWITCH / SC_TO_FIELD unchanged
# (different mechanics — setup, player-initiated switch, generic targeting).
# Off by default (byte-identical); flip PROMOTE_RULE=1 on the challenger for A/B.
PROMOTE_RULE = os.environ.get("PTCG_PROMOTE_RULE", "0") == "1"
# Gate B (2026-07-24): engine-exact lethal probe. Sanjay §1 item 3: probe each
# ATTACK option via search_step across K determinizations; if all K show a
# win for us, take it. Bounds hard-capped by LETHAL_PROBE_DEADLINE_S so a
# slow probe cannot compound the governor coupling (§6h). Off by default;
# LETHAL_PROBE=1 on the challenger for A/B.
LETHAL_PROBE = os.environ.get("PTCG_LETHAL_PROBE", "0") == "1"
# END-veto (HORIZON_TEST.md): v1 scores END at -1e6 and structurally cannot
# pass while any option exists (measured: v1-alone ends with development still
# available 0.0% of 554 ENDs). The SEARCH layer introduces that pathology from
# nothing -- 46.3% at cap=400, 60.8% at cap=16. This vetoes the search's END
# and defers to v1's ordering, which is the only arm measured at 0%.
#   "narrow" = veto only when bench < benchMax AND a playable Basic-searcher is
#              on the menu; the replacement IS that searcher, so the action is
#              strictly dominated (a free Item converting deck Basics into
#              board presence cannot be worse than passing).
#   "broad"  = veto whenever ANY development option is on the menu; replacement
#              is the highest v1-scored development option. NOT dominated --
#              can burn a Supporter or misattach energy.
# "" (default) = off, byte-identical to the shipped agent.
END_VETO = os.environ.get("PTCG_END_VETO", "")     # "" | "narrow" | "broad"
BASIC_SEARCHERS = frozenset((
    "buddy-buddy poffin", "nest ball", "ultra ball", "hop's bag",
    "poke ball", "great ball", "pokegear 3.0",
))
LETHAL_PROBE_K = 3          # determinizations per attack option (unanimity required)
LETHAL_PROBE_MAX_ATTACKS = 4  # top-N attack options by v1 score
LETHAL_PROBE_DEADLINE_S = 0.5  # hard cap on total probe budget per decision
SEARCH_DET = int(os.environ.get("PTCG_SEARCH_DET", "16"))    # determinizations
SEARCH_ROLL = int(os.environ.get("PTCG_SEARCH_ROLL", "2"))   # rollouts/candidate
SEARCH_TOPK = int(os.environ.get("PTCG_SEARCH_TOPK", "4"))   # candidates by v1 score
SEARCH_CAP = int(os.environ.get("PTCG_SEARCH_CAP", "0"))     # rollout step cap, 0=terminal
SEARCH_SEED = int(os.environ.get("PTCG_SEARCH_SEED", "0"))
SEARCH_MIN_BASICS = 1        # sampled opp deck must keep >= this many Basics at setup
ROLLOUT = os.environ.get("PTCG_ROLLOUT", "v1")               # v1 | s1
# Candidate-set arms (2026-07-26). Measured on 60 self-play + 25 VN ladder +
# 28 canary ladder games: on ~32% of attack-legal MAIN decisions the best
# attack scores below cands[0:SEARCH_TOPK] and is therefore invisible to the
# search, which then picks an attack 0/1068 times. The dominant cause is the
# _pilot_score_main tempo hook being gated on cur["supporterPlayed"] (75.6% of
# exclusions). Two independent, default-off arms; see CANDIDATE_SET.md.
#   A-INCLUDE: force the best legal attack into cands (candidate-set change)
#   A-WEIGHT:  a second, lower tempo tier that does not require the supporter
#              to have resolved (scoring change)
# ---------------------------------------------------------------------------
# Card-knowledge rules (2026-07-27, PILOT_KNOWLEDGE.md). Mined from the two
# top-10 agents piloting THIS deck (junlee789, Yudai Ueno) and verified against
# card_data.json `skills[]`.
#
# All three live in the ALWAYS-ACTIVE scoring path (_score_main /
# _attach_target_score / _attack_damage_est), NOT in _pilot_score_main:
# bake_ship_config() never bakes PTCG_PILOT, so anything gated on
# PILOT == "garchomp" is dead code in every bundle we ship.
#
#   R1 a once-per-turn deck-search ability is card advantage at no cost and
#      should outrank ordinary setup (top-10 use 36.3%, we use 16.8%).
#   R2 attach to a bench Pokemon that can still evolve. Cynthia's Garchomp ex
#      has retreatCost 0, so a bench-built attacker promotes for free
#      (top-10 attach to bench 56-62%, we do 37.5%).
#   R3 Raging Curse's printed damage is 0 and all of its damage comes from the
#      scaling text, so v1 prices a measured 360-damage attack at the 1000.0
#      floor. Narrowly scoped to that one attack; EVAL_FIX stays off.
# ---------------------------------------------------------------------------
CARD_R1_SEARCH_ABILITY = os.environ.get("PTCG_CARD_R1", "1") == "1"
CARD_R2_BENCH_ATTACH = os.environ.get("PTCG_CARD_R2", "1") == "1"
CARD_R3_RAGING_CURSE = os.environ.get("PTCG_CARD_R3", "1") == "1"

# Conditional ordering gates (2026-07-27, CONDITIONAL_DESIGN.md).
#
# ATTACK is terminal; every other MAIN action is free. Top-10 attack as the
# FIRST action of a turn 2.0% of the time, we do it 43.0% of the time; they
# take mean 5.87 actions before swinging, we take 2.97.
#
# These are GATES ON THE OPTION SET, not score changes. A-WEIGHT already failed
# by reweighting attack. No v1 constant is touched by any of them; they replace
# the chosen option when a stated condition holds, exactly as _end_veto does.
# All live in the always-active path -- never inside _pilot_score_main.
#
#   E1 do not attack while a board-advancing card play remains (PLAY/ATTACH/EVOLVE)
#   E2 do not attack while an ability is available
#   E3 do not retreat while our active is not KO-able
#   E4 when BEHIND on prizes, disable E1 (push damage)
#   E1b attack at once when the KO takes our last prize   (evidence AGAINST; off)
#   E1c attack at once when our active is doomed and powered (off)
SEQ_E1 = os.environ.get("PTCG_SEQ_E1", "1") == "1"
SEQ_E2 = os.environ.get("PTCG_SEQ_E2", "1") == "1"
SEQ_E3 = os.environ.get("PTCG_SEQ_E3", "1") == "1"
SEQ_E4 = os.environ.get("PTCG_SEQ_E4", "1") == "1"
SEQ_E1B_LETHAL = os.environ.get("PTCG_SEQ_E1B", "0") == "1"
SEQ_E1C_DOOMED = os.environ.get("PTCG_SEQ_E1C", "0") == "1"

# ---------------------------------------------------------------------------
# Target-selection fixes (2026-07-30, MATCHUP_MINING.md). Mined from 504
# top-10 Grimmsnarl sides: WHICH specific bench Pokemon gets targeted, not
# whether an action fires. Both are matchup-INVARIANT -- no opponent
# detection needed; the top-10 rate barely moves across archetypes.
#
#   T1  SC_SWITCH (Boss's Orders / forced switch) targeting the OPPONENT's
#       bench: confirmed live bug -- _score_card bundles this context with
#       our own post-KO promotion under one hp+energy+attack formula, and the
#       fallback path (LEARNED_VALUE is off by default) never checks
#       playerIndex. So Boss's Orders currently scores by "which of their
#       Pokemon is strongest", when the mined top-10 rate (n=232) is 84.1%
#       "which is worth the most prizes". Self-target decisions (choosing our
#       OWN next active, ~73% of SC_SWITCH volume) are untouched.
#   T2  SC_DAMAGE (Shadow Bullet splash) by HP RATIO, not raw HP. The
#       existing rule (200 - raw_hp) already prefers low-HP targets, but two
#       Pokemon at the same raw HP score identically regardless of max HP,
#       when the mined top-10 criterion (n=1538, 82.4%) is ratio-based.
TARGET_T1_BOSS_PRIZE = os.environ.get("PTCG_TARGET_T1", "1") == "1"
TARGET_T2_SPLASH_RATIO = os.environ.get("PTCG_TARGET_T2", "1") == "1"
# T3 (MATCHUP_MINING.md priority 3): against Fezandipiti/Dudunsparce, top-10
# still snipes lowest HP-ratio most often (78.7%, vs 82.4% pooled) but breaks
# near-ties toward energy count / prize value noticeably more than pooled
# (66.6%/65.2% vs 56.2%/59.9%). Small tie-break addition on top of T2's ratio
# term -- never overrides a real ratio gap, only settles near-ties. Detection
# is live (marquee card ids seen in opponent's active/bench/discard), not a
# replay-only label -- see _opp_archetype.
TARGET_T3_FEZ_TIEBREAK = os.environ.get("PTCG_TARGET_T3", "1") == "1"
# T4 (T4_KO_CONVERT.md): the damage-target scorer ranks by HP RATIO (T2) and
# never asks whether the placement would KO the target. Measured on 300 games
# of the shipped build: 29.4% of all damage dealt lands on Pokemon that are
# never knocked out (Ogerpon, single-target, strands 4.4%). A 320-HP attacker
# at 48 HP outranks a 70-HP Basic at 30 HP that these same 30 damage kill.
# T4 substitutes a lethal target for a non-lethal one -- same action, different
# target index, so it cannot shift the state into a line the pilot cannot
# continue (the failure mode that killed KE_SUP/KE_BOLT/KE_WELL and the four
# mined rules of writeup S6).
# Damage per source is a table, not `remainDamageCounter`: that field is in the
# schema but measured 0 at every one of these decisions across 40 games and is
# referenced nowhere else in this file.
TARGET_T4_LETHAL = os.environ.get("PTCG_TARGET_T4", "1") == "1"

# Pure-Python Expectimax Engine Flag (2026-08-13, EXPECTIMAX_DESIGN.md).
# 2-ply prize-delta forward evaluation with Instant Lethal Win Veto.
EXPECTIMAX = os.environ.get("PTCG_EXPECTIMAX", "1") == "1"

# F1 (FETCH_MINE.md): SC_TO_HAND -- "a search resolved, pick the card" -- is the
# largest sub-action slot in the game (23,309 decisions with >1 option across
# 287 top-10 replays; 3.7x T2's slot, 100x T1's). It was scored by
# `_card_value`, whose own docstring says it measures "how much we mind LOSING
# this card (used for discard/keep choices)" -- so Basic Energy, the cheapest
# thing to lose, scored 10.0, dead last, while Marnie's Grimmsnarl ex scored
# ~300. Mined from top-10 winning sides (n=662): they fetch Basic Energy 55.6%
# of the time, and 70.6% of the time it is on the menu. Agreement of our
# shipped ordering with their choice: 36.0%. Energy-first: 68.3%.
# This is T1's defect (a scorer reused for a decision it was not built for) on
# the highest-volume slot, and here the borrowed scorer is near-inverted.
FETCH_F1_ENERGY_FIRST = os.environ.get("PTCG_FETCH_F1", "1") == "1"
# effect.id -> damage this placement applies. Verified against replay:
# ctx 15 SC_DAMAGE  = Marnie's Grimmsnarl ex Shadow Bullet bench splash (30)
# ctx 13 SC_DMG_COUNTER = Munkidori Adrena-Brain, 3 counters (30)
T4_DMG_BY_SOURCE = {648: 30, 112: 30}
T4_LETHAL_SCORE = 5000.0
# KE1 (KANGASKHAN_E1.md): NOT a port of E1. Native-mined for Kangaskhan/
# Raging Bolt: kangaskhan_mine.py's `can_KO` cell (n=404 top-10 vs n=342 us,
# TVD=0.720) showed top-10 pilots pick ABILITY 24.0% of the time when a
# lethal is on the menu, vs 0.0% for us. Concrete case: Mega Kangaskhan
# ex's *Run Errand* -- once/turn, active-slot only, "draw 2 cards", no
# terminal side effect. Rule: on a MAIN decision where the chosen option
# is an ATTACK/RETREAT/END AND the active carries a "draw N cards" skill
# whose one-per-turn use is still available AND the menu offers OT_ABILITY,
# swap to the Ability. Scoped to "draw N cards" skill text (matches Run
# Errand); avoids Raging Bolt's Burst Roar (an OT_ATTACK, not OT_ABILITY --
# won't be touched). Own flag, default off.
KE1_FREE_DRAW = os.environ.get("PTCG_KE1", "0") == "1"
_KE1_ABILITY_CACHE = {}   # cid -> bool (this card has a free-draw ability)
# KE2 (KE2_SCREEN.md): mined from `supporter_pending` cell (n_them=1693, the
# largest cell by frequency in kangaskhan_mine.py at 54.1% of all decisions,
# TVD=0.226). Top-10 use free-draw abilities 31.2% of decisions BEFORE
# playing their supporter; we use them 13.8%. Conversely we ATTACH 20% vs
# their 5.5% -- we're spending on ATTACH before extracting the free draws.
# Rule: on a MAIN decision where v1 chose ATTACH AND supporterPlayed is False
# AND the engine offers OT_ABILITY on a Pokemon carrying our free-draw skill
# text pattern, swap to the Ability. Same "no discard" filter as KE1 to
# avoid hybrid-effect misfires. Own flag, default off.
KE2_ABIL_BEFORE_ATTACH = os.environ.get("PTCG_KE2", "0") == "1"
# KE3 (KE3_SCREEN.md): second Kangaskhan-native free-ability veto, targeting
# Teal Mask Ogerpon ex's *Teal Dance* -- "Once during your turn, you may
# attach a Basic {G} Energy card from your hand to this Pokemon. If you
# attached Energy to a Pokemon in this way, draw a card." Once/turn, no
# discard cost, separate from the normal per-turn energy attach action, so
# using it doesn't consume the turn's attach slot -- strictly-dominated
# same as KE1. Unlike Run Errand it does NOT require active spot, so the
# helper is more permissive there. Own flag, default off.
KE3_TEAL_DANCE = os.environ.get("PTCG_KE3", "0") == "1"
_KE3_ABILITY_CACHE = {}   # cid -> bool (this card has a free-attach ability)
# KE_SUP (KE_SUP_SCREEN.md): mined from `atk_legal & supporter_pending` cell
# (n_them=504, n_us=954, TVD=0.271). Top-10 ATTACK 15.9% in this cell; we
# ATTACK 34.7% — we're firing attacks before playing our supporter, missing
# a per-turn resource slot. Rule: on a MAIN decision where v1 chose ATTACK
# AND supporterPlayed is False AND the menu offers OT_PLAY on a Supporter-
# type hand card, swap to that Supporter play. Targets the once-per-turn
# Supporter slot (a distinct engine resource from KE1/KE2/KE3's OT_ABILITY),
# so composes with them by construction (KE3_SCREEN.md line 82-84).
KE_SUP_ATK_BEFORE_SUPPORTER = os.environ.get("PTCG_KE_SUP", "0") == "1"
# KE_BOLT (KE_BOLT_SCREEN.md): mined finding — top-10 Kang uses Bellowing
# Thunder (Raging Bolt ex attackId=72) 0.412×/game (35/85 games), we use it
# 0 times in 200 games despite it being offered 135 times. Root cause: v1's
# _score_main reads printed damage (=0 for Bellowing, which is dynamic
# damage = 70 × basic energies discarded), so Burst Roar (0-cost draw-6)
# wins the scoring by default. Rule: two hooks — (1) on ST_MAIN, if
# Bellowing offered AND our active is Raging Bolt (id=63) AND enough basic
# energies attached beyond cost (2 for 1L+1F) to secure a KO, swap chosen
# to Bellowing; (2) on ST_ATTACHED_CARD context=26 (Bellowing discard),
# pick K = ceil(opp_hp / 70) basic-energy indices. Both hooks needed —
# without (2), v1's default returns 0 discards (main.py:1803) → 0 damage.
# Orthogonal to KE1 by construction: KE1 only fires when Mega Kangaskhan
# (id=756) is active; KE_BOLT only fires when Raging Bolt (id=63) is
# active. Different active-slot precondition = disjoint firings.
KE_BOLT_ENGAGE = os.environ.get("PTCG_KE_BOLT", "0") == "1"
KE_BOLT_ATTACK_ID = 72       # Bellowing Thunder
KE_BOLT_SOURCE_ID = 63       # Raging Bolt ex
KE_BOLT_CONTEXT = 26         # ST_ATTACHED_CARD context for Bellowing discard
KE_BOLT_DMG_PER = 70         # damage per discarded basic energy
KE_BOLT_COST = 2             # 1L + 1F must remain attached to fund the attack
# KE_WELL (KE_WELL_SCREEN.md): mined attach-target distribution — top-10
# attaches to Kang 43.6% vs us 62.4% (us +18.8pt over-attach); Wellspring
# 23.7% vs us 4.6% (us -19.1pt under-attach). Downstream: Wellspring's
# Torrential Pump (100 dmg + 120 to bench) fires 0.576×/g for top-10 vs
# 0.035×/g for us (16× under-usage). Rule: on ST_MAIN, if v1 chose OT_ATTACH
# to Mega Kangaskhan (756) AND Wellspring Ogerpon (108) is on field with
# < 3 energies AND OT_ATTACH to Wellspring is on the menu, swap to
# Wellspring. Fires only on Kang attach picks — non-Kang picks (RB,
# Ogerpon, Latias) are left alone. Orthogonal to KE1 (different chosen-
# action precondition). May also indirectly unlock KE_BOLT by freeing
# later attaches to Raging Bolt.
KE_WELL_ATTACH_PRIORITY = os.environ.get("PTCG_KE_WELL", "0") == "1"
KE_WELL_KANG_ID = 756
KE_WELL_WELL_ID = 108
KE_WELL_CAP = 3   # stop attaching to Wellspring once it has 3+ energies
# G_ABIL_BROAD (G_ABIL_BROAD_SCREEN.md): fresh mining pass on post-shipped-
# bundle Grimm play (horizon_T1T2) vs top-10 (4 snapshots including jul31)
# found that even with E1/E2/T1/T2 shipped, we still lag top-10 by 14-20pt
# on ABILITY usage in critical cells (KOable & powered -20.3pt,
# supporter_pending -15.1pt, turn=T7+ -12.4pt). E2 only fires when chosen
# == OT_ATTACK; top-10 fires abilities BEFORE PLAY/ATTACH/EVOLVE too.
# Rule: extend E2's shape — on ST_MAIN, if chosen action ≠ OT_ABILITY AND
# an OT_ABILITY is offered AND per-turn veto budget not exhausted, swap
# to best-scoring OT_ABILITY. Deck abilities in Grimm/Kang/Fez/Mewtwo are
# all strictly-positive (Munkidori damage-move, Fez draw-3, Run Errand,
# Teal Dance, etc.), so the substitution is unconditional-value — same
# KE1-shape that succeeded, broader trigger.
G_ABIL_BROAD = os.environ.get("PTCG_G_ABIL_BROAD", "0") == "1"
_POSITIVE_ABIL_CACHE = {}   # cid -> bool
OPP_ARCHETYPE_IDS = {
    "starmie": frozenset((1030, 1031)),
    "abomasnow": frozenset((722, 723)),
    "alakazam": frozenset((66, 743)),
    "garchomp": frozenset((540, 756, 63)),
    "kangaskhan": frozenset((756, 63)),
    "grimmsnarl": frozenset((412, 413, 414)),
    "mewtwo": frozenset((431,)),
    "dragapult": frozenset((301, 302, 303)),
    "fezandipiti": frozenset((743, 744)),
}
E1_MAX_VETO = 12       # per own turn; top-10 p90 is 9 actions before attacking.
                       # Bounds the "defer forever" failure mode if a repeatable
                       # option never clears the menu.
_SEQ = {"turn": None, "vetoes": 0, "ceiling_turns": 0, "turns": 0}
DEVELOP_TYPES = (7, 8, 9)      # OT_PLAY, OT_ATTACH, OT_EVOLVE
CARD_R1_SEARCH_ABILITY = os.environ.get("PTCG_CARD_R1", "0") == "1"
CARD_R2_BENCH_ATTACH = os.environ.get("PTCG_CARD_R2", "0") == "1"
CARD_R3_RAGING_CURSE = os.environ.get("PTCG_CARD_R3", "0") == "1"
WEIGHT_ABILITY_SEARCH = 2900.0  # above evolve 2800 / item 2400 / bench 2300,
                                # below energy attach 3000 (still once-per-turn
                                # and time-critical) and bench-urgent 3500
EVO_TARGET_BONUS = 150.0        # bench Pokemon that can still evolve; must
                                # exceed ACTIVE_TARGET_BONUS (100) to flip the
                                # attach target from active to the growing line
CAND_INCLUDE_ATTACK = os.environ.get("PTCG_CAND_INCLUDE_ATK", "0") == "1"
CAND_ATK_W = float(os.environ.get("PTCG_CAND_ATK_W", "0") or "0")  # 0 = off
CAND_ATK_MIN_DMG = float(os.environ.get("PTCG_CAND_ATK_MIN_DMG", "100") or "100")
GOVERNOR = os.environ.get("PTCG_GOVERNOR", "1") == "1"
POLICY_WEIGHTS_FILE = "policy_weights.npz"
GOV_CAP_S = 3.0              # per-decision budget ceiling
GOV_STICKY_S = 0.2           # budget below this -> heuristic-only for the game
GOV_P90_TURNS = 20.0         # conservative game length: mirror p99 (27k-game
                             # distill_c1 distribution: p50=5 p90=12 p99=20),
                             # padded because ladder field games run longer
                             # (META.md field average 13.1 turns)

# ---------------------------------------------------------------------------
# Engine enums (values copied from the sample submission's cg/api.py)
# ---------------------------------------------------------------------------
AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH, AREA_PRIZE = 1, 2, 3, 4, 5, 6
AREA_STADIUM, AREA_LOOKING = 7, 12

OT_NUMBER, OT_YES, OT_NO, OT_CARD, OT_TOOL_CARD, OT_ENERGY_CARD, OT_ENERGY = 0, 1, 2, 3, 4, 5, 6
OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY, OT_DISCARD, OT_RETREAT = 7, 8, 9, 10, 11, 12
OT_ATTACK, OT_END, OT_SKILL, OT_SPECIAL_CONDITION = 13, 14, 15, 16

ST_MAIN, ST_CARD, ST_ATTACHED_CARD, ST_CARD_OR_ATTACHED, ST_ENERGY, ST_SKILL = 0, 1, 2, 3, 4, 5
ST_ATTACK, ST_EVOLVE, ST_COUNT, ST_YES_NO, ST_SPECIAL_CONDITION = 6, 7, 8, 9, 10

CT_POKEMON, CT_ITEM, CT_TOOL, CT_SUPPORTER, CT_STADIUM = 0, 1, 2, 3, 4
CT_BASIC_ENERGY, CT_SPECIAL_ENERGY = 5, 6

SC_SETUP_ACTIVE, SC_SETUP_BENCH, SC_SWITCH, SC_TO_ACTIVE, SC_TO_BENCH = 1, 2, 3, 4, 5
SC_TO_FIELD, SC_TO_HAND, SC_DISCARD, SC_TO_DECK, SC_TO_DECK_BOTTOM = 6, 7, 8, 9, 10
SC_TO_PRIZE, SC_NOT_MOVE, SC_DMG_COUNTER, SC_DMG_COUNTER_ANY, SC_DAMAGE = 11, 12, 13, 14, 15
SC_REMOVE_DMG, SC_HEAL, SC_EVOLVES_FROM, SC_EVOLVES_TO, SC_DEVOLVE = 16, 17, 18, 19, 20
SC_ATTACH_FROM, SC_ATTACH_TO, SC_DETACH_FROM, SC_LOOK, SC_EFFECT_TARGET = 21, 22, 23, 24, 25
SC_ATTACK, SC_DISABLE_ATTACK, SC_EVOLVE = 35, 36, 37
SC_DRAW_COUNT = 38
SC_IS_FIRST, SC_MULLIGAN, SC_ACTIVATE, SC_FIRST_EFFECT, SC_MORE_DEVOLVE, SC_COIN_HEAD = 41, 42, 43, 44, 45, 46
SC_AFFECT_COND, SC_RECOVER_COND = 47, 48

# SpecialConditionType: POISON=0 BURN=1 SLEEP=2 PARALYZE=3 CONFUSE=4
CONDITION_PRIORITY = {3: 5, 2: 4, 4: 3, 0: 2, 1: 1}

# ---------------------------------------------------------------------------
# Scoring weights (tune between submissions; ordering encodes turn structure:
# all setup actions score above attacks because attacking ends the turn)
# ---------------------------------------------------------------------------
WEIGHT_LETHAL = 100000.0
WEIGHT_BENCH_URGENT = 3500.0      # 0-1 of our Pokemon in play: avoid losing by empty board
WEIGHT_ATTACH_ENERGY = 3000.0
WEIGHT_EVOLVE = 2800.0
WEIGHT_PLAY_ITEM = 2400.0
WEIGHT_BENCH = 2300.0
WEIGHT_PLAY_SUPPORTER = 2150.0    # after bench/items so hand-shuffle draw effects cost less
WEIGHT_ATTACH_TOOL = 2100.0
WEIGHT_ABILITY = 2060.0
WEIGHT_PLAY_STADIUM = 2030.0
WEIGHT_ATTACK_BASE = 1000.0       # + capped damage bonus; always below setup, above retreat/end
WEIGHT_RETREAT = -500.0
WEIGHT_DISCARD_IN_PLAY = -300.0
WEIGHT_END = -1000000.0
ACTIVE_TARGET_BONUS = 100.0
POWERING_UP_BONUS = 50.0
ATTACK_DAMAGE_SCALE = 0.5         # attack score = base + min(dmg, 1900) * scale
YESNO_MATCH = 10.0

# ---------------------------------------------------------------------------
# v3 evaluator weights (sign convention: positive = good for us).
# evaluate_state() is a linear value function over Observation.current;
# MAIN-phase options are scored tier + (evaluate_state(after) - evaluate_state(now)),
# with the "after" state approximated analytically from card_data.json.
# Tiers reuse the v1 constants so turn structure (setup before attack) holds.
# ---------------------------------------------------------------------------
V3_W_PRIZE = 60.0           # per prize card of differential (theirs remaining - ours)
                            # tuned 2026-07-07: hill-climb over ACTIVE/ATTACKER_ENERGY/
                            # PRIZE/KO_THREAT, 100-game rounds; this config confirmed
                            # 53% vs v1 policy over 200 games (runs/tune_v3.json)
V3_W_BOARD_HP = 0.10        # per point of on-board HP differential
V3_W_ATTACKER_ENERGY = 40.0 # per useful energy (<= attack cost) on our best attacker
V3_W_KO_THREAT = 60.0       # our active can KO the opposing active this turn
V3_W_BENCH = 12.0           # per Pokemon on our bench
V3_W_HAND = 2.0             # per card in our hand
V3_W_ACTIVE = 30.0          # attach/evolve preference for the Active Spot: only
                            # the active attacks, and retreat costs 3-4 here

# Fallback deck (sample submission deck) used only if deck.csv is unreadable.
FALLBACK_DECK = (
    [1158, 721, 721, 722, 722, 722, 722, 723, 723, 723, 723,
     1145, 1145, 1145, 1145, 1205, 1205, 1227, 1227, 1227, 1227,
     1235, 1235, 1235, 1235] + [3] * 35
)

STATS = {"calls": 0, "fallbacks": 0, "total_ms": 0.0, "max_ms": 0.0}
LAST_INFO = {}


def _find_file(name):
    """Resolve a bundled file both locally and under Kaggle's exec() load."""
    candidates = []
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    candidates.append(os.getcwd())
    candidates.append("/kaggle_simulations/agent")
    candidates.extend(p for p in sys.path if isinstance(p, str) and p)
    for d in candidates:
        try:
            fp = os.path.join(d, name)
            if os.path.isfile(fp):
                return fp
        except Exception:
            pass
        # Also search the bot/ subdirectory (weights bundled there)
        try:
            fp = os.path.join(d, "bot", name)
            if os.path.isfile(fp):
                return fp
        except Exception:
            pass
    return None



def _load_deck():
    fp = _find_file("deck.csv")
    if fp is None:
        print("[agent] WARNING: deck.csv not found, using baked-in fallback deck",
              file=sys.stderr, flush=True)
        return list(FALLBACK_DECK)
    try:
        with open(fp, "r") as f:
            ids = [int(line.strip()) for line in f if line.strip()]
        if len(ids) != 60:
            raise ValueError("deck.csv has %d cards, expected 60" % len(ids))
        return ids
    except Exception as e:
        print("[agent] WARNING: failed reading deck.csv (%s), using fallback deck" % e,
              file=sys.stderr, flush=True)
        return list(FALLBACK_DECK)


def _load_card_data():
    """card_data.json is baked at build time from cg.api.all_card_data().
    Missing file degrades scoring but must never crash the agent (C3)."""
    fp = _find_file("card_data.json")
    if fp is None:
        print("[agent] WARNING: card_data.json not found, running with degraded scoring",
              file=sys.stderr, flush=True)
        return {}, {}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        cards = {int(k): v for k, v in data.get("cards", {}).items()}
        attacks = {int(k): v for k, v in data.get("attacks", {}).items()}
        return cards, attacks
    except Exception as e:
        print("[agent] WARNING: failed reading card_data.json (%s), degraded scoring" % e,
              file=sys.stderr, flush=True)
        return {}, {}


DECK = _load_deck()
CARDS, ATTACKS = _load_card_data()
TOTAL_BASIC_ENERGY = sum(1 for cid in DECK if CARDS.get(cid, {}).get("cardType") == CT_BASIC_ENERGY)


def _card(cid):
    return CARDS.get(cid) or {}


def _best_attack_info(cid):
    """(max damage, energy-cost length of that attack) over a card's attacks."""
    best_dmg, best_cost = 0.0, 0
    for aid in _card(cid).get("attacks") or []:
        atk = ATTACKS.get(aid)
        if not atk:
            continue
        dmg = atk.get("damage") or 0
        if dmg >= best_dmg:
            best_dmg = dmg
            best_cost = len(atk.get("energies") or [])
    return best_dmg, best_cost


def _players(cur):
    return cur.get("players") or [{}, {}]


def _my(cur, me):
    return _players(cur)[me]


def _opp(cur, me):
    return _players(cur)[1 - me]


def _opp_archetype(cur, me):
    """Live opponent-archetype guess from marquee card ids seen in play or
    discard (both fully public zones -- no hand/deck inference needed).
    Returns a label in OPP_ARCHETYPE_IDS or None. Cheap: no persistent state,
    recomputed from `cur` each call, so a KO'd-and-discarded marquee card
    still counts via the discard pile."""
    theirs = _opp(cur, me)
    ids = set()
    for pk in (theirs.get("active") or []) + (theirs.get("bench") or []):
        if pk:
            ids.add(pk.get("id"))
    for c in (theirs.get("discard") or []):
        if c:
            ids.add(c.get("id"))
    for label, sig in OPP_ARCHETYPE_IDS.items():
        if ids & sig:
            return label
    return None


def _active_pokemon(player):
    act = player.get("active") or []
    return act[0] if act else None


def _pokemon_at(cur, player_index, area, index, me):
    p = _players(cur)[player_index if player_index is not None else me]
    try:
        if area == AREA_ACTIVE:
            return _active_pokemon(p)
        if area == AREA_BENCH:
            return (p.get("bench") or [])[index]
    except (IndexError, TypeError):
        pass
    return None


def _option_card_id(opt, sel, cur, me):
    """Map a CARD option (area, index, playerIndex) to a card ID where visible."""
    area = opt.get("area")
    index = opt.get("index")
    pi = opt.get("playerIndex")
    pi = me if pi is None else pi
    try:
        if area == AREA_DECK and sel.get("deck"):
            return (sel["deck"][index] or {}).get("id")
        if area == AREA_LOOKING and cur.get("looking"):
            return (cur["looking"][index] or {}).get("id")
        p = _players(cur)[pi]
        if area == AREA_HAND and p.get("hand"):
            return (p["hand"][index] or {}).get("id")
        if area == AREA_DISCARD:
            return ((p.get("discard") or [])[index] or {}).get("id")
        if area == AREA_ACTIVE:
            pk = _active_pokemon(p)
            return pk.get("id") if pk else None
        if area == AREA_BENCH:
            return ((p.get("bench") or [])[index] or {}).get("id")
        if area == AREA_PRIZE:
            pr = (p.get("prize") or [])[index]
            return pr.get("id") if pr else None
        if area == AREA_STADIUM and cur.get("stadium"):
            return (cur["stadium"][0] or {}).get("id")
    except (IndexError, TypeError, KeyError):
        pass
    return None


def _hand_card_id(cur, me, index):
    hand = _my(cur, me).get("hand") or []
    try:
        return (hand[index] or {}).get("id")
    except (IndexError, TypeError):
        return None


def _card_value(cid):
    """How much we mind losing this card (used for discard/keep choices)."""
    c = _card(cid)
    ct = c.get("cardType")
    if ct == CT_POKEMON:
        v = 150.0 + (c.get("hp") or 0) / 10.0 + _best_attack_info(cid)[0] / 10.0
        if c.get("ex") or c.get("megaEx"):
            v += 100.0
        return v
    if ct == CT_SUPPORTER:
        return 80.0
    if ct == CT_SPECIAL_ENERGY:
        return 60.0
    if ct == CT_TOOL:
        return 50.0
    if ct == CT_ITEM:
        return 40.0
    if ct == CT_STADIUM:
        return 30.0
    if ct == CT_BASIC_ENERGY:
        return 10.0
    return 60.0  # unknown card: assume moderately valuable


def _count_basic_energy(cards):
    return sum(1 for c in cards or [] if c and _card(c.get("id")).get("cardType") == CT_BASIC_ENERGY)


_SCALING_ATTACK_TAGS = {
    # Gate A: attack_id -> (per_unit, source), where source is a callable
    # (cur, me, attacker_pk) -> non-negative int count.
    # Only attacks whose condition is verifiable from public observation live
    # here — the ABSTAIN discipline (§6j) is enforced by omission.
    540: ("raging_curse", 10),   # Cynthia's Spiritomb: damage counters on our benched Cynthia's Pokemon
    88: ("psychic", 30),         # Alakazam Psychic: energies on opponent's active
}


def _is_cynthia_pokemon(cid):
    """Cynthia's Pokemon family — verifiable from card name prefix."""
    return (_card(cid).get("name") or "").startswith("Cynthia'")


def _scaling_damage_bonus(attack_id, cur, me):
    """Compute the "+N per unit" bonus for attacks in _SCALING_ATTACK_TAGS.
    Returns None if attack is not in the tag list OR condition unverifiable
    (ABSTAIN → caller keeps printed damage)."""
    tag = _SCALING_ATTACK_TAGS.get(attack_id)
    if tag is None:
        return None
    kind, per_unit = tag
    if kind == "raging_curse":
        # 10 damage per damage counter on benched Cynthia's Pokemon
        mine = _my(cur, me)
        counters = 0
        for pk in mine.get("bench") or []:
            if pk and _is_cynthia_pokemon(pk.get("id")):
                maxhp = pk.get("maxHp") or 0
                hp = pk.get("hp") or 0
                counters += max(0, (maxhp - hp) // 10)
        return per_unit * counters
    if kind == "psychic":
        # 30 damage per energy attached to opponent's active
        opp_pk = _active_pokemon(_opp(cur, me))
        if not opp_pk:
            return 0
        return per_unit * len(opp_pk.get("energies") or [])
    return None


def _attack_damage_est(attack_id, cur, me):
    """Damage estimate for an attack; dynamic for known variable attacks.
    Gate A: when EVAL_FIX is on, verifiable scaling attacks add their bonus
    on top of printed damage; unverifiable attacks fall through unchanged."""
    atk = ATTACKS.get(attack_id) or {}
    dmg = float(atk.get("damage") or 0)
    name = (atk.get("name") or "").lower()
    mine = _my(cur, me)
    if EVAL_FIX:
        bonus = _scaling_damage_bonus(attack_id, cur, me)
        if bonus is not None:
            dmg += float(bonus)
    # R3: Raging Curse's printed damage is 0 -- "This attack does 10 damage
    # for each damage counter on all of your Benched Cynthia's Pokemon"
    # (card_data.json attack 540). Without this it scores exactly
    # WEIGHT_ATTACK_BASE, so a measured 360-damage swing is priced identically
    # to a whiff. Read straight off our own bench; nothing hidden is involved.
    # Deliberately scoped to this one attack -- EVAL_FIX stays off and killed.
    if CARD_R3_RAGING_CURSE and "raging curse" in name:
        counters = 0
        for pk in (mine.get("bench") or []):
            if not pk or not _is_cynthia_pokemon(pk.get("id")):
                continue
            mx = _card(pk.get("id")).get("hp") or 0
            hp = pk.get("hp")
            if hp is None or mx <= 0:
                continue
            counters += max(0, int(round((mx - hp) / 10.0)))
        return 10.0 * counters
    if "riptide" in name:
        # 20 damage per Basic Water Energy in our discard pile
        dmg = 20.0 * _count_basic_energy(mine.get("discard"))
    elif "hammer" in name:
        # 100 per Basic Energy in the top 6 of our deck: estimate from density
        seen = _count_basic_energy(mine.get("discard")) + _count_basic_energy(mine.get("hand"))
        for pk in (mine.get("active") or []) + (mine.get("bench") or []):
            if pk:
                seen += _count_basic_energy(pk.get("energyCards"))
        unseen = (mine.get("deckCount") or 0) + len(mine.get("prize") or [])
        remaining = max(0, TOTAL_BASIC_ENERGY - seen)
        frac = (remaining / unseen) if unseen > 0 else 0.0
        dmg = 100.0 * min(6, int(6 * frac + 0.5))
    # Weakness doubling when the defender is a card we know (e.g. mirror match)
    opp_pk = _active_pokemon(_opp(cur, me))
    my_pk = _active_pokemon(_my(cur, me))
    if opp_pk and my_pk:
        opp_c, my_c = _card(opp_pk.get("id")), _card(my_pk.get("id"))
        if opp_c.get("weakness") is not None and opp_c.get("weakness") == my_c.get("energyType"):
            dmg *= 2
        if opp_c and opp_c.get("ex") and my_pk.get("tools"):
            for t in my_pk["tools"]:
                if "maximum belt" in (_card((t or {}).get("id")).get("name") or "").lower():
                    dmg += 50
    return dmg


def _attack_score(attack_id, cur, me):
    dmg = _attack_damage_est(attack_id, cur, me)
    opp_pk = _active_pokemon(_opp(cur, me))
    if opp_pk and opp_pk.get("hp") is not None and dmg >= opp_pk["hp"] > 0:
        return WEIGHT_LETHAL + dmg
    return WEIGHT_ATTACK_BASE + min(dmg, 1900.0) * ATTACK_DAMAGE_SCALE


_SEARCH_ABILITY_CACHE = {}


def _is_search_ability(cid):
    """R1: does this Pokemon carry a deck-search ability?

    Read from card_data.json `skills[]` text rather than a card-id table, so it
    generalises to any deck we might pilot. Cynthia's Gabite's Champion's Call
    ("search your deck for a Cynthia's Pokemon ... put it into your hand") is
    the case this was built for."""
    hit = _SEARCH_ABILITY_CACHE.get(cid)
    if hit is None:
        hit = False
        for sk in (_card(cid).get("skills") or []):
            t = (sk.get("text") or "").lower()
            if "search your deck" in t and "hand" in t:
                hit = True
                break
        _SEARCH_ABILITY_CACHE[cid] = hit
    return hit


def _can_evolve_further(cid):
    """R2: is this Pokemon a non-final stage of a line present in OUR deck?

    True when some card in DECK evolves from it, i.e. attaching here is
    building toward a bigger attacker rather than feeding a dead end."""
    nm = _card(cid).get("name")
    if not nm:
        return False
    for other in set(DECK or ()):
        if _card(other).get("evolvesFrom") == nm:
            return True
    return False


def _attach_target_score(cur, me, in_area, in_index):
    """Prefer attaching to the active / strongest / still-powering-up Pokemon."""
    pk = _pokemon_at(cur, me, in_area, in_index, me)
    if not pk:
        return 0.0
    best_dmg, best_cost = _best_attack_info(pk.get("id"))
    s = best_dmg / 10.0
    if in_area == AREA_ACTIVE:
        s += ACTIVE_TARGET_BONUS
    if len(pk.get("energies") or []) < best_cost:
        s += POWERING_UP_BONUS
    # R2: a benched Pokemon that can still evolve is the growing attacker.
    # Garchomp ex retreats for 0, so building it on the bench costs no tempo.
    if CARD_R2_BENCH_ATTACH and in_area == AREA_BENCH \
            and _can_evolve_further(pk.get("id")):
        s += EVO_TARGET_BONUS
    return s


# ---------------------------------------------------------------------------
# v3: state evaluator + analytic 1-ply option deltas (MAIN phase)
# ---------------------------------------------------------------------------

def _board(player):
    return [pk for pk in (player.get("active") or []) + (player.get("bench") or []) if pk]


def _prizes_for_ko(cid):
    c = _card(cid)
    if c.get("megaEx"):
        return 3
    if c.get("ex"):
        return 2
    return 1


def _best_attacker(cur, me):
    """Our board Pokemon with the strongest attack: (pk, best_dmg, cost_len)."""
    best = None
    for pk in _board(_my(cur, me)):
        dmg, cost = _best_attack_info(pk.get("id"))
        if best is None or dmg > best[1]:
            best = (pk, dmg, cost)
    return best


def _active_ready_damage(cur, me):
    """Best damage our active can deal THIS turn (attacks whose cost is paid)."""
    pk = _active_pokemon(_my(cur, me))
    if not pk:
        return 0.0
    n_energy = len(pk.get("energies") or [])
    best = 0.0
    for aid in _card(pk.get("id")).get("attacks") or []:
        atk = ATTACKS.get(aid)
        if atk and len(atk.get("energies") or []) <= n_energy:
            best = max(best, _attack_damage_est(aid, cur, me))
    return best


def evaluate_state(cur):
    """Linear value of Observation.current for the observing player.

    Positive = good for us. Prize arrays hold cards REMAINING to take, so
    fewer of ours remaining means we are ahead.
    """
    me = cur.get("yourIndex") or 0
    mine, theirs = _my(cur, me), _opp(cur, me)
    v = V3_W_PRIZE * (len(theirs.get("prize") or []) - len(mine.get("prize") or []))
    my_hp = sum((pk.get("hp") or 0) for pk in _board(mine))
    their_hp = sum((pk.get("hp") or 0) for pk in _board(theirs))
    v += V3_W_BOARD_HP * (my_hp - their_hp)
    best = _best_attacker(cur, me)
    if best is not None:
        pk, _dmg, cost = best
        v += V3_W_ATTACKER_ENERGY * min(len(pk.get("energies") or []), cost)
    opp_pk = _active_pokemon(theirs)
    if opp_pk and (opp_pk.get("hp") or 0) > 0 \
            and _active_ready_damage(cur, me) >= opp_pk["hp"]:
        v += V3_W_KO_THREAT
    v += V3_W_BENCH * len(mine.get("bench") or [])
    v += V3_W_HAND * len(mine.get("hand") or [])
    return v


# ---------------------------------------------------------------------------
# State feature encoder (RL groundwork). Pure feature extraction from
# Observation.current + card_data.json — stdlib only, no engine calls.
# The shipped policy never calls this unless a learned-value flag is on;
# tools/gen_selfplay.py imports it so training data and runtime inference
# share ONE feature definition (train/serve parity).
# ---------------------------------------------------------------------------

ENC_HP_SCALE = 350.0
ENC_DMG_SCALE = 400.0
N_HAND_SLOTS = 15
HAND_SLOT_IDS = tuple(sorted(set(DECK)))[:N_HAND_SLOTS]
N_SLOT_FEATURES = 11
N_STATE_FEATURES = 12 * N_SLOT_FEATURES + 23 + N_HAND_SLOTS  # 170

N_CARD_SLOTS = 20
CARD_SLOT_IDS = tuple(sorted(set(DECK)))[:N_CARD_SLOTS]
_DECK_TABLES = {"key": None, "hand": HAND_SLOT_IDS, "card": CARD_SLOT_IDS}


def _deck_tables():
    """(hand_slot_ids, card_slot_ids) — import-time constants unless
    DYN_DECK_TABLES, then re-derived from the current DECK (cached)."""
    if not DYN_DECK_TABLES:
        return HAND_SLOT_IDS, CARD_SLOT_IDS
    key = tuple(DECK)
    if _DECK_TABLES["key"] != key:
        ids = tuple(sorted(set(key)))
        _DECK_TABLES["key"] = key
        _DECK_TABLES["hand"] = ids[:N_HAND_SLOTS]
        _DECK_TABLES["card"] = ids[:N_CARD_SLOTS]
    return _DECK_TABLES["hand"], _DECK_TABLES["card"]


def _encode_pokemon_slot(pk, opp_active_card, dyn_dmg):
    """11 features for one board slot; zeros when the slot is empty.

    `dyn_dmg` (or None) overrides the static best-attack damage — needed for
    deck-density attacks like Hammer-lanche whose db damage is 0.
    """
    if not pk:
        return [0.0] * N_SLOT_FEATURES
    c = _card(pk.get("id"))
    hp = float(pk.get("hp") or 0)
    max_hp = float(pk.get("maxHp") or c.get("hp") or 0)
    n_energy = float(len(pk.get("energies") or []))
    best_dmg, best_cost = _best_attack_info(pk.get("id"))
    if dyn_dmg is not None:
        best_dmg = max(best_dmg, dyn_dmg)
    weak = 1.0 if (opp_active_card is not None
                   and c.get("weakness") is not None
                   and c.get("weakness") == opp_active_card.get("energyType")) else 0.0
    return [
        1.0,
        hp / ENC_HP_SCALE,
        max_hp / ENC_HP_SCALE,
        max(0.0, max_hp - hp) / ENC_HP_SCALE,
        n_energy / 5.0,
        1.0 if c.get("ex") else 0.0,
        1.0 if c.get("megaEx") else 0.0,
        min(best_dmg, 800.0) / ENC_DMG_SCALE,
        max(0.0, best_cost - n_energy) / 4.0,
        (c.get("retreatCost") or 0) / 4.0,
        weak,
    ]


def _encode_board_slots(cur, me, player, opp_active_card, dynamic):
    """Active + 5 bench slots (padded). dynamic=True uses our density-aware
    damage estimate — only valid for the observing player's own slots."""
    out = []
    board = [_active_pokemon(player)] + list(player.get("bench") or [])[:5]
    while len(board) < 6:
        board.append(None)
    for pk in board[:6]:
        dyn = None
        if dynamic and pk:
            dyn = max((_attack_damage_est(aid, cur, me)
                       for aid in _card(pk.get("id")).get("attacks") or []),
                      default=None)
        out.extend(_encode_pokemon_slot(pk, opp_active_card, dyn))
    return out


def encode_state(cur):
    """170-dim feature list for the observing player. All ~[0, 1] scaled."""
    me = cur.get("yourIndex") or 0
    mine, theirs = _my(cur, me), _opp(cur, me)
    my_act, opp_act = _active_pokemon(mine), _active_pokemon(theirs)
    my_act_card = _card(my_act.get("id")) if my_act else None
    opp_act_card = _card(opp_act.get("id")) if opp_act else None

    feats = _encode_board_slots(cur, me, mine, opp_act_card, True)
    feats += _encode_board_slots(cur, me, theirs, my_act_card, False)

    feats.append(min(float(cur.get("turn") or 0), 40.0) / 20.0)
    feats.append(len(mine.get("prize") or []) / 6.0)
    feats.append(len(theirs.get("prize") or []) / 6.0)
    feats.append((mine.get("deckCount") or 0) / 60.0)
    feats.append((theirs.get("deckCount") or 0) / 60.0)
    feats.append((mine.get("handCount") or len(mine.get("hand") or [])) / 10.0)
    feats.append((theirs.get("handCount") or 0) / 10.0)
    feats.append(_count_basic_energy(mine.get("discard")) / 35.0)
    feats.append(_count_basic_energy(theirs.get("discard")) / 35.0)
    for flag in ("supporterPlayed", "energyAttached", "retreated"):
        feats.append(1.0 if cur.get(flag) else 0.0)
    for p in (mine, theirs):
        for cond in ("poisoned", "burned", "asleep", "paralyzed", "confused"):
            feats.append(1.0 if p.get(cond) else 0.0)
    feats.append(1.0 if cur.get("firstPlayer") == me else 0.0)

    counts = {}
    for c in mine.get("hand") or []:
        if c:
            counts[c.get("id")] = counts.get(c.get("id"), 0) + 1
    hand_ids, _card_ids = _deck_tables()
    for i in range(N_HAND_SLOTS):
        if i < len(hand_ids):
            feats.append(min(counts.get(hand_ids[i], 0), 4) / 4.0)
        else:
            feats.append(0.0)
    return feats


def state_feature_names():
    """Index map for encode_state — kept adjacent so they move together."""
    slot_feats = ["present", "hp", "max_hp", "damage_taken", "energy",
                  "is_ex", "is_mega_ex", "best_dmg", "energy_needed",
                  "retreat_cost", "weak_to_opp_active"]
    names = []
    for side in ("my", "opp"):
        for slot in ["active"] + ["bench%d" % i for i in range(5)]:
            names += ["%s_%s_%s" % (side, slot, f) for f in slot_feats]
    names += ["turn", "my_prizes_left", "opp_prizes_left", "my_deck", "opp_deck",
              "my_hand_n", "opp_hand_n", "my_discard_energy", "opp_discard_energy",
              "supporter_played", "energy_attached", "retreated"]
    for side in ("my", "opp"):
        names += ["%s_%s" % (side, c)
                  for c in ("poisoned", "burned", "asleep", "paralyzed", "confused")]
    names += ["i_am_first_player"]
    names += ["hand_count_id%d" % cid for cid in HAND_SLOT_IDS]
    names += ["hand_count_pad%d" % i for i in range(len(HAND_SLOT_IDS), N_HAND_SLOTS)]
    return names


# ---------------------------------------------------------------------------
# Option feature encoder (Phase 2c search distillation). Same contract as
# encode_state: pure extraction from the observation + card_data.json, shared
# by tools/gen_distill.py (training data) and any future distilled-policy
# inference, so features can never drift between train and serve. The shipped
# v1 policy never calls this.
# ---------------------------------------------------------------------------

N_OPTION_TYPES = 17    # OptionType enum 0..16
N_CARD_TYPES = 7       # CardType enum 0..6
N_OPTION_FEATURES = N_OPTION_TYPES + N_CARD_TYPES + N_SLOT_FEATURES + 6  # 41


def _option_target_pokemon(opt, cur, me):
    """Our board Pokemon the option acts on (attach/evolve target, attacker,
    retreater), or None when the option has no board target."""
    t = opt.get("type")
    if t in (OT_ATTACK, OT_RETREAT):
        return _active_pokemon(_my(cur, me))
    area, index = opt.get("inPlayArea"), opt.get("inPlayIndex")
    if area is None:
        area, index = opt.get("area"), opt.get("index")
    if area in (AREA_ACTIVE, AREA_BENCH):
        return _pokemon_at(cur, opt.get("playerIndex"), area, index, me)
    return None


def encode_option(opt, sel, cur, me, v1_rank=0.0, v1_top=0.0):
    """41 features for one option of a MAIN-phase decision, ~[0, 1] scaled."""
    t = opt.get("type")
    feats = [0.0] * N_OPTION_TYPES
    if isinstance(t, int) and 0 <= t < N_OPTION_TYPES:
        feats[t] = 1.0

    if t == OT_PLAY:
        cid = _hand_card_id(cur, me, opt.get("index"))
    else:
        cid = _option_card_id(opt, sel, cur, me)
    c = _card(cid)
    ct = c.get("cardType")
    ct_onehot = [0.0] * N_CARD_TYPES
    if isinstance(ct, int) and 0 <= ct < N_CARD_TYPES:
        ct_onehot[ct] = 1.0
    feats += ct_onehot

    opp_act = _active_pokemon(_opp(cur, me))
    opp_act_card = _card(opp_act.get("id")) if opp_act else None
    pk = _option_target_pokemon(opt, cur, me)
    if pk is None and t == OT_PLAY and ct == CT_POKEMON:
        # benching from hand: encode the card as the slot it would become
        pk = {"id": cid, "hp": c.get("hp"), "maxHp": c.get("hp"), "energies": []}
    dyn = None
    if pk:
        dyn = max((_attack_damage_est(aid, cur, me)
                   for aid in _card(pk.get("id")).get("attacks") or []),
                  default=None)
    feats += _encode_pokemon_slot(pk, opp_act_card, dyn)

    dmg = _attack_damage_est(opt.get("attackId"), cur, me) if t == OT_ATTACK else 0.0
    ko = 1.0 if (t == OT_ATTACK and opp_act
                 and (opp_act.get("hp") or 0) > 0 and dmg >= opp_act["hp"]) else 0.0
    feats.append(min(dmg, 800.0) / ENC_DMG_SCALE)
    feats.append(ko)
    feats.append(min(_card_value(cid), 400.0) / 400.0)
    feats.append(1.0 if (opt.get("inPlayArea") == AREA_ACTIVE
                         or t in (OT_ATTACK, OT_RETREAT)) else 0.0)
    feats.append(v1_rank)
    feats.append(v1_top)
    return feats


def encode_options(sel, cur):
    """Feature rows for every option of one decision (list of 41-dim lists).

    The v1-prior features (rank in v1 order, is-v1-top-choice) always come
    from the plain v1 MAIN scorer `_score_main`, independent of any policy
    flag, so a learned policy that consumes them cannot recurse into itself.
    """
    me = cur.get("yourIndex") or 0
    options = sel.get("option") or []
    n = len(options)
    scores = [_score_main(o or {}, sel, cur, me) for o in options]
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    rank = [0.0] * n
    for r, i in enumerate(order):
        rank[i] = r / (n - 1) if n > 1 else 0.0
    top = order[0] if n else None
    return [encode_option(options[i] or {}, sel, cur, me,
                          rank[i], 1.0 if i == top else 0.0)
            for i in range(n)]


def option_feature_names():
    """Index map for encode_option — kept adjacent so they move together."""
    slot_feats = ["present", "hp", "max_hp", "damage_taken", "energy",
                  "is_ex", "is_mega_ex", "best_dmg", "energy_needed",
                  "retreat_cost", "weak_to_opp_active"]
    names = ["opt_type_%d" % i for i in range(N_OPTION_TYPES)]
    names += ["card_type_%d" % i for i in range(N_CARD_TYPES)]
    names += ["target_%s" % f for f in slot_feats]
    names += ["attack_dmg", "ko_if_used", "card_value", "targets_active",
              "v1_rank", "v1_top"]
    return names


# ---------------------------------------------------------------------------
# ST_CARD option encoder (Stage 3B Option A: BC-full). Same train/serve-parity
# contract as encode_options, for the CARD/ATTACHED_CARD/CARD_OR_ATTACHED
# sub-decisions (fetch targets, bench picks, promotes, discards) that v1
# answers with _score_card. Card identity is one-hot over OUR deck's distinct
# ids (like HAND_SLOT_IDS, but complete) because the setup lines BC must
# imitate are which-of-my-cards choices; off-deck ids (opponent board targets)
# fall into the unknown slot and are described by type/stat/board features.
# The selection's `contextCard` is always null in replays, so the effect
# source is characterized only by (context, option areas) — fields present
# identically at serve time.
# ---------------------------------------------------------------------------

CARD_CTX_BUCKETS = (
    (SC_SETUP_ACTIVE,), (SC_SETUP_BENCH,), (SC_SWITCH,),
    (SC_TO_ACTIVE, SC_TO_FIELD), (SC_TO_BENCH,), (SC_TO_HAND,),
    (SC_DISCARD, SC_DETACH_FROM), (SC_TO_DECK, SC_TO_DECK_BOTTOM, SC_TO_PRIZE),
    (SC_DMG_COUNTER, SC_DMG_COUNTER_ANY, SC_DAMAGE), (SC_REMOVE_DMG, SC_HEAL),
    (SC_EVOLVES_FROM, SC_EVOLVES_TO),
)  # + 1 trailing "other" bucket
CARD_OPT_AREAS = (AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE,
                  AREA_BENCH, AREA_PRIZE, AREA_STADIUM, AREA_LOOKING)
N_CARD_OPTION_FEATURES = (N_CARD_SLOTS + 1) + N_CARD_TYPES + 5 \
    + N_SLOT_FEATURES + len(CARD_OPT_AREAS) + 1 \
    + (len(CARD_CTX_BUCKETS) + 1) + 6 + 2  # 73


def encode_card_option(opt, sel, cur, me, v1_rank=0.0, v1_top=0.0):
    """73 features for one option of an ST_CARD-family decision, ~[0,1]."""
    cid = _option_card_id(opt, sel, cur, me)
    c = _card(cid)

    _hand_ids, card_ids = _deck_tables()
    feats = [0.0] * (N_CARD_SLOTS + 1)
    feats[card_ids.index(cid) if cid in card_ids else N_CARD_SLOTS] = 1.0

    ct = c.get("cardType")
    ct_onehot = [0.0] * N_CARD_TYPES
    if isinstance(ct, int) and 0 <= ct < N_CARD_TYPES:
        ct_onehot[ct] = 1.0
    feats += ct_onehot

    best_dmg, _cost = _best_attack_info(cid)
    feats += [
        1.0 if c.get("basic") else 0.0,
        (c.get("hp") or 0) / ENC_HP_SCALE,
        1.0 if (c.get("ex") or c.get("megaEx")) else 0.0,
        min(best_dmg, 800.0) / ENC_DMG_SCALE,
        min(_card_value(cid), 400.0) / 400.0,
    ]

    area, pi = opt.get("area"), opt.get("playerIndex")
    is_mine = pi in (None, me)
    pk = None
    if area in (AREA_ACTIVE, AREA_BENCH):
        pk = _pokemon_at(cur, pi, area, opt.get("index"), me)
    dyn = None
    if pk and is_mine:
        dyn = max((_attack_damage_est(aid, cur, me)
                   for aid in _card(pk.get("id")).get("attacks") or []),
                  default=None)
    opp_act = _active_pokemon(_opp(cur, me))
    opp_act_card = _card(opp_act.get("id")) if opp_act else None
    feats += _encode_pokemon_slot(pk, opp_act_card if is_mine else None, dyn)

    area_onehot = [0.0] * len(CARD_OPT_AREAS)
    if area in CARD_OPT_AREAS:
        area_onehot[CARD_OPT_AREAS.index(area)] = 1.0
    feats += area_onehot
    feats.append(0.0 if is_mine else 1.0)

    ctx = sel.get("context")
    ctx_onehot = [0.0] * (len(CARD_CTX_BUCKETS) + 1)
    for i, bucket in enumerate(CARD_CTX_BUCKETS):
        if ctx in bucket:
            ctx_onehot[i] = 1.0
            break
    else:
        ctx_onehot[-1] = 1.0
    feats += ctx_onehot

    stype = sel.get("type")
    n = len(sel.get("option") or [])
    mx = sel.get("maxCount")
    mx = n if mx is None else mx
    feats += [
        1.0 if stype == ST_CARD else 0.0,
        1.0 if stype == ST_ATTACHED_CARD else 0.0,
        1.0 if stype == ST_CARD_OR_ATTACHED else 0.0,
        min(float(sel.get("minCount") or 0), 6.0) / 6.0,
        min(float(mx), 6.0) / 6.0,
        min(float(n), 20.0) / 20.0,
    ]
    feats.append(v1_rank)
    feats.append(v1_top)
    return feats


def encode_card_options(sel, cur):
    """Feature rows for every option of one ST_CARD-family decision.

    The v1-prior features come from the plain `_score_card` ordering (same
    anti-recursion rule as encode_options: independent of any policy flag).
    """
    me = cur.get("yourIndex") or 0
    ctx = sel.get("context")
    options = sel.get("option") or []
    n = len(options)
    scores = [_score_card(o or {}, sel, cur, me, ctx) for o in options]
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    rank = [0.0] * n
    for r, i in enumerate(order):
        rank[i] = r / (n - 1) if n > 1 else 0.0
    top = order[0] if n else None
    return [encode_card_option(options[i] or {}, sel, cur, me,
                               rank[i], 1.0 if i == top else 0.0)
            for i in range(n)]


def card_option_feature_names():
    """Index map for encode_card_option — kept adjacent so they move together."""
    slot_feats = ["present", "hp", "max_hp", "damage_taken", "energy",
                  "is_ex", "is_mega_ex", "best_dmg", "energy_needed",
                  "retreat_cost", "weak_to_opp_active"]
    names = ["deck_id_%d" % cid for cid in CARD_SLOT_IDS]
    names += ["deck_id_pad%d" % i for i in range(len(CARD_SLOT_IDS), N_CARD_SLOTS)]
    names += ["card_id_unknown"]
    names += ["card_type_%d" % i for i in range(N_CARD_TYPES)]
    names += ["is_basic", "card_hp", "is_ex_or_mega", "card_best_dmg", "card_value"]
    names += ["target_%s" % f for f in slot_feats]
    names += ["area_%d" % a for a in CARD_OPT_AREAS]
    names += ["is_opponent_target"]
    names += ["ctx_bucket_%d" % i for i in range(len(CARD_CTX_BUCKETS))]
    names += ["ctx_other"]
    names += ["st_card", "st_attached", "st_card_or_attached",
              "min_count", "max_count", "n_options"]
    names += ["v1_rank", "v1_top"]
    return names


# ---------------------------------------------------------------------------
# Learned value model: loading + inference + analytic post-option features.
# Weight file contract (training/train_value.py header): n_layers, n_features,
# kind, W0..W{L-1} float32 [in,out], b0..b{L-1} float32 [out];
# forward = relu hidden layers, sigmoid output = P(win | state).
# ---------------------------------------------------------------------------

# Feature indices derived from the encode_state layout (see state_feature_names).
LVI_GLOBAL = 12 * N_SLOT_FEATURES        # first global feature ("turn")
LVI_MY_PRIZES = LVI_GLOBAL + 1
LVI_MY_HAND = LVI_GLOBAL + 5
LVI_ENERGY_ATTACHED = LVI_GLOBAL + 10
LVI_HAND_COUNTS = LVI_GLOBAL + 23
LVI_OPP_ACTIVE = 6 * N_SLOT_FEATURES

_LV = {"tried": False, "model": None}
_LV_CACHE = {"key": None, "feats": None, "p": None}


def _lv_read_npz_pure(fp):
    """Minimal .npz reader (stdlib only) for the numpy-missing fallback.
    Returns {name: (shape, values)} — float/int arrays as flat lists,
    unicode scalars as str."""
    import array
    import ast
    import struct
    import zipfile
    out = {}
    with zipfile.ZipFile(fp) as z:
        for name in z.namelist():
            raw = z.read(name)
            if raw[:6] != b"\x93NUMPY":
                raise ValueError("bad .npy magic in %s" % name)
            if raw[6] == 1:
                hlen, off = struct.unpack("<H", raw[8:10])[0], 10
            else:
                hlen, off = struct.unpack("<I", raw[8:12])[0], 12
            hdr = ast.literal_eval(raw[off:off + hlen].decode("latin1"))
            if hdr.get("fortran_order"):
                raise ValueError("fortran_order unsupported")
            shape, descr = hdr["shape"], hdr["descr"]
            body = raw[off + hlen:]
            key = name[:-4] if name.endswith(".npy") else name
            if descr.startswith("<U"):
                out[key] = (shape, body.decode("utf-32-le").rstrip("\x00"))
                continue
            typecode = {"<f4": "f", "<f8": "d", "<i4": "i", "<i8": "q"}.get(descr)
            if typecode is None:
                raise ValueError("dtype %s unsupported in %s" % (descr, name))
            a = array.array(typecode)
            n = 1
            for s in shape:
                n *= s
            a.frombytes(body[:a.itemsize * n])
            if sys.byteorder == "big":
                a.byteswap()
            out[key] = (shape, list(a))
    return out


def _lv_load(fp):
    """Load + validate the weights file. Returns a model dict or raises."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        d = np.load(fp)
        n_layers, nf = int(d["n_layers"]), int(d["n_features"])
        layers = [(np.asarray(d["W%d" % i], dtype=np.float32),
                   np.asarray(d["b%d" % i], dtype=np.float32))
                  for i in range(n_layers)]
        dims = [(w.shape[0], w.shape[1], b.shape[0]) for w, b in layers]
    else:
        arrs = _lv_read_npz_pure(fp)
        n_layers, nf = int(arrs["n_layers"][1][0]), int(arrs["n_features"][1][0])
        layers = []
        for i in range(n_layers):
            (rows, cols), wvals = arrs["W%d" % i]
            _bs, bvals = arrs["b%d" % i]
            layers.append(([wvals[r * cols:(r + 1) * cols] for r in range(rows)],
                           list(bvals)))
        dims = [(len(w), len(w[0]), len(b)) for w, b in layers]
    if nf not in (N_STATE_FEATURES, 194):
        raise ValueError("weights expect %d features, encoder has %d or 194"
                         % (nf, N_STATE_FEATURES))
    if dims[0][0] != nf or dims[-1][1] != 1:
        raise ValueError("layer dims %r do not match %d -> 1" % (dims, nf))
    for (i_in, i_out, i_b), (j_in, _o, _b) in zip(dims, dims[1:]):
        if i_out != i_b or i_out != j_in:
            raise ValueError("inconsistent layer chain %r" % (dims,))
    if dims[-1][1] != dims[-1][2]:
        raise ValueError("inconsistent output bias %r" % (dims,))
    return {"np": np, "layers": layers}


def _lv_model():
    """Cached model, loaded on first use. Any failure warns once to stderr and
    pins the model to None so every scorer falls back to heuristic tiers."""
    if _LV["tried"]:
        return _LV["model"]
    _LV["tried"] = True
    fp = _find_file(LV_WEIGHTS_FILE)
    if fp is None:
        print("[agent] WARNING: %s not found; learned value disabled, "
              "using heuristic tiers" % LV_WEIGHTS_FILE, file=sys.stderr, flush=True)
        return None
    try:
        _LV["model"] = _lv_load(fp)
    except Exception as e:
        print("[agent] WARNING: failed loading %s (%s); learned value disabled, "
              "using heuristic tiers" % (LV_WEIGHTS_FILE, e),
              file=sys.stderr, flush=True)
    return _LV["model"]


def _lv_predict(model, rows):
    """rows: list of feature lists -> list of win probabilities."""
    np, layers = model["np"], model["layers"]
    if np is not None:
        h = np.asarray(rows, dtype=np.float32)
        for w, b in layers[:-1]:
            h = np.maximum(h @ w + b, 0.0)
        w, b = layers[-1]
        z = np.clip((h @ w + b).ravel(), -30.0, 30.0)
        return (1.0 / (1.0 + np.exp(-z))).tolist()
    out = []
    last = len(layers) - 1
    for row in rows:
        h = row
        for li, (w, b) in enumerate(layers):
            nxt = list(b)
            for i, hi in enumerate(h):
                if hi != 0.0:
                    wi = w[i]
                    for j in range(len(nxt)):
                        nxt[j] += hi * wi[j]
            h = nxt if li == last else [v if v > 0.0 else 0.0 for v in nxt]
        z = max(-30.0, min(30.0, h[0]))
        out.append(1.0 / (1.0 + math.exp(-z)))
    return out


def _lv_now(cur, me, model):
    """(features, P(win)) for the current state, cached per decision."""
    key = (id(cur), cur.get("turn"), me)
    if _LV_CACHE["key"] != key:
        feats = encode_state(cur)
        _LV_CACHE["key"] = key
        _LV_CACHE["feats"] = feats
        _LV_CACHE["p"] = _lv_predict(model, [feats])[0]
        if LV_TRACE:
            VALUE_TRACE.append(_LV_CACHE["p"])
    return _LV_CACHE["feats"], _LV_CACHE["p"]


def _lv_delta(model, p_now, feats_after):
    d = _lv_predict(model, [feats_after])[0] - p_now
    return LV_SCALE * max(-LV_DELTA_CLIP, min(LV_DELTA_CLIP, d))


def _lv_slot_base(opp, area, index):
    slot = 0 if area == AREA_ACTIVE else 1 + min(int(index or 0), 4)
    return ((6 if opp else 0) + slot) * N_SLOT_FEATURES


def _lv_spend_hand_card(f, cid):
    """Approximate a card leaving our hand in feature space."""
    f[LVI_MY_HAND] = max(0.0, f[LVI_MY_HAND] - 0.1)
    if cid in HAND_SLOT_IDS:
        hi = LVI_HAND_COUNTS + HAND_SLOT_IDS.index(cid)
        f[hi] = max(0.0, f[hi] - 0.25)


def _lv_after_attach(cur, me, feats, area, index, cid=None):
    """Post-state features for attaching one energy to (area, index)."""
    base = _lv_slot_base(False, area, index)
    if area not in (AREA_ACTIVE, AREA_BENCH) or feats[base] == 0.0:
        return None
    f = list(feats)
    f[base + 4] += 0.2                                   # +1 energy (/5 scale)
    f[base + 8] = max(0.0, f[base + 8] - 0.25)           # energy_needed (/4)
    f[LVI_ENERGY_ATTACHED] = 1.0
    if cid is not None:
        _lv_spend_hand_card(f, cid)
    return f


def _lv_after_evolve(cur, me, feats, cid, area, index):
    pk = _pokemon_at(cur, me, area, index, me)
    c = _card(cid)
    base = _lv_slot_base(False, area, index)
    if not pk or not c or feats[base] == 0.0:
        return None
    dmg_taken = max(0, (pk.get("maxHp") or 0) - (pk.get("hp") or 0))
    new_pk = {"id": cid, "hp": max(10, (c.get("hp") or 0) - dmg_taken),
              "maxHp": c.get("hp") or 0, "energies": pk.get("energies") or []}
    opp_act = _active_pokemon(_opp(cur, me))
    dyn = max((_attack_damage_est(aid, cur, me)
               for aid in c.get("attacks") or []), default=None)
    f = list(feats)
    f[base:base + N_SLOT_FEATURES] = _encode_pokemon_slot(
        new_pk, _card(opp_act.get("id")) if opp_act else None, dyn)
    _lv_spend_hand_card(f, cid)
    return f


def _lv_after_attack(cur, me, feats, attack_id):
    opp_pk = _active_pokemon(_opp(cur, me))
    if not opp_pk:
        return None
    dmg = _attack_damage_est(attack_id, cur, me)
    hp = opp_pk.get("hp") or 0
    f = list(feats)
    base = LVI_OPP_ACTIVE
    if dmg >= hp > 0:
        f[base:base + N_SLOT_FEATURES] = [0.0] * N_SLOT_FEATURES
        f[LVI_MY_PRIZES] = max(
            0.0, f[LVI_MY_PRIZES] - _prizes_for_ko(opp_pk.get("id")) / 6.0)
    else:
        f[base + 1] = max(0.0, f[base + 1] - dmg / ENC_HP_SCALE)
        f[base + 3] += dmg / ENC_HP_SCALE
    return f


def _lv_after_bench(cur, me, feats, cid):
    c = _card(cid)
    if not c:
        return None
    for b in range(1, 6):
        base = b * N_SLOT_FEATURES
        if feats[base] == 0.0:
            break
    else:
        return None
    opp_act = _active_pokemon(_opp(cur, me))
    dyn = max((_attack_damage_est(aid, cur, me)
               for aid in c.get("attacks") or []), default=None)
    new_pk = {"id": cid, "hp": c.get("hp") or 0, "maxHp": c.get("hp") or 0,
              "energies": []}
    f = list(feats)
    f[base:base + N_SLOT_FEATURES] = _encode_pokemon_slot(
        new_pk, _card(opp_act.get("id")) if opp_act else None, dyn)
    _lv_spend_hand_card(f, cid)
    return f


def _lv_after_promote(feats, index):
    """Swap our active slot with bench slot `index` in feature space."""
    src = _lv_slot_base(False, AREA_BENCH, index)
    if feats[src] == 0.0:
        return None
    f = list(feats)
    f[0:N_SLOT_FEATURES], f[src:src + N_SLOT_FEATURES] = (
        f[src:src + N_SLOT_FEATURES], f[0:N_SLOT_FEATURES])
    return f


def _lv_score_main(opt, sel, cur, me, model):
    """Tier + learned win-prob delta for the option types whose post-state is
    constructible in feature space; v1 scoring everywhere else."""
    t = opt.get("type")
    feats_now, p_now = _lv_now(cur, me, model)
    if t == OT_ATTACK:
        f = _lv_after_attack(cur, me, feats_now, opt.get("attackId"))
        if f is not None:
            opp_pk = _active_pokemon(_opp(cur, me))
            dmg = _attack_damage_est(opt.get("attackId"), cur, me)
            hp = (opp_pk or {}).get("hp") or 0
            tier = WEIGHT_LETHAL if dmg >= hp > 0 else WEIGHT_ATTACK_BASE
            return tier + _lv_delta(model, p_now, f)
    elif t == OT_ATTACH:
        cid = _option_card_id(opt, sel, cur, me)
        if _card(cid).get("cardType") != CT_TOOL:
            f = _lv_after_attach(cur, me, feats_now, opt.get("inPlayArea"),
                                 opt.get("inPlayIndex"), cid)
            if f is not None:
                return WEIGHT_ATTACH_ENERGY + _lv_delta(model, p_now, f)
    elif t == OT_EVOLVE:
        cid = _option_card_id(opt, sel, cur, me)
        f = _lv_after_evolve(cur, me, feats_now, cid,
                             opt.get("inPlayArea"), opt.get("inPlayIndex"))
        if f is not None:
            return WEIGHT_EVOLVE + _lv_delta(model, p_now, f)
    elif t == OT_PLAY:
        cid = _hand_card_id(cur, me, opt.get("index"))
        if _card(cid).get("cardType") == CT_POKEMON:
            f = _lv_after_bench(cur, me, feats_now, cid)
            if f is not None:
                mine = _my(cur, me)
                in_play = len(mine.get("active") or []) + len(mine.get("bench") or [])
                tier = WEIGHT_BENCH_URGENT if in_play <= 1 else WEIGHT_BENCH
                return tier + _lv_delta(model, p_now, f)
    return _score_main(opt, sel, cur, me)


def _v3_attach_target_delta(cur, me, area, index):
    """Value gained by attaching one energy to the Pokemon at (area, index)."""
    pk = _pokemon_at(cur, me, area, index, me)
    if not pk:
        return 0.0
    best = _best_attacker(cur, me)
    dmg, cost = _best_attack_info(pk.get("id"))
    n_energy = len(pk.get("energies") or [])
    s = V3_W_ACTIVE if area == AREA_ACTIVE else 0.0
    if best is not None and pk.get("serial") == best[0].get("serial") and n_energy < best[2]:
        return s + V3_W_ATTACKER_ENERGY
    if n_energy < cost:
        return s + V3_W_ATTACKER_ENERGY * 0.25 + dmg / 100.0
    return s + 1.0


def _v3_score_main(opt, sel, cur, me):
    """Tier + analytic evaluate_state delta for the option types where the
    delta is computable from card_data.json; falls back to v1 elsewhere."""
    t = opt.get("type")
    mine = _my(cur, me)
    if t == OT_ATTACK:
        dmg = _attack_damage_est(opt.get("attackId"), cur, me)
        opp_pk = _active_pokemon(_opp(cur, me))
        opp_hp = (opp_pk or {}).get("hp") or 0
        if opp_pk and dmg >= opp_hp > 0:
            return WEIGHT_LETHAL + V3_W_PRIZE * _prizes_for_ko(opp_pk.get("id")) \
                + V3_W_BOARD_HP * opp_hp
        return WEIGHT_ATTACK_BASE + V3_W_BOARD_HP * min(dmg, opp_hp if opp_hp else dmg)
    if t == OT_ATTACH:
        cid = _option_card_id(opt, sel, cur, me)
        if _card(cid).get("cardType") == CT_TOOL:
            return WEIGHT_ATTACH_TOOL + _attach_target_score(
                cur, me, opt.get("inPlayArea"), opt.get("inPlayIndex")) * 0.5
        return WEIGHT_ATTACH_ENERGY + _v3_attach_target_delta(
            cur, me, opt.get("inPlayArea"), opt.get("inPlayIndex"))
    if t == OT_EVOLVE:
        cid = _option_card_id(opt, sel, cur, me)
        target = _pokemon_at(cur, me, opt.get("inPlayArea"), opt.get("inPlayIndex"), me)
        c = _card(cid)
        hp_gain = (c.get("hp") or 0) - ((target or {}).get("maxHp") or 0)
        dmg_gain = _best_attack_info(cid)[0] - _best_attack_info((target or {}).get("id"))[0]
        s = V3_W_ACTIVE if opt.get("inPlayArea") == AREA_ACTIVE else 0.0
        return WEIGHT_EVOLVE + s + V3_W_BOARD_HP * max(0, hp_gain) + max(0, dmg_gain) / 10.0
    if t == OT_PLAY:
        cid = _hand_card_id(cur, me, opt.get("index"))
        if _card(cid).get("cardType") == CT_POKEMON:
            in_play = len(mine.get("active") or []) + len(mine.get("bench") or [])
            tier = WEIGHT_BENCH_URGENT if in_play <= 1 else WEIGHT_BENCH
            return tier + V3_W_BENCH + V3_W_BOARD_HP * (_card(cid).get("hp") or 0) - V3_W_HAND
    return _score_main(opt, sel, cur, me)


def _score_main(opt, sel, cur, me):
    t = opt.get("type")
    if t == OT_ATTACK:
        return _attack_score(opt.get("attackId"), cur, me)
    if t == OT_END:
        return WEIGHT_END
    if t == OT_RETREAT:
        return WEIGHT_RETREAT
    if t == OT_DISCARD:
        return WEIGHT_DISCARD_IN_PLAY
    if t == OT_ABILITY:
        # R1: a once-per-turn deck-search ability is free card advantage and
        # compounds (fetch a Cynthia's Pokemon -> bench it -> another Gabite ->
        # another Champion's Call). Flat WEIGHT_ABILITY ranks it below item,
        # bench and evolve, which is why our uptake is 16.8% vs top-10 36.3%.
        if CARD_R1_SEARCH_ABILITY:
            pk = _pokemon_at(cur, me, opt.get("inPlayArea"),
                             opt.get("inPlayIndex"), me)
            if pk and _is_search_ability(pk.get("id")):
                return WEIGHT_ABILITY_SEARCH
        return WEIGHT_ABILITY
    if t == OT_EVOLVE:
        cid = _option_card_id(opt, sel, cur, me)
        s = WEIGHT_EVOLVE + _best_attack_info(cid)[0] / 10.0
        if opt.get("inPlayArea") == AREA_ACTIVE:
            s += ACTIVE_TARGET_BONUS
        return s
    if t == OT_ATTACH:
        cid = _option_card_id(opt, sel, cur, me)
        ct = _card(cid).get("cardType")
        tgt = _attach_target_score(cur, me, opt.get("inPlayArea"), opt.get("inPlayIndex"))
        if ct == CT_TOOL:
            return WEIGHT_ATTACH_TOOL + tgt * 0.5
        return WEIGHT_ATTACH_ENERGY + tgt
    if t == OT_PLAY:
        cid = _hand_card_id(cur, me, opt.get("index"))
        ct = _card(cid).get("cardType")
        if ct == CT_POKEMON:
            mine = _my(cur, me)
            in_play = len(mine.get("active") or []) + len(mine.get("bench") or [])
            return WEIGHT_BENCH_URGENT if in_play <= 1 else WEIGHT_BENCH
        if ct == CT_SUPPORTER:
            return WEIGHT_PLAY_SUPPORTER
        if ct == CT_ITEM:
            return WEIGHT_PLAY_ITEM
        if ct == CT_STADIUM:
            return WEIGHT_PLAY_STADIUM
        return 100.0
    return 0.0


def _score_card(opt, sel, cur, me, ctx):
    cid = _option_card_id(opt, sel, cur, me)
    pk = None
    if opt.get("area") in (AREA_ACTIVE, AREA_BENCH):
        pk = _pokemon_at(cur, opt.get("playerIndex"), opt.get("area"), opt.get("index"), me)

    if ctx in (SC_SETUP_ACTIVE, SC_TO_ACTIVE, SC_SWITCH, SC_TO_FIELD):
        # promote/choose active: prefer high HP, energy already attached, big attacks
        if LEARNED_VALUE and pk and opt.get("area") == AREA_BENCH \
                and opt.get("playerIndex") in (None, me):
            model = _lv_model()
            if model is not None:
                feats_now, p_now = _lv_now(cur, me, model)
                f = _lv_after_promote(feats_now, opt.get("index"))
                if f is not None:
                    return 10.0 + _lv_delta(model, p_now, f)
        # Gate D: post-KO promote — maxHp + 30·energy (Sanjay §6q rule 1).
        # SC_TO_ACTIVE only; SETUP / SWITCH / TO_FIELD keep the original scorer.
        if PROMOTE_RULE and ctx == SC_TO_ACTIVE and pk:
            return float(pk.get("maxHp") or pk.get("hp") or 0) \
                + 30.0 * len(pk.get("energies") or [])
        # T1: SC_SWITCH targeting the OPPONENT's bench (Boss's Orders / gust)
        # is a different decision from choosing OUR OWN next active, and the
        # existing hp+energy+attack formula below is the wrong goal for it.
        # Scoped tightly: only fires when playerIndex names the opponent, so
        # the ~73% of SC_SWITCH volume that is self-targeting is untouched.
        if TARGET_T1_BOSS_PRIZE and pk and ctx == SC_SWITCH \
                and opt.get("playerIndex") is not None \
                and opt.get("playerIndex") != me:
            STATS["t1_fired"] = STATS.get("t1_fired", 0) + 1
            our_act = (_my(cur, me).get("active") or [None])[0]
            our_dmg = _best_attack_info((our_act or {}).get("id"))[0] if our_act else 0
            hp = pk.get("hp") or 0
            is_one_shot = (hp > 0 and hp <= our_dmg)
            ko_weight = 5000.0 if is_one_shot else 0.0
            return ko_weight + 1000.0 * _prizes_for_ko(pk.get("id")) \
                + 50.0 * len(pk.get("energies") or []) \
                - 10.0 * ((pk.get("hp") or 0) / max(1.0, float(pk.get("maxHp") or pk.get("hp") or 1)))
        if pk:
            return (pk.get("hp") or 0) + 20.0 * len(pk.get("energies") or []) \
                + _best_attack_info(pk.get("id"))[0] / 10.0
        return (_card(cid).get("hp") or 0) + _best_attack_info(cid)[0] / 10.0
    if ctx in (SC_SETUP_BENCH, SC_TO_BENCH):
        return 10.0 + (_card(cid).get("hp") or 0) / 10.0
    if ctx == SC_TO_HAND:
        # F1: retrieving is not discarding. Prefer Basic Energy, then fall back
        # to the existing ordering unchanged (the mined "energy-first, then
        # _card_value" criterion, 68.3% agreement vs 36.0% shipped).
        if FETCH_F1_ENERGY_FIRST and cid is not None \
                and _card(cid).get("cardType") == CT_BASIC_ENERGY:
            STATS["f1_fired"] = STATS.get("f1_fired", 0) + 1
            return 1000.0 + _card_value(cid)
        return _card_value(cid) if cid is not None else 10.0
    if ctx in (SC_DISCARD, SC_TO_DECK, SC_TO_DECK_BOTTOM, SC_TO_PRIZE, SC_DETACH_FROM):
        return -_card_value(cid) if cid is not None else -60.0
    if ctx == SC_NOT_MOVE:
        return _card_value(cid) if cid is not None else 10.0
    if ctx in (SC_DMG_COUNTER, SC_DMG_COUNTER_ANY, SC_DAMAGE):
        # damaging opponents: prefer the closest to a KO, prefer the active
        # T4: if this placement actually KOs the target, take it. Scoped to
        # opponent-owned targets only, so self-targeting placements are
        # untouched. Falls through to the T2 ratio scorer when not lethal.
        if TARGET_T4_LETHAL and pk \
                and opt.get("playerIndex") is not None \
                and opt.get("playerIndex") != me:
            _t4_dmg = T4_DMG_BY_SOURCE.get(((sel or {}).get("effect") or {}).get("id"))
            if _t4_dmg and (pk.get("hp") or 0) <= _t4_dmg:
                STATS["t4_fired"] = STATS.get("t4_fired", 0) + 1
                # prefer the most expensive kill available, then the active
                return T4_LETHAL_SCORE \
                    + 100.0 * _prizes_for_ko(pk.get("id")) \
                    + (30.0 if opt.get("area") == AREA_ACTIVE else 0.0)
        if pk:
            # T2: rank by HP RATIO, not raw HP, so a fresh low-max-HP Basic
            # doesn't outrank a half-dead high-max-HP attacker just because
            # its absolute HP number happens to be lower right now.
            if TARGET_T2_SPLASH_RATIO:
                STATS["t2_fired"] = STATS.get("t2_fired", 0) + 1
                maxhp = float(pk.get("maxHp") or pk.get("hp") or 1)
                ratio = (pk.get("hp") or 0) / max(1.0, maxhp)
                s = 200.0 * (1.0 - ratio)
                if TARGET_T3_FEZ_TIEBREAK and _opp_archetype(cur, me) == "fezandipiti":
                    STATS["t3_fired"] = STATS.get("t3_fired", 0) + 1
                    s += 2.0 * len(pk.get("energies") or []) \
                        + 3.0 * _prizes_for_ko(pk.get("id"))
            else:
                s = 200.0 - (pk.get("hp") or 200)
            if opt.get("area") == AREA_ACTIVE:
                s += 30.0
            return s
        return 10.0
    if ctx in (SC_REMOVE_DMG, SC_HEAL):
        if pk:
            return float((pk.get("maxHp") or 0) - (pk.get("hp") or 0))
        return 10.0
    if ctx in (SC_EVOLVES_FROM, SC_EVOLVES_TO):
        s = (_card(cid).get("hp") or 0) / 10.0 + _best_attack_info(cid)[0] / 10.0
        if opt.get("area") == AREA_ACTIVE:
            s += ACTIVE_TARGET_BONUS
        return 10.0 + s
    if ctx in (SC_ATTACH_FROM, SC_ATTACH_TO):
        if LEARNED_VALUE and opt.get("area") in (AREA_ACTIVE, AREA_BENCH) \
                and opt.get("playerIndex") in (None, me):
            model = _lv_model()
            if model is not None:
                feats_now, p_now = _lv_now(cur, me, model)
                f = _lv_after_attach(cur, me, feats_now,
                                     opt.get("area"), opt.get("index"))
                if f is not None:
                    return 10.0 + _lv_delta(model, p_now, f)
        if ctx == SC_ATTACH_FROM:
            if V3_EVAL:
                return 10.0 + _v3_attach_target_delta(cur, me, opt.get("area"), opt.get("index"))
            return 10.0 + _attach_target_score(cur, me, opt.get("area"), opt.get("index"))
        if V3_EVAL and opt.get("area") in (AREA_ACTIVE, AREA_BENCH):
            return 10.0 + _v3_attach_target_delta(cur, me, opt.get("area"), opt.get("index"))
        return 10.0
    if ctx in (SC_LOOK, SC_EFFECT_TARGET):
        return 10.0
    return 0.0


def _score_yesno(opt, ctx, cur, me):
    if ctx == SC_MULLIGAN:
        hand = _my(cur, me).get("hand") or []
        has_basic = any(_card((c or {}).get("id")).get("basic") for c in hand)
        want_yes = not has_basic
    elif ctx == SC_MORE_DEVOLVE:
        want_yes = False
    else:
        # IS_FIRST, ACTIVATE, FIRST_EFFECT, COIN_HEAD and unknown contexts: yes
        want_yes = True
    is_yes = opt.get("type") == OT_YES
    return YESNO_MATCH if is_yes == want_yes else -YESNO_MATCH


def _pilot_score_main(opt, sel, cur, me):
    """Garchomp tempo layer over v1 MAIN scoring. Traced to nasuo445's replays:
    they attack 93% of turns once a loaded attacker exists (first attack turn 4),
    playing the once-per-turn draw supporter first and then swinging. We keep v1
    ordering until the turn's supporter has resolved (so the draw engine still
    fires), then let a loaded attack outrank the remaining marginal setup so the
    attack is never deferred across turns."""
    base = _score_main(opt, sel, cur, me)
    t = opt.get("type")
    if t == OT_ATTACK and (cur.get("turn") or 0) >= 4 and base < WEIGHT_LETHAL:
        dmg = _attack_damage_est(opt.get("attackId"), cur, me)
        if dmg > 0 and cur.get("supporterPlayed"):
            return max(base, WEIGHT_TEMPO_LOADED + min(dmg, 1900.0) * ATTACK_DAMAGE_SCALE)
        # A-WEIGHT: the hook above is gated on the turn's supporter having
        # resolved, which is false on 75.6% of the decisions where the best
        # attack falls out of the search candidate set (median 100 damage --
        # real swings, not chip). This second, lower tier fires without that
        # gate for a loaded, non-chip attack only: CAND_ATK_W=2200 puts a
        # 100-damage attack at 2250, above marginal setup (stadium 2030,
        # ability 2060, tool 2100, supporter 2150) but still below bench
        # (2300), item (2400), evolve (2800) and energy attach (3000).
        if CAND_ATK_W > 0 and dmg >= CAND_ATK_MIN_DMG:
            return max(base, CAND_ATK_W + min(dmg, 1900.0) * ATTACK_DAMAGE_SCALE)
    elif t == OT_EVOLVE:
        # evolution rush: nasuo445 gets Garchomp ex online by ~turn 6. Nudge
        # evolutions toward an ex (the win condition) above ordinary evolves so
        # the attacker line completes before side pieces (e.g. Roserade).
        cid = _option_card_id(opt, sel, cur, me)
        c = _card(cid)
        if c.get("ex") or c.get("megaEx"):
            return base + WEIGHT_EVOLVE_EX_BONUS
    return base


def _score_option(opt, sel, cur, me):
    stype = sel.get("type")
    ctx = sel.get("context")
    if stype == ST_MAIN:
        if LEARNED_VALUE:
            model = _lv_model()
            if model is not None:
                return _lv_score_main(opt, sel, cur, me, model)
        if V3_EVAL:
            return _v3_score_main(opt, sel, cur, me)
        if PILOT == "garchomp":
            return _pilot_score_main(opt, sel, cur, me)
        return _score_main(opt, sel, cur, me)
    if stype in (ST_CARD, ST_CARD_OR_ATTACHED, ST_ATTACHED_CARD):
        return _score_card(opt, sel, cur, me, ctx)
    if stype == ST_YES_NO:
        return _score_yesno(opt, ctx, cur, me)
    if stype == ST_COUNT:
        return float(opt.get("number") or 0)
    if stype == ST_ATTACK:
        aid = opt.get("attackId")
        if ctx == SC_DISABLE_ATTACK:
            return float((ATTACKS.get(aid) or {}).get("damage") or 0)
        return _attack_score(aid, cur, me)
    if stype == ST_EVOLVE:
        cid = _option_card_id(opt, sel, cur, me)
        s = _best_attack_info(cid)[0] / 10.0
        if opt.get("inPlayArea") == AREA_ACTIVE:
            s += ACTIVE_TARGET_BONUS
        return 10.0 + s
    if stype == ST_SPECIAL_CONDITION:
        return float(CONDITION_PRIORITY.get(opt.get("specialConditionType"), 0))
    # ST_ENERGY, ST_SKILL and unknown select types: neutral, deterministic first-N
    return 0.0


def resolve_selection(options, scores, min_count, max_count):
    """One resolution path for every phase (C2).

    Picks positive-scoring options (best first) up to max_count, then pads
    with the least-bad remaining options until min_count is met. Ties break
    on lowest index, so the agent is fully deterministic.
    """
    n = len(options)
    if n == 0 or max_count <= 0:
        return []
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    chosen = [i for i in order if scores[i] > 0][:max_count]
    if len(chosen) < min_count:
        for i in order:
            if i not in chosen:
                chosen.append(i)
            if len(chosen) >= min_count:
                break
    return chosen


def _legal_fallback(sel):
    """Smallest safe legal answer: [0] (or first minCount indices)."""
    try:
        options = sel.get("option") or []
        min_c = sel.get("minCount") or 0
        max_c = sel.get("maxCount")
        max_c = len(options) if max_c is None else max_c
        if len(options) == 0 or max_c <= 0:
            return []
        k = min(max(min_c, 1), max_c, len(options))
        return list(range(k))
    except Exception:
        return []


def _compact_options(sel):
    try:
        opts = [{k: v for k, v in (o or {}).items() if v is not None}
                for o in (sel.get("option") or [])]
        return json.dumps(opts)[:600]
    except Exception:
        return "<unprintable>"


def _log_fallback(reason, turn, sel):
    print("[agent %s] FALLBACK turn=%s reason=%s options=%s"
          % (AGENT_VERSION, turn, reason, _compact_options(sel) if sel else None),
          file=sys.stderr, flush=True)


def _validate_result(result, sel):
    """C1: enforce legality of every return. Returns (result, was_fixed)."""
    options = sel.get("option") or []
    n = len(options)
    min_c = sel.get("minCount") or 0
    max_c = sel.get("maxCount")
    max_c = n if max_c is None else max_c

    cleaned = []
    for x in result if isinstance(result, list) else []:
        if isinstance(x, bool) or not isinstance(x, int):
            continue
        if 0 <= x < n and x not in cleaned:
            cleaned.append(x)
    if len(cleaned) > max_c:
        cleaned = cleaned[:max_c]
    if len(cleaned) < min_c:
        for i in range(n):
            if i not in cleaned:
                cleaned.append(i)
            if len(cleaned) >= min_c:
                break
    ok = (cleaned == result if isinstance(result, list) else False)
    if not (min_c <= len(cleaned) <= max_c and all(0 <= i < n for i in cleaned)):
        return _legal_fallback(sel), False
    return cleaned, ok


# ===========================================================================
# Belief-sampled determinized search (PTCG_SEARCH). Layout:
#   engine glue        _search_lib / _sb_begin / _sb_step / _sb_release / _sb_end
#   card pool          _pool (full 1,267-card db baked into card_data.json)
#   belief             CardTracker (per-perspective, serial-keyed => idempotent
#                      against the engine's repeated log entries)
#   determinization    _sample_determinization (+ sample_opponent_deck hook)
#   rollouts           _rollout_choose (v1 | s1 policy net) / _rollout
#   time governor      _gov_* (budget, degradation curve, telemetry ring)
#   search             _searchable / _search_decide (called from agent())
# ===========================================================================

_SES = {"lib": None, "ptr": None, "tried": False, "errs": 0}


def _search_lib():
    """Engine handle, loaded once. On the ladder the eager call below runs
    while Kaggle still has the agent dir on sys.path (exec window); locally
    the repo root carries a cg/ copy. Failure => one stderr line, search off."""
    if _SES["lib"] is not None or _SES["tried"]:
        return _SES["lib"]
    _SES["tried"] = True
    try:
        marker = _find_file(os.path.join("cg", "sim.py"))
        if marker:
            parent = os.path.dirname(os.path.dirname(marker))
            if parent not in sys.path:
                sys.path.insert(0, parent)
        import cg.sim as _sim  # loads platform lib + GameInitialize()
        _SES["lib"] = _sim.lib
        _SES["ptr"] = _sim.lib.AgentStart()
    except Exception as e:
        print("[search] cg engine unavailable (%r) - heuristic-only mode" % e,
              file=sys.stderr, flush=True)
    return _SES["lib"]


def _carr(v):
    return (ctypes.c_int * len(v))(*v)


def _sb_begin(sbi, your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active):
    r = json.loads(_SES["lib"].SearchBegin(
        _SES["ptr"], sbi.encode("ascii"), len(sbi),
        _carr(your_deck), _carr(your_prize), _carr(opp_deck), _carr(opp_prize),
        _carr(opp_hand), _carr(opp_active), 0))
    if r.get("error"):
        raise RuntimeError("SearchBegin error %s" % r["error"])
    return r["state"]


def _sb_step(search_id, select):
    r = json.loads(_SES["lib"].SearchStep(_SES["ptr"], search_id,
                                          _carr(select), len(select)))
    if r.get("error"):
        raise RuntimeError("SearchStep error %s" % r["error"])
    return r["state"]


def _sb_release(search_id):
    try:
        _SES["lib"].SearchRelease(_SES["ptr"], search_id)
    except Exception:
        pass


def _sb_end():
    try:
        _SES["lib"].SearchEnd(_SES["ptr"])
    except Exception:
        pass


_POOL_CACHE = None


def _pool():
    """Full card pool {id: {name, cardType, energyType, basic}} baked into
    card_data.json at build time. Empty dict if absent (sampler degrades)."""
    global _POOL_CACHE
    if _POOL_CACHE is None:
        pool = {}
        fp = _find_file("card_data.json")
        if fp:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    pool = {int(k): v
                            for k, v in (json.load(f).get("pool") or {}).items()}
            except Exception as e:
                print("[search] card pool unreadable (%s); mirror-guess sampling" % e,
                      file=sys.stderr, flush=True)
        if not pool:
            print("[search] no card pool in card_data.json; mirror-guess sampling",
                  file=sys.stderr, flush=True)
        _POOL_CACHE = pool
    return _POOL_CACHE


# Log types consumed by CardTracker (values from cg/api.py LogType).
LOG_DRAW, LOG_MOVE_CARD, LOG_MOVE_CARD_REVERSE = 4, 6, 7
LOG_PLAY, LOG_ATTACH, LOG_EVOLVE = 10, 11, 12


class CardTracker:
    """Opponent-knowledge belief from one player's perspective.

    Every card in a match has a unique serial, so all knowledge is keyed by
    serial => reprocessing a repeated log entry is a no-op (Observation.logs
    repeats entries across steps). Zones we can see (board, discard, revealed
    prizes) come straight from `current`; the tracker's real product is:
      hand_known  serial->id  cards known to be in the opponent's hand now
      floating    serial->id  revealed cards ambiguous between hand and deck
                  (face-down shuffles demote hand knowledge here)
      serial_id   serial->id  every opponent card ever identified (for the
                  4-copy budget of the deck belief)
      energy_types            opponent energy types observed so far
    New game = turn regression or a prize count growing back (prizes only
    ever shrink within a game).
    """

    def __init__(self, me):
        self.me = me
        self.reset()

    def reset(self):
        self.serial_id = {}
        self.hand_known = {}
        self.floating = {}
        self.energy_types = set()
        self.last_turn = -1
        self.last_prizes = (99, 99)

    def _forget(self, serial):
        self.hand_known.pop(serial, None)
        self.floating.pop(serial, None)

    def _see(self, serial, cid):
        if serial is not None and cid is not None:
            self.serial_id[serial] = cid

    def update(self, obs):
        """Consume one of our observations. Returns True if a new game was
        detected (tracker was reset before processing)."""
        cur = obs.get("current") or {}
        players = cur.get("players") or [{}, {}]
        turn = cur.get("turn") or 0
        mine = players[self.me] if len(players) > self.me else {}
        theirs = players[1 - self.me] if len(players) > 1 - self.me else {}
        n_my_pr = len(mine.get("prize") or [])
        n_op_pr = len(theirs.get("prize") or [])
        # prizes only shrink within a game; growth from a nonzero baseline =
        # new game (growth from 0 is the setup->dealt transition, same game)
        fresh = (turn < self.last_turn
                 or 0 < self.last_prizes[0] < n_my_pr
                 or 0 < self.last_prizes[1] < n_op_pr)
        if fresh:
            self.reset()

        opp = 1 - self.me
        for lg in obs.get("logs") or []:
            if not isinstance(lg, dict) or lg.get("playerIndex") != opp:
                continue
            t = lg.get("type")
            cid, ser = lg.get("cardId"), lg.get("serial")
            if t == LOG_MOVE_CARD and ser is not None and cid is not None:
                self._see(ser, cid)
                to = lg.get("toArea")
                if to == AREA_HAND:
                    self.floating.pop(ser, None)
                    self.hand_known[ser] = cid
                elif to == AREA_DECK:
                    self.hand_known.pop(ser, None)
                    self.floating[ser] = cid   # certainly deck; hand-or-deck is safe
                else:
                    self._forget(ser)          # visible zone: `current` covers it
            elif t == LOG_MOVE_CARD_REVERSE:
                if lg.get("fromArea") == AREA_HAND:
                    # an unidentified hand card moved face-down: we no longer
                    # know WHICH, so every hand-known card demotes to floating
                    self.floating.update(self.hand_known)
                    self.hand_known.clear()
            elif t in (LOG_PLAY, LOG_ATTACH, LOG_EVOLVE):
                self._see(ser, cid)
                self._forget(ser)
            elif t == LOG_DRAW and ser is not None and cid is not None:
                # opponent draws normally arrive as DRAW_REVERSE; if the engine
                # reveals one (card effect), remember it
                self._see(ser, cid)
                self.hand_known[ser] = cid

        # visible opponent zones: ingest identities, clear stale hand knowledge
        for card in (theirs.get("discard") or []) + [c for c in theirs.get("prize") or [] if c]:
            if isinstance(card, dict):
                self._see(card.get("serial"), card.get("id"))
                self._forget(card.get("serial"))
        for pk in (theirs.get("active") or []) + (theirs.get("bench") or []):
            if not pk:
                continue
            self._see(pk.get("serial"), pk.get("id"))
            self._forget(pk.get("serial"))
            for zone in ("energyCards", "tools", "preEvolution"):
                for card in pk.get(zone) or []:
                    if isinstance(card, dict):
                        self._see(card.get("serial"), card.get("id"))
                        self._forget(card.get("serial"))
            for et in pk.get("energies") or []:
                if isinstance(et, int):
                    self.energy_types.add(et)

        pool = _pool()
        for cid in self.serial_id.values():
            info = pool.get(cid)
            if info and info.get("cardType") == CT_BASIC_ENERGY \
                    and info.get("energyType") is not None:
                self.energy_types.add(info["energyType"])

        # bookkeeping sanity: hand knowledge can never exceed the hand count
        if len(self.hand_known) > (theirs.get("handCount") or 0):
            self.floating.update(self.hand_known)
            self.hand_known.clear()

        self.last_turn = turn
        self.last_prizes = (n_my_pr, n_op_pr)
        return fresh


def _sd_visible_ids(player, include_hand):
    """Card ids visible in a player's zones (searcher.py logic)."""
    ids = []
    if include_hand:
        ids += [c["id"] for c in player.get("hand") or [] if c]
    for pk in (player.get("active") or []) + (player.get("bench") or []):
        if pk:  # face-down active shows as None
            ids.append(pk["id"])
            for zone in ("energyCards", "tools", "preEvolution"):
                ids += [c["id"] for c in pk.get(zone) or [] if c]
    ids += [c["id"] for c in player.get("discard") or [] if c]
    ids += [c["id"] for c in player.get("prize") or [] if c]
    return ids


def _sd_fill_prize(prize, sampled):
    """Keep revealed prize cards in position, fill hidden slots from sampled."""
    out, k = [], 0
    for c in prize or []:
        if c:
            out.append(c["id"])
        else:
            out.append(sampled[k])
            k += 1
    return out


# Belief over the unseen part of the opponent's list. "comp" (default) is a
# STRUCTURAL prior only — real decks are ~1/3 energy, ~1/3 Pokemon, ~1/3
# trainers, while the raw pool is 8/1267 basic energy: uniform-over-pool
# sampling produces energy-less strawman opponents whose rollouts all
# saturate at a win, erasing candidate discrimination (measured: 96% of
# rollout values = 1.0). "uniform" keeps the raw pool for A/B reference;
# "mirror" assumes our own list (the teacher's exact-knowledge determinization,
# used as the diagnosis comparator). Card-level archetype priors from META.md
# plug in through SEARCH_PRIOR / the `prior` argument without code changes.
SEARCH_BELIEF = os.environ.get("PTCG_SEARCH_BELIEF", "comp")
_COMP_TARGETS = {"energy": 0.30, "pokemon": 0.35, "trainer": 0.35}
_COMP_PRIOR_CACHE = None

# Top-ladder meta archetypes for dynamic opponent deck inference
META_ARCHETYPES = {
    "grimmsnarl": [7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 104, 104, 112, 112, 112, 112, 646, 646, 646, 646, 647, 647, 647, 648, 648, 648, 860, 860, 1079, 1079, 1079, 1080, 1086, 1086, 1086, 1086, 1097, 1097, 1097, 1122, 1137, 1152, 1152, 1152, 1152, 1182, 1182, 1219, 1219, 1219, 1219, 1227, 1227, 1227, 1227, 1231, 1259, 1259, 1259, 1259],
    "fezandipiti": [5, 5, 13, 19, 19, 19, 19, 66, 66, 140, 305, 305, 305, 343, 741, 741, 741, 741, 742, 742, 742, 742, 743, 743, 743, 743, 1079, 1079, 1079, 1081, 1081, 1081, 1081, 1086, 1086, 1086, 1086, 1097, 1129, 1152, 1152, 1152, 1152, 1182, 1182, 1182, 1184, 1197, 1197, 1197, 1225, 1225, 1225, 1225, 1231, 1231, 1231, 1231, 1266, 1266],
    "garchomp": [341, 341, 341, 341, 342, 342, 342, 381, 381, 381, 379, 379, 379, 379, 380, 380, 380, 380, 6, 6, 6, 6, 6, 20, 20, 20, 20, 387, 387, 1080, 1086, 1086, 1086, 1086, 1097, 1097, 1142, 1142, 1142, 1142, 1152, 1152, 1152, 1152, 1173, 1173, 1173, 1182, 1182, 1203, 1197, 1225, 1225, 1225, 1227, 1227, 1227, 1227, 1261, 1261],
    "kangaskhan": [1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 4, 4, 5, 6, 6, 63, 63, 96, 96, 96, 108, 140, 184, 184, 272, 756, 756, 756, 978, 1071, 1071, 1071, 1088, 1097, 1097, 1098, 1098, 1116, 1116, 1116, 1116, 1121, 1121, 1121, 1121, 1182, 1182, 1197, 1197, 1198, 1198, 1198, 1198, 1205, 1205, 1250, 1250, 1250, 1250],
    "mewtwo": [1, 1, 1, 1, 1, 1, 1, 1, 1, 15, 15, 15, 15, 400, 400, 400, 400, 401, 401, 401, 401, 414, 414, 431, 431, 434, 434, 1094, 1094, 1094, 1116, 1121, 1134, 1134, 1134, 1134, 1152, 1152, 1152, 1152, 1159, 1175, 1216, 1216, 1216, 1216, 1217, 1218, 1218, 1218, 1220, 1220, 1220, 1220, 1227, 1227, 1227, 1257, 1257, 1257],
    "dragapult": [2, 2, 2, 2, 5, 5, 5, 5, 7, 7, 112, 112, 119, 119, 119, 119, 120, 120, 120, 120, 121, 121, 121, 140, 235, 235, 1071, 1080, 1086, 1086, 1086, 1086, 1097, 1097, 1120, 1120, 1120, 1120, 1121, 1121, 1121, 1121, 1152, 1152, 1152, 1152, 1182, 1182, 1182, 1198, 1198, 1198, 1213, 1227, 1227, 1227, 1227, 1231, 1246, 1246],
}


def infer_opponent_archetype(known_ids):
    """Classify opponent deck into one of the top meta archetypes."""
    if not known_ids:
        return None
    pool = _pool()
    scores = {}
    for name, deck in META_ARCHETYPES.items():
        arch_counter = Counter(deck)
        score = 0.0
        for cid in known_ids:
            if cid in arch_counter:
                cinfo = pool.get(cid) or {}
                ct = cinfo.get("cardType")
                if ct == CT_POKEMON:
                    score += 5.0
                elif ct == CT_BASIC_ENERGY:
                    score += 0.5
                else:
                    score += 2.0
        scores[name] = score
    best_name = max(scores, key=scores.get)
    if scores[best_name] >= 5.0:
        return META_ARCHETYPES[best_name]
    return None


def _comp_prior():
    """Card-id -> weight implementing the composition prior (cached)."""
    global _COMP_PRIOR_CACHE
    if _COMP_PRIOR_CACHE is None:
        pool = _pool()
        cats = {"energy": [], "pokemon": [], "trainer": []}
        for cid, info in pool.items():
            ct = info.get("cardType")
            if ct in (CT_BASIC_ENERGY, CT_SPECIAL_ENERGY):
                cats["energy"].append(cid)
            elif ct == CT_POKEMON:
                cats["pokemon"].append(cid)
            else:
                cats["trainer"].append(cid)
        prior = {}
        for cat, ids in cats.items():
            w = _COMP_TARGETS[cat] / max(1, len(ids))
            for cid in ids:
                prior[cid] = w
        _COMP_PRIOR_CACHE = prior
    return _COMP_PRIOR_CACHE


def sample_opponent_deck(n, known_ids, tracker, rng, prior=None):
    """Sample n unseen opponent cards from the legal pool subject to the
    4-copy-per-name limit (revealed copies included; basic energy exempt) and
    observed-energy-type consistency. `prior` (card id -> weight) is the
    archetype hook; None = the SEARCH_BELIEF default. Raises ValueError on
    underflow."""
    pool = _pool()
    if SEARCH_BELIEF == "oracle" and SEARCH_ORACLE_DECK:
        # diagnosis only: sample the remainder of the opponent's TRUE list.
        base = list((Counter(SEARCH_ORACLE_DECK) - Counter(known_ids)).elements())
        rng.shuffle(base)
        if len(base) < n:
            raise ValueError("oracle pool underflow (%d/%d)" % (len(base), n))
        return base[:n]
    if not pool or SEARCH_BELIEF == "mirror":
        # exact-knowledge guess: remainder of OUR list (teacher determinization)
        base = list((Counter(DECK) - Counter(known_ids)).elements())
        rng.shuffle(base)
        if len(base) < n:
            raise ValueError("mirror pool underflow (%d/%d)" % (len(base), n))
        return base[:n]

    # Archetype belief matching: if opponent revealed archetype cards, sample from archetype remainder
    if prior is None and SEARCH_BELIEF == "comp":
        matched_arch = infer_opponent_archetype(known_ids)
        if matched_arch is not None:
            base = list((Counter(matched_arch) - Counter(known_ids)).elements())
            rng.shuffle(base)
            if len(base) >= n:
                return base[:n]

    dom_type = None
    if prior is None and SEARCH_BELIEF == "comp":
        prior = _comp_prior()
        # type coherence: a deck whose energy doesn't match its Pokemon can
        # never pay attack costs — an iid sample is a strawman opponent even
        # with the right energy COUNT. Pick one dominant energy type per
        # determinization (from observed evidence when we have it) and build
        # the sample around it.
        etypes_seen = sorted(tracker.energy_types)
        if etypes_seen:
            dom_type = etypes_seen[rng.randrange(len(etypes_seen))]
        else:
            all_et = sorted({info.get("energyType") for info in pool.values()
                             if info.get("cardType") == CT_BASIC_ENERGY
                             and info.get("energyType") is not None})
            if all_et:
                dom_type = all_et[rng.randrange(len(all_et))]
    name_used = Counter()
    for cid in known_ids:
        info = pool.get(cid)
        if info and info.get("cardType") != CT_BASIC_ENERGY:
            name_used[info["name"]] += 1
    etypes = tracker.energy_types
    cands, weights = [], []
    for cid, info in pool.items():
        if info.get("cardType") == CT_BASIC_ENERGY:
            if etypes and info.get("energyType") not in etypes:
                continue
            if dom_type is not None and info.get("energyType") != dom_type:
                continue
        elif name_used[info["name"]] >= 4:
            continue
        w = 1.0 if prior is None else max(0.0, prior.get(cid, 1.0))
        if (dom_type is not None and info.get("cardType") == CT_POKEMON
                and info.get("energyType") == dom_type):
            w *= 6.0
        cands.append(cid)
        weights.append(w)
    out = []
    guard = 0
    while len(out) < n and guard < 40 * (n + 1) and cands:
        guard += 1
        if prior is None:
            cid = cands[rng.randrange(len(cands))]
        else:
            cid = rng.choices(cands, weights=weights, k=1)[0]
        info = pool[cid]
        if info.get("cardType") != CT_BASIC_ENERGY:
            if name_used[info["name"]] >= 4:
                continue
            name_used[info["name"]] += 1
        out.append(cid)
    if len(out) < n:
        raise ValueError("pool sampling underflow (%d/%d)" % (len(out), n))
    return out


def _sample_determinization(obs, tracker, rng):
    """One full hidden-state assignment for search_begin, consistent with the
    observation and the tracker's belief. Raises ValueError on inconsistency
    (the caller resamples and eventually falls back to the heuristic)."""
    cur = obs["current"]
    me = tracker.me
    mine, theirs = cur["players"][me], cur["players"][1 - me]

    # --- our side: full 60-card list is known, sample order/prizes uniformly
    my_pool = list((Counter(DECK) - Counter(_sd_visible_ids(mine, True))).elements())
    rng.shuffle(my_pool)
    n_hp = sum(1 for c in mine.get("prize") or [] if not c)
    if len(my_pool) < n_hp:
        raise ValueError("own pool underflow")
    my_prize = _sd_fill_prize(mine.get("prize"), my_pool[:n_hp])
    my_deck = my_pool[n_hp:]

    # --- opponent: revealed knowledge + sampled remainder
    visible = _sd_visible_ids(theirs, False)
    hand_known = list(tracker.hand_known.values())
    floating = list(tracker.floating.values())
    hc = theirs.get("handCount") or 0
    dc = theirs.get("deckCount") or 0
    n_ohp = sum(1 for c in theirs.get("prize") or [] if not c)
    active = theirs.get("active") or []
    facedown = 1 if (active and active[0] is None) else 0
    unknown = (hc - len(hand_known)) + dc + n_ohp + facedown
    if unknown < 0:
        raise ValueError("hand knowledge exceeds hand count")
    if len(floating) > unknown - n_ohp - facedown:
        floating = floating[:max(0, unknown - n_ohp - facedown)]  # stale belief
    need = unknown - len(floating)
    remainder = sample_opponent_deck(need, visible + hand_known + floating,
                                     tracker, rng, prior=SEARCH_PRIOR)

    pool = _pool()
    # prizes are set aside at game start => only never-seen cards can be there
    opp_prize = _sd_fill_prize(theirs.get("prize"), remainder[:n_ohp])
    rest = remainder[n_ohp:]
    opp_active = []
    if facedown:
        idx = next((i for i, c in enumerate(rest)
                    if (pool.get(c) or {}).get("basic")), None)
        if idx is None:
            raise ValueError("no basic for face-down active")
        opp_active = [rest.pop(idx)]
    mix = rest + floating
    rng.shuffle(mix)
    n_fill = hc - len(hand_known)
    opp_hand = hand_known + mix[:n_fill]
    opp_deck = mix[n_fill:]
    if len(opp_hand) != hc or len(opp_deck) != dc:
        raise ValueError("zone count mismatch")
    if pool and dc > 0 and (cur.get("turn") or 0) <= 1:
        # engine requires a Basic in the predicted deck at setup
        n_basics = sum(1 for c in opp_deck if (pool.get(c) or {}).get("basic"))
        if n_basics < SEARCH_MIN_BASICS:
            raise ValueError("no basic in sampled setup deck")
    return {"your_deck": my_deck, "your_prize": my_prize,
            "opp_deck": opp_deck, "opp_prize": opp_prize,
            "opp_hand": opp_hand, "opp_active": opp_active}


SEARCH_PRIOR = None   # archetype-prior hook consumed by sample_opponent_deck
SEARCH_ORACLE_DECK = None   # diagnosis-only: true opponent list for oracle belief


# ------------------------------------------------------- rollout policies ----

_POL = {"model": None, "tried": False}


def _pol_model():
    """Distilled policy net (policy_weights.npz, contract in
    training/train_policy.py). Needs numpy; anything missing => one stderr
    line and v1 rollouts."""
    if _POL["model"] is not None or _POL["tried"]:
        return _POL["model"]
    _POL["tried"] = True
    try:
        import numpy as np
        fp = _find_file(POLICY_WEIGHTS_FILE)
        if fp is None:
            raise FileNotFoundError(POLICY_WEIGHTS_FILE)
        z = np.load(fp)
        n_trunk, n_head = int(z["n_trunk"]), int(z["n_head"])
        model = {
            "np": np,
            "trunk": [(z["TW%d" % i].astype(np.float32),
                       z["Tb%d" % i].astype(np.float32)) for i in range(n_trunk)],
            "head": [(z["HW%d" % i].astype(np.float32),
                      z["Hb%d" % i].astype(np.float32)) for i in range(n_head)],
        }
        _POL["model"] = model
    except Exception as e:
        print("[search] policy net unavailable (%r); v1 rollouts" % e,
              file=sys.stderr, flush=True)
    return _POL["model"]


def _pol_choose(model, sel, cur):
    """argmax option by the policy net (ties -> lowest index), or None."""
    np = model["np"]
    emb = np.asarray(encode_state(cur), dtype=np.float32)
    for W, b in model["trunk"]:
        emb = np.maximum(emb @ W + b, 0.0)
    rows = np.asarray(encode_options(sel, cur), dtype=np.float32)
    h = np.concatenate([np.repeat(emb[None, :], len(rows), 0), rows], axis=1)
    for W, b in model["head"][:-1]:
        h = np.maximum(h @ W + b, 0.0)
    W, b = model["head"][-1]
    logits = (h @ W + b).ravel()
    return int(np.argmax(logits))


_BC = {"model": None, "tried": None}


def _bc_model():
    """BC policy net for the active BC flag (same contract as _pol_model).

    Two formats: single-head (bc_weights_garchomp.npz, MAIN only) and
    two-headed BC-full ("policy_two_head": shared trunk, MAIN head HW*/Hb*
    plus ST_CARD head CW*/Cb* over the 73-dim encode_card_option rows)."""
    if _BC["tried"] == BC:
        return _BC["model"]
    _BC["tried"] = BC
    _BC["model"] = None
    if not BC:
        return None
    try:
        import numpy as np
        fp = _find_file("bc_weights_%s.npz" % BC)
        if fp is None:
            raise FileNotFoundError("bc_weights_%s.npz" % BC)
        z = np.load(fp)
        n_trunk, n_head = int(z["n_trunk"]), int(z["n_head"])
        model = {
            "np": np,
            "trunk": [(z["TW%d" % i].astype(np.float32),
                       z["Tb%d" % i].astype(np.float32)) for i in range(n_trunk)],
            "head": [(z["HW%d" % i].astype(np.float32),
                      z["Hb%d" % i].astype(np.float32)) for i in range(n_head)],
            "head_card": None,
        }
        if "n_head_card" in z:
            model["head_card"] = [
                (z["CW%d" % i].astype(np.float32),
                 z["Cb%d" % i].astype(np.float32))
                for i in range(int(z["n_head_card"]))]
        _BC["model"] = model
    except Exception as e:
        print("[bc] weights unavailable (%r); v1 behavior" % e,
              file=sys.stderr, flush=True)
    return _BC["model"]


def _bc_card_choose(model, sel, cur):
    """ST_CARD-family picks by the BC-full card head: iterative argmax over
    the shrinking option set up to maxCount picks (mirrors the Plackett-Luce
    decomposition the head was trained on)."""
    np = model["np"]
    options = sel.get("option") or []
    n = len(options)
    mn = sel.get("minCount") or 0
    mx = sel.get("maxCount")
    mx = n if mx is None else mx
    k = min(mx, n)
    if k <= 0:
        return []
    emb = np.asarray(encode_state(cur), dtype=np.float32)
    for W, b in model["trunk"]:
        emb = np.maximum(emb @ W + b, 0.0)
    remaining = list(range(n))
    picks = []
    red = dict(sel)
    for j in range(k):
        red["option"] = [options[i] for i in remaining]
        red["minCount"], red["maxCount"] = max(0, mn - j), mx - j
        rows = np.asarray(encode_card_options(red, cur), dtype=np.float32)
        h = np.concatenate([np.repeat(emb[None, :], len(rows), 0), rows], axis=1)
        for W, b in model["head_card"][:-1]:
            h = np.maximum(h @ W + b, 0.0)
        W, b = model["head_card"][-1]
        logits = (h @ W + b).ravel()
        i = int(np.argmax(logits))
        picks.append(remaining[i])
        remaining.pop(i)
        if not remaining:
            break
    return picks


# Optional self-draw/fetch MAIN actions of the list-0 Alakazam engine, as
# (option type, card id). Measured mean own-deck consumption per action in
# brake diagnostics: Enriching Energy +3.7, Fezandipiti ex ability +2.8,
# Dawn +2.7, Hilda +1.8, Buddy-Buddy Poffin +1.6, Poke Pad +1.0,
# Dudunsparce ability (pure draw, spammed 2.7x/game). Deliberately EXCLUDED:
# evolutions/Rare Candy (their consumption is triggered bonus draws — blocking
# them would stunt board development) and Sacred Ash (returns cards to deck).
BRAKE_DRAW_ACTIONS = frozenset({
    (OT_ABILITY, 140),   # Fezandipiti ex ability
    (OT_ABILITY, 66),    # Dudunsparce ability
    (OT_ATTACH, 13),     # Enriching Energy
    (OT_PLAY, 1231),     # Dawn
    (OT_PLAY, 1225),     # Hilda
    (OT_PLAY, 1086),     # Buddy-Buddy Poffin
    (OT_PLAY, 1152),     # Poke Pad
})


def _bc_brake_mask(sel, cur):
    """Allowed option indices under the draw-brake, or None when the brake
    does not bind (flag off, deck not thin, ahead on prizes, nothing to
    exclude, or exclusion would leave no options)."""
    if not BC_BRAKE:
        return None
    me = cur.get("yourIndex")
    players = cur.get("players") or []
    if me is None or not isinstance(players, list) or len(players) < 2:
        return None
    mine, theirs = players[me], players[1 - me]
    if (mine.get("deckCount") or 0) > BC_BRAKE:
        return None
    if len(mine.get("prize") or []) < len(theirs.get("prize") or []):
        return None            # fires when not ahead on prizes (parity included)
    options = sel.get("option") or []
    allowed = []
    for i, opt in enumerate(options):
        t = opt.get("type")
        cid = None
        try:
            if t == OT_PLAY:
                cid = _hand_card_id(cur, me, opt.get("index"))
            elif t == OT_ABILITY:
                pk = _pokemon_at(cur, me, opt.get("inPlayArea"),
                                 opt.get("inPlayIndex"), me)
                cid = (pk or {}).get("id")
            elif t == OT_ATTACH:
                cid = _option_card_id(opt, sel, cur, me)
        except Exception:
            cid = None
        if (t, cid) in BRAKE_DRAW_ACTIONS:
            continue
        allowed.append(i)
    if not allowed or len(allowed) == len(options):
        return None
    return allowed


def _bc_decide(obs, sel, cur, v1_result):
    """(result, handled) — BC's choice on MAIN single-selects, and (BC-full
    only) on ST_CARD-family selections via the card head. Head-fire telemetry
    in STATS: bc_main / bc_card fired, bc_v1 = eligible but fell back."""
    if not (isinstance(sel, dict) and isinstance(cur, dict)):
        return v1_result, False
    stype = sel.get("type")
    nopt = len(sel.get("option") or [])
    is_main = (stype == ST_MAIN and sel.get("minCount", 1) == 1
               and sel.get("maxCount", 1) == 1 and nopt > 1)
    is_card = stype in (ST_CARD, ST_ATTACHED_CARD, ST_CARD_OR_ATTACHED) \
        and nopt > 1
    if not (is_main or is_card):
        return v1_result, False
    # BC_CARD_ONLY: bypass MAIN decisions entirely, use v1 for those
    if BC_CARD_ONLY and is_main:
        return v1_result, False
    model = _bc_model()
    if model is None or (is_card and model.get("head_card") is None):
        STATS["bc_v1"] = STATS.get("bc_v1", 0) + 1
        return v1_result, False
    if is_main:
        mask = None
        try:
            mask = _bc_brake_mask(sel, cur)
        except Exception:
            mask = None
        if mask:
            red = dict(sel)
            red["option"] = [sel["option"][i] for i in mask]
            result = [mask[_pol_choose(model, red, cur)]]
            STATS["bc_brake"] = STATS.get("bc_brake", 0) + 1
        else:
            result = [_pol_choose(model, sel, cur)]
        STATS["bc_main"] = STATS.get("bc_main", 0) + 1
    else:
        result = _bc_card_choose(model, sel, cur)
        STATS["bc_card"] = STATS.get("bc_card", 0) + 1
    STATS["bc_decisions"] = STATS.get("bc_decisions", 0) + 1
    if result != v1_result:
        STATS["bc_changed"] = STATS.get("bc_changed", 0) + 1
    return result, True


def _rollout_choose(node_obs):
    """Selection for one rollout node (plays BOTH seats). ROLLOUT=s1 uses the
    policy net on MAIN single-selects; everything else v1. Never raises."""
    sel = node_obs.get("select") or {}
    try:
        if (ROLLOUT == "s1" and sel.get("type") == ST_MAIN
                and sel.get("minCount", 1) == 1 and sel.get("maxCount", 1) == 1
                and len(sel.get("option") or []) > 1):
            model = _pol_model()
            if model is not None:
                return [_pol_choose(model, sel, node_obs.get("current") or {})]
        result, _top, _scores = _decide(node_obs)
        result, _ok = _validate_result(result, sel)
        return result
    except Exception:
        return _legal_fallback(sel)


def _rollout(node, me, cap):
    """Play a search node to terminal (or `cap` engine steps, then the rung-a
    value net scores the leaf). Returns a value in [0,1] for player `me`
    (equivalent to the [-1,1] convention up to the affine map 2v-1)."""
    steps = 0
    prev_id = None
    while True:
        cur = node["observation"]["current"]
        if cur["result"] != -1:
            v = 1.0 if cur["result"] == me else (0.5 if cur["result"] == 2 else 0.0)
            break
        if steps >= cap:
            v = 0.5
            model = _lv_model()
            if model is not None:
                p = _lv_predict(model, [encode_state(cur)])[0]
                v = p if cur["yourIndex"] == me else 1.0 - p
            break
        nxt = _sb_step(node["searchId"], _rollout_choose(node["observation"]))
        if prev_id is not None:
            _sb_release(prev_id)
        prev_id = node["searchId"]
        node = nxt
        steps += 1
    if prev_id is not None:
        _sb_release(prev_id)
    return v


# ----------------------------------------------------------- time governor ----

GOV_EMIT_EVERY = 40   # in-flight [gov-snap] telemetry cadence (0 = off);
                      # emission only, never read by any decision path
GOV_WARMSTART_N = 10  # first N searches use full SEARCH_DET regardless of EMA
GOV_HYST_M = 3        # force re-engagement after M consecutive EMA-caused skips
_GOV = {"n_dec": 0, "spent": 0.0, "max_dec": 0.0, "sticky": False,
        "ema_det": 0.05, "ring": [], "games": 0, "hooked": False,
        "searches_run": 0, "sum_dets": 0,
        "cons_ema_skip": 0, "max_cons_ema_skip": 0,
        "max_ema": 0.05,
        "warmstart_forced": 0, "hyst_forced": 0}


def _gov_emit(tag="gov"):
    """Print the telemetry line WITHOUT resetting counters.

    Instrumentation only — no decision logic reads this. Split out from
    _gov_flush so an in-flight snapshot can be emitted periodically: the
    Kaggle platform terminates the agent process without running atexit
    handlers, so the atexit flush never fired on ladder and 28 games produced
    zero search telemetry. The new-game flush at the _search_decide call site
    still handles game boundaries; this covers the final game and teardown."""
    if _GOV["n_dec"] == 0:
        return
    worst = sorted(_GOV["ring"], key=lambda r: -r[2])[:3]
    ema = _GOV["ema_det"]
    sr = _GOV["searches_run"]
    avg_dets = (_GOV["sum_dets"] / sr) if sr else 0.0
    print("[" + tag + "] game=%d decisions=%d spent=%.1fs max=%.2fs ema=%s max_ema=%.3f "
          "searches=%d avg_dets=%.2f warmN=%d hystM=%d max_cons_skip=%d sticky=%s "
          "end_veto=%d atk_legal=%d atk_in=%d cand_forced=%d cand_atk_w=%d changed=%d "
          "worst(turn,budget,spent,det)=%s"
          % (_GOV["games"], _GOV["n_dec"], _GOV["spent"], _GOV["max_dec"],
             ("%.3f" % ema) if ema is not None else "None", _GOV["max_ema"],
             sr, avg_dets, _GOV["warmstart_forced"], _GOV["hyst_forced"],
             _GOV["max_cons_ema_skip"], _GOV["sticky"],
             STATS.get("end_veto", 0), STATS.get("atk_legal", 0),
             STATS.get("atk_in_cands", 0), STATS.get("cand_forced", 0),
             STATS.get("cand_atk_w", 0), STATS.get("search_changed", 0),
             [(t, round(b, 2) if b is not None else None,
               round(s, 2), d) for t, b, s, d in worst]),
          file=sys.stderr, flush=True)


def _gov_flush():
    """Emit the game line and reset per-game counters (new-game boundary)."""
    if _GOV["n_dec"] == 0:
        return
    _gov_emit("gov")
    _GOV.update({"n_dec": 0, "spent": 0.0, "max_dec": 0.0, "sticky": False,
                 "ring": [], "games": _GOV["games"] + 1})


def _gov_budget(obs):
    """Per-decision time budget in seconds, None = unlimited (governor off)."""
    if not GOVERNOR:
        return None
    remaining = obs.get("remainingOverageTime")
    if not isinstance(remaining, (int, float)):
        remaining = 600.0
    turn = (obs.get("current") or {}).get("turn") or 0
    dpt = (_GOV["n_dec"] / max(1.0, float(turn))) if turn else 4.0
    est = max(8.0, dpt * max(GOV_P90_TURNS - turn, 2.0))
    return max(0.0, min(GOV_CAP_S, 0.5 * float(remaining) / est))


def _gov_det(budget):
    """Degradation curve: full det -> /2 -> /4 -> 0 (skip search)."""
    if budget is None:
        return SEARCH_DET
    per_det = _GOV["ema_det"] or 0.015
    for div in (1, 2, 4):
        d = max(1, SEARCH_DET // div)
        if per_det * d <= budget:
            return d
    return 0


def _gov_note(turn, budget, spent, dets):
    _GOV["n_dec"] += 1
    _GOV["spent"] += spent
    _GOV["max_dec"] = max(_GOV["max_dec"], spent)
    if dets:
        per = min(spent / dets, 0.2)  # cap: bounds EMA ≤ 0.2 by construction (seed 0.05)
        _GOV["ema_det"] = per if _GOV["ema_det"] is None \
            else 0.7 * _GOV["ema_det"] + 0.3 * per
        if _GOV["ema_det"] > _GOV["max_ema"]:
            _GOV["max_ema"] = _GOV["ema_det"]
        _GOV["searches_run"] += 1
        _GOV["sum_dets"] += dets
        _GOV["cons_ema_skip"] = 0
    _GOV["ring"].append((turn, budget, spent, dets))
    if len(_GOV["ring"]) > 64:
        _GOV["ring"].pop(0)
    # In-flight snapshot: atexit does not run on the Kaggle platform, so
    # without this the final game of every episode emits no telemetry at all
    # (28 ladder games produced none). Print-only; resets nothing; no decision
    # path reads it.
    if GOV_EMIT_EVERY > 0 and _GOV["n_dec"] % GOV_EMIT_EVERY == 0:
        _gov_emit("gov-snap")


# ------------------------------------------------------------------ search ----

_TRACKERS = {}
_SEARCH_RNG = random.Random(SEARCH_SEED)


def _find_lethal(obs, sel, cur, scores, me, tr, deadline):
    """Gate B: engine-exact lethal probe. For each ATTACK option (top-N by
    v1 score), sample K determinizations and probe via search_step; if ALL K
    show cur.result == me, this attack is confirmed lethal.

    Returns the winning option index or None. Never raises — every failure
    path degrades to None (caller uses normal search)."""
    if not obs.get("search_begin_input"):
        return None
    options = sel.get("option") or []
    # Rank ATTACK options by v1 score, take top-N to probe first
    attack_idxs = [i for i, o in enumerate(options)
                   if (o or {}).get("type") == OT_ATTACK]
    if not attack_idxs:
        return None
    attack_idxs.sort(key=lambda i: -scores[i])
    attack_idxs = attack_idxs[:LETHAL_PROBE_MAX_ATTACKS]

    t_start = time.perf_counter()
    K = LETHAL_PROBE_K
    for idx in attack_idxs:
        wins = 0
        checked = 0
        for _ in range(K):
            if time.perf_counter() - t_start > deadline:
                return None
            det = None
            try:
                det = _sample_determinization(obs, tr, _SEARCH_RNG)
            except Exception:
                pass
            if det is None:
                # sampling failed — treat as inconclusive; try next det
                continue
            try:
                root = _sb_begin(obs["search_begin_input"], **det)
                node = _sb_step(root["searchId"], [idx])
                res = ((node.get("observation") or {}).get("current") or {}).get("result", -1)
                if res == me:
                    wins += 1
                checked += 1
            except Exception:
                pass
            finally:
                _sb_end()
        if checked == K and wins == K:
            return idx
    return None


def _searchable(obs, sel, cur):
    return (isinstance(sel, dict) and isinstance(cur, dict)
            and obs.get("search_begin_input")
            and cur.get("result", -1) == -1
            and sel.get("type") == ST_MAIN
            and sel.get("minCount", 1) == 1 and sel.get("maxCount", 1) == 1
            and len(sel.get("option") or []) > 1)


def _end_veto(result, sel, cur, scores):
    """Replace a chosen END with a development action, per END_VETO mode.

    Returns `result` unchanged on every path that is not a clean, in-range,
    single-index END on a MAIN selection with a qualifying replacement, so the
    agent can never be left without a legal action. `_validate_result` and the
    fallback chain still run downstream and are untouched."""
    if not END_VETO or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    if (options[ci] or {}).get("type") != OT_END:
        return result
    if not isinstance(scores, (list, tuple)) or len(scores) != len(options):
        return result

    me = cur.get("yourIndex") or 0
    mine = _my(cur, me)
    dev_types = (OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY)

    if END_VETO == "broad":
        pool = [i for i, o in enumerate(options)
                if (o or {}).get("type") in dev_types]
    else:                                    # "narrow" (default non-empty mode)
        # bench must have room -- capacity is benchMax, NOT len(bench).
        # Sanjay shipped this rule silently dead by using len(bench), which
        # reads a 1/5 bench as "full" (his §6l). Use benchMax.
        bench = [b for b in (mine.get("bench") or []) if b]
        bmax = mine.get("benchMax")
        if not isinstance(bmax, int) or bmax <= 0:
            return result                    # unknown capacity -> abstain
        if len(bench) >= bmax:
            return result
        hand = mine.get("hand") or []
        pool = []
        for i, o in enumerate(options):
            if (o or {}).get("type") != OT_PLAY:
                continue
            ix = (o or {}).get("index")
            if isinstance(ix, int) and 0 <= ix < len(hand) and hand[ix]:
                nm = (_card((hand[ix] or {}).get("id")).get("name") or "").lower()
                if nm in BASIC_SEARCHERS:
                    pool.append(i)           # replacement IS the searcher
    if not pool:
        return result
    best = max(pool, key=lambda i: (scores[i], -i))
    STATS["end_veto"] = STATS.get("end_veto", 0) + 1
    return [best]


def _has_free_draw_ability(cid):
    """True iff card `cid` has an Ability whose text is a once-per-turn free
    'draw N cards' effect from the Active Spot -- Mega Kangaskhan's *Run
    Errand* is the case this was mined for. Cached; skills text is static per
    cid. Deliberately narrow: matches 'draw' + a small integer, requires the
    once-per-turn/active-spot phrasing, and excludes 'discard' side effects
    (so it won't fire on cards like Cinderace's Turbo Flare, which was the
    ARCHALUDON_TEST negative-transfer bug shape)."""
    hit = _KE1_ABILITY_CACHE.get(cid)
    if hit is not None:
        return hit
    hit = False
    for sk in (_card(cid).get("skills") or []):
        t = (sk.get("text") or "").lower()
        if "discard" in t:
            continue
        if "once during your turn" not in t or "active spot" not in t:
            continue
        # look for "draw N cards" with N in 1-5 (Run Errand is "draw 2 cards")
        for n in ("1", "2", "3", "4", "5"):
            if f"draw {n} card" in t:
                hit = True
                break
        if hit:
            break
    _KE1_ABILITY_CACHE[cid] = hit
    return hit


def _ke1_veto(result, sel, cur):
    """KE1: if v1's chosen action is a terminal ATTACK/RETREAT/END on a MAIN
    decision, and the active carries an unused free-draw Ability that the
    engine is currently offering us as an OT_ABILITY on the menu, swap the
    chosen index to that Ability. Strictly dominated: taking a free draw
    before ending the tempo of the turn cannot be worse than not taking it,
    and mining says top-10 pilots do this 24% of the time in the exact
    can_KO state where we do it 0%. Abstain paths return `result` unchanged
    -- `_validate_result` and the fallback chain are untouched."""
    if not KE1_FREE_DRAW or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    chosen_type = (options[ci] or {}).get("type")
    if chosen_type not in (OT_ATTACK, OT_RETREAT, OT_END):
        return result
    me = cur.get("yourIndex") or 0
    mine = _my(cur, me)
    active = (mine.get("active") or [None])[0]
    if not active:
        return result
    active_id = active.get("id")
    if not _has_free_draw_ability(active_id):
        return result
    # find an OT_ABILITY option on the menu targeting THIS active
    active_serial = active.get("serial")
    for i, o in enumerate(options):
        if (o or {}).get("type") != OT_ABILITY:
            continue
        opt_serial = (o or {}).get("serial")
        # engine either indexes the ability by option's card ref (serial) or
        # by position -- accept either if it plausibly points at our active
        if opt_serial is None or opt_serial == active_serial:
            STATS["ke1_veto"] = STATS.get("ke1_veto", 0) + 1
            return [i]
    return result


def _has_free_attach_ability(cid):
    """True iff card `cid` has an Ability that attaches a Basic energy from
    hand for free (once per turn, no discard). Teal Mask Ogerpon ex's *Teal
    Dance* is the case this was mined for. Unlike KE1's helper, does NOT
    require active-spot (Teal Dance fires from bench too). Excludes hybrid
    effects via the same "no discard" filter."""
    hit = _KE3_ABILITY_CACHE.get(cid)
    if hit is not None:
        return hit
    hit = False
    for sk in (_card(cid).get("skills") or []):
        t = (sk.get("text") or "").lower()
        if "discard" in t:
            continue
        if "once during your turn" not in t:
            continue
        # "attach a basic ... energy card from your hand to this pokemon"
        if "attach" in t and "basic" in t and "energy" in t and "hand" in t \
                and "this pok" in t:
            hit = True
            break
    _KE3_ABILITY_CACHE[cid] = hit
    return hit


def _ke3_veto(result, sel, cur):
    """KE3: if v1's chosen action is terminal (ATTACK/RETREAT/END) or ATTACH,
    and any of our Pokemon (active OR bench) carries an unused free-attach
    Ability that the engine is offering as OT_ABILITY on the menu, swap to
    that Ability. Same strict-dominance argument as KE1: Teal Dance is a
    separate action from the per-turn manual attach, so taking it does not
    consume the normal attach slot; it also draws a card as a rider. Never
    fires on ATTACH toward the same target (no useful sequencing there) --
    that's why the trigger set is {ATTACK, RETREAT, END, ATTACH}."""
    if not KE3_TEAL_DANCE or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    # Narrowed trigger: {ATTACK, RETREAT, END} only. Initial version also
    # included OT_ATTACH, and the KE13 screen (KE1+KE3 combined) crashed win
    # rate to 31.2% vs baseline 32.3% -- the ATTACH trigger reproduces the
    # exact regression seen in KE12 (KE1+KE2). Removing OT_ATTACH from the
    # trigger set aligns KE3's shape with KE1 so the two rules address
    # disjoint decision types (KE1: Mega Kang free-draw; KE3: Ogerpon free-
    # energy-attach), no overlap.
    if (options[ci] or {}).get("type") not in (OT_ATTACK, OT_RETREAT, OT_END):
        return result
    me = cur.get("yourIndex") or 0
    mine = _my(cur, me)
    # any Pokemon on our board (active or bench) with the free-attach ability
    free_serials = set()
    for pk in ((mine.get("active") or []) + (mine.get("bench") or [])):
        if not pk:
            continue
        if _has_free_attach_ability(pk.get("id")):
            ser = pk.get("serial")
            if ser is not None:
                free_serials.add(ser)
    if not free_serials:
        return result
    for i, o in enumerate(options):
        if (o or {}).get("type") != OT_ABILITY:
            continue
        opt_serial = (o or {}).get("serial")
        if opt_serial in free_serials or opt_serial is None:
            STATS["ke3_veto"] = STATS.get("ke3_veto", 0) + 1
            return [i]
    return result


def _ke2_veto(result, sel, cur):
    """KE2: if v1's chosen action is ATTACH energy AND the supporter for this
    turn has NOT been played AND the engine is offering us an OT_ABILITY on
    a Pokemon whose skill matches our free-draw pattern (from
    `_has_free_draw_ability`), swap the chosen index to that Ability. Same
    strict-dominance argument as KE1: a once-per-turn free draw does not
    prevent us from attaching this turn (both are non-terminal actions and
    the MAIN menu re-presents after each), so taking the draw first only
    adds information for the attach decision that follows. Abstains on every
    non-qualifying path -- `_validate_result` untouched."""
    if not KE2_ABIL_BEFORE_ATTACH or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    if (options[ci] or {}).get("type") != OT_ATTACH:
        return result
    if cur.get("supporterPlayed"):
        return result
    me = cur.get("yourIndex") or 0
    mine = _my(cur, me)
    # Build a map: serial -> True if this Pokemon carries a free-draw ability.
    # Include active + bench (bench abilities like Munkidori/Fezandipiti are
    # filtered out by _has_free_draw_ability -- only draw-N-cards matches).
    free_serials = set()
    for pk in ((mine.get("active") or []) + (mine.get("bench") or [])):
        if not pk:
            continue
        if _has_free_draw_ability(pk.get("id")):
            ser = pk.get("serial")
            if ser is not None:
                free_serials.add(ser)
    if not free_serials:
        return result
    for i, o in enumerate(options):
        if (o or {}).get("type") != OT_ABILITY:
            continue
        opt_serial = (o or {}).get("serial")
        if opt_serial in free_serials or opt_serial is None:
            STATS["ke2_veto"] = STATS.get("ke2_veto", 0) + 1
            return [i]
    return result


def _playable_supporter_index(options, cur, me):
    """Return the option index of the first OT_PLAY whose hand card has
    cardType == CT_SUPPORTER (3), else None. Engine gates OT_PLAY for
    Supporters when supporterPlayed=True, so presence implies playability."""
    for i, o in enumerate(options):
        if (o or {}).get("type") != OT_PLAY:
            continue
        cid = _hand_card_id(cur, me, (o or {}).get("index"))
        if cid is None:
            continue
        if _card(cid).get("cardType") == CT_SUPPORTER:
            return i
    return None


def _ke_sup_veto(result, sel, cur):
    """KE_SUP: if v1's chosen action is OT_ATTACK on a MAIN decision, and
    the Supporter for this turn has not been played, and the menu offers
    an OT_PLAY on a Supporter-type hand card, swap the chosen index to that
    supporter play. Mined from `atk_legal & supporter_pending` cell (top-10
    ATTACK 15.9% vs us 34.7%, us over-attack +18.8pt). Targets the once-per-
    turn Supporter slot — disjoint from KE1/KE2/KE3's OT_ABILITY slot, so
    composes with them by construction. Trigger is OT_ATTACK only (not
    RETREAT/END) — matches the mined cell exactly. Abstain paths return
    `result` unchanged; `_validate_result` and fallback chain untouched."""
    if not KE_SUP_ATK_BEFORE_SUPPORTER or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    if (options[ci] or {}).get("type") != OT_ATTACK:
        return result
    if cur.get("supporterPlayed"):
        return result
    me = cur.get("yourIndex") or 0
    sup_idx = _playable_supporter_index(options, cur, me)
    if sup_idx is None:
        return result
    STATS["ke_sup_veto"] = STATS.get("ke_sup_veto", 0) + 1
    return [sup_idx]


def _count_basic_energies_on(pk):
    """Count basic-energy attachments on a Pokemon slot. Returns 0 for None
    or empty."""
    if not pk:
        return 0
    n = 0
    for e in pk.get("energies") or []:
        cid = (e or {}).get("id") if isinstance(e, dict) else e
        if _card(cid).get("cardType") == CT_BASIC_ENERGY:
            n += 1
    return n


def _ke_bolt_main_veto(result, sel, cur):
    """KE_BOLT hook 1 (opportunistic-damage shape, v2): on a MAIN decision,
    if v1 picked Burst Roar (attackId=71 — 0-cost draw-6, 0 damage) but
    Bellowing Thunder (attackId=72) is on the same menu AND our active
    Raging Bolt (id=63) has at least 1 basic-energy surplus beyond the
    1L+1F cost, swap to Bellowing. Rationale: 70+ damage strictly beats
    0 damage; the mining data (top-10 uses Bellowing 35 times, mean discard
    = 3 basics = 210 dmg) shows opportunistic damage is the correct policy,
    not lethal-only. Only fires when chosen was Burst — leaves other
    non-Burst picks alone (e.g., a search-and-develop PLAY is not our call
    to override)."""
    if not KE_BOLT_ENGAGE or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    chosen = options[ci] or {}
    if chosen.get("type") != OT_ATTACK:
        return result
    if chosen.get("attackId") != 71:   # only swap Burst Roar
        return result
    me = cur.get("yourIndex") or 0
    mine = _my(cur, me)
    active = (mine.get("active") or [None])[0]
    if not active or active.get("id") != KE_BOLT_SOURCE_ID:
        return result
    basics_extra = _count_basic_energies_on(active) - KE_BOLT_COST
    if basics_extra < 1:
        return result
    for i, o in enumerate(options):
        if (o or {}).get("type") != OT_ATTACK:
            continue
        if (o or {}).get("attackId") != KE_BOLT_ATTACK_ID:
            continue
        STATS["ke_bolt_main"] = STATS.get("ke_bolt_main", 0) + 1
        return [i]
    return result


def _ke_bolt_discard_policy(result, sel, cur):
    """KE_BOLT hook 2: on ST_ATTACHED_CARD with context=26 (Bellowing
    Thunder discard) and Raging Bolt as the source, discard K basics where
    K = ceil(opp_hp / 70) if we can KO, else discard 2 (top-10 median from
    mining harvest of 35 uses). Both capped at (available options,
    maxCount). Default v1 on this select scores 0.0 and picks 0 items
    (`main.py:1803`), delivering 0 damage — this policy fixes that.

    First 2 option indices are used (options are typically basic energies
    in attach order; the sub-select is a "pick which cards to discard"
    over a fixed set, so index 0..K-1 discards the first K)."""
    if not KE_BOLT_ENGAGE or not isinstance(sel, dict) or sel.get("type") != ST_ATTACHED_CARD:
        return result
    if sel.get("context") != KE_BOLT_CONTEXT:
        return result
    eff = sel.get("effect") or {}
    if eff.get("id") != KE_BOLT_SOURCE_ID:
        return result
    options = sel.get("option") or []
    if not options:
        return result
    me = cur.get("yourIndex") or 0
    opp_active = (_opp(cur, me).get("active") or [None])[0]
    opp_hp = (opp_active or {}).get("hp") or 0
    max_count = sel.get("maxCount") if sel.get("maxCount") is not None else len(options)
    if opp_hp > 0:
        need = (opp_hp + KE_BOLT_DMG_PER - 1) // KE_BOLT_DMG_PER
    else:
        need = 2
    if opp_hp > 0 and need <= len(options) and need <= max_count:
        k = need                       # can KO — pick exact
    else:
        k = min(2, len(options), max_count)   # can't KO — top-10 median
    if k <= 0:
        return result
    STATS["ke_bolt_discard"] = STATS.get("ke_bolt_discard", 0) + 1
    return list(range(k))


def _has_positive_ability(cid):
    """True iff `cid` has a strictly-positive OT_ABILITY: free draw or
    damage-counter move, without destructive side effects. Rejects
    "shuffle this pokemon back" (Dudunsparce), "put this pokemon into
    hand" (Meowth ex Last-Ditch Catch), and any text with "discard"
    (which catches hybrid attack+draw effects like Cinderace's Turbo
    Flare that broke E1 on Archaludon). Cached; skills text is static.
    Broader than `_has_free_draw_ability` (does not require active spot,
    so it matches Fez's Flip the Script and Munkidori's Adrena-Brain
    which fire from bench)."""
    hit = _POSITIVE_ABIL_CACHE.get(cid)
    if hit is not None:
        return hit
    hit = False
    for sk in (_card(cid).get("skills") or []):
        t = (sk.get("text") or "").lower()
        if "discard" in t:
            continue
        if "shuffle this pok" in t or "put this pok" in t:
            continue
        if "once during your turn" not in t:
            continue
        # Free draw (any card count)
        if any(f"draw {n} card" in t for n in ("1", "2", "3", "4", "5")):
            hit = True
            break
        if "draw a card" in t:
            hit = True
            break
        # Damage counter move (Munkidori)
        if "damage counter" in t and "move" in t:
            hit = True
            break
    _POSITIVE_ABIL_CACHE[cid] = hit
    return hit


def _count_all_energies_on(pk):
    """Total energy attachments (any type) on a Pokemon slot."""
    if not pk:
        return 0
    return len(pk.get("energies") or [])


def _find_pokemon_by_id(cur, me, pk_id):
    """Locate a Pokemon by card id on our side. Returns the slot dict, or None."""
    mine = _my(cur, me)
    a = (mine.get("active") or [None])[0]
    if a and a.get("id") == pk_id:
        return a
    for b in mine.get("bench") or []:
        if b and b.get("id") == pk_id:
            return b
    return None


def _attach_target_id(opt, cur, me):
    """Return card id of the Pokemon this OT_ATTACH option targets, or None."""
    area, index = opt.get("inPlayArea"), opt.get("inPlayIndex")
    if area is None:
        area, index = opt.get("area"), opt.get("index")
    mine = _my(cur, me)
    if area == AREA_ACTIVE:
        a = (mine.get("active") or [None])[0]
        return (a or {}).get("id")
    if area == AREA_BENCH:
        try:
            b = (mine.get("bench") or [])[int(index or 0)]
            return (b or {}).get("id")
        except (IndexError, ValueError, TypeError):
            return None
    return None


def _ke_well_attach_veto(result, sel, cur):
    """KE_WELL: if v1 chose OT_ATTACH to Mega Kangaskhan AND Wellspring
    Ogerpon is on our field with < KE_WELL_CAP energies AND an OT_ATTACH
    to Wellspring is offered, swap to the Wellspring attach. Diversifies
    energy from over-fed Kang to starved Wellspring so Torrential Pump
    (100 + 120-bench) becomes legal within a few turns."""
    if not KE_WELL_ATTACH_PRIORITY or not isinstance(sel, dict) or sel.get("type") != ST_MAIN:
        return result
    if not (isinstance(result, list) and len(result) == 1):
        return result
    options = sel.get("option") or []
    ci = result[0]
    if not isinstance(ci, int) or not (0 <= ci < len(options)):
        return result
    chosen = options[ci] or {}
    if chosen.get("type") != OT_ATTACH:
        return result
    me = cur.get("yourIndex") or 0
    if _attach_target_id(chosen, cur, me) != KE_WELL_KANG_ID:
        return result
    well = _find_pokemon_by_id(cur, me, KE_WELL_WELL_ID)
    if not well:
        return result
    if _count_all_energies_on(well) >= KE_WELL_CAP:
        return result
    for i, o in enumerate(options):
        if (o or {}).get("type") != OT_ATTACH:
            continue
        if _attach_target_id(o, cur, me) == KE_WELL_WELL_ID:
            STATS["ke_well_veto"] = STATS.get("ke_well_veto", 0) + 1
            return [i]
    return result


def _seq_gate(result, sel, cur, scores):
    """Ordering gates E1-E4 + G_ABIL_BROAD. Returns `result` unchanged on
    every path that does not qualify. Option-set override only; no score
    is modified."""
    if not (SEQ_E1 or SEQ_E2 or SEQ_E3 or G_ABIL_BROAD):
        return result
    if sel.get("type") != ST_MAIN or len(result) != 1:
        return result
    options = sel.get("option") or []
    i = result[0]
    if not isinstance(i, int) or i >= len(options):
        return result
    chosen = options[i] or {}
    ct = chosen.get("type")
    me = cur.get("yourIndex") or 0
    mine = _my(cur, me)
    opp = _opp(cur, me)
    turn = cur.get("turn") or 0

    # per-own-turn veto budget; reset whenever the turn number changes
    if _SEQ["turn"] != turn:
        if _SEQ["turn"] is not None:
            _SEQ["turns"] += 1
            if _SEQ["vetoes"] >= E1_MAX_VETO:
                _SEQ["ceiling_turns"] += 1
        _SEQ["turn"] = turn
        _SEQ["vetoes"] = 0

    def best_of(types):
        pool = [k for k, o in enumerate(options) if (o or {}).get("type") in types]
        return max(pool, key=lambda k: (scores[k], -k)) if pool else None

    my_act = (mine.get("active") or [None])[0]
    op_act = (opp.get("active") or [None])[0]

    # ---- E3: do not retreat while nothing threatens the active ----
    if SEQ_E3 and ct == OT_RETREAT:
        threat = _best_attack_info((op_act or {}).get("id"))[0] if op_act else 0.0
        hp = (my_act or {}).get("hp")
        if my_act and hp is not None and hp > 0 and threat < hp:
            alt = best_of(tuple(t for t in
                                (OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY, OT_ATTACK)
                                if True))
            if alt is not None:
                STATS["e3_veto"] = STATS.get("e3_veto", 0) + 1
                return [alt]
        return result

    if ct != OT_ATTACK:
        # ---- G_ABIL_BROAD: fire a POSITIVE-ability OT_ABILITY before any
        # non-OT_ATTACK, non-OT_ABILITY chosen action. Scoped via
        # `_has_positive_ability` (draw or damage-counter move, no
        # destructive side effects). Rejects Meowth ex's Last-Ditch Catch
        # ("put this pokemon into hand"), Dudunsparce's shuffle-back, and
        # anything with "discard" in text. Respects E1_MAX_VETO budget.
        if G_ABIL_BROAD and ct != OT_ABILITY and _SEQ["vetoes"] < E1_MAX_VETO:
            board_serials = set()
            for pk in ((mine.get("active") or []) + (mine.get("bench") or [])):
                if pk and _has_positive_ability(pk.get("id")):
                    ser = pk.get("serial")
                    if ser is not None:
                        board_serials.add(ser)
            if board_serials:
                # find highest-scored OT_ABILITY option whose serial matches
                best_i, best_s = None, None
                for k, o in enumerate(options):
                    if (o or {}).get("type") != OT_ABILITY:
                        continue
                    ser = (o or {}).get("serial")
                    if ser is not None and ser not in board_serials:
                        continue   # ability on a non-positive pokemon
                    if best_i is None or scores[k] > best_s:
                        best_i, best_s = k, scores[k]
                if best_i is not None:
                    _SEQ["vetoes"] += 1
                    STATS["g_abil_broad_veto"] = STATS.get("g_abil_broad_veto", 0) + 1
                    return [best_i]
        return result

    # ---- E1b / E1c: stated exceptions, both default off ----
    if SEQ_E1B_LETHAL and op_act:
        gain = _prizes_for_ko(op_act.get("id"))
        left = len(mine.get("prize") or [])
        if 0 < left <= gain:
            return result
    if SEQ_E1C_DOOMED and my_act and op_act:
        threat = _best_attack_info(op_act.get("id"))[0]
        hp = my_act.get("hp")
        if hp is not None and threat >= hp > 0:
            return result

    # ---- E4: when BEHIND on the prize race, push damage (disable E1) ----
    behind = len(mine.get("prize") or []) > len(opp.get("prize") or [])
    if _SEQ["vetoes"] >= E1_MAX_VETO:
        return result

    # ---- E2: abilities are free and self-clearing; fire them first ----
    if SEQ_E2:
        alt = best_of((OT_ABILITY,))
        if alt is not None:
            _SEQ["vetoes"] += 1
            STATS["e2_veto"] = STATS.get("e2_veto", 0) + 1
            return [alt]
    # ---- E1: board-advancing card plays before the terminal action ----
    if SEQ_E1 and not (SEQ_E4 and behind):
        alt = best_of(DEVELOP_TYPES)
        if alt is not None:
            _SEQ["vetoes"] += 1
            STATS["e1_veto"] = STATS.get("e1_veto", 0) + 1
            return [alt]
    return result


def _search_decide(obs, sel, cur, v1_result, scores, t0):
    """Belief-sampled flat determinized MC over the top-k options by v1 score.
    Returns v1_result untouched on any degradation. The caller wraps this in
    try/except, so even a bug here cannot break the v1 answer."""
    me = cur.get("yourIndex") or 0
    tr = _TRACKERS.get(me)
    if tr is None:
        tr = _TRACKERS[me] = CardTracker(me)
    if tr.update(obs):
        _gov_flush()
    if not _GOV["hooked"]:
        _GOV["hooked"] = True
        atexit.register(_gov_flush)

    if _GOV["sticky"] or not _searchable(obs, sel, cur) or _search_lib() is None:
        _gov_note((cur.get("turn") or 0), None, time.perf_counter() - t0, 0)
        return v1_result

    # Gate B: engine-exact lethal probe. Fast-path before budget-gated dets.
    # If a confirmed lethal is found, take it immediately (Sanjay §1 item 3).
    # Failure paths (probe raises, no lethal, timeout) all return None → fall
    # through to normal search. Doesn't touch governor telemetry to keep the
    # gate signal isolated.
    if LETHAL_PROBE:
        try:
            lethal_idx = _find_lethal(obs, sel, cur, scores, me, tr,
                                       LETHAL_PROBE_DEADLINE_S)
        except Exception:
            lethal_idx = None
        if lethal_idx is not None:
            STATS["lethal_probe_fired"] = STATS.get("lethal_probe_fired", 0) + 1
            _gov_note((cur.get("turn") or 0), None, time.perf_counter() - t0, 0)
            return [lethal_idx]

    budget = _gov_budget(obs)
    if budget is not None and budget < GOV_STICKY_S:
        _GOV["sticky"] = True
        print("[search] budget %.2fs < %.2fs: heuristic-only for the rest of the game"
              % (budget, GOV_STICKY_S), file=sys.stderr, flush=True)
        _gov_note((cur.get("turn") or 0), budget, time.perf_counter() - t0, 0)
        return v1_result
    # Hysteresis: warm-start floor forces full dets for first N searches;
    # ongoing engagement floor forces re-sample after M consecutive EMA-caused
    # skips. Both are safety-nets on top of the seed+cap fix.
    if _GOV["searches_run"] < GOV_WARMSTART_N:
        dets = SEARCH_DET
        _GOV["warmstart_forced"] += 1
    elif _GOV["cons_ema_skip"] >= GOV_HYST_M:
        dets = max(1, SEARCH_DET // 4)
        _GOV["hyst_forced"] += 1
    else:
        dets = _gov_det(budget)
    options = sel.get("option") or []
    order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
    cands = order[:SEARCH_TOPK]
    # A-INCLUDE: the v1 ladder puts every setup action (2030-3500) above a
    # non-lethal attack (1000 + dmg/2), so with >=SEARCH_TOPK setup options on
    # the menu the attack never enters the candidate set and the search cannot
    # choose it (measured: 0 of 1068 excluded decisions ended in an attack).
    # Appending keeps the attack LAST, so _cands.index() tie-breaking still
    # resolves ties to v1's own top pick -- inclusion only, no reordering, and
    # no v1 weight is touched.
    # Counters are decision-level on purpose: _score_option also runs inside
    # every rollout, so incrementing there would report ~10^5 per game and be
    # useless as ladder telemetry. This block runs once per real decision.
    atks = [i for i, o in enumerate(options) if (o or {}).get("type") == OT_ATTACK]
    if atks:
        ba = max(atks, key=lambda i: (scores[i], -i))
        STATS["atk_legal"] = STATS.get("atk_legal", 0) + 1
        if ba in cands:
            STATS["atk_in_cands"] = STATS.get("atk_in_cands", 0) + 1
        elif CAND_INCLUDE_ATTACK:
            cands = cands + [ba]
            STATS["cand_forced"] = STATS.get("cand_forced", 0) + 1
        if CAND_ATK_W > 0 and CAND_ATK_W <= scores[ba] < WEIGHT_TEMPO_LOADED:
            STATS["cand_atk_w"] = STATS.get("cand_atk_w", 0) + 1
    if dets <= 0 or len(cands) < 2:
        if dets == 0 and len(cands) >= 2:
            _GOV["cons_ema_skip"] += 1
            if _GOV["cons_ema_skip"] > _GOV["max_cons_ema_skip"]:
                _GOV["max_cons_ema_skip"] = _GOV["cons_ema_skip"]
        _gov_note((cur.get("turn") or 0), budget, time.perf_counter() - t0, 0)
        return v1_result

    STATS["searched"] = STATS.get("searched", 0) + 1
    cap = SEARCH_CAP if SEARCH_CAP > 0 else 400
    rolls = max(1, SEARCH_ROLL)
    totals = {i: 0.0 for i in cands}
    n = 0
    fails = 0
    dets_run = 0
    for _d in range(dets):
        if budget is not None and time.perf_counter() - t0 > budget:
            break
        try:
            det = _sample_determinization(obs, tr, _SEARCH_RNG)
        except Exception as e:
            fails += 1
            if fails >= 5:
                print("[search] sampling failed %dx (%r); heuristic for this decision"
                      % (fails, e), file=sys.stderr, flush=True)
                break
            continue
        try:
            root = _sb_begin(obs["search_begin_input"], **det)
            for i in cands:
                for _r in range(rolls):
                    node = _sb_step(root["searchId"], [i])
                    totals[i] += _rollout(node, me, cap)
            n += rolls
            dets_run += 1
        except Exception as e:
            fails += 1
            if fails >= 5:
                print("[search] engine search failed %dx (%r); heuristic for this decision"
                      % (fails, e), file=sys.stderr, flush=True)
                break
        finally:
            _sb_end()
    spent = time.perf_counter() - t0
    _gov_note((cur.get("turn") or 0), budget, spent, dets_run)
    if n == 0:
        return v1_result
    best = max(cands, key=lambda i: (totals[i] / n, -cands.index(i)))
    if [best] != v1_result:
        STATS["search_changed"] = STATS.get("search_changed", 0) + 1
    return [best]


if SEARCH:
    _search_lib()
    _pool()


def _pilot_telemetry(sel, cur, result):
    """Cheap ladder telemetry (Garchomp): on our real MAIN decisions from turn
    4 on, note when we DON'T attack and why — 'SKIP' = an attack was available
    and we chose something else (the tempo failure), 'not-loaded' = no legal
    attack yet (a setup-speed problem). One stderr line, only when not
    attacking, so it stays quiet on healthy turns."""
    if PILOT != "garchomp" or sel.get("type") != ST_MAIN:
        return
    turn = cur.get("turn") or 0
    if turn < 4:
        return
    options = sel.get("option") or []
    chosen_types = {(options[i] or {}).get("type") for i in result}
    if OT_ATTACK in chosen_types:
        return  # we attacked — healthy, stay quiet
    # only log a genuine SKIP: an attack was legal and we chose otherwise. The
    # 'not-loaded' case (no legal attack) is expected setup, not a skip, so we
    # stay quiet there to keep ladder logs cheap.
    if not any((o or {}).get("type") == OT_ATTACK for o in options):
        return
    me = cur.get("yourIndex") or 0
    act = _active_pokemon(_my(cur, me)) or {}
    print("[tempo] turn=%s SKIP attack-available chose=%s active=%s energies=%d supPlayed=%s"
          % (turn, sorted(t for t in chosen_types if t is not None),
             act.get("id"), len(act.get("energies") or []),
             bool(cur.get("supporterPlayed"))),
          file=sys.stderr, flush=True)


def _expectimax_decide(obs, sel, cur, me, options, scores):
    """Pure-Python Prize-Delta Expectimax Engine. Evaluates legal options
    on prize differential and active KO guarantees without any C++ or DLL dependency."""
    if not EXPECTIMAX:
        return
    stype = sel.get("type")
    min_c = sel.get("minCount") or 0
    max_c = sel.get("maxCount")
    max_c = len(options) if max_c is None else max_c

    if stype != ST_MAIN or min_c != 1 or max_c != 1 or len(options) <= 1:
        return

    players = cur.get("players") or [{}, {}]
    mine = players[me] if len(players) > me else {}
    opp = players[1 - me] if len(players) > (1 - me) else {}

    my_prizes = len(mine.get("prize") or [])
    opp_act = (opp.get("active") or [{}])[0] or {}
    opp_hp = opp_act.get("hp") or 0

    # 1. Instant Lethal Veto (100% Win Guarantee)
    for i, opt in enumerate(options):
        if (opt or {}).get("type") == OT_ATTACK:
            dmg = _attack_damage_est((opt or {}).get("attackId"), cur, me)
            if dmg >= opp_hp and opp_hp > 0 and my_prizes <= 1:
                scores[i] += 100000.0
                return

    # 2. KO Prize Delta Scoring
    for i, opt in enumerate(options):
        if (opt or {}).get("type") == OT_ATTACK:
            dmg = _attack_damage_est((opt or {}).get("attackId"), cur, me)
            if dmg >= opp_hp and opp_hp > 0:
                scores[i] += 3000.0


def _decide(obs):
    """Score all options and resolve. Returns (indices, top_score)."""
    sel = obs["select"]
    cur = obs.get("current") or {}
    me = cur.get("yourIndex") or 0
    options = sel.get("option") or []
    min_c = sel.get("minCount") or 0
    max_c = sel.get("maxCount")
    max_c = len(options) if max_c is None else max_c
    scores = [_score_option(o or {}, sel, cur, me) for o in options]
    try:
        _expectimax_decide(obs, sel, cur, me, options, scores)
    except Exception:
        pass
    chosen = resolve_selection(options, scores, min_c, max_c)
    top = max((scores[i] for i in chosen), default=None)
    return chosen, top, scores



def agent(obs):
    """Entry point (must be the last callable in this file)."""
    t0 = time.perf_counter()
    STATS["calls"] += 1
    sel = None
    turn = None
    fallback = False
    top = None
    chosen_types = []
    try:
        sel = obs["select"] if "select" in obs else obs.get("select")
        cur = obs.get("current") or {}
        turn = cur.get("turn")
        if sel is None:
            result = list(DECK)
            info = {"phase": "deck", "n_options": 60, "chosen": None}
        else:
            result, top, _scores = _decide(obs)
            bc_handled = False
            if Q_POLICY:
                try:
                    global _Q_POLICY_EVAL
                    if _Q_POLICY_EVAL is None:
                        from bot.q_policy import QPolicyEvaluator
                        _Q_POLICY_EVAL = QPolicyEvaluator()
                    me = cur.get("yourIndex") or 0
                    tr = _TRACKERS.get(me)
                    if tr is None:
                        tr = CardTracker(me)
                        _TRACKERS[me] = tr
                    tr.update(obs)
                    q_res = _Q_POLICY_EVAL.evaluate_decision(
                        obs, sel, cur, me, tracker=tr,
                        search_depth=Q_DEPTH,
                        n_determinizations=Q_DETS
                    )
                    if q_res is not None:
                        result = q_res
                        bc_handled = True
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[q_policy] hook error (%r); fallback kept" % e,
                              file=sys.stderr, flush=True)
            elif BS_CEI:
                try:
                    global _BS_CEI_EVAL
                    if _BS_CEI_EVAL is None:
                        from bot.counterfactual_v15 import CounterfactualEvaluatorV15
                        _BS_CEI_EVAL = CounterfactualEvaluatorV15()
                    me = cur.get("yourIndex") or 0
                    tr = _TRACKERS.get(me)
                    if tr is None:
                        tr = CardTracker(me)
                        _TRACKERS[me] = tr
                    tr.update(obs)
                    bs_res = _BS_CEI_EVAL.evaluate_actions(
                        obs, sel, cur, me, tracker=tr,
                        use_2ply=BS_CEI_2PLY,
                        use_3ply=BS_CEI_3PLY,
                        use_probabilistic_opponent=BS_CEI_PROB_OPP,
                        n_determinizations=BS_CEI_DETS
                    )
                    if bs_res is not None:
                        result = bs_res
                        bc_handled = True
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[bs_cei] hook error (%r); fallback kept" % e,
                              file=sys.stderr, flush=True)
            if BC and not bc_handled:
                try:
                    result, bc_handled = _bc_decide(obs, sel, cur, result)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[bc] hook error (%r); v1 answer kept" % e,
                              file=sys.stderr, flush=True)
            if SEARCH and not bc_handled:
                try:
                    result = _search_decide(obs, sel, cur, result, _scores, t0)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[search] hook error (%r); v1 answer kept" % e,
                              file=sys.stderr, flush=True)
            if END_VETO:
                try:
                    result = _end_veto(result, sel, cur, _scores)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[endveto] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if KE1_FREE_DRAW:
                try:
                    result = _ke1_veto(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke1] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if KE2_ABIL_BEFORE_ATTACH:
                try:
                    result = _ke2_veto(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke2] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if KE3_TEAL_DANCE:
                try:
                    result = _ke3_veto(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke3] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if KE_SUP_ATK_BEFORE_SUPPORTER:
                try:
                    result = _ke_sup_veto(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke_sup] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if KE_BOLT_ENGAGE:
                try:
                    result = _ke_bolt_main_veto(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke_bolt_main] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
                try:
                    result = _ke_bolt_discard_policy(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke_bolt_discard] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if KE_WELL_ATTACH_PRIORITY:
                try:
                    result = _ke_well_attach_veto(result, sel, cur)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[ke_well] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            if SEQ_E1 or SEQ_E2 or SEQ_E3:
                try:
                    result = _seq_gate(result, sel, cur, _scores)
                except Exception as e:
                    _SES["errs"] += 1
                    if _SES["errs"] <= 3:
                        print("[seq] hook error (%r); prior answer kept" % e,
                              file=sys.stderr, flush=True)
            result, was_clean = _validate_result(result, sel)
            if not was_clean:
                fallback = True
                STATS["fallbacks"] += 1
                _log_fallback("post-scoring validation fixed the result", turn, sel)
            if PILOT:
                try:
                    _pilot_telemetry(sel, cur, result)
                except Exception:
                    pass
            options = sel.get("option") or []
            chosen_types = [(options[i] or {}).get("type") for i in result]
            info = {"phase": "move", "n_options": len(options), "chosen": result}
    except Exception:
        import traceback
        fallback = True
        STATS["fallbacks"] += 1
        print("[agent %s] EXCEPTION turn=%s\n%s" % (AGENT_VERSION, turn, traceback.format_exc()),
              file=sys.stderr, flush=True)
        _log_fallback("exception", turn, sel if isinstance(sel, dict) else None)
        result = _legal_fallback(sel) if isinstance(sel, dict) else list(DECK)
        info = {"phase": "error", "n_options": None, "chosen": result}

    ms = (time.perf_counter() - t0) * 1000.0
    STATS["total_ms"] += ms
    STATS["max_ms"] = max(STATS["max_ms"], ms)
    if ms > 1000.0:
        print("[agent %s] SLOW decision turn=%s took %.0f ms" % (AGENT_VERSION, turn, ms),
              file=sys.stderr, flush=True)
    try:
        cur = obs.get("current") or {}
        players = cur.get("players") or [{}, {}]
        me = cur.get("yourIndex") or 0
        LAST_INFO.clear()
        LAST_INFO.update({
            "version": AGENT_VERSION,
            "turn": turn,
            "phase": info["phase"],
            "select_type": sel.get("type") if isinstance(sel, dict) else None,
            "context": sel.get("context") if isinstance(sel, dict) else None,
            "min": sel.get("minCount") if isinstance(sel, dict) else None,
            "max": sel.get("maxCount") if isinstance(sel, dict) else None,
            "n_options": info["n_options"],
            "chosen": info["chosen"],
            "chosen_types": chosen_types,
            "top_score": top,
            "ms": round(ms, 3),
            "fallback": fallback,
            "my_index": me,
            "my_prize": len((players[me] or {}).get("prize") or []) if len(players) > me else None,
            "opp_prize": len((players[1 - me] or {}).get("prize") or []) if len(players) > 1 - me else None,
        })
    except Exception:
        pass
    return result
