"""Builds the Archetype Inventory and Deck Candidates for Project Mew Archetype Search."""

import json
import os
import sys
from pathlib import Path
from collections import Counter

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import main as agent_mod

def inspect_decks():
    deck_files = {
        "Starmie_S0": "meta_starmie.csv",
        "Alakazam_Psychic": "metaB_alakazam.csv",
        "Grimmsnarl_Dark": "metaG_grimmsnarl_top10.csv",
        "Mewtwo_Stall": "meta_mewtwo_stall.csv",
        "Dragapult_Spread": "metaZ_dragapult_top10.csv",
        "Archaludon_Metal": "metaX_archaludon_sanjay.csv",
        "Ogerpon_Grass": "metaZ_teal_ogerpon_top10.csv"
    }

    out_dir = Path("deck_search")
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = {}
    for name, fpath in deck_files.items():
        if not os.path.exists(fpath):
            continue
        deck = [int(line.strip()) for line in open(fpath) if line.strip()]
        counts = Counter(deck)
        cards_detail = []
        for cid, c in counts.most_common():
            info = agent_mod.CARDS.get(cid, {})
            cname = info.get("name", f"Unknown_{cid}")
            ctype = info.get("cardType", -1)
            hp = info.get("hp", 0)
            cards_detail.append({"id": cid, "name": cname, "count": c, "type": ctype, "hp": hp})
        
        inventory[name] = {
            "name": name,
            "path": fpath,
            "total_cards": len(deck),
            "unique_cards": len(counts),
            "cards": cards_detail
        }
        print(f"Deck {name:20s}: {len(deck)} cards, {len(counts)} unique")

    (out_dir / "archetype_inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Wrote deck_search/archetype_inventory.json")

if __name__ == "__main__":
    inspect_decks()
