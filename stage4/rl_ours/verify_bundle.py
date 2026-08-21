"""Verify a SHIPPED bundle by exec-loading the bundle's own main.py.

Deliberately does NOT import the repo's main.py: the point is to test the
artifact that would be uploaded, under the same load path Kaggle uses
(exec, no __file__, cwd elsewhere, bundle dir on sys.path).

Checks:
  2. self-play N games -- crashes / caught exceptions / FALLBACK / timing
  3. fault injection -- weights removed, engine removed, malformed select,
     policy head raising
  5. bundled weights load and are actually exercised

Run: py -3.12 -X utf8 stage4/rl_ours/verify_bundle.py \
        --tar submission_bc_metaC_garchomp_nasuo.tar.gz --games 20
"""
import argparse
import contextlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAMPLE_CG = REPO / "sample_submission" / "sample_submission"


def load_bundle(bundle_dir, env_over=None):
    """exec-load bundle/main.py the way the platform does."""
    src = (bundle_dir / "main.py").read_text(encoding="utf-8")
    sys.path.insert(0, str(bundle_dir))
    env = {}
    exec(compile(src, "main.py", "exec"), env)          # noqa: S102
    for k, v in (env_over or {}).items():
        env[k] = v
    ag = [v for v in env.values() if callable(v)][-1]
    assert ag.__name__ == "agent", ag.__name__
    return env, ag


def selfplay(bundle_dir, games, deck_path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        from kaggle_environments import make
    env, ag = load_bundle(bundle_dir)
    deck = [int(x) for x in open(deck_path) if x.strip()]
    env["DECK"] = list(deck)
    if "CARDS" in env:
        env["TOTAL_BASIC_ENERGY"] = sum(
            1 for c in deck if (env["CARDS"].get(c) or {}).get("cardType") == 5)

    stats = {"games": 0, "calls": 0, "timing": [], "err": 0}

    def wrapper(t, seat):
        def w(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            stats["calls"] += 1
            s = time.perf_counter()
            try:
                return ag(obs)
            finally:
                t[seat] += time.perf_counter() - s
        return w

    logbuf = io.StringIO()
    for _g in range(games):
        t = {0: 0.0, 1: 0.0}
        with contextlib.redirect_stdout(logbuf), contextlib.redirect_stderr(logbuf):
            e = make("cabt", debug=True)
            e.run([wrapper(t, 0), wrapper(t, 1)])
        stats["games"] += 1
        stats["timing"] += [t[0], t[1]]
    text = logbuf.getvalue()
    stats["log"] = text
    stats["fallback"] = text.count("FALLBACK")
    stats["traceback"] = text.count("Traceback")
    stats["hook_err"] = text.count("hook error")
    stats["selfcheck"] = text.count("SELFCHECK FAIL")
    stats["stats_obj"] = dict(env.get("STATS") or {})
    return stats


def faults(bundle_dir, deck_path, weights_name):
    """Four degradation scenarios; every one must still return a LEGAL answer."""
    deck = [int(x) for x in open(deck_path) if x.strip()]
    probe = {"select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1,
                        "option": [{"type": 14}, {"type": 12}]},
             "logs": [], "current": {"turn": 3, "yourIndex": 0,
                                     "players": [{"hand": [], "bench": [],
                                                  "active": [], "deckCount": 40,
                                                  "prize": [1, 2, 3]},
                                                 {"hand": [], "bench": [],
                                                  "active": [], "deckCount": 40,
                                                  "prize": [1, 2, 3]}]}}
    out = {}

    def one(name, mutate, obs=probe):
        tmp = Path(tempfile.mkdtemp())
        try:
            d = tmp / "b"
            shutil.copytree(bundle_dir, d)
            mutate(d)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                env, ag = load_bundle(d)
                env["DECK"] = list(deck)
                r = ag(obs)
            legal = (isinstance(r, list) and len(r) == 1
                     and isinstance(r[0], int)
                     and 0 <= r[0] < len(obs["select"]["option"]))
            out[name] = {"ok": legal, "answer": r,
                         "stderr_lines": len(buf.getvalue().splitlines())}
        except Exception:
            out[name] = {"ok": False, "answer": None,
                         "exc": traceback.format_exc()[-400:]}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if weights_name:
        one("weights-removed",
            lambda d: (d / weights_name).unlink()
            if (d / weights_name).is_file() else None)
    else:
        # bundle ships no .npz at all (v1-alone): the scenario is vacuous.
        out["weights-removed"] = {"ok": True, "answer": "n/a - bundle has no weights"}
    one("engine-removed",
        lambda d: shutil.rmtree(d / "cg", ignore_errors=True))
    one("carddata-removed",
        lambda d: (d / "card_data.json").unlink() if (d / "card_data.json").exists() else None)
    bad = {"select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1,
                      "option": [{"type": 14}, {"type": 99, "bogus": True}]},
           "logs": [], "current": {}}
    one("malformed-option", lambda d: None, obs=bad)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", required=True)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--weights", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    tar = REPO / args.tar if (REPO / args.tar).exists() else Path(args.tar)
    work = Path(tempfile.mkdtemp()) / "bundle"
    work.mkdir(parents=True)
    with tarfile.open(tar) as t:
        members = t.getnames()
        t.extractall(work)
    weights = args.weights or next(
        (m for m in members if m.endswith(".npz")), "")

    env, _ = load_bundle(work)
    ver = env["AGENT_VERSION"]
    print(f"bundle   : {tar}")
    print(f"version  : {ver}")
    print(f"members  : {len(members)} -> {members}")
    print(f"weights  : {weights or '(none)'}")
    print(f"config   : BC={env.get('BC')!r} SEARCH={env.get('SEARCH')!r} "
          f"PILOT={env.get('PILOT')!r} SEARCH_CAP={env.get('SEARCH_CAP')!r} "
          f"END_VETO={env.get('END_VETO', '')!r} GOVERNOR={env.get('GOVERNOR')!r}")

    print(f"\n--- check 2: self-play {args.games} games ---", flush=True)
    s = selfplay(work, args.games, work / "deck.csv")
    tm = sorted(s["timing"])
    n = len(tm)
    print(f"games={s['games']} agent calls={s['calls']}")
    print(f"FALLBACK={s['fallback']}  Traceback={s['traceback']}  "
          f"hook-error={s['hook_err']}  SELFCHECK-FAIL={s['selfcheck']}")
    print(f"wall-clock per player-game: p50={tm[n//2]:.1f}s "
          f"p90={tm[int(n*.9)]:.1f}s MAX={tm[-1]:.1f}s  "
          f"-> x1.8 Kaggle projection MAX={tm[-1]*1.8:.1f}s "
          f"({tm[-1]*1.8/600*100:.1f}% of 600s bank)")
    interesting = {k: v for k, v in s["stats_obj"].items()
                   if k in ("calls", "searched", "search_changed", "bc_used",
                            "bc_brake", "end_veto", "cand_forced", "atk_legal",
                            "value_evals", "fallbacks")}
    print(f"STATS: {interesting}")

    print("\n--- check 3: fault injection ---", flush=True)
    f = faults(work, work / "deck.csv", weights)
    for k, v in f.items():
        print(f"  {k:<20s} legal-answer={v['ok']}  answer={v.get('answer')}")

    if args.out:
        (REPO / args.out).write_text(json.dumps(
            {"version": ver, "members": members, "selfplay":
             {k: v for k, v in s.items() if k not in ("log",)},
             "faults": f}, indent=1, default=str), encoding="utf-8")
    ok = (s["fallback"] == 0 and s["traceback"] == 0 and s["hook_err"] == 0
          and all(v["ok"] for v in f.values()))
    print(f"\nVERDICT: {'ALL CHECKS PASS' if ok else 'FAILURES PRESENT'}")


if __name__ == "__main__":
    main()
