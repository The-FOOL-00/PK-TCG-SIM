"""Runs 20-game simulation test and 1000-decision latency benchmark on extracted bundle."""

import sys
import os
import time
from pathlib import Path
from kaggle_environments import make

BUNDLE_DIR = Path(__file__).resolve().parent.parent / "build" / "validation_temp"
sys.path.insert(0, str(BUNDLE_DIR))

import main as bundle_agent

def run_isolated_benchmark():
    print(f"Running isolated gameplay validation on bundle at: {BUNDLE_DIR}")
    
    n_games = 20
    wins = 0
    losses = 0
    draws = 0
    crashes = 0
    invalids = 0
    timeouts = 0
    latencies = []

    for g in range(n_games):
        def p0(obs, _config):
            t0 = time.perf_counter()
            res = bundle_agent.agent(obs)
            dt = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt)
            return res

        def p1(obs, _config):
            t0 = time.perf_counter()
            res = bundle_agent.agent(obs)
            dt = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt)
            return res

        env = make("cabt", debug=False)
        env.run([p0, p1])
        st0, st1 = env.state[0], env.state[1]

        if st0.status in ("INVALID", "ERROR"):
            invalids += 1
            crashes += 1
        elif st0.status == "TIMEOUT":
            timeouts += 1
            crashes += 1

        if st0.reward == 1:
            wins += 1
        elif st0.reward == -1:
            losses += 1
        else:
            draws += 1

    lat_arr = [float(x) for x in latencies]
    import numpy as np
    p50 = float(np.percentile(lat_arr, 50))
    p95 = float(np.percentile(lat_arr, 95))
    p99 = float(np.percentile(lat_arr, 99))
    avg_l = float(np.mean(lat_arr))
    max_l = float(np.max(lat_arr))

    res_dict = {
        "games_completed": n_games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crashes": crashes,
        "invalids": invalids,
        "timeouts": timeouts,
        "total_decisions": len(lat_arr),
        "latency_ms": {
            "average": avg_l,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "max": max_l
        }
    }
    print("Isolated Validation Benchmark Results:")
    print(res_dict)
    return res_dict

if __name__ == "__main__":
    run_isolated_benchmark()
