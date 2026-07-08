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

import json
import math
import os
import sys
import time

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


def _attack_damage_est(attack_id, cur, me):
    """Damage estimate for an attack; dynamic for known variable attacks."""
    atk = ATTACKS.get(attack_id) or {}
    dmg = float(atk.get("damage") or 0)
    name = (atk.get("name") or "").lower()
    mine = _my(cur, me)
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
    for i in range(N_HAND_SLOTS):
        if i < len(HAND_SLOT_IDS):
            feats.append(min(counts.get(HAND_SLOT_IDS[i], 0), 4) / 4.0)
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
    if nf != N_STATE_FEATURES:
        raise ValueError("weights expect %d features, encoder has %d"
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
        if pk:
            return (pk.get("hp") or 0) + 20.0 * len(pk.get("energies") or []) \
                + _best_attack_info(pk.get("id"))[0] / 10.0
        return (_card(cid).get("hp") or 0) + _best_attack_info(cid)[0] / 10.0
    if ctx in (SC_SETUP_BENCH, SC_TO_BENCH):
        return 10.0 + (_card(cid).get("hp") or 0) / 10.0
    if ctx == SC_TO_HAND:
        return _card_value(cid) if cid is not None else 10.0
    if ctx in (SC_DISCARD, SC_TO_DECK, SC_TO_DECK_BOTTOM, SC_TO_PRIZE, SC_DETACH_FROM):
        return -_card_value(cid) if cid is not None else -60.0
    if ctx == SC_NOT_MOVE:
        return _card_value(cid) if cid is not None else 10.0
    if ctx in (SC_DMG_COUNTER, SC_DMG_COUNTER_ANY, SC_DAMAGE):
        # damaging opponents: prefer the closest to a KO, prefer the active
        if pk:
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
            result, was_clean = _validate_result(result, sel)
            if not was_clean:
                fallback = True
                STATS["fallbacks"] += 1
                _log_fallback("post-scoring validation fixed the result", turn, sel)
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
