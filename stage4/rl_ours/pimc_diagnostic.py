"""PIMC pathology diagnostic — INSTRUMENTATION ONLY.

Measures, without altering any decision:
  D1 strategy-fusion incidence  per-determinization argmax agreement
  D2 disambiguation factor      opponent-hand belief entropy vs turn
  D3 seat bias                  (pooled separately from gate JSONs)
  D4 time budget                wall-clock per player per match vs the 600 s bank

The patched `_search_decide` is a line-faithful copy of main.py's with
recording added: identical arithmetic, identical RNG call order, identical
return value. Decisions are unchanged by construction.

Run:
  py -3.12 -X utf8 stage4/rl_ours/pimc_diagnostic.py --games 60 \
      --out stage4/rl_ours/pimc_raw.json
"""

import argparse
import atexit
import contextlib
import io
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import deck_compare  # noqa: E402  (sets up kaggle_environments + main import)

agent_mod = deck_compare.agent_mod
make = deck_compare.make

REC = {
    "decisions": [],   # one row per searched MAIN decision
    "games": [],       # one row per game
    "leaf": {          # Gate 1: leaf-value telemetry (scale + branch audit)
        "n_terminal": 0, "n_cap": 0, "n_cap_valuenet": 0, "n_cap_flat": 0,
        "min": None, "max": None, "hist": Counter(),
    },
}

JITTER = 0.0           # Gate 1 null control: uniform +/- JITTER added to leaves


def _hand_entropy(hands):
    """Shannon entropy (bits) of the card-id distribution across sampled
    opponent hands, plus perplexity = effective distinct-hand-content size."""
    c = Counter()
    for h in hands:
        c.update(h)
    total = sum(c.values())
    if total <= 0:
        return 0.0, 0.0
    ent = 0.0
    for n in c.values():
        p = n / total
        ent -= p * math.log2(p)
    return ent, 2.0 ** ent


def install_rollout(agent_mod, rng):
    """Faithful copy of _rollout with leaf telemetry, and the Gate 1 jitter
    null control. Arithmetic identical to main.py's when JITTER == 0."""
    m = agent_mod
    L = REC["leaf"]

    def _rollout_instrumented(node, me, cap):
        steps = 0
        prev_id = None
        branch = "terminal"
        while True:
            cur = node["observation"]["current"]
            if cur["result"] != -1:
                v = 1.0 if cur["result"] == me else (0.5 if cur["result"] == 2 else 0.0)
                branch = "terminal"
                break
            if steps >= cap:
                v = 0.5
                branch = "cap_flat"
                model = m._lv_model()
                if model is not None:
                    p = m._lv_predict(model, [m.encode_state(cur)])[0]
                    v = p if cur["yourIndex"] == me else 1.0 - p
                    branch = "cap_valuenet"
                break
            nxt = m._sb_step(node["searchId"], m._rollout_choose(node["observation"]))
            if prev_id is not None:
                m._sb_release(prev_id)
            prev_id = node["searchId"]
            node = nxt
            steps += 1
        if prev_id is not None:
            m._sb_release(prev_id)
        if JITTER:
            v += rng.uniform(-JITTER, JITTER)
        # ---- telemetry (no effect on the returned value) ----
        if branch == "terminal":
            L["n_terminal"] += 1
        else:
            L["n_cap"] += 1
            L["n_cap_valuenet" if branch == "cap_valuenet" else "n_cap_flat"] += 1
        L["min"] = v if L["min"] is None else min(L["min"], v)
        L["max"] = v if L["max"] is None else max(L["max"], v)
        L["hist"][round(min(max(v, 0.0), 1.0) * 10) / 10] += 1
        return v

    m._rollout = _rollout_instrumented


def install(agent_mod):
    """Replace _search_decide with a recording copy (behaviour-identical)."""
    m = agent_mod

    def _search_decide_instrumented(obs, sel, cur, v1_result, scores, t0):
        me = cur.get("yourIndex") or 0
        tr = m._TRACKERS.get(me)
        if tr is None:
            tr = m._TRACKERS[me] = m.CardTracker(me)
        if tr.update(obs):
            m._gov_flush()
        if not m._GOV["hooked"]:
            m._GOV["hooked"] = True
            atexit.register(m._gov_flush)

        if m._GOV["sticky"] or not m._searchable(obs, sel, cur) or m._search_lib() is None:
            m._gov_note((cur.get("turn") or 0), None, time.perf_counter() - t0, 0)
            return v1_result

        if m.LETHAL_PROBE:
            try:
                lethal_idx = m._find_lethal(obs, sel, cur, scores, me, tr,
                                            m.LETHAL_PROBE_DEADLINE_S)
            except Exception:
                lethal_idx = None
            if lethal_idx is not None:
                m.STATS["lethal_probe_fired"] = m.STATS.get("lethal_probe_fired", 0) + 1
                m._gov_note((cur.get("turn") or 0), None, time.perf_counter() - t0, 0)
                return [lethal_idx]

        budget = m._gov_budget(obs)
        if budget is not None and budget < m.GOV_STICKY_S:
            m._GOV["sticky"] = True
            m._gov_note((cur.get("turn") or 0), budget, time.perf_counter() - t0, 0)
            return v1_result
        if m._GOV["searches_run"] < m.GOV_WARMSTART_N:
            dets = m.SEARCH_DET
            m._GOV["warmstart_forced"] += 1
        elif m._GOV["cons_ema_skip"] >= m.GOV_HYST_M:
            dets = max(1, m.SEARCH_DET // 4)
            m._GOV["hyst_forced"] += 1
        else:
            dets = m._gov_det(budget)
        options = sel.get("option") or []
        order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
        cands = order[:m.SEARCH_TOPK]
        if dets <= 0 or len(cands) < 2:
            if dets == 0 and len(cands) >= 2:
                m._GOV["cons_ema_skip"] += 1
                if m._GOV["cons_ema_skip"] > m._GOV["max_cons_ema_skip"]:
                    m._GOV["max_cons_ema_skip"] = m._GOV["cons_ema_skip"]
            m._gov_note((cur.get("turn") or 0), budget, time.perf_counter() - t0, 0)
            return v1_result

        m.STATS["searched"] = m.STATS.get("searched", 0) + 1
        cap = m.SEARCH_CAP if m.SEARCH_CAP > 0 else 400
        rolls = max(1, m.SEARCH_ROLL)
        totals = {i: 0.0 for i in cands}
        n = 0
        fails = 0
        dets_run = 0
        # --- instrumentation state (does not affect control flow) ---
        per_det_argmax = []     # candidate index each det would pick alone
        per_det_tied = []       # how many candidates tied for top in that det
        per_det_spread = []     # max-min of that det's candidate values
        sampled_hands = []
        for _d in range(dets):
            if budget is not None and time.perf_counter() - t0 > budget:
                break
            try:
                det = m._sample_determinization(obs, tr, m._SEARCH_RNG)
            except Exception:
                fails += 1
                if fails >= 5:
                    break
                continue
            try:
                root = m._sb_begin(obs["search_begin_input"], **det)
                det_vals = {}
                for i in cands:
                    v = 0.0
                    for _r in range(rolls):
                        node = m._sb_step(root["searchId"], [i])
                        r = m._rollout(node, me, cap)
                        totals[i] += r
                        v += r
                    det_vals[i] = v
                n += rolls
                dets_run += 1
                # this determinization, judged alone
                best_v = max(det_vals.values())
                tied = [i for i in cands if det_vals[i] == best_v]
                per_det_argmax.append(min(tied, key=lambda i: cands.index(i)))
                per_det_tied.append(len(tied))
                per_det_spread.append(best_v - min(det_vals.values()))
                sampled_hands.append(list(det.get("opp_hand") or []))
            except Exception:
                fails += 1
                if fails >= 5:
                    break
            finally:
                m._sb_end()
        spent = time.perf_counter() - t0
        m._gov_note((cur.get("turn") or 0), budget, spent, dets_run)
        if n == 0:
            return v1_result
        best = max(cands, key=lambda i: (totals[i] / n, -cands.index(i)))
        if [best] != v1_result:
            m.STATS["search_changed"] = m.STATS.get("search_changed", 0) + 1

        # ---------------- record (after the decision is fixed) ----------------
        if per_det_argmax:
            means = sorted((totals[i] / n for i in cands), reverse=True)
            margin = (means[0] - means[1]) if len(means) > 1 else 1.0
            votes = Counter(per_det_argmax)
            modal, modal_n = votes.most_common(1)[0]
            # Signal-bearing subset: determinizations whose argmax was STRICT
            # (no tie). A tied world has not "chosen" anything — its recorded
            # argmax is our index tie-break, an instrumentation artifact, so it
            # casts no vote. Definition fixed from a 2-game smoke BEFORE the
            # measurement run; see PIMC_DIAGNOSTIC.md header.
            strict = [a for a, t in zip(per_det_argmax, per_det_tied) if t == 1]
            if strict:
                sv = Counter(strict)
                s_modal, s_modal_n = sv.most_common(1)[0]
                agreement_strict = s_modal_n / len(strict)
                distinct_votes_strict = len(sv)
                strict_modal_is_chosen = int(s_modal == best)
            else:
                agreement_strict = None
                distinct_votes_strict = 0
                strict_modal_is_chosen = None
            theirs = (cur.get("players") or [{}, {}])[1 - me]
            hc = theirs.get("handCount") or 0
            ent, perp = _hand_entropy(sampled_hands)
            REC["decisions"].append({
                "turn": cur.get("turn") or 0,
                "seat": me,
                "n_legal": len(options),
                "n_cands": len(cands),
                "n_dets": len(per_det_argmax),
                "agreement": modal_n / len(per_det_argmax),
                "modal_is_chosen": int(modal == best),
                "distinct_votes": len(votes),
                "n_dets_strict": len(strict),
                "agreement_strict": agreement_strict,
                "distinct_votes_strict": distinct_votes_strict,
                "strict_modal_is_chosen": strict_modal_is_chosen,
                "margin": margin,
                "mean_tied": sum(per_det_tied) / len(per_det_tied),
                "all_tied_frac": sum(1 for t in per_det_tied if t == len(cands))
                                  / len(per_det_tied),
                "mean_spread": sum(per_det_spread) / len(per_det_spread),
                "opp_hand_count": hc,
                "opp_hand_known": len(tr.hand_known),
                "opp_hand_entropy_bits": ent,
                "opp_hand_perplexity": perp,
                "spent_s": spent,
            })
        return [best]

    m._search_decide = _search_decide_instrumented


def make_wrapper(deck, seat_key, timing):
    n_energy = sum(1 for cid in deck
                   if agent_mod.CARDS.get(cid, {}).get("cardType") == 5)

    def wrapper(obs, _config):
        if obs.get("select") is None:
            return list(deck)
        agent_mod.DECK = list(deck)
        agent_mod.TOTAL_BASIC_ENERGY = n_energy
        t = time.perf_counter()
        try:
            return agent_mod.agent(obs)
        finally:
            timing[seat_key] += time.perf_counter() - t
    return wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--deck", default="metaC_garchomp_nasuo.csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--search-cap", type=int, default=0,
                    help="engine-step cap for rollouts; 0 = shipped default (400)")
    ap.add_argument("--jitter", type=float, default=0.0,
                    help="null control: uniform +/- J added to every leaf value")
    ap.add_argument("--prior", choices=("uniform", "archetype"), default="uniform",
                    help="uniform = shipped _comp_prior()+dom_type path; "
                         "archetype = populate SEARCH_PRIOR from the 07-22 harvest")
    args = ap.parse_args()

    global JITTER
    JITTER = args.jitter

    # match the gate configuration exactly (all component flags OFF)
    agent_mod.SEARCH = True
    agent_mod.ROLLOUT = "v1"
    agent_mod.PILOT = "garchomp"
    agent_mod.DYN_DECK_TABLES = True
    agent_mod.EVAL_FIX = False
    agent_mod.PROMOTE_RULE = False
    agent_mod.LETHAL_PROBE = False
    # THE SINGLE VARIABLE for Gate 1. 0 keeps the shipped cap=400 path.
    agent_mod.SEARCH_CAP = args.search_cap
    agent_mod._search_lib()
    agent_mod._pool()
    # Gate 2 factorial variable 2: belief model. SEARCH_PRIOR=None keeps the
    # shipped _comp_prior()+dom_type path; a dict routes sample_opponent_deck
    # through the archetype weights (and, per main.py, skips dom_type).
    if args.prior == "archetype":
        import archetype_prior
        prior, _arch = archetype_prior.build_prior(agent_mod._pool().keys())
        agent_mod.SEARCH_PRIOR = prior
    else:
        agent_mod.SEARCH_PRIOR = None
    import random as _random
    install_rollout(agent_mod, _random.Random(12345))
    install(agent_mod)
    print(f"config: SEARCH_CAP={agent_mod.SEARCH_CAP} "
          f"(effective cap={agent_mod.SEARCH_CAP if agent_mod.SEARCH_CAP > 0 else 400} steps), "
          f"jitter={JITTER}, prior={args.prior} "
          f"({'populated' if agent_mod.SEARCH_PRIOR else 'None -> comp+dom_type'})",
          flush=True)

    deck = deck_compare.read_deck(REPO / args.deck)
    for g in range(args.games):
        timing = {0: 0.0, 1: 0.0}
        before = len(REC["decisions"])
        agents = [make_wrapper(deck, 0, timing), make_wrapper(deck, 1, timing)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = make("cabt", debug=True)
            env.run(agents)
            ev = deck_compare.game_events(env)
        res = (ev.get("result") or {})
        winner = res.get("result")
        # turn of each prize-take (game-deciding events)
        prize_turns = []
        step0 = env.steps[0][0]
        vis = step0.get("visualize") if hasattr(step0, "get") else step0.visualize
        last_turn = 0
        for entry in vis or []:
            t_now = (entry.get("current") or {}).get("turn") or last_turn
            last_turn = max(last_turn, t_now)
            for l in entry.get("logs") or []:
                if l.get("type") == "MoveCard" and l.get("fromArea") == 6 \
                        and l.get("toArea") == 2:
                    prize_turns.append(t_now)
        REC["games"].append({
            "game": g,
            "winner": winner,
            "reason": res.get("reason"),
            "turns": last_turn,
            "time_seat0": timing[0],
            "time_seat1": timing[1],
            "decisions_recorded": len(REC["decisions"]) - before,
            "prize_turns": prize_turns,
        })
        print(f"  game {g+1}/{args.games}: winner={winner} turns={last_turn} "
              f"t0={timing[0]:.1f}s t1={timing[1]:.1f}s "
              f"decisions={len(REC['decisions']) - before}", flush=True)

    L = REC["leaf"]
    tot = L["n_terminal"] + L["n_cap"]
    if tot:
        print(f"\nleaf audit: {tot} rollouts | terminal {L['n_terminal']} "
              f"({L['n_terminal']/tot*100:.1f}%) | cap {L['n_cap']} "
              f"({L['n_cap']/tot*100:.1f}%; valuenet {L['n_cap_valuenet']}, "
              f"flat0.5 {L['n_cap_flat']}) | leaf range [{L['min']:.4f}, {L['max']:.4f}]")
    REC["leaf"]["hist"] = dict(L["hist"])
    REC["config"] = {"search_cap": args.search_cap, "jitter": args.jitter,
                     "games": args.games}
    Path(args.out).write_text(json.dumps(REC), encoding="utf-8")
    print(f"\nsaved {len(REC['decisions'])} decisions / {len(REC['games'])} games "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
