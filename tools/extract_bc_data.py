"""Extract BC training targets from harvested top-team replays.

Filters to WINNING sides of the given team playing the given deck, applies
the verified step-i-observation <-> step-i+1-action alignment, and encodes
every MAIN-single decision with main.encode_state / main.encode_options —
the exact serve-time code path, so train/serve parity is structural.

Option A (BC-full) addition: ALSO extracts every ST_CARD-family sub-decision
(CARD / ATTACHED_CARD / CARD_OR_ATTACHED — the fetch/bench/promote/discard
picks v1 answers with _score_card) via main.encode_card_options. Multi-select
decisions (choose k of n, e.g. Buddy-Buddy Poffin's up-to-2 bench picks) are
decomposed Plackett-Luce style into k sequential single-choices over the
shrinking option set, in the expert's pick order, so the same segment-softmax
CE trainer covers them; serve mirrors this with iterative argmax.

Output: two .npz in gen_distill's shard schema (state [D,170], n_options,
label, turn, game_id, opt_x [sum(n), 41 or 73]) consumable by
train_policy.py-style loaders, split happens at training time BY GAME.

Run:  py tools/extract_bc_data.py --team nasuo445 --deck metaC_garchomp_nasuo.csv \
          --out data/bc_garchomp/decisions.npz \
          --out-card data/bc_garchomp_card/decisions.npz
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import main  # noqa: E402
assert hasattr(main, "encode_state"), "wrong main.py on sys.path"

ST_MAIN = 0
ST_CARD_FAMILY = (1, 2, 3)   # CARD, ATTACHED_CARD, CARD_OR_ATTACHED

AREA_NAMES = {1: "deck", 2: "hand", 3: "discard", 4: "active", 5: "bench",
              6: "prize", 7: "stadium", 12: "looking"}
CTX_NAMES = {1: "SETUP_ACTIVE", 2: "SETUP_BENCH", 3: "SWITCH", 4: "TO_ACTIVE",
             5: "TO_BENCH", 6: "TO_FIELD", 7: "TO_HAND", 8: "DISCARD",
             9: "TO_DECK", 10: "TO_DECK_BOT", 11: "TO_PRIZE", 12: "NOT_MOVE",
             13: "DMG_COUNTER", 14: "DMG_ANY", 15: "DAMAGE", 16: "REMOVE_DMG",
             17: "HEAL", 18: "EVOLVES_FROM", 19: "EVOLVES_TO",
             21: "ATTACH_FROM", 22: "ATTACH_TO", 23: "DETACH_FROM",
             24: "LOOK", 25: "EFFECT_TARGET"}
# effect-source guess from (context, dominant option area) — reporting only
SOURCE_GUESS = {
    ("TO_HAND", "deck"): "deck fetch to hand (Fighting Gong / Poke Pad ...)",
    ("TO_HAND", "discard"): "discard recovery (Night Stretcher)",
    ("TO_BENCH", "deck"): "deck to bench (Buddy-Buddy Poffin)",
    ("SWITCH", "bench"): "switch/gust pick",
    ("TO_ACTIVE", "bench"): "promote after KO",
    ("SETUP_ACTIVE", "hand"): "opening active",
    ("SETUP_BENCH", "hand"): "opening bench",
    ("DISCARD", "hand"): "hand discard (Hilda / Lillie's / Xerosic's)",
}


def card_pl_steps(sel, action):
    """Plackett-Luce decomposition of one ST_CARD decision into single-choice
    training steps: (reduced_sel, label) pairs in the expert's pick order.
    Steps with no real choice (n<=1 or must-take-all) are omitted."""
    options = sel.get("option") or []
    mn = sel.get("minCount") or 0
    mx = sel.get("maxCount")
    mx = len(options) if mx is None else mx
    remaining = list(range(len(options)))
    steps = []
    for j, pick in enumerate(action):
        if pick not in remaining:
            return None                       # replay/action inconsistency
        n_j = len(remaining)
        mn_j, mx_j = max(0, mn - j), mx - j
        if n_j > 1 and mn_j < n_j:
            red = dict(sel)
            red["option"] = [options[i] for i in remaining]
            red["minCount"], red["maxCount"] = mn_j, mx_j
            steps.append((red, remaining.index(pick)))
        remaining.remove(pick)
    return steps


def active_with_select(step):
    for a in (0, 1):
        e = step[a]
        if isinstance(e, dict) and e.get("status") == "ACTIVE" \
                and (e.get("observation") or {}).get("select") is not None:
            return a
    return None


def run(team, deck_file, src_dir, out, out_card=None):
    deck_ids = [int(x) for x in open(REPO / deck_file) if x.strip()]
    want_deck = Counter(deck_ids)
    # Deck-identity features (hand-count block, ST_CARD id one-hot) must
    # describe the deck being IMITATED, not our default deck.csv. Serve time
    # matches via PTCG_DYN_DECK_TABLES=1 (ab_gate sets DECK per side) or a
    # bundle whose deck.csv is this same deck. The prior (pre-Option-A)
    # extraction skipped this: its hand block could see 1 of 20 Garchomp ids.
    main.DECK = list(deck_ids)
    main.DYN_DECK_TABLES = True
    files = sorted((REPO / src_dir).glob("*.json"))
    files = [f for f in files if not f.name.startswith("_")]

    states, n_options, labels, turns, game_ids, opt_rows = [], [], [], [], [], []
    c_states, c_n_options, c_labels, c_turns, c_game_ids, c_opt_rows = \
        [], [], [], [], [], []
    c_ctxs, c_dom_areas = [], []   # per-step context + dominant option area
    n_games = 0
    skipped = Counter()
    card_by_source = Counter()    # (ctx name, dominant option area) -> decisions
    card_stats = Counter()
    for fp in files:
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            skipped["unreadable"] += 1
            continue
        if not isinstance(d, dict):
            continue
        teams = (d.get("info") or {}).get("TeamNames") or ["?", "?"]
        rewards = d.get("rewards") or [None, None]
        steps = d.get("steps") or []
        if team not in teams or len(steps) < 3:
            continue
        side = teams.index(team)
        if rewards[side] != 1:
            skipped["lost-side"] += 1
            continue
        act0 = steps[1][side].get("action") if isinstance(steps[1][side], dict) else None
        if not (isinstance(act0, list) and len(act0) == 60
                and Counter(act0) == want_deck):
            skipped["other-deck"] += 1
            continue
        gid = int(fp.stem.split("-")[0])
        n_before = len(labels) + len(c_labels)
        for i in range(1, len(steps) - 1):
            a = active_with_select(steps[i])
            if a != side:
                continue
            obs = steps[i][a]["observation"]
            sel = obs.get("select")
            cur = obs.get("current")
            action = steps[i + 1][a].get("action")
            stype = sel.get("type")
            nopt = len(sel.get("option") or [])

            if stype == ST_MAIN:
                if not (sel.get("minCount", 1) == 1 and sel.get("maxCount", 1) == 1
                        and nopt > 1 and cur is not None):
                    continue
                if not (isinstance(action, list) and len(action) == 1
                        and isinstance(action[0], int) and 0 <= action[0] < nopt):
                    skipped["bad-action"] += 1
                    continue
                try:
                    s = main.encode_state(cur)
                    o = main.encode_options(sel, cur)
                except Exception:
                    skipped["encode-fail"] += 1
                    continue
                states.append(s)
                n_options.append(nopt)
                labels.append(action[0])
                turns.append(cur.get("turn") or 0)
                game_ids.append(gid)
                opt_rows.extend(o)
                continue

            if out_card is None or stype not in ST_CARD_FAMILY or cur is None:
                continue
            card_stats["seen"] += 1
            mn = sel.get("minCount") or 0
            mx = sel.get("maxCount")
            mx = nopt if mx is None else mx
            if not (isinstance(action, list)
                    and all(isinstance(x, int) and 0 <= x < nopt for x in action)
                    and len(set(action)) == len(action)
                    and mn <= len(action) <= mx):
                card_stats["bad-action"] += 1
                continue
            areas = Counter((o or {}).get("area") for o in sel.get("option") or [])
            dom_area = AREA_NAMES.get(areas.most_common(1)[0][0], "?") if areas else "?"
            ctx_name = CTX_NAMES.get(sel.get("context"), str(sel.get("context")))
            card_by_source[(ctx_name, dom_area)] += 1
            if len(action) == 0:
                card_stats["chose-none"] += 1
                continue
            if nopt <= 1:
                card_stats["forced-single"] += 1
                continue
            pl = card_pl_steps(sel, action)
            if pl is None:
                card_stats["bad-action"] += 1
                continue
            if len(action) > 1:
                card_stats["multi-select-decisions"] += 1
            try:
                s = main.encode_state(cur)
                rows = [(red, lab, main.encode_card_options(red, cur))
                        for red, lab in pl]
            except Exception:
                card_stats["encode-fail"] += 1
                continue
            dom_area_id = areas.most_common(1)[0][0] if areas else 0
            for red, lab, o in rows:
                c_states.append(s)
                c_n_options.append(len(red["option"]))
                c_labels.append(lab)
                c_turns.append(cur.get("turn") or 0)
                c_game_ids.append(gid)
                c_opt_rows.extend(o)
                c_ctxs.append(sel.get("context") or 0)
                c_dom_areas.append(dom_area_id or 0)
                card_stats["pl-steps"] += 1
        if len(labels) + len(c_labels) > n_before:
            n_games += 1

    out_p = REPO / out
    out_p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_p,
        state=np.asarray(states, dtype=np.float32),
        n_options=np.asarray(n_options, dtype=np.int16),
        label=np.asarray(labels, dtype=np.int16),
        turn=np.asarray(turns, dtype=np.int16),
        game_id=np.asarray(game_ids, dtype=np.int64),
        opt_x=np.asarray(opt_rows, dtype=np.float32),
    )
    lab = np.asarray(labels)
    print(f"team={team} deck={deck_file}")
    print(f"  games used      : {n_games}")
    print(f"MAIN-single -> {out_p}")
    print(f"  decisions       : {len(labels)}")
    print(f"  option rows     : {len(opt_rows)}  (avg {len(opt_rows)/max(1,len(labels)):.1f} options/decision)")
    print(f"  label==0 share  : {100*float((lab==0).mean()):.1f}%  (always-index-0 floor)")
    print(f"  skipped         : {dict(skipped)}")

    if out_card is not None:
        outc_p = REPO / out_card
        outc_p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            outc_p,
            state=np.asarray(c_states, dtype=np.float32),
            n_options=np.asarray(c_n_options, dtype=np.int16),
            label=np.asarray(c_labels, dtype=np.int16),
            turn=np.asarray(c_turns, dtype=np.int16),
            game_id=np.asarray(c_game_ids, dtype=np.int64),
            opt_x=np.asarray(c_opt_rows, dtype=np.float32),
            ctx=np.asarray(c_ctxs, dtype=np.int16),
            dom_area=np.asarray(c_dom_areas, dtype=np.int16),
        )
        c_lab = np.asarray(c_labels)
        print(f"ST_CARD -> {outc_p}")
        print(f"  raw decisions   : {card_stats['seen']}  "
              f"(multi-select {card_stats['multi-select-decisions']}, "
              f"forced-single {card_stats['forced-single']}, "
              f"chose-none {card_stats['chose-none']}, "
              f"bad-action {card_stats['bad-action']}, "
              f"encode-fail {card_stats['encode-fail']})")
        print(f"  training steps  : {len(c_labels)}  (after PL decomposition)")
        print(f"  option rows     : {len(c_opt_rows)}  "
              f"(avg {len(c_opt_rows)/max(1,len(c_labels)):.1f} options/step, "
              f"{np.asarray(c_opt_rows).shape[1] if len(c_opt_rows) else 0} dims)")
        print(f"  label==0 share  : {100*float((c_lab==0).mean()):.1f}%  (always-index-0 floor)")
        print(f"  by (context, dominant option area):")
        for (ctx, area), v in card_by_source.most_common():
            guess = SOURCE_GUESS.get((ctx, area), "")
            print(f"    {ctx:14s} {area:8s} {v:6d}  {guess}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--deck", required=True)
    ap.add_argument("--src", default="data/top_replays_bulk")
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-card", default=None,
                    help="also extract ST_CARD-family targets to this .npz")
    args = ap.parse_args()
    run(args.team, args.deck, args.src, args.out, args.out_card)
