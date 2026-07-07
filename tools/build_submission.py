"""Build and verify submission.tar.gz for the PTCG AI Battle Challenge.

Pipeline (all pure Python, Windows-safe):
  1. validate_deck()          - 60 cards, known IDs, 4-copy rule, ACE SPEC, has a Basic
  2. extract_card_data()      - bake card_data.json from cg.api.all_card_data()/all_attack()
  3. smoke eval               - 3 self-play games, zero crashes/fallbacks required
  4. import check             - load main.py exactly like Kaggle does (exec, no __file__,
                                cwd elsewhere) and exercise deck-selection + fallback paths
  5. package                  - tarfile with main.py/deck.csv/card_data.json at top level,
                                verify member names and the 190 MiB budget

Run:  python tools/build_submission.py
"""

import io
import json
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
print("IMPORT-CHECK-OK deck_head=%s" % deck[:3])
'''


def import_check(bundle_dir):
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            [sys.executable, "-c", IMPORT_CHECK_CODE, str(bundle_dir)],
            cwd=td, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or "IMPORT-CHECK-OK" not in proc.stdout:
        raise SystemExit(f"import check failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    return proc.stdout.strip()


def build():
    print(f"repo: {REPO}")

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
    for name in BUNDLE_FILES:
        shutil.copy2(REPO / name, bundle / name)
    print(f"[4/5] {import_check(bundle)}")

    tar_path = REPO / "submission.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in BUNDLE_FILES:
            tar.add(bundle / name, arcname=name)

    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getnames()
    nested = [m for m in members if "/" in m or "\\" in m]
    if nested:
        raise SystemExit(f"archive has nested paths: {nested}")
    if "main.py" not in members or "deck.csv" not in members:
        raise SystemExit(f"main.py/deck.csv missing from archive top level: {members}")
    size_mib = tar_path.stat().st_size / (1024 * 1024)
    if size_mib > MAX_SIZE_MIB:
        raise SystemExit(f"archive is {size_mib:.1f} MiB, exceeds {MAX_SIZE_MIB} MiB budget")
    print(f"[5/5] {tar_path.name} OK: {size_mib:.3f} MiB, members={members}")
    print("BUILD OK")


if __name__ == "__main__":
    build()
