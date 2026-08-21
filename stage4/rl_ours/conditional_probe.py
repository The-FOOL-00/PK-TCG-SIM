"""Phase 1 follow-up: test the mechanism behind the top divergence cell.

Hypothesis: ATTACK ends the turn; every other action is free. Top-10 therefore
exhaust free value first and attack LAST. Our WEIGHT_LETHAL = 100000 fires the
instant a KO is available, spending the rest of the turn.

Measures, per own turn that contained an attack: how many non-attack MAIN
decisions preceded the attack, and what they were.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

GRIMM = "Marnie's Grimmsnarl ex / Munkidori"
NAME = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
        11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END"}


def walk(fp, want_team=None):
    try:
        js = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return
    steps = js.get("steps") or []
    if len(steps) < 2:
        return
    tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]
    for seat in (0, 1):
        if want_team is not None and (seat >= len(tn) or tn[seat] not in want_team):
            continue
        act = steps[1][seat].get("action")
        if not (isinstance(act, list) and len(act) == 60):
            continue
        a = archetype(act)
        if not a or a["label"] != GRIMM:
            continue
        per_turn = defaultdict(list)
        for i in range(len(steps) - 1):
            e = steps[i][seat]
            if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                continue
            obs = e.get("observation") or {}
            sel = obs.get("select") or {}
            if sel.get("type") != 0:
                continue
            opts = sel.get("option") or []
            if len(opts) < 2:
                continue
            a2 = steps[i + 1][seat].get("action")
            if not (isinstance(a2, list) and len(a2) == 1):
                continue
            ci = a2[0]
            if not isinstance(ci, int) or ci >= len(opts):
                continue
            t = (obs.get("current") or {}).get("turn") or 0
            per_turn[t].append(NAME.get((opts[ci] or {}).get("type"), "?"))
        yield per_turn


def summarise(label, dirs, teams_by_dir=None):
    before = []
    kinds = Counter()
    turns_with_attack = turns_total = 0
    ability_turns = 0
    for d in dirs:
        wt = (teams_by_dir or {}).get(str(d))
        for fp in sorted(Path(d).glob("*.json")):
            for per_turn in walk(fp, wt):
                for t, seq in per_turn.items():
                    turns_total += 1
                    if "ABILITY" in seq:
                        ability_turns += 1
                    if "ATTACK" in seq:
                        turns_with_attack += 1
                        k = seq.index("ATTACK")
                        before.append(k)
                        for s in seq[:k]:
                            kinds[s] += 1
    before.sort()
    n = len(before)
    print(f"\n=== {label} ===")
    print(f"own turns                     : {turns_total}")
    print(f"turns containing an attack    : {turns_with_attack} "
          f"({turns_with_attack/max(1,turns_total)*100:.1f}%)")
    print(f"turns using an ability        : {ability_turns} "
          f"({ability_turns/max(1,turns_total)*100:.1f}%)")
    if n:
        print(f"actions taken BEFORE the attack, that turn:")
        print(f"   mean={sum(before)/n:.2f}  median={before[n//2]}  "
              f"p90={before[int(n*0.9)]}  max={before[-1]}")
        print(f"   attacked as the FIRST action of the turn: "
              f"{sum(1 for b in before if b == 0)}/{n} = "
              f"{sum(1 for b in before if b == 0)/n*100:.1f}%")
        tot = sum(kinds.values()) or 1
        print("   what preceded it: " + "  ".join(
            f"{k}={v/tot*100:.0f}%" for k, v in kinds.most_common()))


if __name__ == "__main__":
    A = REPO / "analysis/phase2_meta_shift"
    dirs = [A / "replays_top10_jul21", A / "replays_top10_jul22",
            A / "replays_top10_jul26"]
    teams = {}
    for d, prof in zip(dirs, ["profile_top10_jul21.json", "profile_top10_jul22.json",
                              "profile_top10_jul26.json"]):
        teams[str(d)] = set(json.loads((A / prof).read_text(encoding="utf-8"))["teams"])
    summarise("TOP-10 Grimmsnarl", dirs, teams)
    summarise("OURS Grimmsnarl (D1)", [REPO / "scratchpad/s3/horizon_D1"])
