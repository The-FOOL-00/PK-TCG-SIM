"""Phase 1: v2.2.0 ladder loss analysis.

Parses the harvested replays of submission 54577670 (v2.2.0-bc-full-garchomp),
filters to losses, and extracts per-loss: turn of loss, end reason, opponent
archetype (from the 60-card deck answer in steps[1]), prize race, Garchomp-ex
online turn, our last MAIN decisions, and a v1-agreement fingerprint.

Fallback check: daily-dataset replays contain no agent stderr, so
"[bc] weights unavailable" cannot be read directly. Instead: if the BC
fallback had fired, the agent IS v1, whose MAIN pick is deterministic
(argmax _score_main) — per-game v1-agreement would be ~100%. BC-full games
show materially lower agreement (BC overrides a chunk of v1 picks).

Run:  py -3.12 -X utf8 analysis/phase1_v2_2_0_losses/analyze_losses.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "tools"))

import main  # noqa: E402
assert hasattr(main, "encode_state"), "wrong main.py on sys.path"
from meta_miner import CARD_DB, archetype  # noqa: E402

OUR_TEAM = "Project Mew"
RAW = HERE / "replays_raw"
META = json.loads((HERE / "episodes_meta.json").read_text(encoding="utf-8"))
META_BY_EP = {m["episode"]: m for m in META}

OT_NAMES = {0: "NUMBER", 1: "YES", 2: "NO", 3: "CARD", 4: "TOOL", 5: "ENERGY_CARD",
            6: "ENERGY", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
            11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END", 15: "SKILL",
            16: "SPECIAL_COND"}
REASONS = {1: "prizes", 2: "deckout", 3: "no-active", 4: "effect"}

GARCHOMP_EX = [cid for cid, c in CARD_DB.items() if "Garchomp ex" in c["name"]]


def cname(cid):
    c = CARD_DB.get(cid)
    return c["name"] if c else f"card{cid}"


def describe_main_choice(opt, sel, cur, me):
    t = opt.get("type")
    name = OT_NAMES.get(t, str(t))
    cid = None
    try:
        cid = main._option_card_id(opt, sel, cur, me)
    except Exception:
        pass
    if t == 7:  # PLAY: index into hand
        try:
            cid = main._hand_card_id(cur, me, opt.get("index"))
        except Exception:
            pass
    if t == 13:
        aid = opt.get("attackId")
        return f"ATTACK(id{aid})"
    return f"{name}({cname(cid)})" if cid else name


def v1_main_pick(sel, cur, me):
    opts = sel.get("option") or []
    scores = [main._score_main(o, sel, cur, me) for o in opts]
    return max(range(len(opts)), key=lambda i: scores[i])


def v1_card_pick(sel, cur, me):
    opts = sel.get("option") or []
    ctx = sel.get("context")
    scores = [main._score_card(o, sel, cur, me, ctx) for o in opts]
    return max(range(len(opts)), key=lambda i: scores[i])


def analyze(fp):
    d = json.loads(fp.read_text(encoding="utf-8"))
    teams = (d.get("info") or {}).get("TeamNames") or ["?", "?"]
    if OUR_TEAM not in teams:
        return None
    ep = int(fp.stem)
    m = META_BY_EP.get(ep, {})
    selfplay = teams[0] == teams[1]
    side = teams.index(OUR_TEAM)  # for selfplay this is seat 0; opp fields marked
    steps = d.get("steps") or []
    rewards = d.get("rewards") or [None, None]

    # opponent deck / archetype
    opp = 1 - side
    opp_arch = None
    act0 = steps[1][opp].get("action") if len(steps) > 1 else None
    if isinstance(act0, list) and len(act0) == 60:
        a = archetype(act0)
        opp_arch = a["label"] if a else None

    # visualize pass: reason, turns, first attacks, prizes, garchomp online
    vis = (steps[0][0].get("visualize")
           or (steps[0][0].get("observation") or {}).get("visualize")) or []
    reason, last_turn = None, 0
    first_attack = [None, None]
    prizes = [0, 0]
    chomp_online = None
    for entry in vis:
        cur = entry.get("current") or {}
        turn = cur.get("turn") or last_turn
        last_turn = max(last_turn, turn)
        for l in entry.get("logs") or []:
            t, pi = l.get("type"), l.get("playerIndex")
            if t == "Result":
                reason = l.get("reason")
            elif t == "Attack" and pi in (0, 1) and first_attack[pi] is None:
                first_attack[pi] = turn
            elif t == "MoveCard" and l.get("fromArea") == 6 and pi in (0, 1):
                prizes[pi] += 1
            elif (t == "Evolve" and pi == side and chomp_online is None
                  and l.get("cardId") in GARCHOMP_EX):
                chomp_online = turn

    # our decisions: v1 agreement + last MAIN choices
    n_main = agree_main = n_card = agree_card = 0
    main_log = []  # (turn, desc, was_v1_pick)
    for i in range(1, len(steps) - 1):
        e = steps[i][side]
        if not isinstance(e, dict) or e.get("status") != "ACTIVE":
            continue
        obs = e.get("observation") or {}
        sel, cur = obs.get("select"), obs.get("current")
        if sel is None or cur is None:
            continue
        action = steps[i + 1][side].get("action")
        if not isinstance(action, list) or not action:
            continue
        stype = sel.get("type")
        nopt = len(sel.get("option") or [])
        me = cur.get("yourIndex")
        if stype == 0 and nopt > 1 and sel.get("minCount", 1) == 1 \
                and sel.get("maxCount", 1) == 1:
            try:
                p = v1_main_pick(sel, cur, me)
            except Exception:
                continue
            n_main += 1
            hit = (p == action[0])
            agree_main += hit
            desc = describe_main_choice(sel["option"][action[0]], sel, cur, me)
            main_log.append((cur.get("turn") or 0, desc, hit))
        elif stype in (1, 2, 3) and nopt > 1:
            try:
                p = v1_card_pick(sel, cur, me)
            except Exception:
                continue
            n_card += 1
            agree_card += (p == action[0])

    return {
        "episode": ep,
        "selfplay": selfplay,
        "opponent": m.get("opp_team") or teams[opp],
        "opp_mu": m.get("opp_mu_before"),
        "opp_arch": opp_arch,
        "reward": rewards[side] if not selfplay else m.get("reward"),
        "reason": REASONS.get(reason, str(reason)),
        "turns": last_turn,
        "our_first_attack": first_attack[side],
        "opp_first_attack": first_attack[opp],
        "our_prizes": prizes[side],
        "opp_prizes": prizes[opp],
        "chomp_online": chomp_online,
        "v1_agree_main": round(agree_main / n_main, 3) if n_main else None,
        "n_main": n_main,
        "v1_agree_card": round(agree_card / n_card, 3) if n_card else None,
        "n_card": n_card,
        "last_mains": main_log[-5:],
    }


def run():
    rows = []
    for fp in sorted(RAW.glob("*.json")):
        try:
            r = analyze(fp)
        except Exception as e:
            print(f"PARSE FAIL {fp.name}: {e!r}", file=sys.stderr)
            continue
        if r:
            rows.append(r)

    wins = [r for r in rows if r["reward"] == 1]
    losses = [r for r in rows if r["reward"] == -1]
    print(f"replays parsed: {len(rows)}  (W {len(wins)} / L {len(losses)}, "
          f"selfplay {sum(1 for r in rows if r['selfplay'])})")

    # fallback fingerprint distribution
    ag = [r["v1_agree_main"] for r in rows if r["v1_agree_main"] is not None]
    print(f"v1-agreement MAIN: min {min(ag):.2f}  median {sorted(ag)[len(ag)//2]:.2f}"
          f"  max {max(ag):.2f}   (fallback would be ~1.00)")
    agc = [r["v1_agree_card"] for r in rows if r["v1_agree_card"] is not None]
    print(f"v1-agreement CARD: min {min(agc):.2f}  median {sorted(agc)[len(agc)//2]:.2f}"
          f"  max {max(agc):.2f}")
    sus = [r["episode"] for r in rows
           if (r["v1_agree_main"] or 0) >= 0.97 and (r["v1_agree_card"] or 0) >= 0.97
           and r["n_main"] >= 10]
    print(f"games looking exactly-v1 (both >=0.97, n_main>=10): {sus or 'none'}")

    # loss table
    print("\n=== LOSSES ===")
    hdr = ("episode", "opponent", "opp_mu", "opp_arch", "reason", "turns",
           "our_fa", "opp_fa", "our_pz", "opp_pz", "chomp_t", "v1agr_m", "v1agr_c")
    print("  ".join(hdr))
    for r in sorted(losses, key=lambda r: (r["reason"], r["turns"])):
        print(f'{r["episode"]}  {(r["opponent"] or "?")[:20]:20s}  '
              f'{r["opp_mu"] or 0:4.0f}  {(r["opp_arch"] or "?")[:32]:32s}  '
              f'{r["reason"]:9s}  {r["turns"]:2d}  '
              f'{str(r["our_first_attack"]):>4s}  {str(r["opp_first_attack"]):>4s}  '
              f'{r["our_prizes"]}  {r["opp_prizes"]}  '
              f'{str(r["chomp_online"]):>4s}  '
              f'{r["v1_agree_main"]}  {r["v1_agree_card"]}')

    print("\n=== last MAIN decisions in each loss ===")
    for r in sorted(losses, key=lambda r: r["turns"]):
        seq = "; ".join(f"t{t} {d}{'' if h else '*'}" for t, d, h in r["last_mains"])
        print(f'{r["episode"]} vs {r["opponent"]} ({r["reason"]}, T{r["turns"]}):'
              f' {seq}')
    print("(* = pick differed from v1)")

    # win/loss by archetype
    print("\n=== W/L by opponent archetype ===")
    by = {}
    for r in rows:
        if r["selfplay"]:
            continue
        k = r["opp_arch"] or "?"
        w, l = by.get(k, (0, 0))
        by[k] = (w + (r["reward"] == 1), l + (r["reward"] == -1))
    for k, (w, l) in sorted(by.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        print(f"  {k[:40]:40s} {w}W-{l}L")

    out = HERE / "losses_table.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        keys = [k for k in rows[0] if k != "last_mains"]
        w.writerow(keys + ["last_mains"])
        for r in rows:
            w.writerow([r[k] for k in keys]
                       + ["; ".join(f"t{t} {d}{'' if h else '*'}"
                                    for t, d, h in r["last_mains"])])
    print(f"\nfull table -> {out}")


if __name__ == "__main__":
    run()
