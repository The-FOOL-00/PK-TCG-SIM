"""Decode S0 Teal Mask Ogerpon decklist and compute opening probabilities."""

import sys
from pathlib import Path
from collections import Counter
import math

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission

def decode_deck():
    cards_db, _ = build_submission.load_engine_card_db()
    lines = [int(line.strip()) for line in open(ROOT_DIR / "metaZ_teal_ogerpon_top10.csv") if line.strip()]
    counts = Counter(lines)

    print(f"Total cards in S0: {len(lines)}")
    print("\n--- S0 Deck Composition ---")
    for cid, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        c = cards_db.get(cid)
        cname = c.name if c else f"Unknown ({cid})"
        ctype = c.cardType if c else "?"
        print(f"  ID {cid:4d}: {cnt}x {cname:32s} (Type: {ctype})")

    # Hypergeometric probability calculations:
    # Deck size N = 60, Hand size k = 7.
    # Total Basics in deck: 4x Teal Mask Ogerpon ex (ID 96).
    N = 60
    k = 7
    M_basics = counts[96] # 4 basics
    M_energy = counts[1]  # Grass energy
    M_search = counts[1127] + counts[1094] # Tera Orb + Bug Catching Set

    def hypergeom_pmf(N, M, k, x):
        return (math.comb(M, x) * math.comb(N - M, k - x)) / math.comb(N, k)

    p_at_least_1_basic = 1.0 - hypergeom_pmf(N, M_basics, k, 0)
    p_at_least_1_energy = 1.0 - hypergeom_pmf(N, M_energy, k, 0)
    p_at_least_1_search = 1.0 - hypergeom_pmf(N, M_search, k, 0)

    print("\n--- Theoretical Opening Probabilities (7-card Opening Hand) ---")
    print(f"  P(>=1 Basic) (4 Ogerpon in 60):  {p_at_least_1_basic*100:5.2f}% (Mulligan prob: {(1-p_at_least_1_basic)*100:5.2f}%)")
    print(f"  P(>=1 Energy) ({M_energy} Energy in 60): {p_at_least_1_energy*100:5.2f}%")
    print(f"  P(>=1 Search) ({M_search} Search in 60): {p_at_least_1_search*100:5.2f}%")

if __name__ == "__main__":
    decode_deck()
