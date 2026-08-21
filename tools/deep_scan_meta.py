"""Deep scan of legal high-tier meta cards in CABT."""

import sys
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission

def deep_scan():
    cards_db, attacks_db = build_submission.load_engine_card_db()
    print(f"Scanning {len(cards_db)} cards and {len(attacks_db)} attacks for high-tier archetypes...")

    keywords = [
        "miraidon", "iron hands", "raikou", "electric generator",
        "raging bolt", "roaring moon", "dark patch", "gouging fire",
        "gholdengo", "chien-pao", "baxcalibur", "charizard", "pidgeot",
        "ogerpon", "squawkabilly", "fezandipiti", "mew", "radiant"
    ]

    found = defaultdict(list)

    for cid, c in sorted(cards_db.items()):
        name = str(c.name).lower()
        for kw in keywords:
            if kw in name:
                found[kw].append((cid, c.name, c.cardType, c.hp, c.energyType))

    for kw, matches in sorted(found.items()):
        print(f"\n=== Keyword: {kw.upper()} ({len(matches)} cards) ===")
        for cid, cname, ctype, hp, etype in matches:
            tname = "Pokemon" if ctype == 0 else ("Item" if ctype == 1 else ("Tool" if ctype == 2 else ("Supporter" if ctype == 3 else ("Stadium" if ctype == 4 else ("Energy" if ctype in (5,6) else str(ctype))))))
            print(f"  ID {cid:4d}: {cname:35s} [Type: {tname:9s}, HP: {hp:3d}, EType: {etype}]")

if __name__ == "__main__":
    deep_scan()
