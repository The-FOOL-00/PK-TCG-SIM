"""Build & Verify Hardened PIMC-1 Garchomp Search Agent (>1000 Elo Target)

Bundles:
  main.py  deck.csv (metaC_garchomp_nasuo.csv)  card_data.json  policy_weights.npz (garchomp_full)  cg/
"""

import sys
import os
import json
import shutil
import tarfile
import tempfile
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CG = REPO / "sample_submission" / "sample_submission" / "cg"
CG_FILES = ["__init__.py", "api.py", "game.py", "sim.py", "utils.py",
            "cg.dll", "libcg.so", "libcg-arm64.so", "libcg.dylib"]
VERSION = "ptcg-search-v1150-garchomp"
DECK_FILE = "metaC_garchomp_nasuo.csv"
OUT_TAR = "submission_garchomp_pimc1000.tar.gz"

sys.path.insert(0, str(SAMPLE_CG.parent))
sys.path.insert(0, str(REPO))

import build_submission
import validate_deck


def bake_hardened_main(main_path):
    src = main_path.read_text(encoding="utf-8")

    substitutions = [
        ('SEARCH = os.environ.get("PTCG_SEARCH", "0") == "1"',
         'SEARCH = os.environ.get("PTCG_SEARCH", "1") == "1"'),
        ('GOVERNOR = os.environ.get("PTCG_GOVERNOR", "1") == "1"',
         'GOVERNOR = os.environ.get("PTCG_GOVERNOR", "1") == "1"'),
        ('EVAL_FIX = os.environ.get("PTCG_EVAL_FIX", "0") == "1"',
         'EVAL_FIX = os.environ.get("PTCG_EVAL_FIX", "1") == "1"'),
        ('PROMOTE_RULE = os.environ.get("PTCG_PROMOTE_RULE", "0") == "1"',
         'PROMOTE_RULE = os.environ.get("PTCG_PROMOTE_RULE", "1") == "1"'),
        ('LETHAL_PROBE = os.environ.get("PTCG_LETHAL_PROBE", "0") == "1"',
         'LETHAL_PROBE = os.environ.get("PTCG_LETHAL_PROBE", "1") == "1"'),
        ('END_VETO = os.environ.get("PTCG_END_VETO", "")',
         'END_VETO = os.environ.get("PTCG_END_VETO", "narrow")'),
        ('BC_CARD_ONLY = os.environ.get("PTCG_BC_CARD_ONLY", "0") == "1"',
         'BC_CARD_ONLY = os.environ.get("PTCG_BC_CARD_ONLY", "1") == "1"'),
        ('BC = os.environ.get("PTCG_BC", "")',
         'BC = os.environ.get("PTCG_BC", "garchomp_full")'),
        ('AGENT_VERSION = "ptcg-heuristic-v1.0.0"',
         f'AGENT_VERSION = "{VERSION}"'),
    ]

    for old, new in substitutions:
        if old not in src:
            raise RuntimeError(f"Expected line not found in main.py: {old!r}")
        src = src.replace(old, new)

    main_path.write_text(src, encoding="utf-8")


def exec_check(bundle_dir, want_cg=True):
    code = r'''
import os, sys
bundle, want_cg = sys.argv[1], sys.argv[2] == "True"
with open(os.path.join(bundle, "main.py"), encoding="utf-8") as f:
    src = f.read()
sys.path.append(bundle)
env = {}
exec(compile(src, "main.py", "exec"), env)
ag = [v for v in env.values() if callable(v)][-1]
assert ag.__name__ == "agent", ag.__name__
assert env["SEARCH"] is True, "SEARCH flag not baked on"
assert env["EVAL_FIX"] is True, "EVAL_FIX not baked on"
assert env["PROMOTE_RULE"] is True, "PROMOTE_RULE not baked on"
assert env["LETHAL_PROBE"] is True, "LETHAL_PROBE not baked on"
assert env["END_VETO"] == "narrow", "END_VETO not narrow"
assert env["AGENT_VERSION"].startswith("ptcg-search"), env["AGENT_VERSION"]
deck = ag({"select": None, "logs": [], "current": None})
assert isinstance(deck, list) and len(deck) == 60, len(deck)
r = ag({"select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1,
                   "option": [{"type": 14}]}, "logs": [], "current": None})
assert r == [0], r
eng = env["_search_lib"]()
if want_cg:
    assert eng is not None, "bundled cg failed to load"
    assert len(env["_pool"]()) > 1000, "card pool missing or empty"
print("EXEC-CHECK-OK cg=%s pool=%d" % (want_cg, len(env["_pool"]())))
'''
    res = subprocess.run([sys.executable, "-c", code, str(bundle_dir), str(want_cg)],
                         capture_output=True, text=True, timeout=60)
    return res


def main():
    print(f"=== Hardened PIMC-1 Garchomp Build ({VERSION}) ===")

    # 1. Deck validation
    cards_db, attacks_db = build_submission.load_engine_card_db()
    deck_ids = validate_deck.read_deck_file(REPO / DECK_FILE)
    errors, breakdown = validate_deck.validate_deck(deck_ids, cards_db)
    if errors:
        raise SystemExit(f"Deck '{DECK_FILE}' invalid: {errors}")
    print(f"[1/6] Deck '{DECK_FILE}' valid: 60 cards ({breakdown['basic_pokemon']} Basics, {breakdown['energy']} Energy)")

    # 2. Assemble bundle
    bundle = REPO / "build" / "hardened_garchomp_bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    (bundle / "cg").mkdir(parents=True)

    shutil.copy2(REPO / "main.py", bundle / "main.py")
    with open(bundle / "deck.csv", "w", encoding="utf-8") as f:
        f.write("\n".join(str(cid) for cid in deck_ids) + "\n")

    from tools import build_search_submission
    baked_card_data = build_search_submission.bake_card_data(cards_db, attacks_db)
    (bundle / "card_data.json").write_text(json.dumps(baked_card_data, indent=1), encoding="utf-8")
    (REPO / "card_data.json").write_text(json.dumps(baked_card_data, indent=1), encoding="utf-8")

    # Copy neural policy and value weights
    bc_weights = REPO / "bc_weights_garchomp_full.npz"
    if not bc_weights.exists():
        bc_weights = REPO / "policy_weights.npz"
    shutil.copy2(bc_weights, bundle / "policy_weights.npz")
    shutil.copy2(bc_weights, bundle / "bc_weights_garchomp_full.npz")

    val_weights = REPO / "value_weights.npz"
    if val_weights.exists():
        shutil.copy2(val_weights, bundle / "value_weights.npz")

    # Copy C++ engine binaries
    for name in CG_FILES:
        shutil.copy2(SAMPLE_CG / name, bundle / "cg" / name)

    # 3. Bake hardened search flags into main.py
    bake_hardened_main(bundle / "main.py")
    print(f"[2/6] Bundle assembled & baked with hardened search options and full card pool ({len(baked_card_data['pool'])} cards).")

    # 4. Exec-load check
    with tempfile.TemporaryDirectory() as td:
        p = exec_check(bundle, want_cg=True)
    if p.returncode != 0 or "EXEC-CHECK-OK" not in p.stdout:
        raise SystemExit(f"Exec-load check FAILED:\n{p.stdout}\n{p.stderr}")
    print(f"[3/6] Exec-load check PASSED: {p.stdout.strip()}")

    # 5. Fallback check (no cg)
    with tempfile.TemporaryDirectory() as td:
        stripped = Path(td) / "b"
        shutil.copytree(bundle, stripped)
        shutil.rmtree(stripped / "cg")
        p = exec_check(stripped, want_cg=False)
    if p.returncode != 0 or "EXEC-CHECK-OK" not in p.stdout:
        raise SystemExit(f"Fallback check (no-cg) FAILED:\n{p.stdout}\n{p.stderr}")
    print("[4/6] Fallback check (no-cg) PASSED: Agent falls back gracefully.")

    # 6. Smoke parallel self-play
    from tools import build_search_submission
    smoke_res = build_search_submission.smoke_parallel(deck_ids, rollout="v1", cap=0, games=30, bc="garchomp_full")
    print(f"[5/6] {smoke_res}")

    # 7. Package tar.gz
    out_tar = REPO / OUT_TAR
    top_files = ["main.py", "deck.csv", "card_data.json", "policy_weights.npz", "bc_weights_garchomp_full.npz", "value_weights.npz"]
    with tarfile.open(out_tar, "w:gz") as tar:
        for name in top_files:
            fp = bundle / name
            if fp.exists():
                tar.add(fp, arcname=name)
        tar.add(bundle / "cg", arcname="cg", filter=lambda ti: None if "__pycache__" in ti.name else ti)

    size_mib = out_tar.stat().st_size / (1024 * 1024)
    print(f"[6/6] Created '{OUT_TAR}' ({size_mib:.2f} MiB).")
    print(f"READY FOR COMPETITION SUBMISSION: {OUT_TAR}")


if __name__ == "__main__":
    main()
