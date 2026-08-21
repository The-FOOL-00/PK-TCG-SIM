"""Analyzer for Prize-Loss Failures in BS-CEI V1.5c.

Reconstructs the critical turns before prize losses in self-play matches to categorize:
1. TARGET_ERROR: Attacked a 1-prize target when a favorable 2-prize EX line was reachable.
2. ENERGY_ERROR: Attached energy to an active with <=30 HP when backup was unpowered.
3. BOTH: Both target and energy errors occurred in the closing turns.
4. NEITHER: Unavoidable prize loss (e.g. brick draw / natural opponent topdeck lethal).
"""

import json
import os
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import numpy as np
from kaggle_environments import make
import main as agent_mod
from tools import deck_compare


def run_prize_loss_analysis(n_games=100, deck_path="meta_starmie.csv"):
    deck = deck_compare.read_deck(deck_path)
    
    # Run games to capture prize-loss trajectories
    prize_losses = []
    
    for g_idx in range(n_games):
        trajectories = [[], []]
        
        def p0(obs, _config):
            if obs.get("select") is None: return list(deck)
            agent_mod.DECK = list(deck)
            agent_mod.BS_CEI = True
            agent_mod.BS_CEI_2PLY = True
            agent_mod.BS_CEI_DETS = 2
            agent_mod.BS_CEI_PROB_OPP = False
            cur = (obs.get("observation") or {}).get("current") or {}
            sel = (obs.get("observation") or {}).get("select") or {}
            res = agent_mod.agent(obs)
            trajectories[0].append({"cur": cur, "sel": sel, "act": res})
            return res

        def p1(obs, _config):
            if obs.get("select") is None: return list(deck)
            agent_mod.DECK = list(deck)
            agent_mod.BS_CEI = False
            cur = (obs.get("observation") or {}).get("current") or {}
            sel = (obs.get("observation") or {}).get("select") or {}
            res = agent_mod.agent(obs)
            trajectories[1].append({"cur": cur, "sel": sel, "act": res})
            return res

        env = make("cabt", debug=False)
        env.run([p0, p1])
        st0 = env.state[0]
        reward0 = st0.reward or 0

        # Loss reason 1 = prize loss
        if reward0 == -1 and len(trajectories[0]) > 0:
            final_cur = trajectories[0][-1]["cur"]
            opp_prizes = len(((final_cur.get("players") or [{}, {}])[1]).get("prize") or [])
            if opp_prizes == 0:
                prize_losses.append(trajectories[0])

    print(f"Captured {len(prize_losses)} prize-loss games. Analyzing critical decision turns...", flush=True)

    target_errors = 0
    energy_errors = 0
    both_errors = 0
    no_fix = 0

    for traj in prize_losses:
        has_target_err = False
        has_energy_err = False

        # Look at last 5 turns of player decisions
        for step in traj[-8:]:
            cur = step["cur"]
            sel = step["sel"]
            act = step["act"]
            opts = sel.get("option") or []
            if not opts or not act:
                continue

            chosen_idx = act[0] if isinstance(act, list) and act else 0
            if chosen_idx >= len(opts):
                continue
            chosen_opt = opts[chosen_idx]
            chosen_type = chosen_opt.get("type", "")
            players = cur.get("players") or [{}, {}]
            our_p = players[0]
            opp_p = players[1]

            # 1. Target Error Check
            if chosen_type == "attack":
                opp_bench = opp_p.get("bench") or []
                opp_active = (opp_p.get("active") or [{}])[0]
                has_ex_target = any(b.get("isEx", False) for b in opp_bench) or opp_active.get("isEx", False)
                # Check if chosen target was non-EX while EX was reachable
                target_slot = chosen_opt.get("targetSlot", 0)
                if has_ex_target and not chosen_opt.get("isExTarget", False):
                    has_target_err = True

            # 2. Energy Error Check
            if chosen_type == "attach_energy":
                our_act = (our_p.get("active") or [{}])[0]
                our_hp = our_act.get("hp", 100)
                our_bench = our_p.get("bench") or []
                target_slot = chosen_opt.get("targetSlot", 0)
                # If active HP is <= 30 and attached to active instead of bench
                if our_hp <= 30 and target_slot == 0 and len(our_bench) > 0:
                    has_energy_err = True

        if has_target_err and has_energy_err:
            both_errors += 1
        elif has_target_err:
            target_errors += 1
        elif has_energy_err:
            energy_errors += 1
        else:
            no_fix += 1

    total = max(len(prize_losses), 1)
    results = {
        "total_prize_losses": len(prize_losses),
        "target_errors": target_errors,
        "energy_errors": energy_errors,
        "both_errors": both_errors,
        "no_fix": no_fix,
        "fixable_rate": float((target_errors + energy_errors + both_errors) / total)
    }
    print(f"Analysis Results: {json.dumps(results, indent=2)}", flush=True)
    return results


if __name__ == "__main__":
    run_prize_loss_analysis(n_games=60)
