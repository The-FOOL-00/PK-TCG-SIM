"""Build the Phase A2 PROBE submission: v1 behavior + on-ladder engine test.

The probe answers every selection exactly like v1 (agent() is called
unconditionally; the hook can only add stderr lines), but:
  - at module load it tries to import the bundled cg engine and reports
    platform + outcome to stderr;
  - at the first MAIN-phase single-select it runs ONE search_begin/search_step
    cycle on a mirror-guess determinization and reports timings (or the error).
Submitting it answers the one question we cannot answer locally: does
libcg.so load and search inside the ladder's agent sandbox? Cost: one slot,
playing at v1 strength.

Bundle layout (nested cg/ like the official sample submission):
  main.py  deck.csv  card_data.json  cg/{__init__,api,game,sim,utils}.py
  cg/{cg.dll, libcg.so, libcg-arm64.so, libcg.dylib}

Checks:
  1. kaggle-style exec import check (no __file__, cwd elsewhere): probe agent
     is the last callable, deck + fallback answers correct, cg imported.
  2. same with cg/ stripped: cg-import FAILED logged, v1 play unaffected.
  3. one real cabt game probe-vs-v1 via kaggle_environments: statuses DONE,
     stderr contains "[probe ...] search OK".

Run:  python tools/build_probe.py
Out:  build/probe/  +  build/probe_submission.tar.gz
"""

import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CG = REPO / "sample_submission" / "sample_submission" / "cg"
CG_FILES = ["__init__.py", "api.py", "game.py", "sim.py", "utils.py",
            "cg.dll", "libcg.so", "libcg-arm64.so", "libcg.dylib"]
MAX_SIZE_MIB = 190

PROBE_BLOCK = r'''

# ===========================================================================
# Phase A2 probe: on-ladder engine feasibility test. Plays EXACTLY like v1
# (every answer comes from agent(); the hook is wrapped in try/except and can
# only emit stderr lines):
#   [probe ...] cg-import ...  at module load (agent dir on sys.path only
#                              while Kaggle exec()s main.py, so import here)
#   [probe ...] search ...     once, at the first MAIN-phase single-select:
#                              one search_begin/search_step cycle on a
#                              mirror-guess determinization, with timings.
# ===========================================================================

PROBE_VERSION = "ptcg-probe-v1.0.0"
_PROBE = {"lib": None, "done": False}


def _probe_log(msg):
    print("[probe %s] %s" % (PROBE_VERSION, msg), file=sys.stderr, flush=True)


def _probe_import_cg():
    import platform
    try:
        marker = _find_file(os.path.join("cg", "sim.py"))
        if marker:
            parent = os.path.dirname(os.path.dirname(marker))
            if parent not in sys.path:
                sys.path.insert(0, parent)
        import cg.sim as _sim  # loads the platform shared lib + GameInitialize
        _PROBE["lib"] = _sim.lib
        _probe_log("cg-import OK platform=%s-%s python=%s"
                   % (platform.system(), platform.machine(),
                      sys.version.split()[0]))
    except Exception as e:
        _probe_log("cg-import FAILED (%r) - heuristic-only mode" % e)


def _probe_visible_ids(player, include_hand):
    ids = []
    if include_hand:
        ids += [c["id"] for c in player.get("hand") or [] if c]
    for pk in (player.get("active") or []) + (player.get("bench") or []):
        if pk:  # face-down active shows as None
            ids.append(pk["id"])
            for zone in ("energyCards", "tools", "preEvolution"):
                ids += [c["id"] for c in pk.get(zone) or [] if c]
    ids += [c["id"] for c in player.get("discard") or [] if c]
    ids += [c["id"] for c in player.get("prize") or [] if c]
    return ids


def _probe_fill_prize(prize, sampled):
    out, k = [], 0
    for c in prize or []:
        if c:
            out.append(c["id"])
        else:
            out.append(sampled[k])
            k += 1
    return out


def _probe_determinize(cur, me, rng):
    """Uniform hidden-zone sample; opponent 60-card list mirror-guessed as
    DECK (probe only needs the call to be mechanically valid, not accurate)."""
    from collections import Counter
    mine, theirs = cur["players"][me], cur["players"][1 - me]

    my_pool = list((Counter(DECK) - Counter(_probe_visible_ids(mine, True))).elements())
    rng.shuffle(my_pool)
    n_hp = sum(1 for c in mine.get("prize") or [] if not c)
    my_prize = _probe_fill_prize(mine.get("prize"), my_pool[:n_hp])
    my_deck = my_pool[n_hp:]

    opp_pool = list((Counter(DECK) - Counter(_probe_visible_ids(theirs, False))).elements())
    rng.shuffle(opp_pool)
    opp_active = []
    active = theirs.get("active") or []
    if active and active[0] is None:
        basics = [i for i in opp_pool if CARDS.get(i, {}).get("basic")]
        pick = rng.choice(basics) if basics else opp_pool[0]
        opp_pool.remove(pick)
        opp_active = [pick]
    n_hand = theirs.get("handCount") or 0
    opp_hand = opp_pool[:n_hand]
    rest = opp_pool[n_hand:]
    n_ohp = sum(1 for c in theirs.get("prize") or [] if not c)
    opp_prize = _probe_fill_prize(theirs.get("prize"), rest[:n_ohp])
    opp_deck = rest[n_ohp:]
    return (my_deck, my_prize, opp_deck, opp_prize, opp_hand, opp_active)


def _probe_search_once(obs):
    if _PROBE["done"] or _PROBE["lib"] is None:
        return
    sel = obs.get("select")
    cur = obs.get("current")
    sbi = obs.get("search_begin_input")
    if not (isinstance(sel, dict) and isinstance(cur, dict) and sbi
            and cur.get("result", -1) == -1
            and sel.get("type") == 0  # ST_MAIN, the decisions Phase B searches
            and sel.get("minCount", 1) == 1 and sel.get("maxCount", 1) == 1
            and len(sel.get("option") or []) > 1):
        return
    _PROBE["done"] = True
    import ctypes
    import random
    lib = _PROBE["lib"]
    me = cur.get("yourIndex") or 0
    arr = lambda v: (ctypes.c_int * len(v))(*v)  # noqa: E731
    t0 = time.perf_counter()
    ptr = lib.AgentStart()
    md, mp, od, op, oh, oa = _probe_determinize(cur, me, random.Random(0))
    r = json.loads(lib.SearchBegin(
        ptr, sbi.encode("ascii"), len(sbi),
        arr(md), arr(mp), arr(od), arr(op), arr(oh), arr(oa), 0))
    if r.get("error"):
        raise RuntimeError("SearchBegin error %s" % r["error"])
    root = r["state"]
    t1 = time.perf_counter()
    r = json.loads(lib.SearchStep(ptr, root["searchId"], arr([0]), 1))
    if r.get("error"):
        raise RuntimeError("SearchStep error %s" % r["error"])
    t2 = time.perf_counter()
    lib.SearchEnd(ptr)
    _probe_log("search OK turn=%s options=%d begin_ms=%.2f step_ms=%.2f"
               % (cur.get("turn"), len(sel["option"]),
                  (t1 - t0) * 1000.0, (t2 - t1) * 1000.0))


_probe_import_cg()


def agent_probe(obs):
    """Probe entry point (LAST callable in the file => the agent Kaggle runs)."""
    try:
        _probe_search_once(obs)
    except Exception as e:
        _PROBE["done"] = True
        _probe_log("search FAILED (%r) - v1 play unaffected" % e)
    return agent(obs)
'''

IMPORT_CHECK_CODE = r'''
import os, sys
bundle, mode = sys.argv[1], sys.argv[2]
with open(os.path.join(bundle, "main.py"), "r", encoding="utf-8") as f:
    src = f.read()
sys.path.append(bundle)  # kaggle keeps agent dir on sys.path during exec only
env = {}
exec(compile(src, "main.py", "exec"), env)
ag = [v for v in env.values() if callable(v)][-1]
assert ag.__name__ == "agent_probe", "last callable is %s" % ag.__name__

deck = ag({"select": None, "logs": [], "current": None})
assert isinstance(deck, list) and len(deck) == 60 and all(isinstance(x, int) for x in deck)

# malformed observation (live select, current=None) must hit the v1 fallback
r = ag({"select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1,
                   "option": [{"type": 14}]}, "logs": [], "current": None})
assert r == [0], r

if mode == "cg":
    assert env["_PROBE"]["lib"] is not None, "bundled cg failed to load"
else:
    assert env["_PROBE"]["lib"] is None, "cg loaded but bundle has no cg/"
print("PROBE-IMPORT-OK mode=%s" % mode)
'''

SMOKE_CODE = r'''
import sys
from kaggle_environments import make
env = make("cabt")
env.run([sys.argv[1], sys.argv[2]])
s = env.state
# agent stdout/stderr is captured into env.logs, not the process streams
for step in env.logs:
    for entry in step or []:
        for stream in ("stdout", "stderr"):
            txt = (entry or {}).get(stream) or ""
            for line in txt.splitlines():
                if line.strip():
                    print("AGENTLOG %s" % line)
print("SMOKE status=%s,%s rewards=%s,%s"
      % (s[0].status, s[1].status, s[0].reward, s[1].reward))
'''


def run_check(code, args, cwd, timeout=300):
    proc = subprocess.run([sys.executable, "-c", code] + [str(a) for a in args],
                          cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc


def build():
    bundle = REPO / "build" / "probe"
    if bundle.exists():
        shutil.rmtree(bundle)
    (bundle / "cg").mkdir(parents=True)

    src = (REPO / "main.py").read_text(encoding="utf-8")
    if "def agent(obs):" not in src:
        raise SystemExit("main.py: agent() not found")
    (bundle / "main.py").write_text(src + PROBE_BLOCK, encoding="utf-8")
    shutil.copy2(REPO / "deck.csv", bundle / "deck.csv")
    shutil.copy2(REPO / "card_data.json", bundle / "card_data.json")
    for name in CG_FILES:
        shutil.copy2(SAMPLE_CG / name, bundle / "cg" / name)
    print(f"[1/5] bundle assembled at {bundle}")

    with tempfile.TemporaryDirectory() as td:
        proc = run_check(IMPORT_CHECK_CODE, [bundle, "cg"], td)
    if proc.returncode != 0 or "PROBE-IMPORT-OK" not in proc.stdout:
        raise SystemExit(f"import check failed:\n{proc.stdout}\n{proc.stderr}")
    if "cg-import OK" not in proc.stderr:
        raise SystemExit(f"probe did not report cg-import OK:\n{proc.stderr}")
    print(f"[2/5] import check OK ({proc.stderr.strip().splitlines()[-1]})")

    with tempfile.TemporaryDirectory() as td:
        stripped = Path(td) / "stripped"
        shutil.copytree(bundle, stripped)
        shutil.rmtree(stripped / "cg")
        proc = run_check(IMPORT_CHECK_CODE, [stripped, "nocg"], td)
    if proc.returncode != 0 or "PROBE-IMPORT-OK" not in proc.stdout:
        raise SystemExit(f"no-cg fallback check failed:\n{proc.stdout}\n{proc.stderr}")
    if "cg-import FAILED" not in proc.stderr:
        raise SystemExit(f"probe did not report cg-import FAILED:\n{proc.stderr}")
    print("[3/5] no-cg fallback check OK (import failure logged, v1 play intact)")

    proc = run_check(SMOKE_CODE, [bundle / "main.py", REPO / "main.py"], REPO,
                     timeout=600)
    combined = proc.stdout + proc.stderr
    ok = (proc.returncode == 0 and "status=DONE,DONE" in proc.stdout
          and "search OK" in combined)
    if not ok:
        raise SystemExit(f"smoke game failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    probe_lines = [l for l in combined.splitlines() if "[probe" in l]
    print("[4/5] smoke game OK: " + proc.stdout.strip().splitlines()[-1])
    for line in probe_lines:
        print("       " + line)

    tar_path = REPO / "build" / "probe_submission.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in ["main.py", "deck.csv", "card_data.json"]:
            tar.add(bundle / name, arcname=name)
        tar.add(bundle / "cg", arcname="cg",
                filter=lambda ti: None if "__pycache__" in ti.name else ti)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getnames()
    bad = [m for m in members if "\\" in m or ".." in m]
    if bad:
        raise SystemExit(f"bad member names: {bad}")
    size_mib = tar_path.stat().st_size / (1024 * 1024)
    if size_mib > MAX_SIZE_MIB:
        raise SystemExit(f"{size_mib:.1f} MiB exceeds {MAX_SIZE_MIB} MiB")
    print(f"[5/5] {tar_path.relative_to(REPO)} OK: {size_mib:.2f} MiB, "
          f"{len(members)} members (cg/ nested like the official sample)")
    print("PROBE BUILD OK")


if __name__ == "__main__":
    build()
