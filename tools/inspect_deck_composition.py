"""Inspects deck composition and card details."""

import sys
from pathlib import Path
from collections import Counter

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import main as agent_mod

def inspect_deck(path="meta_starmie.csv"):
    deck = [int(line.strip()) for line in open(path) if line.strip()]
    counts = Counter(deck)
    print(f"Total cards: {len(deck)} across {len(counts)} unique IDs:")
    for cid, c in counts.most_common():
        info = agent_mod.CARDS.get(cid, {})
        name = info.get("name", f"Unknown_{cid}")
        ctype = info.get("cardType", -1)
        hp = info.get("hp", "")
        print(f"  {c}x {name:25s} (ID: {cid:4d}, Type: {ctype}, HP: {hp})")

if __name__ == "__main__":
    inspect_deck()
