"""Stop 2b analysis: choose N from the brake diagnostic.

Reads brake_diag_b_vs_crustle.json and reports:
1. Which chosen MAIN actions consume our deck (deckCount delta to the next
   decision, attributed to the chosen action) -> the brake's card set.
2. Self-deckout trajectory: deck size by turn; optional-draw cards consumed
   below each candidate threshold N -> "turns bought" if the brake had fired.
3. Interference: in WON games, how often deck<=N AND behind occurs at a
   would-be-braked decision.
"""

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import CARD_DB  # noqa: E402

OT = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY", 11: "DISCARD",
      12: "RETREAT", 13: "ATTACK", 14: "END"}

games = json.loads((REPO / "stage4/runs/brake_diag_b_vs_crustle.json")
                   .read_text(encoding="utf-8"))

# ---- 1. consumption attribution --------------------------------------------
# Delta between consecutive MAIN decisions WITHIN the same turn, attributed to
# the first MAIN action — this rolls sub-selection chains (Poffin/Poke Pad
# fetches) into the action that started them. Turn-crossing deltas (END,
# ATTACK) are excluded: they conflate turn-start draws and opponent effects.
consume = defaultdict(list)   # (opt_type, card) -> list of deck deltas
for g in games:
    rows = [r for r in g["decisions"]
            if r["deck"] is not None and r["stype"] == 0 and r["chosen"] is not None]
    for i in range(len(rows) - 1):
        r, nxt = rows[i], rows[i + 1]
        if r["turn"] != nxt["turn"]:
            continue
        delta = (r["deck"] or 0) - (nxt["deck"] or 0)
        consume[(r["opt_type"], r["card"])].append(delta)

print("=== deck consumption per chosen MAIN action (mean cards, n>=20) ===")
brake_set = []
for (ot, cid), deltas in sorted(consume.items(),
                                key=lambda kv: -st.mean(kv[1])):
    if len(deltas) < 20:
        continue
    name = CARD_DB.get(cid, {}).get("name", cid)
    m = st.mean(deltas)
    print(f"  {OT.get(ot, ot):8s} {str(name)[:28]:28s} n={len(deltas):5d}  "
          f"mean deck delta {m:+.2f}")
    if m >= 0.8 and ot in (7, 8, 10):   # candidate optional self-draw actions
        brake_set.append((ot, cid, name, m))
print("\ncandidate brake set (PLAY/ATTACH/ABILITY with mean consumption >= 0.8):")
for ot, cid, name, m in brake_set:
    print(f"  {OT[ot]} {name} (id {cid}, {m:+.2f})")
BRAKE_IDS = {cid for _, cid, _, _ in brake_set}

# ---- 2. self-deckout trajectories + turns bought per N ---------------------
sd_games = [g for g in games if g["reward"] == -1 and g["reason"] == "deckout"]
won = [g for g in games if g["reward"] == 1]
print(f"\nself-deckout games: {len(sd_games)}, wins: {len(won)}")

hist_final_behind = Counter()
for g in sd_games:
    rows = [r for r in g["decisions"] if r["deck"] is not None and r["stype"] == 0]
    # deck size when the game entered its final 3 turns
    turns = sorted({r["turn"] for r in rows})
    if len(turns) >= 3:
        t3 = turns[-3]
        at_t3 = [r["deck"] for r in rows if r["turn"] == t3]
        hist_final_behind[min(10, max(0, at_t3[0] if at_t3 else 0))] += 1

print("deck size 3-turns-before-deckout histogram:", dict(sorted(hist_final_behind.items())))

print("\nN trade-off (self-deckout games: cards saved by brake; won games: braked decisions)")
print(f"{'N':>3s} {'saved cards med':>16s} {'saved>=4 games':>15s} "
      f"{'won-game braked decisions':>26s} {'won games affected':>19s}")
for N in (6, 8, 10, 12, 14, 16):
    saved_per_game = []
    for g in sd_games:
        rows = [r for r in g["decisions"] if r["deck"] is not None
                and r["stype"] == 0 and r["chosen"] is not None]
        saved = 0.0
        for i in range(len(rows) - 1):
            r = rows[i]
            if r["turn"] != rows[i + 1]["turn"]:
                continue
            behind = r["my_prizes_left"] > r["opp_prizes_left"]
            if r["deck"] <= N and behind and r["card"] in BRAKE_IDS \
                    and r["opt_type"] in (7, 8, 10):
                saved += max(0, (r["deck"] or 0) - (rows[i + 1]["deck"] or 0))
        saved_per_game.append(saved)
    n_affected = 0
    n_decisions = 0
    for g in won:
        rows = [r for r in g["decisions"] if r["deck"] is not None
                and r["stype"] == 0 and r["chosen"] is not None]
        hit = 0
        for r in rows:
            behind = r["my_prizes_left"] > r["opp_prizes_left"]
            if r["deck"] <= N and behind and r["card"] in BRAKE_IDS \
                    and r["opt_type"] in (7, 8, 10):
                hit += 1
        n_decisions += hit
        n_affected += 1 if hit else 0
    med = st.median(saved_per_game) if saved_per_game else 0
    ge4 = sum(1 for s in saved_per_game if s >= 4)
    print(f"{N:3d} {med:16.1f} {ge4:11d}/{len(sd_games):2d} "
          f"{n_decisions:26d} {n_affected:15d}/{len(won)}")
