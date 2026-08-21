"""BS-CEI Opponent Belief Model & Dynamic Game Context Extractor.

Tracks public observations and CardTracker state to estimate:
1. Probabilistic opponent archetype posterior P(archetype | evidence) across 8 top meta decks + other.
2. Opponent observed energy types (8 basic energy channels).
3. Opponent hidden hand & deck certainty metrics.
4. Dynamic game context (prize differential, deckout hazard, immediate KO threat).

Outputs a compact 24-dimensional normalized float32 vector.
"""

import math
from typing import Dict, List, Set, Tuple, Optional

# Meta Archetype Signatures (Card IDs characteristic of each archetype)
META_ARCHETYPE_SIGNATURES: Dict[str, Set[int]] = {
    "grimmsnarl": {104, 112, 646, 647, 648, 860},
    "fezandipiti": {19, 66, 140, 305, 343, 741, 742, 743},
    "garchomp": {341, 342, 379, 380, 381, 387},
    "kangaskhan": {63, 96, 108, 184, 272, 756},
    "mewtwo": {400, 401, 414, 431, 434},
    "dragapult": {119, 120, 121, 235},
    "starmie": {1030, 1031},
    "alakazam": {66, 743, 744},
}

ARCHETYPE_NAMES = [
    "grimmsnarl",
    "fezandipiti",
    "garchomp",
    "kangaskhan",
    "mewtwo",
    "dragapult",
    "starmie",
    "alakazam",
]

N_ARCHETYPES = len(ARCHETYPE_NAMES) + 1  # 8 + 1 other/unknown = 9
N_ENERGY_TYPES = 8                       # Colorless, Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness
N_BELIEF_FEATURES = N_ARCHETYPES + N_ENERGY_TYPES + 4 + 3  # 9 + 8 + 4 + 3 = 24


class BeliefModel:
    """Maintains probabilistic opponent archetype & hidden-information belief."""

    def __init__(self, my_index: int = 0):
        self.my_index = my_index
        self.seen_opp_card_ids: Set[int] = set()
        self.opp_energy_types: Set[int] = set()
        self.archetype_probs: List[float] = [1.0 / N_ARCHETYPES] * N_ARCHETYPES

    def reset(self):
        self.seen_opp_card_ids.clear()
        self.opp_energy_types.clear()
        self.archetype_probs = [1.0 / N_ARCHETYPES] * N_ARCHETYPES

    def update(self, cur: dict, tracker: Optional[object] = None) -> List[float]:
        """Update beliefs from current public state and CardTracker, returning 24-dim vector."""
        if not cur or "players" not in cur:
            return [0.0] * N_BELIEF_FEATURES

        players = cur.get("players") or [{}, {}]
        me = cur.get("yourIndex", self.my_index)
        opp = 1 - me
        mine = players[me] if len(players) > me else {}
        theirs = players[opp] if len(players) > opp else {}

        # 1. Update seen opponent cards from public zones
        for card in theirs.get("discard") or []:
            if isinstance(card, dict) and card.get("id"):
                self.seen_opp_card_ids.add(card["id"])

        for pk in (theirs.get("active") or []) + (theirs.get("bench") or []):
            if pk and isinstance(pk, dict) and pk.get("id"):
                self.seen_opp_card_ids.add(pk["id"])
                for et in pk.get("energies") or []:
                    if isinstance(et, int) and 0 <= et < N_ENERGY_TYPES:
                        self.opp_energy_types.add(et)

        # Ingest tracker identities if available
        if tracker is not None:
            if hasattr(tracker, "serial_id"):
                for cid in tracker.serial_id.values():
                    if cid is not None:
                        self.seen_opp_card_ids.add(cid)
            if hasattr(tracker, "energy_types"):
                for et in tracker.energy_types:
                    if isinstance(et, int) and 0 <= et < N_ENERGY_TYPES:
                        self.opp_energy_types.add(et)

        # 2. Compute Bayesian Archetype Posterior P(archetype | seen_cards)
        log_priors = [0.0] * len(ARCHETYPE_NAMES)
        for i, name in enumerate(ARCHETYPE_NAMES):
            sigs = META_ARCHETYPE_SIGNATURES[name]
            matches = len(self.seen_opp_card_ids & sigs)
            log_priors[i] = 1.8 * matches

        other_log = 0.5
        all_logits = log_priors + [other_log]
        max_l = max(all_logits)
        exps = [math.exp(l - max_l) for l in all_logits]
        sum_e = sum(exps)
        self.archetype_probs = [e / sum_e for e in exps]

        # 3. Energy Types Channels (8 dims)
        energy_vec = [1.0 if et in self.opp_energy_types else 0.0 for et in range(N_ENERGY_TYPES)]

        # 4. Hidden Hand & Deck Certainty (4 dims)
        hand_count = float(theirs.get("handCount") or 0)
        deck_count = float(theirs.get("deckCount") or 0)
        known_hand_count = float(len(tracker.hand_known)) if tracker and hasattr(tracker, "hand_known") else 0.0
        floating_count = float(len(tracker.floating)) if tracker and hasattr(tracker, "floating") else 0.0

        known_hand_ratio = min(1.0, known_hand_count / max(1.0, hand_count))
        floating_ratio = min(1.0, floating_count / max(1.0, deck_count + hand_count))
        revealed_deck_ratio = min(1.0, len(self.seen_opp_card_ids) / 60.0)
        est_energy_density = min(1.0, max(0.0, (14.0 - len(self.opp_energy_types) * 2) / max(1.0, deck_count + hand_count)))

        certainty_vec = [known_hand_ratio, floating_ratio, revealed_deck_ratio, est_energy_density]

        # 5. Dynamic Game Context (3 dims)
        my_prizes = len(mine.get("prize") or [])
        opp_prizes = len(theirs.get("prize") or [])
        prize_diff = (opp_prizes - my_prizes) / 6.0

        turn = float(cur.get("turn") or 0)
        my_deck_count = float(mine.get("deckCount") or 0)
        deckout_hazard = max(0.0, 1.0 - (my_deck_count / 15.0)) if my_deck_count <= 15 else 0.0

        opp_act = (theirs.get("active") or [None])[0]
        my_act = (mine.get("active") or [None])[0]
        ko_threat = 0.0
        if opp_act and my_act:
            my_hp = my_act.get("hp") or 0
            opp_energies = len(opp_act.get("energies") or [])
            if opp_energies >= 2 and my_hp > 0 and my_hp <= opp_energies * 60:
                ko_threat = 1.0

        context_vec = [prize_diff, deckout_hazard, ko_threat]

        belief_vec = self.archetype_probs + energy_vec + certainty_vec + context_vec
        return belief_vec


def belief_feature_names() -> List[str]:
    names = [f"belief_arch_{name}" for name in ARCHETYPE_NAMES] + ["belief_arch_other"]
    names += [f"belief_energy_type_{i}" for i in range(N_ENERGY_TYPES)]
    names += ["known_hand_ratio", "floating_ratio", "revealed_deck_ratio", "est_energy_density"]
    names += ["prize_diff", "deckout_hazard", "opp_ko_threat"]
    return names
