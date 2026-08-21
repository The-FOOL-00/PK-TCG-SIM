"""Searches the CABT card database for available legal cards."""

import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import main as agent_mod

def search_cards():
    keywords = ["boss", "orders", "iono", "research", "nest", "switch", "rod", "vessel", "arven", "prime", "catcher", "poffin", "ultra", "lillie", "waitress", "starmie", "staryu", "duskull", "dusknoir", "mantine", "manaphy", "fezidipiti", "radiant", "greninja"]
    found = {}
    for cid, info in sorted(agent_mod.CARDS.items()):
        name = str(info.get("name", "")).lower()
        if any(kw in name for kw in keywords):
            found[cid] = info
            
    print(f"Found {len(found)} matching legal cards in CABT:")
    for cid, info in sorted(found.items(), key=lambda x: (x[1].get("cardType", 0), x[1].get("name", ""))):
        print(f"  ID: {cid:4d} | Type: {info.get('cardType', -1)} | Name: {info.get('name', ''):30s} | HP: {info.get('hp', 0)}")

if __name__ == "__main__":
    search_cards()
