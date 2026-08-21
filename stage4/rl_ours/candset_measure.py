"""STEP 1 — candidate-set exclusion measurement.

Recomputes the v1 score vector offline for every MAIN decision in a set of
saved replays, exactly as _decide() does, then reproduces the candidate-set
construction from _search_decide():

    order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
    cands = order[:SEARCH_TOPK]

and asks: when an ATTACK was legal, was the best-scoring attack inside cands?

Read-only. Imports main.py but never calls agent()/_search_decide(); no game
is played and no agent state is mutated beyond module-level config flags.

Run: py -3.12 -X utf8 stage4/rl_ours/candset_measure.py \
        --arms H1=scratchpad/s3/horizon_H1 CANARY=scratchpad/s3/canary_replays
"""
import argparse
import contextlib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
    import deck_compare  # noqa: E402
agent_mod = deck_compare.agent_mod

ST_MAIN = 0
OT_ATTACK = 13
OT_END = 14
DEVT = (7, 8, 9, 10)
OT = {7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY", 11: "DISCARD",
      12: "RETREAT", 13: "ATTACK", 14: "END"}


def configure(deck_path):
    """Match the policy config the replays were generated under (H1 family)."""
    deck = deck_compare.read_deck(deck_path)
    agent_mod.ROLLOUT = "v1"
    agent_mod.PILOT = "garchomp"
    agent_mod.DYN_DECK_TABLES = True
    agent_mod.EVAL_FIX = False
    agent_mod.PROMOTE_RULE = False
    agent_mod.LETHAL_PROBE = False
    agent_mod.LEARNED_VALUE = False
    agent_mod.V3_EVAL = False
    agent_mod.BC = False
    agent_mod.DECK = list(deck)
    agent_mod.TOTAL_BASIC_ENERGY = sum(
        1 for cid in deck if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)
    return deck


def seat_map(sub_id):
    """episode id -> our seat index, from the harvested episode indices.

    Ladder replays are games against OTHER teams; info.TeamNames in the replay
    is unreliable (it reports 'Project Mew' for both seats). The episode index
    is authoritative, so scoring is restricted to our own seat.
    """
    m = {}
    for f in (REPO / "scratchpad" / "s3").glob("eps_*.json"):
        for ep in json.loads(f.read_text(encoding="utf-8")).get("episodes", []):
            for a in ep.get("agents", []):
                if a.get("submissionId") == sub_id:
                    m[ep["id"]] = a.get("index", 0)
    return m


def scan(d, topk, seats=None):
    """Walk every MAIN decision; return per-turn and aggregate counters.

    seats: None = both seats (self-play, same agent on both). Otherwise a
    {episode_id: seat} map restricting the scan to our own agent's decisions.
    """
    R = {
        "games": 0, "main": 0,
        "atk_legal": 0,            # MAIN decisions with >=1 legal attack
        "atk_excluded": 0,         # ... best attack NOT in cands
        "atk_in_cands": 0,         # ... best attack IS in cands
        "chose_atk_when_in": 0,    # ... and the agent chose an attack
        "chose_atk_when_out": 0,   # excluded yet an attack was chosen anyway
        "lethal_legal": 0, "lethal_excluded": 0,
        "tempo_fired": 0,          # best attack scored >= WEIGHT_TEMPO_LOADED
        "n_opts": Counter(),
        "by_turn": defaultdict(lambda: {"legal": 0, "excl": 0, "chose": 0,
                                        "in": 0, "chose_in": 0}),
        "rank_of_best_atk": Counter(),
        "excl_chosen_type": Counter(),
        "n_setup_above": Counter(),
        "score_atk": [], "score_cut": [],
    }
    W_LETHAL = agent_mod.WEIGHT_LETHAL
    W_TEMPO = agent_mod.WEIGHT_TEMPO_LOADED

    for fp in sorted(Path(d).glob("*.json")):
        try:
            js = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = js.get("steps")
        if not steps:
            continue
        if seats is not None:
            try:
                eid = int(fp.stem)
            except ValueError:
                continue
            if eid not in seats:
                continue
            which = (seats[eid],)
        else:
            which = (0, 1)
        R["games"] += 1
        for i in range(len(steps) - 1):
            for seat in which:
                e = steps[i][seat]
                if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                    continue
                obs = e.get("observation") or {}
                sel = obs.get("select") or {}
                if sel.get("type") != ST_MAIN:
                    continue
                options = sel.get("option") or []
                if len(options) < 2:
                    continue
                act = steps[i + 1][seat].get("action")
                if not (isinstance(act, list) and len(act) == 1):
                    continue
                ci = act[0]
                if not isinstance(ci, int) or ci >= len(options):
                    continue
                cur = obs.get("current") or {}
                me = cur.get("yourIndex") or 0
                try:
                    scores = [agent_mod._score_option(o or {}, sel, cur, me)
                              for o in options]
                except Exception:
                    continue
                R["main"] += 1
                R["n_opts"][min(len(options), 20)] += 1

                order = sorted(range(len(options)), key=lambda k: (-scores[k], k))
                cands = order[:topk]
                types = [(o or {}).get("type") for o in options]
                atks = [k for k, t in enumerate(types) if t == OT_ATTACK]
                if not atks:
                    continue

                turn = cur.get("turn") or 0
                best_atk = max(atks, key=lambda k: (scores[k], -k))
                R["atk_legal"] += 1
                R["by_turn"][turn]["legal"] += 1
                chose_atk = types[ci] == OT_ATTACK
                if chose_atk:
                    R["by_turn"][turn]["chose"] += 1
                if scores[best_atk] >= W_LETHAL:
                    R["lethal_legal"] += 1
                if scores[best_atk] >= W_TEMPO:
                    R["tempo_fired"] += 1
                R["rank_of_best_atk"][min(order.index(best_atk), 12)] += 1
                R["n_setup_above"][min(
                    sum(1 for k in range(len(options))
                        if scores[k] > scores[best_atk]), 12)] += 1

                if best_atk in cands:
                    R["atk_in_cands"] += 1
                    R["by_turn"][turn]["in"] += 1
                    if chose_atk:
                        R["chose_atk_when_in"] += 1
                        R["by_turn"][turn]["chose_in"] += 1
                else:
                    R["atk_excluded"] += 1
                    R["by_turn"][turn]["excl"] += 1
                    R["excl_chosen_type"][OT.get(types[ci], types[ci])] += 1
                    R["score_atk"].append(scores[best_atk])
                    R["score_cut"].append(scores[cands[-1]])
                    if scores[best_atk] >= W_LETHAL:
                        R["lethal_excluded"] += 1
                    if chose_atk:
                        R["chose_atk_when_out"] += 1
    return R


def pct(a, b):
    return (a / b * 100.0) if b else 0.0


def report(lab, R, topk):
    print(f"\n{'='*78}\n{lab}   (SEARCH_TOPK={topk})\n{'='*78}")
    print(f"games={R['games']}  MAIN decisions={R['main']}  "
          f"attack-legal decisions={R['atk_legal']}")
    if not R["atk_legal"]:
        print("  no attack-legal decisions")
        return
    print(f"\n  best attack EXCLUDED from cands[0:{topk}] : "
          f"{R['atk_excluded']}/{R['atk_legal']} = "
          f"{pct(R['atk_excluded'], R['atk_legal']):.1f}%")
    print(f"  best attack IN cands                      : "
          f"{R['atk_in_cands']}/{R['atk_legal']} = "
          f"{pct(R['atk_in_cands'], R['atk_legal']):.1f}%")
    print(f"  -> when IN cands, search chose an attack  : "
          f"{R['chose_atk_when_in']}/{R['atk_in_cands']} = "
          f"{pct(R['chose_atk_when_in'], R['atk_in_cands']):.1f}%")
    print(f"  -> when EXCLUDED, attack chosen anyway    : "
          f"{R['chose_atk_when_out']}/{R['atk_excluded']} = "
          f"{pct(R['chose_atk_when_out'], R['atk_excluded']):.1f}%")
    print(f"  tempo hook fired (best atk >= {agent_mod.WEIGHT_TEMPO_LOADED:.0f}) : "
          f"{R['tempo_fired']}/{R['atk_legal']} = "
          f"{pct(R['tempo_fired'], R['atk_legal']):.1f}%")
    print(f"  lethal legal={R['lethal_legal']}  lethal excluded={R['lethal_excluded']}")

    if R["score_atk"]:
        sa, sc = sorted(R["score_atk"]), sorted(R["score_cut"])
        n = len(sa)
        print(f"\n  on excluded decisions: best-attack score median "
              f"{sa[n//2]:.0f} (min {sa[0]:.0f}, max {sa[-1]:.0f}) vs "
              f"cands cutoff median {sc[n//2]:.0f}")

    print("\n  rank of best attack in the v1 order (0 = top):")
    tot = sum(R["rank_of_best_atk"].values())
    for r in sorted(R["rank_of_best_atk"]):
        c = R["rank_of_best_atk"][r]
        lbl = f"{r}" + ("+" if r == 12 else "")
        bar = "#" * int(pct(c, tot) / 2)
        print(f"    rank {lbl:>3s}: {c:5d}  {pct(c, tot):5.1f}%  {bar}")

    print("\n  by turn:")
    print(f"    {'turn':>4s} {'atk-legal':>9s} {'excluded':>8s} {'excl%':>7s} "
          f"{'chose atk':>9s} {'atk-when-legal%':>15s}")
    for t in sorted(R["by_turn"]):
        b = R["by_turn"][t]
        if b["legal"] < 3:
            continue
        print(f"    {t:>4d} {b['legal']:>9d} {b['excl']:>8d} "
              f"{pct(b['excl'], b['legal']):>6.1f}% {b['chose']:>9d} "
              f"{pct(b['chose'], b['legal']):>14.1f}%")

    print("\n  when excluded, what was chosen instead:")
    tot = sum(R["excl_chosen_type"].values()) or 1
    for k, c in R["excl_chosen_type"].most_common():
        print(f"    {str(k):<9s} {c:5d}  {pct(c, tot):5.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True,
                    help="LABEL=dir  or  LABEL=dir:submissionId (ladder, our seat only)")
    ap.add_argument("--deck", default="metaC_garchomp_nasuo.csv")
    ap.add_argument("--topk", type=int, default=None)
    # Re-scoring must match the config the replays were PLAYED under, otherwise
    # an arm is measured with the baseline's scorer and looks unchanged.
    ap.add_argument("--cand-include", action="store_true")
    ap.add_argument("--cand-atk-w", type=float, default=0.0)
    # Shipped bundles never bake PTCG_PILOT, so on ladder PILOT == "" and the
    # _pilot_score_main tempo hook is dead code. Default here stays "garchomp"
    # to reproduce earlier runs; pass --pilot "" for the true ship config.
    ap.add_argument("--pilot", default="garchomp")
    ap.add_argument("--out", default="scratchpad/s3/candset_step1.json")
    args = ap.parse_args()

    configure(REPO / args.deck)
    agent_mod.CAND_INCLUDE_ATTACK = args.cand_include
    agent_mod.CAND_ATK_W = args.cand_atk_w
    agent_mod.PILOT = args.pilot
    print(f"scorer config: PILOT={agent_mod.PILOT!r} "
          f"CAND_INCLUDE_ATTACK={agent_mod.CAND_INCLUDE_ATTACK} "
          f"CAND_ATK_W={agent_mod.CAND_ATK_W}")
    topk = args.topk if args.topk is not None else agent_mod.SEARCH_TOPK
    print(f"SEARCH_TOPK={agent_mod.SEARCH_TOPK} (measuring with {topk})")
    print(f"WEIGHT_ATTACK_BASE={agent_mod.WEIGHT_ATTACK_BASE} "
          f"ATTACK_DAMAGE_SCALE={agent_mod.ATTACK_DAMAGE_SCALE} "
          f"WEIGHT_TEMPO_LOADED={agent_mod.WEIGHT_TEMPO_LOADED}")

    out = {}
    for spec in args.arms:
        lab, d = spec.split("=", 1)
        seats = None
        if ":" in d:
            d, sub = d.rsplit(":", 1)
            seats = seat_map(int(sub))
            print(f"\n[{lab}] ladder mode: our seat only, "
                  f"{len(seats)} episodes indexed for submission {sub}")
        if not (REPO / d).exists() and not Path(d).exists():
            print(f"missing {d}")
            continue
        R = scan(REPO / d if (REPO / d).exists() else Path(d), topk, seats)
        report(lab, R, topk)
        out[lab] = {k: (dict(v) if isinstance(v, (Counter, defaultdict)) else v)
                    for k, v in R.items() if k not in ("score_atk", "score_cut")}
        out[lab]["by_turn"] = {str(t): dict(v) for t, v in R["by_turn"].items()}
    (REPO / args.out).write_text(json.dumps(out, indent=1, default=str),
                                 encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
