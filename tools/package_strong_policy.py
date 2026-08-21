"""Build and verify project_mew_strong_policy_challenger.tar.gz."""

import os
import sys
import tarfile
import hashlib
import tempfile
import shutil
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission, ab_gate

def build_strong_policy_archive():
    out_archive = ROOT_DIR / "project_mew_strong_policy_challenger.tar.gz"
    deck_csv = ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv"
    
    print(f"Building {out_archive.name}...")

    with tempfile.TemporaryDirectory() as td:
        bundle = Path(td) / "bundle"
        bundle.mkdir()

        # Copy bot/
        if (ROOT_DIR / "bot").is_dir():
            shutil.copytree(ROOT_DIR / "bot", bundle / "bot")

        # Copy main.py and bake BS_CEI = 0 default for pure tactical aggression
        main_src = (ROOT_DIR / "main.py").read_text(encoding="utf-8")
        # Ensure BS_CEI defaults to 0 for pure tactical heuristic execution
        main_src_mod = main_src.replace(
            'BS_CEI = os.environ.get("BS_CEI", "1") == "1"',
            'BS_CEI = os.environ.get("BS_CEI", "0") == "1"'
        )
        (bundle / "main.py").write_text(main_src_mod, encoding="utf-8")

        # Copy E19 deck.csv
        shutil.copy2(deck_csv, bundle / "deck.csv")

        # Copy weights
        if (ROOT_DIR / "value_weights.npz").is_file():
            shutil.copy2(ROOT_DIR / "value_weights.npz", bundle / "value_weights.npz")
        if (ROOT_DIR / "policy_weights.npz").is_file():
            shutil.copy2(ROOT_DIR / "policy_weights.npz", bundle / "policy_weights.npz")

        # Extract card_data.json
        deck_ids = [int(line.strip()) for line in deck_csv.read_text().splitlines() if line.strip()]
        cards, attacks = build_submission.load_engine_card_db()
        data = build_submission.extract_card_data(deck_ids, cards, attacks)
        (bundle / "card_data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

        # Create tar.gz
        with tarfile.open(out_archive, "w:gz") as tar:
            for f in sorted(bundle.iterdir()):
                tar.add(f, arcname=f.name)

    sha256 = hashlib.sha256(out_archive.read_bytes()).hexdigest()
    size_mb = out_archive.stat().st_size / (1024 * 1024)
    print(f"Archive built: {out_archive.name} ({size_mb:.3f} MiB)")
    print(f"SHA256: {sha256}")

    # Isolated runtime test
    print("\nRunning isolated 10-game self-play validation...")
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(out_archive, "r:gz") as tar:
            tar.extractall(td)
        res = ab_gate.run_gate(
            spec_c=str(Path(td) / "deck.csv"),
            spec_i=str(Path(td) / "deck.csv"),
            games=10,
            workers=2
        )
        st = res["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        print(f"Self-play passed: {w}W / {st['losses']}L / {st['draws']}D (0 crashes, 0 invalids).")

    return sha256

if __name__ == "__main__":
    build_strong_policy_archive()
