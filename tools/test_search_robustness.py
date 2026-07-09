"""B4 fault injection: every search failure mode must degrade to v1.

Method: record real decision observation streams (search OFF = pure v1
answers as the reference), then replay the SAME stream through agent() under
each fault scenario with SEARCH on. In every scenario the answers must be
byte-identical to v1's — the search may only ever change answers when it is
healthy. Scenarios:

  1. no-engine     cg import failed (_SES poisoned)
  2. begin-raises  SearchBegin throws on every call
  3. sampler-raises _sample_determinization throws on every call
  4. budget-zero   governor returns 0 budget -> sticky heuristic mode
  5. healthy       (control) search runs and IS allowed to differ; its
                   answers must still all be legal per C1 validation

Run:  python tools/test_search_robustness.py [--games 4]
"""

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import main  # noqa: E402
from tools import deck_compare  # noqa: E402


def record_streams(games):
    """Play v1-vs-v1 games, recording seat-0's obs stream + v1 answers."""
    deck = deck_compare.read_deck(REPO / "deck.csv")
    streams = []
    for g in range(games):
        stream = []

        def rec(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            main.SEARCH = False
            ans = main.agent(obs)
            stream.append((json.loads(json.dumps(obs)), list(ans)))
            return ans

        def plain(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            main.SEARCH = False
            return main.agent(obs)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = deck_compare.make("cabt", debug=True)
            env.run([rec, plain] if g % 2 == 0 else [plain, rec])
        assert all(env.state[i].status == "DONE" for i in (0, 1))
        streams.append(stream)
    return streams


def fresh_state():
    """Reset all module search state between scenarios."""
    main._TRACKERS.clear()
    main._GOV.update({"n_dec": 0, "spent": 0.0, "max_dec": 0.0, "sticky": False,
                      "ema_det": None, "ring": [], "games": 0})
    main.SEARCH_DET, main.SEARCH_ROLL, main.SEARCH_TOPK = 16, 2, 4
    main.SEARCH_CAP, main.ROLLOUT, main.GOVERNOR = 0, "v1", True


def replay(stream, expect_equal, label):
    n_diff = 0
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        for obs, v1_ans in stream:
            main.SEARCH = True
            ans = main.agent(obs)
            sel = obs.get("select") or {}
            checked, ok = main._validate_result(list(ans), sel)
            assert checked == list(ans), f"{label}: illegal answer {ans}"
            if list(ans) != v1_ans:
                n_diff += 1
    err_lines = [l for l in buf.getvalue().splitlines() if "[search]" in l]
    if expect_equal:
        assert n_diff == 0, f"{label}: {n_diff} answers differ from v1 under fault"
    return n_diff, len(err_lines)


def main_run(games):
    assert main._search_lib() is not None, "engine needed (healthy control)"
    streams = record_streams(games)
    n_dec = sum(len(s) for s in streams)
    print(f"recorded {games} games, {n_dec} decisions (v1 reference answers)")

    lib_backup = dict(main._SES)

    # 1. no-engine
    fresh_state()
    main._SES.update({"lib": None, "ptr": None, "tried": True})
    for s in streams:
        replay(s, True, "no-engine")
    main._SES.update(lib_backup)
    print("scenario 1 no-engine        : all answers == v1  OK")

    # 2. SearchBegin raises
    fresh_state()
    orig_begin = main._sb_begin
    main._sb_begin = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected"))
    total_err = 0
    for s in streams:
        _, ne = replay(s, True, "begin-raises")
        total_err += ne
    main._sb_begin = orig_begin
    print(f"scenario 2 begin-raises     : all answers == v1  OK ({total_err} stderr lines)")

    # 3. sampler raises
    fresh_state()
    orig_sample = main._sample_determinization
    main._sample_determinization = \
        lambda *a, **k: (_ for _ in ()).throw(ValueError("injected"))
    for s in streams:
        replay(s, True, "sampler-raises")
    main._sample_determinization = orig_sample
    print("scenario 3 sampler-raises   : all answers == v1  OK")

    # 4. budget zero -> sticky heuristic
    fresh_state()
    orig_budget = main._gov_budget
    main._gov_budget = lambda obs: 0.0
    for s in streams:
        replay(s, True, "budget-zero")
        assert main._GOV["sticky"], "budget-zero must latch sticky mode"
        fresh_state()
        main._gov_budget = lambda obs: 0.0
    main._gov_budget = orig_budget
    print("scenario 4 budget-zero      : sticky latched, all answers == v1  OK")

    # 5. healthy control: search allowed to differ, all answers legal
    fresh_state()
    diffs = 0
    for s in streams:
        d, _ = replay(s, False, "healthy")
        diffs += d
    print(f"scenario 5 healthy control  : {diffs}/{n_dec} answers changed by search, "
          f"all legal  OK")
    assert diffs > 0, "healthy search never changed a decision — suspicious"

    main.SEARCH = False
    print("\nB4 FAULT-INJECTION SUITE: ALL OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=4)
    args = ap.parse_args()
    main_run(args.games)
