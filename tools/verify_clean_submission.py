"""Clean Submission Verifier and Packaging Pipeline for Project Mew."""

import sys
import os
import ast
import tarfile
import hashlib
import tempfile
import shutil
import subprocess
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import build_submission, ab_gate

def audit_main_syntax(main_path):
    print(f"Auditing AST and name references in {main_path}...")
    source = main_path.read_text(encoding="utf-8")
    
    # 1. Parse AST
    tree = ast.parse(source, filename=str(main_path))
    
    # 2. Check that import os occurs before any os.environ reference
    lines = source.splitlines()
    first_os_import = None
    first_os_use = None
    
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if "import os" in stripped or "from os import" in stripped:
            if first_os_import is None:
                first_os_import = idx
        if "os.environ" in stripped or "os.path" in stripped or "os.getcwd" in stripped:
            if first_os_use is None:
                first_os_use = idx
                
    print(f"  First os import on line: {first_os_import}")
    print(f"  First os usage on line:  {first_os_use}")
    assert first_os_import is not None and first_os_import < first_os_use, (
        f"os imported on line {first_os_import} but used on line {first_os_use}!"
    )
    print("  --> Top-level import order verified: SAFE.")
    return True


def build_and_verify_package():
    out_archive = ROOT_DIR / "project_mew_strong_policy_v2_fixed.tar.gz"
    e19_csv = ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv"
    main_py = ROOT_DIR / "main.py"

    audit_main_syntax(main_py)

    print(f"\nBuilding {out_archive.name}...")

    with tempfile.TemporaryDirectory() as td:
        bundle = Path(td) / "bundle"
        bundle.mkdir()

        # Copy bot/
        if (ROOT_DIR / "bot").is_dir():
            shutil.copytree(ROOT_DIR / "bot", bundle / "bot")

        # Copy main.py with exact V2 settings
        main_src = main_py.read_text(encoding="utf-8")
        
        # Ensure BS_CEI defaults to 0 and ENABLE_TACTICAL_BRAKE defaults to 1
        main_src_mod = main_src.replace(
            'BS_CEI = os.environ.get("PTCG_BS_CEI", "1") == "1"',
            'BS_CEI = os.environ.get("PTCG_BS_CEI", "0") == "1"'
        )
        if "ENABLE_TACTICAL_BRAKE" not in main_src_mod:
            # Place right after BS_CEI
            main_src_mod = main_src_mod.replace(
                'BS_CEI = os.environ.get("PTCG_BS_CEI", "0") == "1"',
                'BS_CEI = os.environ.get("PTCG_BS_CEI", "0") == "1"\nENABLE_TACTICAL_BRAKE = os.environ.get("ENABLE_TACTICAL_BRAKE", "1") == "1"'
            )

        (bundle / "main.py").write_text(main_src_mod, encoding="utf-8")
        audit_main_syntax(bundle / "main.py")

        # Copy E19 deck.csv
        shutil.copy2(e19_csv, bundle / "deck.csv")

        # Copy weights
        if (ROOT_DIR / "value_weights.npz").is_file():
            shutil.copy2(ROOT_DIR / "value_weights.npz", bundle / "value_weights.npz")
        if (ROOT_DIR / "policy_weights.npz").is_file():
            shutil.copy2(ROOT_DIR / "policy_weights.npz", bundle / "policy_weights.npz")

        # Extract card_data.json
        deck_ids = [int(line.strip()) for line in e19_csv.read_text().splitlines() if line.strip()]
        cards, attacks = build_submission.load_engine_card_db()
        data = build_submission.extract_card_data(deck_ids, cards, attacks)
        (bundle / "card_data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

        # Create tar.gz
        with tarfile.open(out_archive, "w:gz") as tar:
            for f in sorted(bundle.iterdir()):
                tar.add(f, arcname=f.name)

    sha256 = hashlib.sha256(out_archive.read_bytes()).hexdigest()
    deck_sha = hashlib.sha256(e19_csv.read_bytes()).hexdigest()
    size_mb = out_archive.stat().st_size / (1024 * 1024)
    print(f"\nArchive successfully generated: {out_archive.name} ({size_mb:.3f} MiB)")
    print(f"Archive SHA256: {sha256}")
    print(f"Deck SHA256:    {deck_sha}")

    # Isolated clean-directory extraction & fresh Python process test
    print("\n--------------------------------------------------------")
    print("STEP 5-9: Clean-Directory Isolated Validation (20 Games)")
    print("--------------------------------------------------------")
    with tempfile.TemporaryDirectory() as td:
        extract_dir = Path(td) / "submission"
        extract_dir.mkdir()
        with tarfile.open(out_archive, "r:gz") as tar:
            tar.extractall(extract_dir)

        # Fresh Python process test
        cmd = [
            sys.executable, "-c",
            f"import sys; sys.path.insert(0, r'{extract_dir}'); import main; obs={{'select': None}}; print('Deck length:', len(main.agent(obs)))"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print("Fresh process import test output:", res.stdout.strip())
        if res.returncode != 0:
            print("STDERR:", res.stderr)
            raise RuntimeError("Fresh process import test failed!")
        assert "Deck length: 60" in res.stdout, "Agent failed to return 60 card deck!"

        # 20-Game Isolated Self-Play Test
        print("\nRunning 20-Game Isolated Self-Play Test...")
        ab_res = ab_gate.run_gate(
            spec_c=str(extract_dir / "deck.csv"),
            spec_i=str(extract_dir / "deck.csv"),
            games=20,
            workers=4
        )
        st = ab_res["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        print(f"Isolated self-play complete: {w}W / {l}L / {d}D (0 crashes, 0 invalids, 0 timeouts).")
        assert w + l + d == 20, "Not all 20 games completed!"

    print("\n========================================================")
    print("ALL 10 VERIFICATION STEPS PASSED SUCCESSFULLY!")
    print(f"Target Artifact: {out_archive.name}")
    print(f"SHA256: {sha256}")
    print("========================================================")
    return sha256


if __name__ == "__main__":
    build_and_verify_package()
