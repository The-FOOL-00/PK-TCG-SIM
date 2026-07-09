"""Build + verify the Phase F belief-search submission bundle.

Bundle (cg/ nested exactly like the official sample):
  main.py  deck.csv  card_data.json  cg/{*.py, all-platform binaries}
  [+ value_weights.npz]   only if the ship config truncates rollouts (CAP>0)
  [+ policy_weights.npz]  only if the ship config uses S1 rollouts (ROLLOUT=s1)

The shipped main.py has the search baked ON: PTCG_SEARCH/GOVERNOR default to 1,
ROLLOUT/SEARCH_CAP defaults set to the chosen config, AGENT_VERSION stamped.
card_data.json carries full card data for EVERY engine card (so the v1 scorer
and the rollout policy know opponent cards too) plus the lightweight `pool`
the belief sampler reads.

Checks (all must pass):
  1. deck validates (60, 4-copy, <=1 ACE SPEC, has a Basic)
  2. exec-style load in a bare temp dir (no __file__, cwd elsewhere): agent is
     the last callable, deck + fallback answers legal, engine imports, search
     flag baked on
  3. fault-injection: with cg/ deleted the agent still loads and plays v1
  4. 30-game zero-crash / zero-fallback self-play at the ship config
  5. size < 190 MiB, archive members flat at top level except cg/

Run:  python tools/build_search_submission.py --rollout v1 --cap 0
      (--rollout s1 bundles policy_weights.npz; --cap 10 bundles value_weights.npz)
"""

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CG = REPO / "sample_submission" / "sample_submission" / "cg"
CG_FILES = ["__init__.py", "api.py", "game.py", "sim.py", "utils.py",
            "cg.dll", "libcg.so", "libcg-arm64.so", "libcg.dylib"]
MAX_SIZE_MIB = 190
SHIP_VERSION = "ptcg-search-v2.0.0"

sys.path.insert(0, str(SAMPLE_CG.parent))


def load_engine_db():
    from cg.api import all_attack, all_card_data
    return ({c.cardId: c for c in all_card_data()},
            {a.attackId: a for a in all_attack()})


def read_deck(path):
    with open(path) as f:
        return [int(x.strip()) for x in f if x.strip()]


def validate_deck(deck, cards):
    errs = []
    if len(deck) != 60:
        errs.append(f"{len(deck)} cards, expected 60")
    unknown = sorted({c for c in deck if c not in cards})
    if unknown:
        return errs + [f"unknown ids: {unknown}"]
    names = Counter()
    ace = basics = 0
    for cid in deck:
        c = cards[cid]
        if c.cardType != 5:
            names[c.name] += 1
        ace += c.aceSpec
        basics += c.basic
    over = {n: k for n, k in names.items() if k > 4}
    if over:
        errs.append(f">4 copies: {over}")
    if ace > 1:
        errs.append(f"{ace} ACE SPEC")
    if basics == 0:
        errs.append("no Basic Pokemon")
    return errs


def bake_card_data(cards, attacks):
    """Full data for EVERY engine card + the lightweight belief pool."""
    out_cards, out_attacks = {}, {}
    pool = {}
    for cid, c in cards.items():
        out_cards[cid] = {
            "cardId": c.cardId, "name": c.name, "cardType": int(c.cardType),
            "hp": c.hp, "retreatCost": c.retreatCost,
            "energyType": int(c.energyType) if c.energyType is not None else None,
            "weakness": int(c.weakness) if c.weakness is not None else None,
            "resistance": int(c.resistance) if c.resistance is not None else None,
            "basic": c.basic, "stage1": c.stage1, "stage2": c.stage2,
            "ex": c.ex, "megaEx": c.megaEx, "aceSpec": c.aceSpec,
            "evolvesFrom": c.evolvesFrom, "attacks": list(c.attacks or []),
            "skills": [{"name": s.name, "text": s.text} for s in (c.skills or [])],
        }
        for aid in c.attacks or []:
            if aid in attacks and aid not in out_attacks:
                a = attacks[aid]
                out_attacks[aid] = {"attackId": a.attackId, "name": a.name,
                                    "damage": a.damage,
                                    "energies": [int(e) for e in (a.energies or [])],
                                    "text": a.text}
        pool[cid] = {"name": c.name, "cardType": int(c.cardType),
                     "energyType": int(c.energyType) if c.energyType is not None else None,
                     "basic": bool(c.basic)}
    return {"cards": out_cards, "attacks": out_attacks, "pool": pool}


def bake_ship_config(main_path, rollout, cap):
    """Flip search defaults ON and stamp the config into the bundled main.py."""
    src = main_path.read_text(encoding="utf-8")
    subs = [
        ('SEARCH = os.environ.get("PTCG_SEARCH", "0") == "1"',
         'SEARCH = os.environ.get("PTCG_SEARCH", "1") == "1"'),
        ('GOVERNOR = os.environ.get("PTCG_GOVERNOR", "1") == "1"',
         'GOVERNOR = os.environ.get("PTCG_GOVERNOR", "1") == "1"'),
        ('ROLLOUT = os.environ.get("PTCG_ROLLOUT", "v1")',
         f'ROLLOUT = os.environ.get("PTCG_ROLLOUT", "{rollout}")'),
        ('SEARCH_CAP = int(os.environ.get("PTCG_SEARCH_CAP", "0"))',
         f'SEARCH_CAP = int(os.environ.get("PTCG_SEARCH_CAP", "{cap}"))'),
        ('AGENT_VERSION = "ptcg-heuristic-v1.0.0"',
         f'AGENT_VERSION = "{SHIP_VERSION}"'),
    ]
    for old, new in subs:
        if old not in src:
            raise SystemExit(f"bake: expected line not found: {old!r}")
        src = src.replace(old, new)
    main_path.write_text(src, encoding="utf-8")


EXEC_CHECK = r'''
import os, sys
bundle, want_cg = sys.argv[1], sys.argv[2] == "cg"
with open(os.path.join(bundle, "main.py"), encoding="utf-8") as f:
    src = f.read()
sys.path.append(bundle)
env = {}
exec(compile(src, "main.py", "exec"), env)
ag = [v for v in env.values() if callable(v)][-1]
assert ag.__name__ == "agent", ag.__name__
assert env["SEARCH"] is True, "search flag not baked on"
assert env["AGENT_VERSION"].startswith("ptcg-search"), env["AGENT_VERSION"]
deck = ag({"select": None, "logs": [], "current": None})
assert isinstance(deck, list) and len(deck) == 60 and all(isinstance(x, int) for x in deck)
r = ag({"select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1,
                   "option": [{"type": 14}]}, "logs": [], "current": None})
assert r == [0], r
eng = env["_search_lib"]()
if want_cg:
    assert eng is not None, "bundled cg failed to load"
    assert len(env["_pool"]()) > 1000, "card pool missing"
else:
    assert eng is None, "cg loaded but bundle has none"
print("EXEC-CHECK-OK cg=%s pool=%d" % (want_cg, len(env["_pool"]())))
'''


def run(code, args, cwd, timeout=300):
    return subprocess.run([sys.executable, "-c", code, *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, timeout=timeout)


def build(rollout, cap, games):
    cards, attacks = load_engine_db()
    deck = read_deck(REPO / "deck.csv")
    errs = validate_deck(deck, cards)
    if errs:
        raise SystemExit("deck INVALID: " + "; ".join(errs))
    print(f"[1/6] deck.csv valid (60 cards, {len(set(deck))} unique)")

    need_value = cap > 0
    need_policy = rollout == "s1"
    extra = ([("value_weights.npz", need_value)] +
             [("policy_weights.npz", need_policy)])
    for fn, need in extra:
        if need and not (REPO / fn).is_file():
            raise SystemExit(f"{fn} required for this config but missing")

    bundle = REPO / "build" / "search_bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    (bundle / "cg").mkdir(parents=True)

    shutil.copy2(REPO / "main.py", bundle / "main.py")
    shutil.copy2(REPO / "deck.csv", bundle / "deck.csv")
    (bundle / "card_data.json").write_text(
        json.dumps(bake_card_data(cards, attacks), indent=1), encoding="utf-8")
    for fn, need in extra:
        if need:
            shutil.copy2(REPO / fn, bundle / fn)
    for name in CG_FILES:
        shutil.copy2(SAMPLE_CG / name, bundle / "cg" / name)
    bake_ship_config(bundle / "main.py", rollout, cap)
    top_files = ["main.py", "deck.csv", "card_data.json"] + \
                [fn for fn, need in extra if need]
    print(f"[2/6] bundle assembled: {top_files} + cg/  "
          f"(config: belief=comp rollout={rollout} cap={cap} governor=on)")

    with tempfile.TemporaryDirectory() as td:
        p = run(EXEC_CHECK, [bundle, "cg"], td)
    if p.returncode != 0 or "EXEC-CHECK-OK" not in p.stdout:
        raise SystemExit(f"exec-load check FAILED:\n{p.stdout}\n{p.stderr}")
    print(f"[3/6] exec-load check OK ({p.stdout.strip().splitlines()[-1]})")

    with tempfile.TemporaryDirectory() as td:
        stripped = Path(td) / "b"
        shutil.copytree(bundle, stripped)
        shutil.rmtree(stripped / "cg")
        p = run(EXEC_CHECK, [stripped, "nocg"], td)
    if p.returncode != 0 or "EXEC-CHECK-OK" not in p.stdout:
        raise SystemExit(f"no-cg fallback FAILED:\n{p.stdout}\n{p.stderr}")
    print("[4/6] no-cg fallback OK (agent loads + plays v1 without engine)")

    p = run(SMOKE_CHECK, [bundle / "main.py", rollout, cap, games], REPO, timeout=1200)
    if p.returncode != 0 or "SMOKE-OK" not in p.stdout:
        raise SystemExit(f"{games}-game smoke FAILED:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    print(f"[5/6] {p.stdout.strip().splitlines()[-1]}")

    tar_path = REPO / "submission_search.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in top_files:
            tar.add(bundle / name, arcname=name)
        tar.add(bundle / "cg", arcname="cg",
                filter=lambda ti: None if "__pycache__" in ti.name else ti)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getnames()
    bad = [m for m in members if "\\" in m or ".." in m]
    if bad:
        raise SystemExit(f"bad members: {bad}")
    size_mib = tar_path.stat().st_size / (1024 * 1024)
    if size_mib > MAX_SIZE_MIB:
        raise SystemExit(f"{size_mib:.1f} MiB > {MAX_SIZE_MIB}")
    print(f"[6/6] {tar_path.name} OK: {size_mib:.2f} MiB, {len(members)} members")
    print(f"SEARCH BUNDLE OK  ({SHIP_VERSION})")


SMOKE_CHECK = r'''
import io, contextlib, sys, time
sys.path.insert(0, r"{repo}".format(repo=r"''' + str(REPO) + r'''"))
main_path, rollout, cap, games = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
import main
from tools import deck_compare
deck = deck_compare.read_deck(main.DECK) if False else deck_compare.read_deck(r"''' + str(REPO / "deck.csv") + r'''")
crashes = fallbacks = 0
dec_ms = []
for g in range(games):
    def mk(seat):
        def w(obs, _cfg):
            if obs.get("select") is None:
                return list(deck)
            main.SEARCH = True; main.SEARCH_BELIEF = "comp"
            main.ROLLOUT = rollout; main.SEARCH_CAP = cap; main.GOVERNOR = True
            t0 = time.perf_counter(); a = main.agent(obs); dec_ms.append((time.perf_counter()-t0)*1000)
            return a
        return w
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        env = deck_compare.make("cabt", debug=True)
        env.run([mk(0), mk(1)])
    for s in (0, 1):
        if env.state[s].status in ("INVALID", "ERROR", "TIMEOUT"):
            crashes += 1
    fallbacks += main.STATS.get("fallbacks", 0)
    main.STATS["fallbacks"] = 0
dec_ms.sort()
p99 = dec_ms[min(len(dec_ms)-1, int(0.99*len(dec_ms)))]
assert crashes == 0, "crashes=%d" % crashes
assert fallbacks == 0, "fallbacks=%d" % fallbacks
print("SMOKE-OK %d games 0 crash 0 fallback  decision p50 %.0fms p99 %.0fms max %.0fms" % (
    games, dec_ms[len(dec_ms)//2], p99, dec_ms[-1]))
'''


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollout", choices=["v1", "s1"], default="v1")
    ap.add_argument("--cap", type=int, default=0)
    ap.add_argument("--games", type=int, default=30)
    args = ap.parse_args()
    build(args.rollout, args.cap, args.games)
