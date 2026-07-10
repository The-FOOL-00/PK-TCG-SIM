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


def active_with_select(step):
    for a in (0, 1):
        e = step[a]
        if isinstance(e, dict) and e.get("status") == "ACTIVE" \
                and (e.get("observation") or {}).get("select") is not None:
            return a
    return None


def run():
    files = sorted((REPO / "data" / "top_replays").glob("*.json"))
    cat = Counter()
    enc_ok = 0
    enc_fail = Counter()
    per_team = Counter()          # winning top-team MAIN-single decisions
    per_team_all = Counter()      # all winning top-team decisions
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
        for a in (0, 1):
            total_sides += 1
            is_top = teams[a] in TOP_TEAMS
            won = rewards[a] == 1
            if is_top and won:
                winning_sides += 1
                opp_available[teams[1 - a] in TOP_TEAMS and rewards[1 - a] == 1] += 1

        for i in range(1, len(steps) - 1):
            a = active_with_select(steps[i])
            if a is None:
                continue
            # only mine winning top-team sides
            if not (teams[a] in TOP_TEAMS and rewards[a] == 1):
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
    for t in TOP_TEAMS:
        print(f"  {t:14s} {per_team[t]:6d}  (of {per_team_all[t]} total decisions)")
    print(f"\nopponent-side availability in winning-top-team games:")
    print(f"  games where opponent is ALSO a winning top team (both sides usable): "
          f"{opp_available.get(True,0)}")
    print(f"  games where only the one top-team side is usable: {opp_available.get(False,0)}")


if __name__ == "__main__":
    run()
