"""Per-TURN comparison (the project's standing unit) of our sides vs the
team-filtered top-10 Cynthia's Garchomp sides.

Turn ownership and attacks come from the `visualize` transcript (TurnStart /
Attack logs) -- the same source horizon_counters.py uses -- so these rows are
directly comparable to the existing tables. Prize counts come from the step
observations: players[i].prize holds prizes REMAINING for that player to take,
so a decrease means that player took prizes.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}
CYNTHIA_LINE = {379, 380, 381, 341, 342, 387}
OT_ATTACK = 13


def side_is_garchomp(steps, seat):
    seen = set()
    for i in range(min(len(steps), 40)):
        e = steps[i][seat]
        if not isinstance(e, dict):
            continue
        cur = (e.get("observation") or {}).get("current") or {}
        pl = cur.get("players") or []
        me = cur.get("yourIndex")
        if me is None or me >= len(pl):
            continue
        p = pl[me]
        for c in (p.get("hand") or []):
            if c:
                seen.add(c.get("id"))
        for pk in (p.get("active") or []) + (p.get("bench") or []):
            if pk:
                seen.add(pk.get("id"))
    return len(seen & CYNTHIA_LINE) >= 2


def analyse(d, label, teams=None, only_garchomp=True, seat_map=None):
    own_turns, atk_turns, legal_turns = [], [], []
    prizes_taken, first_prize_turn, game_turns = [], [], []
    tot_own = tot_atk = tot_legal = 0
    sides = 0

    for fp in sorted(Path(d).glob("*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = js.get("steps") or []
        if not steps:
            continue
        tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]

        if seat_map is not None:
            try:
                eid = int(fp.stem)
            except ValueError:
                continue
            if eid not in seat_map:
                continue
            which = (seat_map[eid],)
        else:
            which = (0, 1)

        vis = (steps[0][0].get("visualize")
               or (steps[0][0].get("observation") or {}).get("visualize")) or []
        turn_owner, atk_log = {}, defaultdict(int)
        last = 0
        for entry in vis:
            cur = entry.get("current") or {}
            t = cur.get("turn") or last
            last = max(last, t)
            for l in entry.get("logs") or []:
                ty, pi = l.get("type"), l.get("playerIndex")
                if ty == "TurnStart" and pi is not None:
                    turn_owner[t] = pi
                elif ty == "Attack" and pi is not None:
                    atk_log[(pi, t)] += 1

        for seat in which:
            if seat >= len(steps[0]):
                continue
            if teams is not None and (seat >= len(tn) or tn[seat] not in teams):
                continue
            if only_garchomp and not side_is_garchomp(steps, seat):
                continue
            sides += 1

            own = sorted(t for t, o in turn_owner.items() if o == seat)
            legal = set()
            prize0 = None
            prize_last = None
            fpt = None
            for i in range(len(steps) - 1):
                e = steps[i][seat]
                if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                    continue
                obs = e.get("observation") or {}
                cur = obs.get("current") or {}
                me = cur.get("yourIndex")
                pl = cur.get("players") or []
                if me is not None and me < len(pl):
                    n = len(pl[me].get("prize") or [])
                    # prize[] is EMPTY during setup before prizes are dealt, so
                    # the first reading is 0, not 6. Baseline on the max seen.
                    if n > 0:
                        prize0 = n if prize0 is None else max(prize0, n)
                        prize_last = n
                        if fpt is None and n < prize0:
                            fpt = cur.get("turn") or 0
                sel = obs.get("select") or {}
                if sel.get("type") != 0:
                    continue
                opts = sel.get("option") or []
                if any((o or {}).get("type") == OT_ATTACK for o in opts):
                    legal.add(cur.get("turn") or 0)

            n_own = len(own)
            n_atk = sum(1 for t in own if atk_log[(seat, t)])
            n_legal = len(legal & set(own))
            own_turns.append(n_own)
            atk_turns.append(n_atk)
            legal_turns.append(n_legal)
            tot_own += n_own
            tot_atk += n_atk
            tot_legal += n_legal
            game_turns.append(max(turn_owner) if turn_owner else 0)
            if prize0 is not None and prize_last is not None:
                prizes_taken.append(prize0 - prize_last)
            if fpt:
                first_prize_turn.append(fpt)

    def med(v):
        return sorted(v)[len(v) // 2] if v else 0

    def mean(v):
        return sum(v) / len(v) if v else 0.0

    print(f"\n{'='*72}\n{label}\n{'='*72}")
    print(f"sides = {sides}")
    print(f"  OWN TURNS PER GAME      mean={mean(own_turns):5.1f}  median={med(own_turns)}")
    print(f"  total game turns        mean={mean(game_turns):5.1f}  median={med(game_turns)}")
    print(f"  attack-share / own turn        = {tot_atk}/{tot_own} = "
          f"{(tot_atk/tot_own*100 if tot_own else 0):5.1f}%")
    print(f"  attack-when-legal / own turn   = {tot_atk}/{tot_legal} = "
          f"{(tot_atk/tot_legal*100 if tot_legal else 0):5.1f}%")
    print(f"  attack-legal turns / own turns = {tot_legal}/{tot_own} = "
          f"{(tot_legal/tot_own*100 if tot_own else 0):5.1f}%")
    print(f"  prizes taken / game     mean={mean(prizes_taken):5.2f}  median={med(prizes_taken)}  (n={len(prizes_taken)})")
    print(f"  turn of first prize     mean={mean(first_prize_turn):5.1f}  median={med(first_prize_turn)}  (n={len(first_prize_turn)})")
    return {"sides": sides, "own_mean": mean(own_turns),
            "atk_share": (tot_atk / tot_own if tot_own else 0),
            "atk_when_legal": (tot_atk / tot_legal if tot_legal else 0),
            "legal_share": (tot_legal / tot_own if tot_own else 0),
            "prizes": mean(prizes_taken), "first_prize": mean(first_prize_turn)}


def vn_seats(sub):
    m = {}
    for f in (REPO / "scratchpad" / "s3").glob("eps_*.json"):
        for ep in json.loads(f.read_text(encoding="utf-8")).get("episodes", []):
            for a in ep.get("agents", []):
                if a.get("submissionId") == sub:
                    m[ep["id"]] = a.get("index", 0)
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all")
    ap.parse_args()
    T = {"junlee789", "Yudai Ueno"}
    analyse(REPO / "analysis/phase2_meta_shift/replays_top10_jul22",
            "TOP-10 Garchomp (jul22, team-filtered)", teams=T)
    analyse(REPO / "analysis/phase2_meta_shift/replays_top10_jul21",
            "TOP-10 Garchomp (jul21, team-filtered)", teams=T)
    analyse(REPO / "scratchpad/s3/horizon_H1", "OURS H1 self-play (search, PILOT=garchomp)",
            only_garchomp=False)
    analyse(REPO / "scratchpad/s3/horizon_H3", "OURS H3 v1-alone (PILOT=garchomp)",
            only_garchomp=False)
    analyse(REPO / "scratchpad/s3/vn_replays", "OURS VN ladder (ship config)",
            only_garchomp=False, seat_map=vn_seats(55003807))
