"""Matchup-conditioned mining, analogous to conditional_mine.py's Phase 1 but
partitioned by OPPONENT ARCHETYPE instead of turn-state.

Primary partition: top-10 Grimmsnarl-side MAIN decisions, grouped by the
opponent's archetype. Leverage = (share of decisions in that matchup) x
(TVD between that matchup's action distribution and the POOLED top-10
Grimmsnarl distribution across all matchups).

Secondary drill-down: within a high-leverage matchup, which of the Phase 1
feature cells (can_KO, race, bench, powered, ...) diverge most from the SAME
cell computed on the pooled (all-matchup) population? This isolates
matchup-specific tactical adaptation from generic state-conditional behaviour
already covered by E1-E4.

Also reports (n permitting) our own ladder behaviour in the same matchup, and
win rate vs the field, explicitly flagging n < 60 as not quotable per the
project's standing rule.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402
import conditional_mine as CM  # noqa: E402 -- reuse features()/cells()

GRIMM = "Marnie's Grimmsnarl ex / Munkidori"
ACTIONS = CM.ACTIONS
A_DIR = REPO / "analysis/phase2_meta_shift"
TOP_DIRS = [A_DIR / "replays_top10_jul21", A_DIR / "replays_top10_jul22",
            A_DIR / "replays_top10_jul26"]
TEAMS = {}
for d, prof in zip(TOP_DIRS, ["profile_top10_jul21.json", "profile_top10_jul22.json",
                              "profile_top10_jul26.json"]):
    TEAMS[str(d)] = set(json.loads((A_DIR / prof).read_text(encoding="utf-8"))["teams"])

MIN_SIDES_QUALIFY = 25   # matchup must have at least this many top-10 sides to mine


def opp_archetype(steps, seat):
    act = steps[1][1 - seat].get("action")
    if isinstance(act, list) and len(act) == 60:
        a = archetype(act)
        return a["label"] if a else "unknown"
    return "unknown"


def collect(dirs, want_team_by_dir, want_arch, wl_out=None):
    """Yield (opponent_archetype, features, action) for every Grimmsnarl-side
    MAIN decision. Also fills wl_out[opp_arch] with W/L if given."""
    rows = []
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
            rewards = js.get("rewards") or [None, None]
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
                if wl_out is not None and rewards[seat] in (1, -1):
                    wl_out[oa]["W" if rewards[seat] == 1 else "L"] += 1
                for f, act_name in _decisions(steps, seat):
                    rows.append((oa, f, act_name))
    return rows


def _decisions(steps, seat):
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
        act2 = steps[i + 1][seat].get("action")
        if not (isinstance(act2, list) and len(act2) == 1):
            continue
        ci = act2[0]
        if not isinstance(ci, int) or ci >= len(opts):
            continue
        f = CM.features(obs, opts)
        if f is None:
            continue
        yield f, CM.NAME.get((opts[ci] or {}).get("type"), "?")


def dist(counter):
    t = sum(counter.values()) or 1
    return {a: counter[a] / t for a in ACTIONS}


def tvd(p, q):
    return 0.5 * sum(abs(p[a] - q[a]) for a in ACTIONS)


if __name__ == "__main__":
    wl = defaultdict(Counter)
    rows = collect(TOP_DIRS, TEAMS, GRIMM, wl)
    print(f"top-10 Grimmsnarl MAIN decisions: {len(rows)}")

    pooled = Counter(a for _, _, a in rows)
    by_arch = defaultdict(Counter)
    sides_by_arch = defaultdict(set)
    for oa, f, a in rows:
        by_arch[oa][a] += 1

    # side counts per archetype (re-derive from wl for a quick n)
    side_n = {k: v["W"] + v["L"] for k, v in wl.items()}

    print("\n=== MATCHUP LEVERAGE RANKING (top-10 Grimmsnarl side) ===")
    print(f"{'opponent archetype':<46s}{'sides':>7s}{'decisions':>10s}"
          f"{'TVD vs pooled':>15s}{'leverage':>10s}{'WR vs field':>13s}")
    total_dec = len(rows)
    ranked = []
    for oa, c in by_arch.items():
        n = sum(c.values())
        if n < 200:   # decision-count floor for a stable distribution
            continue
        d = tvd(dist(c), dist(pooled))
        freq = n / total_dec
        w, l = wl[oa]["W"], wl[oa]["L"]
        wr = w / (w + l) * 100 if (w + l) else None
        ranked.append({"opp": oa, "sides": side_n.get(oa, 0), "n": n,
                       "tvd": d, "leverage": freq * d, "W": w, "L": l, "wr": wr})
    ranked.sort(key=lambda r: -r["leverage"])
    for r in ranked:
        flag = "" if (r["W"] + r["L"]) >= 60 else " (n<60, not quotable)"
        wr_s = f"{r['wr']:.1f}%{flag}" if r["wr"] is not None else "n/a"
        print(f"{r['opp'][:46]:<46s}{r['sides']:>7d}{r['n']:>10d}"
              f"{r['tvd']:>15.3f}{r['leverage']:>10.4f}{wr_s:>13s}")

    print(f"\nPOOLED action distribution (all matchups, n={total_dec}):")
    pd = dist(pooled)
    print("  " + "  ".join(f"{a}={pd[a]*100:.1f}%" for a in ACTIONS))

    out = {"pooled": dict(pooled), "by_arch": {k: dict(v) for k, v in by_arch.items()},
          "wl": {k: dict(v) for k, v in wl.items()}, "ranked": ranked}
    (REPO / "scratchpad/s3/matchup_cells.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print("\n-> scratchpad/s3/matchup_cells.json")
