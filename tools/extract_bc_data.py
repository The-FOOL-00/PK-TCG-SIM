"""Extract BC training targets from harvested top-team replays.

Filters to WINNING sides of the given team playing the given deck, applies
the verified step-i-observation <-> step-i+1-action alignment, and encodes
every MAIN-single decision with main.encode_state / main.encode_options —
the exact serve-time code path, so train/serve parity is structural.

Output: one .npz in gen_distill's shard schema (state [D,170], n_options,
label, turn, game_id, opt_x [sum(n),41]) consumable by train_policy.py-style
loaders, split happens at training time BY GAME.

Run:  py tools/extract_bc_data.py --team nasuo445 --deck metaC_garchomp_nasuo.csv \
          --out data/bc_garchomp/decisions.npz
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


def active_with_select(step):
    for a in (0, 1):
        e = step[a]
        if isinstance(e, dict) and e.get("status") == "ACTIVE" \
                and (e.get("observation") or {}).get("select") is not None:
            return a
    return None


def run(team, deck_file, src_dir, out):
    want_deck = Counter(int(x) for x in open(REPO / deck_file) if x.strip())
    files = sorted((REPO / src_dir).glob("*.json"))
    files = [f for f in files if not f.name.startswith("_")]

    states, n_options, labels, turns, game_ids, opt_rows = [], [], [], [], [], []
    n_games = 0
    skipped = Counter()
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
        n_before = len(labels)
        for i in range(1, len(steps) - 1):
            a = active_with_select(steps[i])
            if a != side:
                continue
            obs = steps[i][a]["observation"]
            sel = obs.get("select")
            cur = obs.get("current")
            action = steps[i + 1][a].get("action")
            nopt = len(sel.get("option") or [])
            if not (sel.get("type") == ST_MAIN and sel.get("minCount", 1) == 1
                    and sel.get("maxCount", 1) == 1 and nopt > 1 and cur is not None):
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
        if len(labels) > n_before:
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
    print(f"  decisions       : {len(labels)}")
    print(f"  option rows     : {len(opt_rows)}  (avg {len(opt_rows)/max(1,len(labels)):.1f} options/decision)")
    print(f"  label==0 share  : {100*float((lab==0).mean()):.1f}%  (always-index-0 floor)")
    print(f"  skipped         : {dict(skipped)}")
    print(f"  wrote {out_p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--deck", required=True)
    ap.add_argument("--src", default="data/top_replays_bulk")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(args.team, args.deck, args.src, args.out)
