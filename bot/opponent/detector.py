"""Opponent Archetype Detector

Tracks revealed opponent cards (active, bench, discard, hand counts, energy)
and provides incremental archetype classification with confidence scores.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional


@dataclass
class ArchetypePrediction:
    archetype: str
    confidence: float
    evidence: Set[str] = field(default_factory=set)


# Signature card IDs mapped to archetype labels
ARCHETYPE_SIGNATURES: Dict[str, Set[int]] = {
    "STARMIE": {1030, 1031},                     # Staryu, Mega Starmie ex
    "ABOMASNOW": {722, 723},                     # Snover, Mega Abomasnow ex
    "ALAKAZAM": {66, 743},                       # Dudunsparce, Alakazam
    "GARCHOMP": {540, 756, 63},                  # Cynthia's Garchomp ex line
    "KANGASKHAN": {756, 63},                     # Mega Kangaskhan ex, Raging Bolt ex
    "GRIMMSNARL": {412, 413, 414},               # Grimmsnarl ex line
    "MEWTWO": {431},                             # Team Rocket's Mewtwo ex
    "DRAGAPULT": {301, 302, 303},                # Dragapult ex line
    "FEZANDIPITI": {743, 744},                   # Fezandipiti ex, Munkidori
}


class OpponentDetector:
    """Incremental opponent archetype detector."""
    
    def __init__(self):
        self.seen_card_ids: Set[int] = set()
        self.current_prediction: ArchetypePrediction = ArchetypePrediction("UNKNOWN", 0.0)

    def update(self, current_obs: dict, my_index: int) -> ArchetypePrediction:
        """Updates seen evidence from public observation and returns current prediction."""
        if not current_obs or "players" not in current_obs:
            return self.current_prediction

        players = current_obs.get("players", [])
        if len(players) <= 1:
            return self.current_prediction

        opp = players[1 - my_index]
        
        # 1. Scan active & bench
        for pk in (opp.get("active") or []) + (opp.get("bench") or []):
            if pk and "id" in pk:
                self.seen_card_ids.add(pk["id"])

        # 2. Scan discard pile
        for card in opp.get("discard") or []:
            if card and "id" in card:
                self.seen_card_ids.add(card["id"])

        # 3. Classify based on evidence
        best_archetype = "UNKNOWN"
        best_evidence_count = 0
        matched_evidence: Set[str] = set()

        for archetype, sig_ids in ARCHETYPE_SIGNATURES.items():
            matches = self.seen_card_ids & sig_ids
            if len(matches) > best_evidence_count:
                best_evidence_count = len(matches)
                best_archetype = archetype
                matched_evidence = {str(cid) for cid in matches}

        # Calculate confidence
        if best_evidence_count >= 3:
            confidence = 0.95
        elif best_evidence_count == 2:
            confidence = 0.85
        elif best_evidence_count == 1:
            confidence = 0.60
        else:
            confidence = 0.0
            best_archetype = "UNKNOWN"

        self.current_prediction = ArchetypePrediction(
            archetype=best_archetype,
            confidence=confidence,
            evidence=matched_evidence,
        )
        return self.current_prediction
