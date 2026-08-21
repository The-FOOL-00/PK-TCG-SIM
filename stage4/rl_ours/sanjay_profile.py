"""Profile Sanjay's Archaludon submission from replays, in our standard units."""
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

OT_ATTACK = 13
NAME = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY", 11: "DISCARD",
        12: "RETREAT", 13: "ATTACK", 14: "END"}


def seat_map(sub):
    eps = json.loads((REPO / f"scratchpad/s3/eps_{sub}.json").read_text(encoding="utf-8"))["episodes"]
    m = {}
    for e in eps:
        for a in e["agents"]:
            if a.get("submissionId") == sub:
                m[e["id"]] = {"seat": a.get("index", 0),
                              "reward": a.get("reward"), "score": a.get("updatedScore")}
    return m


def opp_archetype(steps, seat):
    act = steps[1][1 - seat].get("action")
    if isinstance(act, list) and len(act) == 60:
        a = archetype(act)
        return a["label"] if a else "unknown"
    return "unknown"


def profile(sub, deck_dir):
    smap = seat_map(sub)
    decks = collections.Counter()
    opp_archs = collections.Counter()
    wl_vs = collections.defaultdict(lambda: collections.Counter())
    dur = []
    own_total = prizes_total = atk_total = atklegal_total = 0
    own_turns_per_game, prizes_per_game = [], []
    first_atk, first_evo, first_prize = [], [], []
    e1_style_before_attack = []
    ability_turns = attack_turns_total = 0
    draws = []
    games = 0
    decklist = None

    for fp in sorted(Path(REPO / deck_dir).glob("*.json")):
        eid = int(fp.stem)
        info = smap.get(eid)
        if not info:
            continue
        seat = info["seat"]
        js = json.loads(fp.read_text(encoding="utf-8"))
        steps = js.get("steps") or []
        if len(steps) < 2:
            continue
        games += 1
        act = steps[1][seat].get("action")
        if isinstance(act, list) and len(act) == 60:
            a = archetype(act)
            decks[a["label"] if a else "unknown"] += 1
            if decklist is None:
                decklist = act
        oa = opp_archetype(steps, seat)
        opp_archs[oa] += 1
        won = info["reward"] == 1
        wl_vs[oa]["W" if won else "L"] += 1

        for step in steps:
            for e in step:
                if isinstance(e, dict) and e.get("duration") is not None:
                    dur.append(e["duration"])

        vis = (steps[0][0].get("visualize")
               or (steps[0][0].get("observation") or {}).get("visualize")) or []
        turn_owner, atk_log = {}, collections.defaultdict(int)
        last = 0
        for e in vis:
            c = e.get("current") or {}
            t = c.get("turn") or last
            last = max(last, t)
            for l in e.get("logs") or []:
                if l.get("type") == "TurnStart" and l.get("playerIndex") is not None:
                    turn_owner[t] = l["playerIndex"]
                elif l.get("type") == "Attack" and l.get("playerIndex") is not None:
                    atk_log[(l["playerIndex"], t)] += 1

        own = sorted(t for t, o in turn_owner.items() if o == seat)
        own_turns_per_game.append(len(own))
        own_total += len(own)
        n_atk_turns = sum(1 for t in own if atk_log[(seat, t)])
        atk_total += n_atk_turns

        legal = set()
        p0 = plast = fpt = fevo = None
        seq_by_turn = collections.defaultdict(list)
        for i in range(len(steps) - 1):
            e = steps[i][seat]
            if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                continue
            obs = e.get("observation") or {}
            sel = obs.get("select") or {}
            cur = obs.get("current") or {}
            me = cur.get("yourIndex")
            pl = cur.get("players") or []
            if me is not None and me < len(pl):
                n = len(pl[me].get("prize") or [])
                if n > 0:
                    p0 = n if p0 is None else max(p0, n)
                    plast = n
                    if fpt is None and n < p0:
                        fpt = cur.get("turn") or 0
            if sel.get("type") != 0:
                continue
            opts = sel.get("option") or []
            a2 = steps[i + 1][seat].get("action")
            if not (isinstance(a2, list) and len(a2) == 1):
                continue
            ci = a2[0]
            if not isinstance(ci, int) or ci >= len(opts):
                continue
            turn = cur.get("turn") or 0
            types = [(o or {}).get("type") for o in opts]
            if OT_ATTACK in types:
                legal.add(turn)
            ct = types[ci]
            seq_by_turn[turn].append(NAME.get(ct, ct))
            if ct == 9 and fevo is None:
                fevo = turn
        legal_own = legal & set(own)
        atklegal_total += len(legal_own)
        if p0 is not None and plast is not None:
            prizes_per_game.append(p0 - plast)
            prizes_total += p0 - plast
        if fpt:
            first_prize.append(fpt)
        if fevo:
            first_evo.append(fevo)
        first_a = None
        for t in sorted(seq_by_turn):
            if "ATTACK" in seq_by_turn[t]:
                if first_a is None:
                    first_a = t
                attack_turns_total += 1
                if "ABILITY" in seq_by_turn[t]:
                    ability_turns += 1
                k = seq_by_turn[t].index("ATTACK")
                e1_style_before_attack.append(k)
        if first_a:
            first_atk.append(first_a)

    def med(v):
        return sorted(v)[len(v) // 2] if v else 0

    def mean(v):
        return sum(v) / len(v) if v else 0.0

    dur.sort()
    print(f"\n{'='*70}\nSANJAY sub {sub}\n{'='*70}")
    print(f"games={games}  decks seen: {dict(decks)}")
    print(f"\ndecision durations: n={len(dur)} p50={mean(dur[:len(dur)//2+1]) if dur else 0:.4f}s "
          f"median={med(dur):.4f}s p90={dur[int(len(dur)*.9)] if dur else 0:.4f}s "
          f"p99={dur[int(len(dur)*.99)] if dur else 0:.4f}s max={dur[-1] if dur else 0:.4f}s")
    print(f"\nown turns/game: mean={mean(own_turns_per_game):.2f} median={med(own_turns_per_game)}")
    print(f"prizes/game: mean={mean(prizes_per_game):.2f}")
    print(f"PRIZE VELOCITY = {prizes_total}/{own_total} = {prizes_total/max(1,own_total):.4f}")
    print(f"attack-share/turn = {atk_total}/{own_total} = {atk_total/max(1,own_total)*100:.1f}%")
    print(f"attack-when-legal/turn = {atk_total}/{atklegal_total} = "
          f"{atk_total/max(1,atklegal_total)*100:.1f}%")
    print(f"first attack turn: mean={mean(first_atk):.2f} (n={len(first_atk)})")
    print(f"first evolution turn: mean={mean(first_evo):.2f} (n={len(first_evo)})")
    print(f"turn of first prize: mean={mean(first_prize):.2f} (n={len(first_prize)})")
    print(f"actions-before-attack: mean={mean(e1_style_before_attack):.2f} "
          f"median={med(e1_style_before_attack)} (n={len(e1_style_before_attack)})")
    print(f"turns using ability (of attacking turns): {ability_turns}/{attack_turns_total} = "
          f"{ability_turns/max(1,attack_turns_total)*100:.1f}%")
    print(f"\nopponent archetypes faced (n={sum(opp_archs.values())}):")
    for k, v in opp_archs.most_common():
        w = wl_vs[k]
        print(f"  {k[:44]:<44s} {v:3d}  W-L={w['W']}-{w['L']}")
    return decklist


if __name__ == "__main__":
    import sys as _s
    for sub, d in ((55082948, "scratchpad/s3/sanjay_55082948"),
                   (55084706, "scratchpad/s3/sanjay_55084706")):
        dl = profile(sub, d)
        if dl:
            fn = REPO / f"scratchpad/s3/sanjay_deck_{sub}.csv"
            fn.write_text("\n".join(str(c) for c in dl) + "\n", encoding="utf-8")
            print(f"\n  -> deck written to {fn}")
