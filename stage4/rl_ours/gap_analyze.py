"""Behavioral gap diagnosis over the 28 canary ladder replays.

Alignment: action at steps[i+1][seat] answers the select in
steps[i][seat]['observation'] (verified empirically).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUB = 54991680
OT = {0: "NUMBER", 1: "YES", 2: "NO", 3: "CARD", 4: "TOOL_CARD", 5: "ENERGY_CARD",
      6: "ENERGY", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY", 11: "DISCARD",
      12: "RETREAT", 13: "ATTACK", 14: "END", 15: "SKILL", 16: "SPECIAL_COND"}
ST_MAIN = 0
DEV = {"PLAY", "ATTACH", "EVOLVE", "ABILITY"}
PASSIVE = {"END", "RETREAT"}

cards = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in cards.get("cards", {}).items()}


def is_basic_poke(cid):
    c = CARDS.get(cid) or {}
    return c.get("cardType") == 0 and bool(c.get("basic"))


def main():
    eps = json.loads((REPO / "scratchpad/s3/eps_54991680.json").read_text())["episodes"]
    ours = {e["id"]: [a for a in e["agents"] if a.get("submissionId") == SUB][0].get("index", 0)
            for e in eps if e.get("state") == "COMPLETED"}
    reward = {e["id"]: [a for a in e["agents"] if a.get("submissionId") == SUB][0].get("reward")
              for e in eps if e.get("state") == "COMPLETED"}

    G = {"main": Counter(), "chosen": Counter(), "atk_legal_turns": 0, "own_turns": 0,
         "atk_turns": 0, "atk_when_legal_dec": [0, 0],
         "benchlegal_dec": 0, "benchtook_dec": 0,
         "first_evo": [], "first_atk": [], "hand": defaultdict(list),
         "xdraw": [], "dtime": []}
    per_game = []

    for fp in sorted(Path(REPO / "scratchpad/s3/canary_replays").glob("*.json")):
        eid = int(fp.stem)
        if eid not in ours:
            continue
        seat = ours[eid]
        d = json.loads(fp.read_text(encoding="utf-8"))
        steps = d["steps"]
        vis = (steps[0][0].get("visualize")
               or (steps[0][0].get("observation") or {}).get("visualize")) or []

        # ---- per-turn facts from the visualize log
        turn_owner, draws, evos, atks = {}, defaultdict(int), defaultdict(int), defaultdict(int)
        hand_start, last = {}, 0
        first_evo = first_atk = None
        for entry in vis:
            cur = entry.get("current") or {}
            t = cur.get("turn") or last
            last = max(last, t)
            pl = cur.get("players") or [{}, {}]
            for l in entry.get("logs") or []:
                ty, pi = l.get("type"), l.get("playerIndex")
                if ty == "TurnStart" and pi is not None:
                    turn_owner[t] = pi
                    if pi == seat and t not in hand_start:
                        hc = (pl[pi] or {}).get("handCount")
                        if hc is not None:
                            hand_start[t] = hc
                elif ty == "Draw" and pi == seat and t > 0:
                    draws[t] += 1
                elif ty == "Evolve" and pi == seat:
                    evos[t] += 1
                    first_evo = t if first_evo is None else first_evo
                elif ty == "Attack" and pi == seat:
                    atks[t] += 1
                    first_atk = t if first_atk is None else first_atk

        own = sorted(t for t, o in turn_owner.items() if o == seat)
        G["own_turns"] += len(own)
        G["atk_turns"] += sum(1 for t in own if atks[t])
        if first_evo: G["first_evo"].append(first_evo)
        if first_atk: G["first_atk"].append(first_atk)
        for k, idx in (("T3", 1), ("T5", 2), ("T7", 3)):
            if len(own) > idx and own[idx] in hand_start:
                G["hand"][k].append(hand_start[own[idx]])
        if own:
            G["xdraw"].append(sum(max(0, draws[t] - 1) for t in own) / len(own))

        # ---- per-decision facts (MAIN only), obs[i] -> action[i+1]
        g_bench_legal = g_bench_took = g_atk_legal = g_atk_took = 0
        turns_with_atk_legal = set()
        for i in range(len(steps) - 1):
            e = steps[i][seat]
            if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                continue
            obs = e.get("observation") or {}
            sel = obs.get("select") or {}
            if sel.get("type") != ST_MAIN:
                continue
            opts = sel.get("option") or []
            act = steps[i + 1][seat].get("action")
            if not isinstance(act, list) or len(act) != 1:
                continue
            ci = act[0]
            if not isinstance(ci, int) or ci >= len(opts):
                continue
            types = [OT.get((o or {}).get("type")) for o in opts]
            chosen = types[ci]
            G["main"].update(t for t in types if t)
            G["chosen"][chosen] += 1
            turn = (obs.get("current") or {}).get("turn") or 0

            if "ATTACK" in types:
                turns_with_atk_legal.add(turn)
                g_atk_legal += 1
                G["atk_when_legal_dec"][1] += 1
                if chosen == "ATTACK":
                    g_atk_took += 1
                    G["atk_when_legal_dec"][0] += 1
            # bench-legal: a PLAY option whose hand card is a Basic Pokemon
            hand = ((obs.get("current") or {}).get("players") or [{}, {}])[seat].get("hand") or []
            bench_opt = False
            for j, o in enumerate(opts):
                if types[j] != "PLAY":
                    continue
                ix = (o or {}).get("index")
                if isinstance(ix, int) and ix < len(hand) and hand[ix]:
                    if is_basic_poke((hand[ix] or {}).get("id")):
                        bench_opt = True
                        break
            if bench_opt:
                g_bench_legal += 1
                G["benchlegal_dec"] += 1
                if chosen == "PLAY":
                    g_bench_took += 1
                    G["benchtook_dec"] += 1
        G["atk_legal_turns"] += len(turns_with_atk_legal & set(own))

        # deliberation time
        prev = None
        for i in range(1, len(steps)):
            e = steps[i][seat]
            ot = (e.get("observation") or {}).get("remainingOverageTime")
            if ot is None: continue
            if prev is not None and e.get("status") == "ACTIVE":
                dt = prev - ot
                if 0 <= dt < 60: G["dtime"].append(dt * 1000)
            prev = ot

        per_game.append({"ep": eid, "won": reward[eid] == 1, "turns": last,
                         "own_turns": len(own), "atk_turns": sum(1 for t in own if atks[t]),
                         "bench_legal": g_bench_legal, "bench_took": g_bench_took,
                         "atk_legal_dec": g_atk_legal, "atk_took_dec": g_atk_took,
                         "first_evo": first_evo, "first_atk": first_atk})

    import statistics as st
    print("=" * 78)
    print("PRIORITY 3/4 — decision-type distribution (MAIN decisions)")
    print("=" * 78)
    tot = sum(G["chosen"].values())
    print(f"{'type':<14s} {'chosen':>7s} {'share':>7s} {'offered':>8s} {'take-rate':>10s}")
    for t, c in G["chosen"].most_common():
        off = G["main"][t]
        print(f"{t:<14s} {c:>7d} {c/tot*100:>6.1f}% {off:>8d} {c/off*100 if off else 0:>9.1f}%")
    print(f"\n  categorised: development {sum(G['chosen'][t] for t in DEV)/tot*100:.1f}%  "
          f"ATTACK {G['chosen']['ATTACK']/tot*100:.1f}%  "
          f"passive(END/RETREAT) {sum(G['chosen'][t] for t in PASSIVE)/tot*100:.1f}%")
    print()
    print("=" * 78)
    print("ATTACK availability vs uptake  (Sanjay §6n units)")
    print("=" * 78)
    print(f"  own turns                       : {G['own_turns']}")
    print(f"  turns containing an attack      : {G['atk_turns']}  "
          f"= {G['atk_turns']/G['own_turns']*100:.1f}%  [field 47-64%]")
    print(f"  turns where ATTACK was legal    : {G['atk_legal_turns']}  "
          f"= {G['atk_legal_turns']/G['own_turns']*100:.1f}%  [Sanjay top 77% / his agent 53%]")
    if G['atk_legal_turns']:
        print(f"  attack taken WHEN legal (turns) : "
              f"{G['atk_turns']/G['atk_legal_turns']*100:.1f}%  [Sanjay top 92% / his 86%]")
    tk, tl = G["atk_when_legal_dec"]
    print(f"  per-DECISION attack-when-legal  : {tk}/{tl} = {tk/tl*100 if tl else 0:.1f}%  (sub-decision unit, inflated)")
    print()
    print("=" * 78)
    print("PRIORITY 2 — bench development")
    print("=" * 78)
    print(f"  decisions where benching a Basic was legal : {G['benchlegal_dec']}")
    print(f"  ... of which we played a card             : {G['benchtook_dec']} "
          f"= {G['benchtook_dec']/G['benchlegal_dec']*100 if G['benchlegal_dec'] else 0:.1f}%")
    print()
    wins = [g for g in per_game if g["won"]]; losses = [g for g in per_game if not g["won"]]
    def agg(rows, k1, k2):
        a = sum(r[k1] for r in rows); b = sum(r[k2] for r in rows)
        return f"{a}/{b} = {a/b*100 if b else 0:.1f}%"
    print(f"  bench-take  WINS  : {agg(wins,'bench_took','bench_legal')}")
    print(f"  bench-take  LOSSES: {agg(losses,'bench_took','bench_legal')}")
    print(f"  attack-take WINS  : {agg(wins,'atk_took_dec','atk_legal_dec')}")
    print(f"  attack-take LOSSES: {agg(losses,'atk_took_dec','atk_legal_dec')}")
    print()
    print("  shortest games (board-wipe candidates):")
    for g in sorted(per_game, key=lambda x: x["turns"])[:8]:
        print(f"    ep{g['ep']} turns={g['turns']:>2d} ownT={g['own_turns']:>2d} "
              f"{'W' if g['won'] else 'L'} benchLegal={g['bench_legal']:>2d} "
              f"benchTook={g['bench_took']:>2d} firstEvo={g['first_evo']} firstAtk={g['first_atk']}")
    print()
    print("=" * 78)
    print("PRIORITY 4 — scorecard inputs")
    print("=" * 78)
    print(f"  first attack turn   : {st.mean(G['first_atk']):.2f}   [field 4.1-5.6]")
    print(f"  first evolution turn: {st.mean(G['first_evo']):.2f}   [field 3.6-4.2]")
    for k in ("T3", "T5", "T7"):
        v = G["hand"][k]
        print(f"  hand {k}             : {st.mean(v):.2f} (n={len(v)})")
    print(f"  extra draws / turn  : {st.mean(G['xdraw']):.2f}   [field 2.1-2.6]")
    print(f"  dtime median        : {st.median(G['dtime']):.0f} ms (n={len(G['dtime'])})")


if __name__ == "__main__":
    main()
