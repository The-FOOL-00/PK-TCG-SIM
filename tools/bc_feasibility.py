"""Phase 3A feasibility: can we recover clean (state, chosen-index) BC targets
from the top-team replays, and in what volume?

Alignment (verified): the ACTIVE agent's observation.select at steps[i] is
answered by that same agent's action at steps[i+1]. We walk every episode,
attribute each decision to the acting team, keep WINNING top-team sides, and
categorize each decision:
  deck-sel     select is None (the 60-card deck; not a BC target)
  MAIN-single  type==MAIN, min==max==1, >1 option  -> encodable, 1 label
  MAIN-multi   type==MAIN, multi-select            -> needs multi-label
  non-MAIN     card / yes-no / count / ...          -> different encoding
For MAIN-single we actually run encode_state + encode_options to confirm the
existing train_policy.py encoding works on replay observations, counting
successes and failure reasons.

Run:  python tools/bc_feasibility.py
"""

import json
import sys
import traceback
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))          # our main.py must win over the sample's
import main  # noqa: E402
assert hasattr(main, "encode_state"), "imported the wrong main.py"

TOP_TEAMS = {"Majkel1337", "kashiwashira", "nasuo445"}
ST_MAIN = 0


def deck_label(deck):
    """Archetype label + energy count from a 60-card list (engine card db)."""
    sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))
    from cg.api import all_card_data
    cs = getattr(deck_label, "_cs", None)
    if cs is None:
        cs = deck_label._cs = {c.cardId: c for c in all_card_data()}
    c = Counter(deck)
    pkmn = [cid for cid in c if cs.get(cid) and cs[cid].cardType == 0]
    heads = sorted(pkmn, key=lambda x: (cs[x].megaEx, cs[x].ex, cs[x].hp), reverse=True)[:2]
    energy = sum(n for cid, n in c.items() if cs.get(cid) and cs[cid].cardType == 5)
    label = " / ".join(cs[h].name for h in heads) or "?"
    return f"{label} (E{energy})"


def active_with_select(step):
    for a in (0, 1):
        e = step[a]
        if isinstance(e, dict) and e.get("status") == "ACTIVE" \
                and (e.get("observation") or {}).get("select") is not None:
            return a
    return None


def run(directory="data/top_replays", teams=None):
    top_teams = set(teams) if teams else TOP_TEAMS
    files = sorted((REPO / directory).glob("*.json"))
    files = [f for f in files if not f.name.startswith("_")]
    cat = Counter()
    enc_ok = 0
    enc_fail = Counter()
    per_team = Counter()          # winning top-team MAIN-single decisions
    per_team_all = Counter()      # all winning top-team decisions
    per_deck = Counter()          # winning top-team MAIN-single targets by DECK
    deck_sides = Counter()        # deck usage among top-team sides (meta table)
    winning_sides = 0
    total_sides = 0
    opp_available = Counter()     # can we also imitate the opponent side?
    idx_valid = idx_invalid = 0

    for fp in files:
        d = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        teams = (d.get("info") or {}).get("TeamNames") or ["?", "?"]
        rewards = d.get("rewards") or [None, None]
        steps = d.get("steps") or []
        decks = [None, None]
        if len(steps) > 1:
            for a in (0, 1):
                act = steps[1][a].get("action") if isinstance(steps[1][a], dict) else None
                if isinstance(act, list) and len(act) == 60:
                    decks[a] = act
        labels = [deck_label(decks[a]) if decks[a] else "?" for a in (0, 1)]
        for a in (0, 1):
            total_sides += 1
            is_top = teams[a] in top_teams
            won = rewards[a] == 1
            if is_top:
                deck_sides[(teams[a], labels[a])] += 1
            if is_top and won:
                winning_sides += 1
                opp_available[teams[1 - a] in top_teams and rewards[1 - a] == 1] += 1

        for i in range(1, len(steps) - 1):
            a = active_with_select(steps[i])
            if a is None:
                continue
            # only mine winning top-team sides
            if not (teams[a] in top_teams and rewards[a] == 1):
                continue
            obs = steps[i][a]["observation"]
            sel = obs.get("select")
            cur = obs.get("current")
            action = steps[i + 1][a].get("action")
            nopt = len(sel.get("option") or [])
            valid = (isinstance(action, list) and action
                     and all(isinstance(x, int) and 0 <= x < nopt for x in action)
                     and sel.get("minCount", 1) <= len(action) <= sel.get("maxCount", 1))
            if valid:
                idx_valid += 1
            else:
                idx_invalid += 1
                continue
            per_team_all[teams[a]] += 1

            stype = sel.get("type")
            mn, mx = sel.get("minCount", 1), sel.get("maxCount", 1)
            if sel is None:
                cat["deck-sel"] += 1
            elif stype == ST_MAIN and mn == 1 and mx == 1 and nopt > 1:
                cat["MAIN-single"] += 1
                per_team[teams[a]] += 1
                per_deck[labels[a]] += 1
                if cur is not None:
                    try:
                        s = main.encode_state(cur)
                        o = main.encode_options(sel, cur)
                        assert len(s) == 170 and len(o) == nopt and len(o[0]) == 41
                        assert 0 <= action[0] < nopt
                        enc_ok += 1
                    except Exception as e:
                        enc_fail[type(e).__name__ + ": " + str(e)[:60]] += 1
                else:
                    enc_fail["no current"] += 1
            elif stype == ST_MAIN:
                cat["MAIN-multi"] += 1
            else:
                cat["non-MAIN(type=%d)" % stype] += 1

    total = sum(cat.values())
    print(f"episodes: {len(files)}   sides: {total_sides}   "
          f"winning top-team sides: {winning_sides}\n")
    print(f"index recovery (steps[i].select <-> steps[i+1].action): "
          f"valid {idx_valid}  invalid {idx_invalid}  "
          f"({100*idx_valid/max(1,idx_valid+idx_invalid):.1f}% clean)\n")
    print("winning top-team decisions by category:")
    for k, v in cat.most_common():
        print(f"  {k:24s} {v:6d}  ({100*v/max(1,total):.0f}%)")
    print(f"\nMAIN-single encodability (train_policy.py 170+41 scheme):")
    print(f"  encode OK   : {enc_ok}")
    if enc_fail:
        for k, v in enc_fail.most_common(6):
            print(f"  encode FAIL : {v:5d}  {k}")
    print(f"\nper-team WINNING MAIN-single targets:")
    for t in sorted(top_teams, key=lambda x: -per_team[x]):
        print(f"  {t:28s} {per_team[t]:6d}  (of {per_team_all[t]} total decisions)")
    print(f"\nper-DECK WINNING MAIN-single targets (BC target-pick table):")
    for k, v in per_deck.most_common():
        print(f"  {k:44s} {v:6d}")
    print(f"\ndeck usage among top-team sides (meta table):")
    for (t, lbl), v in deck_sides.most_common(20):
        print(f"  {t:24s} {lbl:44s} {v:3d} sides")
    print(f"\nopponent-side availability in winning-top-team games:")
    print(f"  games where opponent is ALSO a winning top team (both sides usable): "
          f"{opp_available.get(True,0)}")
    print(f"  games where only the one top-team side is usable: {opp_available.get(False,0)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/top_replays")
    ap.add_argument("--leaderboard", default=None,
                    help="CSV snapshot; use its top 10 teams instead of the builtin set")
    args = ap.parse_args()
    teams = None
    if args.leaderboard:
        import csv as _csv
        rows = list(_csv.DictReader(open(args.leaderboard, encoding="utf-8")))
        teams = [r["team"] for r in rows[:10]]
        print("teams from leaderboard:", teams, "\n")
    run(args.dir, teams)
