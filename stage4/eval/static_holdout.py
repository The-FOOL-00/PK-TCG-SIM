"""Stage 4 Stop-2 static eval: all BC-v2 variants on ONE common holdout.

The trainer's val split (game_id % 10 == 0) is deterministic by episode id, so
holdout games of the union dataset were excluded from training in EVERY
variant. This scores each variant's best weights on that common set:
overall MAIN/CARD top-1, per-opponent-class accuracy (crustle / aggro /
mirror / alakazam-family / other -> the C1/C2 static view), and per-context
CARD accuracy with prize-fetch broken out.

Run:  py -3.12 -X utf8 stage4/eval/static_holdout.py
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "training"))
sys.path.insert(0, str(REPO / "tools"))
import train_bc_full as tbf  # noqa: E402
from meta_miner import CARD_DB  # noqa: E402

DATA = REPO / "stage4" / "data" / "bc_v2" / "c_majkel_yushin_bono"
REPLAYS = REPO / "stage4" / "data" / "replays_list0"
WEIGHTS = {v: REPO / f"bc_weights_list0_{v}.npz" for v in ("a", "b", "c")}

# ---- opponent class per episode id -----------------------------------------
LIST0 = Counter(int(x) for x in open(REPO / "stage4" / "deck_list0.csv") if x.strip())


def opp_class(deck):
    if not deck:
        return "?"
    names = {CARD_DB.get(c, {}).get("name", "") for c in deck}
    if any("Crustle" in n for n in names):
        return "crustle"
    if any(n in ("Mega Lucario ex", "Archaludon ex") for n in names):
        return "aggro"
    if Counter(deck) == LIST0:
        return "mirror"
    if any("Alakazam" in n for n in names):
        return "alakazam-family"
    return "other"


def build_game_class_map():
    m = {}
    for fp in REPLAYS.glob("*.json"):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = d.get("steps") or []
        if len(steps) < 2:
            continue
        decks = [steps[1][a].get("action") for a in (0, 1)]
        # the list-0 side(s): class of the OTHER deck
        for a in (0, 1):
            if isinstance(decks[a], list) and Counter(decks[a]) == LIST0:
                m[int(fp.stem)] = opp_class(decks[1 - a])
                break
    return m


def load_model(fp):
    z = np.load(fp)
    def part(prefix, n):
        return [[z[f"{prefix}W{i}"], z[f"{prefix}b{i}"]] for i in range(n)]
    trunk = part("T", int(z["n_trunk"]))
    return ({"trunk": trunk, "head": part("H", int(z["n_head"]))},
            {"trunk": trunk, "head": part("C", int(z["n_head_card"]))})


def main():
    game_cls = build_game_class_map()
    _, va_m, _ = tbf.load_stream(DATA / "main.npz")
    _, va_c, extras = tbf.load_stream(DATA / "card.npz", ("ctx", "dom_area"))
    ctx_va, area_va = extras["ctx"][1], extras["dom_area"][1]
    cls_m = np.array([game_cls.get(int(g), "?") for g in va_m.game_id])
    cls_c = np.array([game_cls.get(int(g), "?") for g in va_c.game_id])
    print(f"common holdout: {len(va_m)} MAIN / {len(va_c)} CARD decisions, "
          f"{va_m.n_games} games")
    print("holdout opp classes:", dict(Counter(cls_m.tolist())))

    for var, fp in WEIGHTS.items():
        view_m, view_c = load_model(fp)
        corr_m, _ = tbf.eval_correct(view_m, va_m)
        corr_c, _ = tbf.eval_correct(view_c, va_c)
        print(f"\n=== variant {var} ({fp.name}) ===")
        print(f"  overall: MAIN {corr_m.mean():.3f}  CARD {corr_c.mean():.3f}")
        print("  per opp class (MAIN | CARD):")
        for cl in sorted(set(cls_m.tolist())):
            mm = cls_m == cl
            mc = cls_c == cl
            print(f"    {cl:16s} MAIN {corr_m[mm].mean():.3f} (n={mm.sum():4d})"
                  f" | CARD {corr_c[mc].mean() if mc.any() else float('nan'):.3f}"
                  f" (n={mc.sum():4d})")
        # prize-fetch context: TO_HAND(7) with dom_area prize(6)
        pf = (ctx_va == 7) & (area_va == 6)
        dk = (ctx_va == 7) & (area_va == 1)
        print(f"  CARD prize-fetch (TO_HAND/prize): acc {corr_c[pf].mean():.3f} "
              f"(n={pf.sum()})")
        print(f"  CARD deck-fetch  (TO_HAND/deck) : acc {corr_c[dk].mean():.3f} "
              f"(n={dk.sum()})")


if __name__ == "__main__":
    main()
