"""Explores all available legal cards and archetypes in the CABT engine."""

import sys
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission

def explore():
    cards_db, attacks_db = build_submission.load_engine_card_db()
    print(f"Loaded {len(cards_db)} cards and {len(attacks_db)} attacks.")

    pokemon_by_type = defaultdict(list)
    ex_pokemon = []
    megas = []
    basics = []

    for cid, c in sorted(cards_db.items()):
        if c.cardType == 0: # Pokemon
            name = str(c.name)
            hp = int(c.hp)
            info = {
                "id": cid,
                "name": name,
                "hp": hp,
                "energy_type": c.energyType,
                "stage": c.stage,
                "retreat": c.retreatCost
            }
            pokemon_by_type[c.energyType].append(info)
            if " ex" in name or " EX" in name:
                ex_pokemon.append(info)
            if "Mega " in name:
                megas.append(info)
            if c.stage == 0:
                basics.append(info)

    print(f"Total Pokemon: {sum(len(v) for v in pokemon_by_type.values())}")
    print(f"  Basics: {len(basics)}")
    print(f"  EX / Mega Pokemon: {len(ex_pokemon)}")
    print("\nProminent EX / Mega Attackers:")
    for p in ex_pokemon:
        print(f"  ID {p['id']:4d}: {p['name']:32s} (Type: {p['energy_type']:2d}, HP: {p['hp']:3d}, Stage: {p['stage']})")

if __name__ == "__main__":
    explore()
