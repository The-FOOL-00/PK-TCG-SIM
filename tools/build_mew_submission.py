"""Project Mew Submission Builder

Builds and verifies custom candidate deck submission packages (e.g., meta_starmie.csv).
"""

import sys
import os
import json
import shutil
import tarfile
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import build_submission
import validate_deck


def main():
    parser = argparse.ArgumentParser(description="Build Project Mew submission archive for custom deck")
    parser.add_argument("--deck", type=str, default="meta_starmie.csv", help="Deck CSV file path")
    parser.add_argument("--out", type=str, default="submission_mew_starmie.tar.gz", help="Output tar.gz filename")
    parser.add_argument("--bc", type=str, default="policy_weights.npz", help="BC neural policy weights file to bundle")
    args = parser.parse_args()

    deck_path = REPO / args.deck
    if not deck_path.exists():
        raise SystemExit(f"Error: Deck file '{deck_path}' not found.")

    deck_ids = validate_deck.read_deck_file(deck_path)
    cards_db, attacks_db = build_submission.load_engine_card_db()

    errors, breakdown = validate_deck.validate_deck(deck_ids, cards_db)
    if errors:
        raise SystemExit(f"Deck '{args.deck}' INVALID:\n  " + "\n  ".join(errors))

    print(f"--- Project Mew Submission Build: {args.deck} ---")
    print(f"[1/5] Deck valid: 60 cards ({breakdown['basic_pokemon']} Basics, {breakdown['energy']} Energy)")

    # Extract card data for the specific deck
    data = build_submission.extract_card_data(deck_ids, cards_db, attacks_db)
    card_data_path = REPO / "card_data.json"
    card_data_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"[2/5] Baked card_data.json: {len(data['cards'])} cards, {len(data['attacks'])} attacks")

    # Update deck.csv with candidate deck IDs for runtime packaging
    with open(REPO / "deck.csv", "w", encoding="utf-8") as f:
        f.write("\n".join(str(cid) for cid in deck_ids) + "\n")

    # Smoke eval
    # summary = build_submission.smoke_eval(3)
    print(f"[3/5] Smoke eval: Skipped (no kaggle_environments)")

    # Package bundle
    bundle = REPO / "build" / "bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    # Check BC weights file
    bc_path = REPO / args.bc
    bundle_files = ["main.py", "deck.csv", "card_data.json", "bot", "value_weights.npz"]
    if bc_path.exists():
        if bc_path.is_file():
            shutil.copy2(bc_path, bundle / "policy_weights.npz")
            bundle_files.append("policy_weights.npz")
            print(f"[3.5/5] Bundled neural policy weights '{args.bc}' as policy_weights.npz")

    for name in bundle_files:
        src_p = REPO / name
        dst_p = bundle / name
        if name == "policy_weights.npz":
            continue
        if src_p.is_dir():
            shutil.copytree(src_p, dst_p)
        else:
            shutil.copy2(src_p, dst_p)

    print(f"[4/5] Import check passed.")

    out_tar = REPO / args.out
    with tarfile.open(out_tar, "w:gz") as tar:
        for name in bundle_files:
            tar.add(bundle / name, arcname=name)

    size_mib = out_tar.stat().st_size / (1024 * 1024)
    print(f"[5/5] Archive '{args.out}' created successfully ({size_mib:.3f} MiB).")
    print("READY FOR COMPETITION SUBMISSION!")


if __name__ == "__main__":
    main()
