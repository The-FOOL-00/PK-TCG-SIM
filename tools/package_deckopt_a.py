"""Packager for project_mew_ogerpon_deckopt_A.tar.gz challenger bundle."""

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

from tools import build_submission

def build_deckopt_archive():
    out_archive = ROOT_DIR / "project_mew_ogerpon_deckopt_A.tar.gz"
    mut4_csv = ROOT_DIR / "deck_search_ogerpon_counter" / "mutations" / "Mut4_Plus2_Energy.csv"
    
    with tempfile.TemporaryDirectory() as td:
        bundle = Path(td) / "bundle"
        bundle.mkdir()

        # Copy bot/
        if (ROOT_DIR / "bot").is_dir():
            shutil.copytree(ROOT_DIR / "bot", bundle / "bot")

        # Copy main.py
        shutil.copy2(ROOT_DIR / "main.py", bundle / "main.py")

        # Copy mutated deck.csv
        shutil.copy2(mut4_csv, bundle / "deck.csv")

        # Copy weights
        if (ROOT_DIR / "value_weights.npz").is_file():
            shutil.copy2(ROOT_DIR / "value_weights.npz", bundle / "value_weights.npz")
        if (ROOT_DIR / "policy_weights.npz").is_file():
            shutil.copy2(ROOT_DIR / "policy_weights.npz", bundle / "policy_weights.npz")

        # Extract card_data.json
        deck_ids = [int(line.strip()) for line in mut4_csv.read_text().splitlines() if line.strip()]
        cards, attacks = build_submission.load_engine_card_db()
        data = build_submission.extract_card_data(deck_ids, cards, attacks)
        (bundle / "card_data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

        # Create tar.gz
        with tarfile.open(out_archive, "w:gz") as tar:
            for f in sorted(bundle.iterdir()):
                tar.add(f, arcname=f.name)

    sha256 = hashlib.sha256(out_archive.read_bytes()).hexdigest()
    size_mb = out_archive.stat().st_size / (1024 * 1024)
    print(f"Created {out_archive.name} ({size_mb:.3f} MiB)")
    print(f"SHA256: {sha256}")
    return sha256

if __name__ == "__main__":
    build_deckopt_archive()
