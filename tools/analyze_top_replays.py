"""Phase 1A intel: characterize top-ladder teams from their episode replays.

Per replay extracts: teams, winner, both 60-card decklists, per-player
decision timing (remainingOverageTime deltas), and game-plan signatures
(first-attack turn, game length, denial/Rare Candy/energy usage) from the
visualize transcript. Aggregates per team.

Run:  python tools/analyze_top_replays.py [--dir data/top_replays] [--json OUT]
"""

import argparse
import glob
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

_CARDS = None


def cards():
    global _CARDS
    if _CARDS is None:
        from cg.api import all_attack, all_card_data
        cs = {c.cardId: c for c in all_card_data()}
        ats = {a.attackId: a for a in all_attack()}
        _CARDS = (cs, ats)
    return _CARDS


def name(cid):
    cs, _ = cards()
    return cs[cid].name if cid in cs else f"#{cid}"


def deck_signature(deck):
    cs, ats = cards()
    c = Counter(deck)
    pkmn = [cid for cid in c if cs.get(cid) and cs[cid].cardType == 0]
    energy = sum(n for cid, n in c.items() if cs.get(cid) and cs[cid].cardType == 5)
    etypes = sorted({cs[cid].energyType for cid in c
                     if cs.get(cid) and cs[cid].cardType == 5})
    heads = sorted(pkmn, key=lambda x: (cs[x].megaEx, cs[x].ex, cs[x].hp),
                   reverse=True)[:2]
    return {"label": " / ".join(name(h) for h in heads),
            "energy": energy, "etypes": [str(e) for e in etypes],
            "pokemon_ids": tuple(sorted(pkmn))}


def parse(fp):
    d = json.loads(Path(fp).read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        return None   # agent-log export (list of steps), handled separately
    info = d.get("info") or {}
    teams = info.get("TeamNames") or ["?", "?"]
    rewards = d.get("rewards") or [None, None]
    steps = d.get("steps") or []
    decks = [None, None]
    if len(steps) > 1:
        for a in (0, 1):
            act = steps[1][a].get("action") if isinstance(steps[1][a], dict) else None
            if isinstance(act, list) and len(act) == 60:
                decks[a] = act

    # decision timing: remainingOverageTime is per-player and only decreases on
    # that player's own decisions. Collect each player's series, diff it.
    overage = {0: [], 1: []}
    for step in steps:
        for a in (0, 1):
            ent = step[a] if a < len(step) else None
            if not isinstance(ent, dict):
                continue
            obs = ent.get("observation") or {}
            rot = obs.get("remainingOverageTime")
            if isinstance(rot, (int, float)) and ent.get("status") == "ACTIVE":
                overage[a].append(rot)
    dec_ms = {0: [], 1: []}
    for a in (0, 1):
        seq = overage[a]
        for i in range(1, len(seq)):
            dt = seq[i - 1] - seq[i]
            if 0 < dt < 600:
                dec_ms[a].append(dt * 1000.0)

    # game plan from the visualize transcript (string enum log types)
    step0 = steps[0][0] if steps else {}
    vis = (step0.get("visualize")
           or (step0.get("observation") or {}).get("visualize")) or []
    reason = None
    last_turn = 0
    first_attack = [None, None]
    denial = Counter()      # per player: Enhanced Hammer / Boss's Orders plays
    rare_candy = Counter()
    attaches = Counter()
    for entry in vis:
        cur = entry.get("current") or {}
        last_turn = max(last_turn, cur.get("turn") or 0)
        for lg in entry.get("logs") or []:
            t, pi = lg.get("type"), lg.get("playerIndex")
            if t == "Result":
                reason = lg.get("reason")
            elif t == "Attack" and pi in (0, 1) and first_attack[pi] is None:
                first_attack[pi] = cur.get("turn")
            elif t == "Play" and pi in (0, 1):
                nm = name(lg.get("cardId"))
                if nm == "Enhanced Hammer" or nm == "Boss’s Orders" or nm == "Boss's Orders":
                    denial[pi] += 1
                if nm == "Rare Candy":
                    rare_candy[pi] += 1
            elif t == "Attach" and pi in (0, 1):
                attaches[pi] += 1
    return {"file": Path(fp).stem, "teams": teams, "rewards": rewards,
            "decks": decks, "dec_ms": dec_ms, "reason": reason,
            "turns": last_turn, "first_attack": first_attack,
            "denial": dict(denial), "rare_candy": dict(rare_candy),
            "attaches": dict(attaches)}


def pct(v, q):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def run(directory, json_out):
    files = sorted(glob.glob(str(REPO / directory / "*.json")))
    games = [g for g in (parse(f) for f in files) if g is not None]
    print(f"parsed {len(games)} episode replays from {directory} "
          f"({len(files) - len(games)} non-episode files skipped)\n")

    # per-team aggregation
    team_games = defaultdict(list)   # team -> list of (game, side)
    for g in games:
        for a in (0, 1):
            if g["teams"][a] != "?":
                team_games[g["teams"][a]].append((g, a))

    summary = {}
    order = sorted(team_games, key=lambda t: -len(team_games[t]))
    for team in order:
        gs = team_games[team]
        wins = sum(1 for g, a in gs if g["rewards"][a] == 1)
        decks = Counter()
        etypes = Counter()
        all_ms = []
        turns = []
        fa = []
        denial = 0
        rc = 0
        for g, a in gs:
            if g["decks"][a]:
                sig = deck_signature(g["decks"][a])
                decks[(sig["label"], sig["energy"], tuple(sig["etypes"]))] += 1
            all_ms += g["dec_ms"][a]
            if g["turns"]:
                turns.append(g["turns"])
            if g["first_attack"][a]:
                fa.append(g["first_attack"][a])
            denial += g["denial"].get(a, 0)
            rc += g["rare_candy"].get(a, 0)
        n = len(gs)
        summary[team] = {
            "sides": n, "wins": wins,
            "decks": [{"deck": k[0], "energy": k[1], "etypes": list(k[2]), "n": v}
                      for k, v in decks.most_common()],
            "timing_ms": {"n": len(all_ms),
                          "median": st.median(all_ms) if all_ms else None,
                          "p50": pct(all_ms, 0.50), "p90": pct(all_ms, 0.90),
                          "p99": pct(all_ms, 0.99), "max": max(all_ms) if all_ms else None},
            "avg_turns": st.mean(turns) if turns else None,
            "avg_first_attack": st.mean(fa) if fa else None,
            "denial_per_game": denial / n, "rare_candy_per_game": rc / n,
        }
        t = summary[team]["timing_ms"]
        arch = ("SEARCH (median>500ms)" if t["median"] and t["median"] > 500
                else "FAST POLICY (median<50ms)" if t["median"] and t["median"] < 50
                else "MIXED/other")
        print(f"== {team}  ({n} sides, {wins}W/{n-wins}L) ==")
        print(f"   decks: {[ (d['deck'], 'E'+str(d['energy']), d['n']) for d in summary[team]['decks'] ]}")
        print(f"   timing: median {t['median'] and round(t['median'])}ms  p90 {t['p90'] and round(t['p90'])}ms  "
              f"p99 {t['p99'] and round(t['p99'])}ms  max {t['max'] and round(t['max'])}ms  (n={t['n']})  -> {arch}")
        print(f"   game: avg {summary[team]['avg_turns'] and round(summary[team]['avg_turns'],1)} turns, "
              f"first-attack turn {summary[team]['avg_first_attack'] and round(summary[team]['avg_first_attack'],1)}, "
              f"denial/game {summary[team]['denial_per_game']:.1f}, rare-candy/game {summary[team]['rare_candy_per_game']:.1f}")
        # losses: who beat them, what deck
        losses = [(g, a) for g, a in gs if g["rewards"][a] == -1]
        for g, a in losses:
            opp = g["teams"][1 - a]
            odeck = deck_signature(g["decks"][1 - a])["label"] if g["decks"][1 - a] else "?"
            print(f"     LOSS to {opp} ({odeck}) reason={g['reason']} turns={g['turns']} [{g['file']}]")
        print()

    if json_out:
        Path(REPO / json_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"json written: {json_out}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/top_replays")
    ap.add_argument("--json", default="runs/top_replays_intel.json")
    args = ap.parse_args()
    run(args.dir, args.json)
