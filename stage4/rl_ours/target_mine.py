"""Target-selection mining: does WHICH opponent bench Pokemon top-10 Grimmsnarl
pilots pick (Shadow Bullet splash, Boss's Orders) vary by opponent archetype?

Two contexts, both engine-verified against main.py's SC_ enum:
  SC_DAMAGE  (15) -- Shadow Bullet's own splash target (fires most attacks)
  SC_SWITCH  (3)  -- Boss's Orders / gust-style forced switch

For each decision, records the chosen target's rank among the legal targets on
three axes an override could plausibly use: prize value (ex=2, mega=3, else 1),
energy count (denial), and HP ratio (finish-off potential). "Chose the max on
axis X" is the behavioural signal; divergence by matchup is the leverage.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}
GRIMM = "Marnie's Grimmsnarl ex / Munkidori"
SC_SWITCH, SC_DAMAGE = 3, 15
AREA_BENCH = 5

A_DIR = REPO / "analysis/phase2_meta_shift"
TOP_DIRS = [A_DIR / "replays_top10_jul21", A_DIR / "replays_top10_jul22",
            A_DIR / "replays_top10_jul26"]
TEAMS = {}
for d, prof in zip(TOP_DIRS, ["profile_top10_jul21.json", "profile_top10_jul22.json",
                              "profile_top10_jul26.json"]):
    TEAMS[str(d)] = set(json.loads((A_DIR / prof).read_text(encoding="utf-8"))["teams"])


def prizes_for_ko(cid):
    c = CARDS.get(cid) or {}
    if c.get("megaEx"):
        return 3
    if c.get("ex"):
        return 2
    return 1


def opp_archetype(steps, seat):
    act = steps[1][1 - seat].get("action")
    if isinstance(act, list) and len(act) == 60:
        a = archetype(act)
        return a["label"] if a else "unknown"
    return "unknown"


def mine(dirs, want_team_by_dir, want_arch, ctx, label):
    by_arch = defaultdict(lambda: {"n": 0, "max_prize": 0, "max_energy": 0,
                                   "min_hp_ratio": 0, "n_multi": 0})
    for d in dirs:
        wt = want_team_by_dir.get(str(d))
        for fp in sorted(Path(d).glob("*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if len(steps) < 2:
                continue
            tn = (js.get("info") or {}).get("TeamNames") or ["?", "?"]
            for seat in (0, 1):
                if seat >= len(tn) or tn[seat] not in wt:
                    continue
                act = steps[1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 60):
                    continue
                a = archetype(act)
                if not a or a["label"] != want_arch:
                    continue
                oa = opp_archetype(steps, seat)
                for i in range(len(steps) - 1):
                    e = steps[i][seat]
                    if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                        continue
                    obs = e.get("observation") or {}
                    sel = obs.get("select") or {}
                    if sel.get("context") != ctx:
                        continue
                    opts = sel.get("option") or []
                    cand = [(j, o) for j, o in enumerate(opts)
                            if (o or {}).get("area") == AREA_BENCH
                            and (o or {}).get("playerIndex") == 1 - (obs.get("current") or {}).get("yourIndex", 0)]
                    if len(cand) < 2:
                        continue   # no real choice
                    act2 = steps[i + 1][seat].get("action")
                    if not (isinstance(act2, list) and len(act2) == 1):
                        continue
                    ci = act2[0]
                    cur = obs.get("current") or {}
                    me = cur.get("yourIndex") or 0
                    opp = (cur.get("players") or [{}, {}])[1 - me]
                    bench = opp.get("bench") or []
                    targets = []
                    for j, o in cand:
                        idx = o.get("index")
                        if idx is None or idx >= len(bench) or not bench[idx]:
                            continue
                        pk = bench[idx]
                        cid = pk.get("id")
                        c = CARDS.get(cid) or {}
                        hp, maxhp = pk.get("hp"), c.get("hp")
                        ratio = (hp / maxhp) if (hp is not None and maxhp) else 1.0
                        targets.append((j, prizes_for_ko(cid),
                                       len(pk.get("energies") or []), ratio))
                    if len(targets) < 2:
                        continue
                    chosen = next((t for t in targets if t[0] == ci), None)
                    if chosen is None:
                        continue
                    r = by_arch[oa]
                    r["n"] += 1
                    r["n_multi"] += 1
                    if chosen[1] == max(t[1] for t in targets):
                        r["max_prize"] += 1
                    if chosen[2] == max(t[2] for t in targets):
                        r["max_energy"] += 1
                    if chosen[3] == min(t[3] for t in targets):
                        r["min_hp_ratio"] += 1
    print(f"\n=== {label} (context={ctx}) ===")
    print(f"{'opponent archetype':<46s}{'n':>5s}{'chose-max-prize':>16s}"
          f"{'chose-max-energy':>17s}{'chose-min-hp':>13s}")
    total = {"n": 0, "max_prize": 0, "max_energy": 0, "min_hp_ratio": 0}
    for oa, r in by_arch.items():
        for k in total:
            total[k] += r[k]
    pooled_pct = {k: (total[k] / total["n"] * 100 if total["n"] else 0)
                  for k in ("max_prize", "max_energy", "min_hp_ratio")}
    for oa, r in sorted(by_arch.items(), key=lambda kv: -kv[1]["n"]):
        if r["n"] < 15:
            continue
        print(f"{oa[:46]:<46s}{r['n']:>5d}"
              f"{r['max_prize']/r['n']*100:>15.1f}%"
              f"{r['max_energy']/r['n']*100:>16.1f}%"
              f"{r['min_hp_ratio']/r['n']*100:>12.1f}%")
    print(f"{'POOLED (all matchups)':<46s}{total['n']:>5d}"
          f"{pooled_pct['max_prize']:>15.1f}%"
          f"{pooled_pct['max_energy']:>16.1f}%"
          f"{pooled_pct['min_hp_ratio']:>12.1f}%")
    return by_arch


if __name__ == "__main__":
    r1 = mine(TOP_DIRS, TEAMS, GRIMM, SC_DAMAGE, "Shadow Bullet splash target")
    r2 = mine(TOP_DIRS, TEAMS, GRIMM, SC_SWITCH, "Boss's Orders / forced switch target")
    out = {"shadow_bullet": {k: v for k, v in r1.items()},
          "boss": {k: v for k, v in r2.items()}}
    (REPO / "scratchpad/s3/target_cells.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print("\n-> scratchpad/s3/target_cells.json")
