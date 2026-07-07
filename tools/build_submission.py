"""Build and verify submission.tar.gz for the PTCG AI Battle Challenge.

Pipeline (all pure Python, Windows-safe):
  1. validate_deck()          - 60 cards, known IDs, 4-copy rule, ACE SPEC, has a Basic
  2. extract_card_data()      - bake card_data.json from cg.api.all_card_data()/all_attack()
  3. smoke eval               - 3 self-play games, zero crashes/fallbacks required
  4. import check             - load main.py exactly like Kaggle does (exec, no __file__,
                                cwd elsewhere) and exercise deck-selection + fallback paths
  5. package                  - tarfile with main.py/deck.csv/card_data.json at top level,
                                verify member names and the 190 MiB budget

Run:  python tools/build_submission.py                  (v1 heuristic bundle)
      python tools/build_submission.py --learned-value  (value-model bundle:
          ships value_weights.npz, bakes PTCG_LEARNED_VALUE default to on,
          stamps AGENT_VERSION ptcg-lv-v1.1.0; smoke + import checks run with
          the model engaged)
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CG_DIR = REPO / "sample_submission" / "sample_submission"
BUNDLE_FILES = ["main.py", "deck.csv", "card_data.json"]
LV_WEIGHTS = "value_weights.npz"
LV_VERSION = "ptcg-lv-v1.1.0"
MAX_SIZE_MIB = 190

sys.path.insert(0, str(SAMPLE_CG_DIR))


def load_engine_card_db():
    """Card/attack database straight from the engine DLL (authoritative)."""
    from cg.api import all_attack, all_card_data
    cards = {c.cardId: c for c in all_card_data()}
    attacks = {a.attackId: a for a in all_attack()}
    return cards, attacks


def read_deck(path):
    with open(path, "r") as f:
        return [int(line.strip()) for line in f if line.strip()]


def validate_deck(deck, cards):
    errors = []
    if len(deck) != 60:
        errors.append(f"deck has {len(deck)} cards, expected 60")
    unknown = sorted({cid for cid in deck if cid not in cards})
    if unknown:
        errors.append(f"unknown card IDs: {unknown}")
        return errors
    name_counts = Counter()
    ace_spec = 0
    basics = 0
    for cid in deck:
        c = cards[cid]
        if c.cardType != 5:  # basic energy is exempt from the 4-copy rule
            name_counts[c.name] += 1
        if c.aceSpec:
            ace_spec += 1
        if c.basic:
            basics += 1
    over = {n: k for n, k in name_counts.items() if k > 4}
    if over:
        errors.append(f"more than 4 copies of: {over}")
    if ace_spec > 1:
        errors.append(f"{ace_spec} ACE SPEC cards, max is 1")
    if basics == 0:
        errors.append("deck contains no Basic Pokemon")
    return errors


def extract_card_data(deck, cards, attacks):
    """Small lookup for ONLY the cards in our deck (+ their attacks)."""
    out_cards = {}
    out_attacks = {}
    for cid in sorted(set(deck)):
        c = cards[cid]
        out_cards[cid] = {
            "cardId": c.cardId,
            "name": c.name,
            "cardType": int(c.cardType),
            "hp": c.hp,
            "retreatCost": c.retreatCost,
            "energyType": int(c.energyType) if c.energyType is not None else None,
            "weakness": int(c.weakness) if c.weakness is not None else None,
            "resistance": int(c.resistance) if c.resistance is not None else None,
            "basic": c.basic,
            "stage1": c.stage1,
            "stage2": c.stage2,
            "ex": c.ex,
            "megaEx": c.megaEx,
            "aceSpec": c.aceSpec,
            "evolvesFrom": c.evolvesFrom,
            "attacks": list(c.attacks or []),
            "skills": [{"name": s.name, "text": s.text} for s in (c.skills or [])],
        }
        for aid in c.attacks or []:
            if aid in attacks:
                a = attacks[aid]
                out_attacks[aid] = {
                    "attackId": a.attackId,
                    "name": a.name,
                    "damage": a.damage,
                    "energies": [int(e) for e in (a.energies or [])],
                    "text": a.text,
                }
    return {"cards": out_cards, "attacks": out_attacks}


def smoke_eval(games=3):
    sys.path.insert(0, str(REPO / "tools"))
    import local_eval
    summary = local_eval.run_series(games=games, opponent="self", tag="smoke")
    if summary["crashes"] or summary["fallbacks"]:
        raise SystemExit(
            f"smoke eval failed: crashes={summary['crashes']} fallbacks={summary['fallbacks']}")
    return summary


IMPORT_CHECK_CODE = r'''
import json, os, sys
bundle = sys.argv[1]

# Simulate kaggle_environments.agent.get_last_callable: exec with empty
# namespace (no __file__), bundle dir on sys.path, cwd somewhere else.
with open(os.path.join(bundle, "main.py"), "r", encoding="utf-8") as f:
    src = f.read()
sys.path.append(bundle)
env = {}
exec(compile(src, "main.py", "exec"), env)
agent = [v for v in env.values() if callable(v)][-1]

deck = agent({"select": None, "logs": [], "current": None})
assert isinstance(deck, list) and len(deck) == 60, f"bad deck answer: {type(deck)} len={len(deck)}"
assert all(isinstance(x, int) for x in deck), "deck answer must be ints"

# Malformed observation (current=None with a live select) must hit the fallback
r = agent({"select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1,
                      "option": [{"type": 14}]}, "logs": [], "current": None})
assert r == [0], f"fallback answer must be [0], got {r}"

# Multi-select shape check
r = agent({"select": {"type": 1, "context": 8, "minCount": 2, "maxCount": 2,
                      "option": [{"type": 3}, {"type": 3}, {"type": 3}]},
           "logs": [], "current": {"yourIndex": 0, "players": [{}, {}]}})
assert len(r) == 2 and len(set(r)) == 2 and all(0 <= i < 3 for i in r), f"bad multi-select: {r}"

if len(sys.argv) > 2 and sys.argv[2] == "lv":
    # learned-value bundle: flag baked on, weights must load from the bundle
    assert env["LEARNED_VALUE"] is True, "PTCG_LEARNED_VALUE default not baked on"
    assert env["AGENT_VERSION"] == "ptcg-lv-v1.1.0", env["AGENT_VERSION"]
    model = env["_lv_model"]()
    assert model is not None, "value_weights.npz failed to load from bundle"
    p = env["_lv_predict"](model, [[0.0] * env["N_STATE_FEATURES"]])[0]
    assert 0.0 < p < 1.0, f"degenerate model output {p}"
    print("LV-CHECK-OK p_empty=%.4f numpy=%s" % (p, model["np"] is not None))
print("IMPORT-CHECK-OK deck_head=%s" % deck[:3])
'''


def import_check(bundle_dir, learned_value=False):
    args = [sys.executable, "-c", IMPORT_CHECK_CODE, str(bundle_dir)]
    if learned_value:
        args.append("lv")
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(args, cwd=td, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or "IMPORT-CHECK-OK" not in proc.stdout:
        raise SystemExit(f"import check failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    if learned_value and "LV-CHECK-OK" not in proc.stdout:
        raise SystemExit(f"learned-value check failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    if learned_value and "WARNING" in proc.stderr:
        raise SystemExit(f"learned-value bundle warned on load:\n{proc.stderr}")
    return " ".join(proc.stdout.split())


def bake_learned_value(main_path):
    """Flip the flag default on and stamp the version in the bundled main.py."""
    src = main_path.read_text(encoding="utf-8")
    flag_old = 'LEARNED_VALUE = os.environ.get("PTCG_LEARNED_VALUE", "0") == "1"'
    flag_new = 'LEARNED_VALUE = os.environ.get("PTCG_LEARNED_VALUE", "1") == "1"'
    ver_old = 'AGENT_VERSION = "ptcg-heuristic-v1.0.0"'
    ver_new = f'AGENT_VERSION = "{LV_VERSION}"'
    if flag_old not in src or ver_old not in src:
        raise SystemExit("bake_learned_value: expected lines not found in main.py")
    main_path.write_text(
        src.replace(flag_old, flag_new).replace(ver_old, ver_new), encoding="utf-8")


def build(learned_value=False):
    print(f"repo: {REPO}" + ("   [learned-value bundle]" if learned_value else ""))
    bundle_files = list(BUNDLE_FILES) + ([LV_WEIGHTS] if learned_value else [])
    if learned_value:
        if not (REPO / LV_WEIGHTS).is_file():
            raise SystemExit(f"{LV_WEIGHTS} not found in repo root")
        # smoke eval must exercise the model path (env read at main import)
        os.environ["PTCG_LEARNED_VALUE"] = "1"

    deck = read_deck(REPO / "deck.csv")
    cards, attacks = load_engine_card_db()
    errors = validate_deck(deck, cards)
    if errors:
        raise SystemExit("deck.csv INVALID:\n  " + "\n  ".join(errors))
    print(f"[1/5] deck.csv valid: 60 cards, {len(set(deck))} unique IDs")

    data = extract_card_data(deck, cards, attacks)
    card_data_path = REPO / "card_data.json"
    card_data_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"[2/5] card_data.json written: {len(data['cards'])} cards, "
          f"{len(data['attacks'])} attacks, {card_data_path.stat().st_size} bytes")

    summary = smoke_eval(3)
    print(f"[3/5] smoke eval OK: {summary['wins']}W/{summary['losses']}L/{summary['draws']}D, "
          f"0 crashes, 0 fallbacks")

    bundle = REPO / "build" / "bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)
    for name in bundle_files:
        shutil.copy2(REPO / name, bundle / name)
    if learned_value:
        bake_learned_value(bundle / "main.py")
    print(f"[4/5] {import_check(bundle, learned_value)}")

    tar_path = REPO / "submission.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in bundle_files:
            tar.add(bundle / name, arcname=name)

    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getnames()
    nested = [m for m in members if "/" in m or "\\" in m]
    if nested:
        raise SystemExit(f"archive has nested paths: {nested}")
    missing = [m for m in bundle_files if m not in members]
    if missing:
        raise SystemExit(f"missing from archive top level: {missing} (members={members})")
    size_mib = tar_path.stat().st_size / (1024 * 1024)
    if size_mib > MAX_SIZE_MIB:
        raise SystemExit(f"archive is {size_mib:.1f} MiB, exceeds {MAX_SIZE_MIB} MiB budget")
    print(f"[5/5] {tar_path.name} OK: {size_mib:.3f} MiB, members={members}")
    print("BUILD OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--learned-value", action="store_true",
                    help=f"bundle {LV_WEIGHTS} with PTCG_LEARNED_VALUE baked on")
    build(ap.parse_args().learned_value)
