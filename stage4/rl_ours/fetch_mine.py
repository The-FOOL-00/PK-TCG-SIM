"""Fetch-selection mining: WHICH card do top-10 Grimmsnarl pilots retrieve?

Context SC_TO_HAND (7) -- "a search/fetch resolved, pick the card" -- is the
largest sub-action slot in the game: 23,309 decisions with >1 option across 287
top-10 replays, 3.7x the SC_DAMAGE slot that produced the shipped T2 rule and
100x the SC_SWITCH slot that produced T1.

main.py scores it with `_card_value(cid)`, whose own docstring reads "how much
we mind losing this card (used for discard/keep choices)" -- a static per-card
constant (cardType + hp/10 + dmg/10, +100 if ex) with no board, hand, or turn
input. That is the T1 defect exactly (a scorer reused for a decision it was not
built for), on a slot with 15x T1's volume.

This mines the top-10's actual criterion, the way T1/T2 were mined: for each
decision, rank the chosen card among the legal alternatives on candidate axes,
and report how often our current ordering would have picked the same card.

Usage:  python stage4/rl_ours/fetch_mine.py [--probe] [--all-archetypes]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

_CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in _CD["cards"].items()}
ATTACKS = {int(k): v for k, v in (_CD.get("attacks") or {}).items()}
GRIMM = "Marnie's Grimmsnarl ex / Munkidori"
SC_TO_HAND = 7
CT_POKEMON, CT_ITEM, CT_TOOL, CT_SUPPORTER, CT_STADIUM = 0, 1, 2, 3, 4
A_DIR = REPO / "analysis/phase2_meta_shift"
TOP_DIRS = [A_DIR / f"replays_top10_{d}" for d in
            ("jul21", "jul22", "jul26", "jul31")]


def card(cid):
    return CARDS.get(cid) or {}


def best_dmg(cid):
    """Max printed damage over the card's attacks. `attacks` is a list of
    attack IDs into the ATTACKS table -- same indirection main.py uses."""
    best = 0.0
    for aid in card(cid).get("attacks") or []:
        atk = ATTACKS.get(aid)
        if atk:
            best = max(best, atk.get("damage") or 0)
    return best


def card_value(cid):
    """Verbatim port of main.py `_card_value` -- the ordering we ship today."""
    c = card(cid)
    ct = c.get("cardType")
    if ct == CT_POKEMON:
        v = 150.0 + (c.get("hp") or 0) / 10.0 + best_dmg(cid) / 10.0
        if c.get("ex") or c.get("megaEx"):
            v += 100.0
        return v
    return {CT_SUPPORTER: 80.0, CT_TOOL: 50.0,
            CT_ITEM: 40.0, CT_STADIUM: 30.0}.get(ct, 60.0)


AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_LOOKING = 1, 2, 3, 12


def opt_cid(o, cur):
    """Fetch options carry {area,index,playerIndex}, not a card id -- resolve
    through the zone. Search reveals land in cur['looking'] (AREA_LOOKING)."""
    if not isinstance(o, dict):
        return None
    area, idx, pi = o.get("area"), o.get("index"), o.get("playerIndex")
    if idx is None:
        return None
    if area == AREA_LOOKING:
        zone = cur.get("looking") or []
    else:
        pl = cur.get("players") or []
        if pi is None or pi >= len(pl):
            return None
        zone = {AREA_HAND: "hand", AREA_DISCARD: "discard"}.get(area)
        if zone is None:
            return None            # deck contents are hidden; not minable
        zone = pl[pi].get(zone) or []
    if idx >= len(zone):
        return None
    c = zone[idx]
    return c.get("id") if isinstance(c, dict) else None


def decisions(dirs, only_grimm=True, probe=False):
    """Yield (chosen_cid, [option_cids], ctx) for top-10 SC_TO_HAND choices."""
    shapes = Counter()
    for d in dirs:
        for fp in sorted(Path(d).glob("*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if not steps:
                continue
            rewards = js.get("rewards") or []
            for seat in (0, 1):
                if only_grimm:
                    # steps[1][seat]["action"] is the 60-card list the agent
                    # returned to the deck-selection call (DECK_SWITCH.md 1.1)
                    try:
                        deck = steps[1][seat].get("action")
                        lab = (archetype(deck) or {}).get("label") if deck else None
                    except Exception:
                        lab = None
                    if lab != GRIMM:
                        continue
                # winning sides only -- same filter the BC extraction used
                if len(rewards) > seat and rewards[seat] != 1:
                    continue
                for i in range(len(steps) - 1):
                    e = steps[i][seat]
                    if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                        continue
                    obs = e.get("observation") or {}
                    sel = obs.get("select") or {}
                    if sel.get("context") != SC_TO_HAND:
                        continue
                    opts = sel.get("option") or []
                    if len(opts) < 2:
                        continue
                    cur = obs.get("current") or {}
                    if probe and len(shapes) < 3:
                        shapes[json.dumps(opts[0], sort_keys=True)] += 1
                    act = steps[i + 1][seat].get("action")
                    # single-select only, matching the T1/T2 mining protocol;
                    # multi-selects are a different decision and are counted
                    # separately rather than flattened into this one
                    if not isinstance(act, list):
                        continue
                    if len(act) != 1:
                        shapes["__multiselect__"] += 1
                        continue
                    ci = act[0]
                    if not isinstance(ci, int) or ci >= len(opts):
                        continue
                    cids = [opt_cid(o, cur) for o in opts]
                    if cids[ci] is None or any(c is None for c in cids):
                        shapes["__unresolved__"] += 1
                        continue
                    yield cids[ci], cids
    if probe:
        print("option shapes seen:")
        for s in shapes:
            print("   ", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="dump option schema")
    ap.add_argument("--all-archetypes", action="store_true")
    args = ap.parse_args()

    n = 0
    ours_agree = 0
    by_type = Counter()
    chosen_cards = Counter()
    basic_when_available = [0, 0]     # [chose basic, basic was on menu]
    for chosen, cids in decisions(TOP_DIRS, not args.all_archetypes, args.probe):
        n += 1
        # would our shipped ordering have picked the same card?
        top = max(cids, key=lambda c: (card_value(c), -cids.index(c)))
        if top == chosen:
            ours_agree += 1
        c = card(chosen)
        by_type[c.get("cardType")] += 1
        chosen_cards[chosen] += 1
        menu_has_basic = any(card(x).get("cardType") == CT_POKEMON
                             and card(x).get("basic") for x in cids)
        if menu_has_basic:
            basic_when_available[1] += 1
            if c.get("cardType") == CT_POKEMON and c.get("basic"):
                basic_when_available[0] += 1

    if not n:
        print("no decisions matched -- run with --probe to inspect option schema")
        return
    TN = {CT_POKEMON: "Pokemon", CT_ITEM: "Item", CT_TOOL: "Tool",
          CT_SUPPORTER: "Supporter", CT_STADIUM: "Stadium"}
    print(f"\nSC_TO_HAND decisions mined (top-10, winning sides, >1 option): {n}")
    print(f"our shipped _card_value ordering agrees with top-10: "
          f"{ours_agree}/{n} = {100*ours_agree/n:.1f}%")
    print(f"  (T2's mined criterion agreed 82.4%; T1's 84.1%)")
    print("\nwhat they take, by card type:")
    for t, v in by_type.most_common():
        print(f"   {TN.get(t, t):<10} {v:6d}  {100*v/n:5.1f}%")
    if basic_when_available[1]:
        a, b = basic_when_available
        print(f"\nwhen a Basic Pokemon is on the menu ({b} decisions): "
              f"took it {a} = {100*a/b:.1f}%")
    print("\nmost-taken cards:")
    for cid, v in chosen_cards.most_common(10):
        print(f"   {v:5d}  {cid:5d}  {card(cid).get('name','?')}")


if __name__ == "__main__":
    main()
