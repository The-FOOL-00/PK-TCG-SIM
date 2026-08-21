"""Inspect CardData fields."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission

def inspect_cards():
    cards_db, attacks_db = build_submission.load_engine_card_db()
    cids = [63, 171, 957, 313, 96, 99, 108, 117, 140, 46]

    for cid in cids:
        c = cards_db.get(cid)
        if not c: continue
        print(f"\n========================================================")
        print(f"Card ID {cid:4d}: {c.name} (HP: {c.hp}, EnergyType: {c.energyType}, CardType: {c.cardType})")
        print(f"  Stage1: {c.stage1}, Stage2: {c.stage2}")
        print(f"  Attacks: {list(c.attacks)}")
        for aid in c.attacks:
            if aid > 0 and aid in attacks_db:
                a = attacks_db[aid]
                print(f"    Attack {aid:4d}: {a.name} | Damage: {a.damage}")

if __name__ == "__main__":
    inspect_cards()
