"""Search CABT Card Database for Fire Pokémon and Anti-Grass Counter Mechanics."""

import sys
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission

def search_counters():
    cards_db, attacks_db = build_submission.load_engine_card_db()
    print(f"Searching across {len(cards_db)} cards and {len(attacks_db)} attacks...")

    fire_pokemon = []
    special_pokemon = []

    for cid, c in sorted(cards_db.items()):
        if c.cardType == 0: # Pokemon
            name = str(c.name)
            hp = int(c.hp)
            etype = c.energyType
            
            # Fire type in CABT is EnergyType 2 (Grass=1, Fire=2, Water=3, Lightning=4, Psychic=5, Fighting=6, Dark=7, Metal=8, Colorless=0 or 9)
            if etype == 2:
                fire_pokemon.append((cid, name, hp, c.stage1, c.stage2))
            
            for kw in ["crustle", "miltank", "mimikyu", "snorlax", "charizard", "gouging", "arcanine", "magmortar", "chi-yu", "volcarona", "cinderace", "fuecoco", "skeledirge", "armarouge"]:
                if kw in name.lower():
                    special_pokemon.append((cid, name, hp, etype))

    print(f"\n--- Legal Fire Pokémon in Database ({len(fire_pokemon)} found) ---")
    for cid, name, hp, s1, s2 in fire_pokemon:
        stg = "Stage 2" if s2 else ("Stage 1" if s1 else "Basic")
        print(f"  ID {cid:4d}: {name:32s} (HP: {hp:3d}, Stage: {stg})")

    print(f"\n--- Specific Counter Search Matches ({len(special_pokemon)} found) ---")
    for cid, name, hp, etype in special_pokemon:
        print(f"  ID {cid:4d}: {name:32s} (HP: {hp:3d}, EnergyType: {etype})")

if __name__ == "__main__":
    search_counters()
