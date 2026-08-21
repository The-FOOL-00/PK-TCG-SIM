"""Read-Only Validation Harness for Project Mew Ogerpon Challenger Archive."""

import os
import sys
import tarfile
import hashlib
import json
import time
from pathlib import Path
from collections import Counter
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent

def validate_ogerpon_archive(archive_path="project_mew_ogerpon_challenger.tar.gz"):
    p_arch = ROOT_DIR / archive_path
    assert p_arch.exists(), f"Archive {p_arch} does not exist"

    # Part 1: Archive Integrity
    b_arch = p_arch.read_bytes()
    sha_arch = hashlib.sha256(b_arch).hexdigest()
    size_arch = len(b_arch)

    temp_dir = ROOT_DIR / "build" / "validation_temp"
    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(p_arch, "r:gz") as tar:
        tar.extractall(temp_dir)
        names = tar.getnames()

    # Part 2: File Manifest
    manifest = {}
    for root, dirs, files in os.walk(temp_dir):
        for f in sorted(files):
            p = Path(root) / f
            rel = p.relative_to(temp_dir).as_posix()
            b = p.read_bytes()
            manifest[rel] = {
                "size": len(b),
                "sha256": hashlib.sha256(b).hexdigest()
            }

    # Part 3: Deck Verification
    deck_csv = temp_dir / "deck.csv"
    assert deck_csv.exists(), "deck.csv missing from archive"
    deck_ids = [int(line.strip()) for line in deck_csv.read_text(encoding="utf-8").splitlines() if line.strip()]
    deck_counts = Counter(deck_ids)
    
    # Load card_data.json
    card_data_file = temp_dir / "card_data.json"
    assert card_data_file.exists(), "card_data.json missing from archive"
    card_data = json.loads(card_data_file.read_text(encoding="utf-8"))
    cards_db = {int(k): v for k, v in card_data.get("cards", {}).items()}

    pokemon_cnt = 0
    trainer_cnt = 0
    energy_cnt = 0
    ogerpon_cnt = 0
    grass_energy_cnt = 0

    deck_details = []
    for cid, cnt in deck_counts.most_common():
        info = cards_db.get(cid, {})
        name = info.get("name", f"Unknown_{cid}")
        ctype = info.get("cardType", -1)
        hp = info.get("hp", 0)
        
        if ctype == 0:
            pokemon_cnt += cnt
        elif ctype in (1, 2, 3, 4):
            trainer_cnt += cnt
        elif ctype == 5:
            energy_cnt += cnt

        if "ogerpon" in name.lower():
            ogerpon_cnt += cnt
        if cid == 1: # Basic Grass Energy
            grass_energy_cnt += cnt

        deck_details.append({
            "id": cid,
            "name": name,
            "count": cnt,
            "type": ctype,
            "hp": hp
        })

    # Part 4: Model Check
    v0_path = temp_dir / "value_weights.npz"
    assert v0_path.exists(), "value_weights.npz missing"
    v0_data = np.load(v0_path)
    v0_hash = manifest["value_weights.npz"]["sha256"]
    
    # Policy check
    policy_path = temp_dir / "policy_weights.npz"
    has_policy = policy_path.exists()
    if has_policy:
        pol_data = np.load(policy_path)

    # Part 5: Code & Agent Identity Check
    main_text = (temp_dir / "main.py").read_text(encoding="utf-8")
    
    bs_cei_default = "BS_CEI = os.environ.get(\"PTCG_BS_CEI\", \"1\") == \"1\"" in main_text
    bs_cei_2ply_default = "BS_CEI_2PLY = os.environ.get(\"PTCG_BS_CEI_2PLY\", \"1\") == \"1\"" in main_text
    bs_cei_3ply_default = "BS_CEI_3PLY = os.environ.get(\"PTCG_BS_CEI_3PLY\", \"0\") == \"1\"" in main_text
    bs_cei_dets_default = "BS_CEI_DETS = int(os.environ.get(\"PTCG_BS_CEI_DETS\", \"2\"))" in main_text
    bs_cei_prob_opp_default = "BS_CEI_PROB_OPP = os.environ.get(\"PTCG_BS_CEI_PROB_OPP\", \"0\") == \"1\"" in main_text
    q_policy_default = "Q_POLICY = os.environ.get(\"PTCG_Q_POLICY\", \"0\") == \"1\"" in main_text

    report = {
        "archive_size_bytes": size_arch,
        "archive_size_mib": size_arch / (1024 * 1024),
        "archive_sha256": sha_arch,
        "member_count": len(names),
        "deck_card_count": len(deck_ids),
        "deck_unique_cards": len(deck_counts),
        "pokemon_count": pokemon_cnt,
        "trainer_count": trainer_cnt,
        "energy_count": energy_cnt,
        "ogerpon_count": ogerpon_cnt,
        "grass_energy_count": grass_energy_cnt,
        "deck_details": deck_details,
        "v0_sha256": v0_hash,
        "v0_keys": list(v0_data.keys()),
        "agent_identity": {
            "bs_cei_enabled_by_default": bs_cei_default,
            "bs_cei_2ply_enabled_by_default": bs_cei_2ply_default,
            "bs_cei_3ply_disabled_by_default": bs_cei_3ply_default,
            "bs_cei_dets_is_2": bs_cei_dets_default,
            "prob_opp_disabled_by_default": bs_cei_prob_opp_default,
            "q_policy_disabled_by_default": q_policy_default
        },
        "manifest": manifest
    }

    (ROOT_DIR / "deck_search" / "ogerpon_validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Read-only validation analysis complete.")
    return report

if __name__ == "__main__":
    validate_ogerpon_archive()
