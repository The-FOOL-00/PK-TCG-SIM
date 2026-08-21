"""Deck Validation Tool for PTCG AI Battle Challenge.

Validates a deck CSV file against official competition rules:
  1. Exactly 60 cards total.
  2. All card IDs exist in the card database.
  3. No more than 4 copies of any non-Basic Energy card (matched by card name).
  4. At most 1 ACE SPEC card.
  5. At least 1 Basic Pokémon.
"""

import sys
import json
import argparse
from pathlib import Path
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_card_database():
    """Loads card database from EN_Card_Data.csv, card_data.json, or cg engine."""
    csv_path = REPO_ROOT / "EN_Card_Data.csv"
    if csv_path.exists():
        import csv
        db = {}
        with open(csv_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                cid = int(r["Card ID"])
                if cid not in db:
                    stage = r.get("Stage (Pokémon)/Type (Energy and Trainer)") or r.get("Stage") or ""
                    rule = r.get("Rule", "")
                    db[cid] = {
                        "cardId": cid,
                        "name": r.get("Card Name", ""),
                        "cardType": 0 if "Pok" in stage or "Basic" in stage or "Stage" in stage else (5 if "Energy" in stage or "Energy" in r.get("Card Name", "") else 1),
                        "basic": "Basic Pok" in stage or stage == "Basic Pokémon",
                        "stage1": "Stage 1" in stage,
                        "stage2": "Stage 2" in stage,
                        "aceSpec": "ACE SPEC" in rule or "ACE SPEC" in r.get("Card Name", ""),
                    }
        return db

    card_data_path = REPO_ROOT / "card_data.json"
    if card_data_path.exists():
        with open(card_data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(cid): c for cid, c in data["cards"].items()}
    return {}


def read_deck_file(deck_path):
    """Reads integer card IDs from a CSV or text file (one card ID per line)."""
    with open(deck_path, "r", encoding="utf-8") as f:
        return [int(line.strip()) for line in f if line.strip() and not line.strip().startswith("#")]


def validate_deck(deck, cards_db):
    """Validates deck list against card database and returns list of error messages."""
    errors = []
    
    # 1. Total deck count check
    if len(deck) != 60:
        errors.append(f"Invalid deck size: has {len(deck)} cards, expected exactly 60")

    # 2. Check for unknown card IDs
    unknown_ids = sorted({cid for cid in deck if cid not in cards_db})
    if unknown_ids:
        errors.append(f"Unknown card IDs not in database: {unknown_ids}")
        return errors, {}

    # 3. Attributes check: 4-copy rule, ACE SPEC count, Basic count
    name_counts = Counter()
    ace_spec_cards = []
    basic_pokemon = []
    stage1_pokemon = []
    stage2_pokemon = []
    trainers = []
    energy_cards = []

    for cid in deck:
        card = cards_db[cid]
        if isinstance(card, dict):
            card_type = card.get("cardType")
            card_name = card.get("name", "Unknown")
            is_basic = card.get("basic", False)
            is_stage1 = card.get("stage1", False)
            is_stage2 = card.get("stage2", False)
            is_ace_spec = card.get("aceSpec", False)
        else:
            card_type = getattr(card, "cardType", None)
            card_name = getattr(card, "name", "Unknown")
            is_basic = getattr(card, "basic", False)
            is_stage1 = getattr(card, "stage1", False)
            is_stage2 = getattr(card, "stage2", False)
            is_ace_spec = getattr(card, "aceSpec", False)

        is_basic_energy = (card_type == 5) or ("Basic" in card_name and "Energy" in card_name)

        if not is_basic_energy:
            name_counts[card_name] += 1

        if is_ace_spec:
            ace_spec_cards.append(card_name)

        if is_basic:
            basic_pokemon.append(card_name)
        elif is_stage1:
            stage1_pokemon.append(card_name)
        elif is_stage2:
            stage2_pokemon.append(card_name)
        elif is_basic_energy or "Energy" in card_name:
            energy_cards.append(card_name)
        else:
            trainers.append(card_name)

    # 4-copy rule check
    over_limit = {name: count for name, count in name_counts.items() if count > 4}
    if over_limit:
        errors.append(f"4-copy rule violation: {over_limit}")

    # ACE SPEC limit check
    if len(ace_spec_cards) > 1:
        errors.append(f"ACE SPEC violation: deck has {len(ace_spec_cards)} ACE SPEC cards {ace_spec_cards}, max allowed is 1")

    # Basic Pokemon check
    if len(basic_pokemon) == 0:
        errors.append("Deck contains no Basic Pokémon (deck would lose instantly on setup)")

    return errors, {
        "basic_pokemon": len(basic_pokemon),
        "stage1_pokemon": len(stage1_pokemon),
        "stage2_pokemon": len(stage2_pokemon),
        "trainers": len(trainers),
        "energy": len(energy_cards),
        "ace_spec": len(ace_spec_cards),
    }


def main():
    parser = argparse.ArgumentParser(description="Validate PTCG AI deck CSV file")
    parser.add_argument("deck_file", type=str, help="Path to deck CSV file")
    args = parser.parse_args()

    deck_path = Path(args.deck_file)
    if not deck_path.exists():
        print(f"Error: File '{deck_path}' does not exist.")
        sys.exit(1)

    cards_db = load_card_database()
    if not cards_db:
        print("Error: Could not load card database.")
        sys.exit(1)

    try:
        deck = read_deck_file(deck_path)
    except Exception as e:
        print(f"Error reading deck file '{deck_path}': {e}")
        sys.exit(1)

    errors, breakdown = validate_deck(deck, cards_db)

    print(f"--- Deck Validation: {deck_path.name} ---")
    print(f"Total Cards      : {len(deck)}")
    if breakdown:
        print(f"  Basic Pokémon  : {breakdown['basic_pokemon']}")
        print(f"  Stage 1        : {breakdown['stage1_pokemon']}")
        print(f"  Stage 2        : {breakdown['stage2_pokemon']}")
        print(f"  Trainers       : {breakdown['trainers']}")
        print(f"  Energy         : {breakdown['energy']}")
        print(f"  ACE SPEC       : {breakdown['ace_spec']}")

    if errors:
        print("\n[VALIDATION FAILED]")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[VALIDATION PASSED] Deck is valid and ready for battle.")
        sys.exit(0)


if __name__ == "__main__":
    main()
