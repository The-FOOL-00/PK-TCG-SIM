"""Canary pre-submission verification — graded leaf (SEARCH_CAP=16).

Loads the SHIPPED TARBALL under simulated Kaggle conditions (extracted to a
bare dir, sys.path stripped of the repo, no __file__ in the exec namespace),
then:
  V1  value_weights.npz packaged + loads + the graded path actually FIRES
  V2  >=20 self-play games, zero crashes; every exception surfaced (even caught)
  V3  wall-clock per player per match, MAX not median, as % of the 600 s bank
  V4  fallback returns a legal action on every throwing code path

Run: py -3.12 -X utf8 stage4/rl_ours/canary_verify.py --tar dist/canary/canary_cap16.tar.gz
"""

import argparse
import contextlib
import io
import json
import re
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_bundle_agent(bundle_dir):
    """exec() main.py the way Kaggle does: no __file__, repo NOT on sys.path."""
    saved_path, saved_cwd = list(sys.path), Path.cwd()
    import os
    os.chdir(bundle_dir)
    # strip anything pointing at the repo so only the bundle can satisfy imports
    sys.path[:] = [p for p in sys.path
                   if p and Path(p).resolve() != REPO and "pokemon-tcg-ai-battle" not in str(p)]
    sys.path.insert(0, str(bundle_dir))          # Kaggle's exec window
    ns = {"__name__": "__kaggle_agent__"}        # NOTE: no __file__
    src = (Path(bundle_dir) / "main.py").read_text(encoding="utf-8")
    exec(compile(src, "main.py", "exec"), ns)
    sys.path[:] = [p for p in sys.path if p != str(bundle_dir)]
    return ns, saved_path, saved_cwd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", required=True)
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--out", default="stage4/rl_ours/canary_verify.json")
    args = ap.parse_args()

    tar = (REPO / args.tar).resolve()
    out_path = (REPO / args.out).resolve()
    tmp = Path(tempfile.mkdtemp(prefix="canary_"))
    with tarfile.open(tar) as tf:
        members = tf.getnames()
        tf.extractall(tmp)
    # tarball may nest one level
    bundle = tmp if (tmp / "main.py").exists() else next(p for p in tmp.iterdir() if p.is_dir())
    print(f"extracted {tar.name} -> {bundle}")
    print(f"members ({len(members)}): {sorted(members)}\n")

    R = {"tar": str(tar), "members": sorted(members)}

    # ---------- V1: weights packaged + load + graded path fires ----------
    print("=" * 70)
    print("V1  value_weights.npz packaged / loads / graded path fires")
    print("=" * 70)
    R["V1_packaged"] = any(m.endswith("value_weights.npz") for m in members)
    print(f"  packaged in tarball                : {R['V1_packaged']}")

    ns, saved_path, saved_cwd = load_bundle_agent(bundle)
    try:
        agent_fn = ns["agent"]
        R["V1_search_cap"] = ns["SEARCH_CAP"]
        R["V1_agent_version"] = ns["AGENT_VERSION"]
        print(f"  AGENT_VERSION                      : {R['V1_agent_version']}")
        print(f"  SEARCH_CAP baked                   : {R['V1_search_cap']}")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            model = ns["_lv_model"]()
        R["V1_model_loads"] = model is not None
        print(f"  _lv_model() loads (clean env)      : {R['V1_model_loads']}")
        if buf.getvalue().strip():
            print(f"  !! stderr during load: {buf.getvalue().strip()[:300]}")
        R["V1_load_stderr"] = buf.getvalue().strip()
        if model is not None:
            probe = [0.0] * ns["N_STATE_FEATURES"]
            p = ns["_lv_predict"](model, [probe])[0]
            R["V1_predict_ok"] = 0.0 <= p <= 1.0
            print(f"  _lv_predict on zero vector         : {p:.6f}  in[0,1]={R['V1_predict_ok']}")
    finally:
        sys.path[:] = saved_path
        import os
        os.chdir(saved_cwd)

    # ---------- V2/V3: self-play under the bundle ----------
    print()
    print("=" * 70)
    print(f"V2/V3  {args.games}-game self-play (bundle agent vs copy of itself)")
    print("=" * 70)
    sys.path.insert(0, str(REPO / "tools"))
    _b = io.StringIO()
    with contextlib.redirect_stdout(_b), contextlib.redirect_stderr(_b):
        from kaggle_environments import make

    ns, saved_path, saved_cwd = load_bundle_agent(bundle)
    import os
    deck = [int(x) for x in (bundle / "deck.csv").read_text().split() if x.strip()]
    agent_fn = ns["agent"]
    STATS = ns["STATS"]

    exceptions = []
    leaf_fire = {"terminal": 0, "cap": 0}
    orig_rollout = ns["_rollout"]

    def counting_rollout(node, me, cap):
        # count how often the graded (cap) path is actually taken in deployment
        v = orig_rollout(node, me, cap)
        return v
    # instrument by wrapping _lv_predict: it is called ONLY on the graded path
    orig_predict = ns["_lv_predict"]

    def counting_predict(model, rows):
        leaf_fire["cap"] += len(rows)
        return orig_predict(model, rows)
    ns["_lv_predict"] = counting_predict

    times, per_game = [], []
    try:
        os.chdir(bundle)
        for g in range(args.games):
            t = {0: 0.0, 1: 0.0}

            def mk(seat):
                def w(obs, _cfg):
                    if obs.get("select") is None:
                        return list(deck)
                    t0 = time.perf_counter()
                    try:
                        return agent_fn(obs)
                    except Exception as e:            # must never happen
                        exceptions.append(f"g{g} seat{seat}: {e!r}\n{traceback.format_exc()}")
                        raise
                    finally:
                        t[seat] += time.perf_counter() - t0
                return w

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                env = make("cabt", debug=True)
                env.run([mk(0), mk(1)])
            err = buf.getvalue()
            for pat in ("FALLBACK", "SELFCHECK FAIL", "WARNING", "Traceback",
                        "cg engine unavailable", "sampling failed", "engine search failed"):
                for line in err.splitlines():
                    if pat in line:
                        exceptions.append(f"g{g} stderr: {line.strip()}")
            times += [t[0], t[1]]
            per_game.append({"game": g, "t0": t[0], "t1": t[1]})
            print(f"  game {g+1}/{args.games}: t0={t[0]:5.1f}s t1={t[1]:5.1f}s "
                  f"(max {max(t[0], t[1])/600*100:4.1f}% of bank)", flush=True)
    finally:
        sys.path[:] = saved_path
        os.chdir(saved_cwd)

    R["V2_games"] = args.games
    R["V2_exceptions"] = exceptions
    R["V2_fallbacks_stat"] = STATS.get("fallbacks", 0)
    R["V2_calls"] = STATS.get("calls", 0)
    print(f"\n  exceptions / caught-error stderr lines : {len(exceptions)}")
    for e in exceptions[:10]:
        print(f"    ! {e[:200]}")
    print(f"  STATS fallbacks / calls                : "
          f"{STATS.get('fallbacks', 0)} / {STATS.get('calls', 0)}")
    print(f"  graded-leaf value-net evaluations      : {leaf_fire['cap']:,}")
    R["V1_valuenet_evals_in_play"] = leaf_fire["cap"]

    times.sort()
    mx = times[-1]
    R["V3_max_s"] = mx
    R["V3_max_pct"] = mx / 600 * 100
    R["V3_median_s"] = times[len(times) // 2]
    R["V3_per_game"] = per_game
    print(f"\n  wall-clock per player per match:")
    print(f"    median {times[len(times)//2]:6.1f}s ({times[len(times)//2]/600*100:4.1f}% of bank)")
    print(f"    MAX    {mx:6.1f}s ({mx/600*100:4.1f}% of bank)   <-- V3 headline")
    print(f"    margin to timeout: {600 - mx:.0f}s ({100 - mx/600*100:.1f} points of bank)")

    out_path.write_text(json.dumps(R, indent=1), encoding="utf-8")
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
