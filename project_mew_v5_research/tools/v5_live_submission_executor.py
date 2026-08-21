"""Project Mew — Live Submission Execution Script.

Submits Candidate 1 (V5 Alakazam Master) and Candidate 2 (Corrected V4 Control)
to Kaggle competition pokemon-tcg-ai-battle with strict byte-level SHA256 verification.
Leaves Submission #3 unused and reserved.
"""

import sys
import os
import json
import hashlib
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

REPORTS_DIR = ROOT_DIR / "project_mew_v5_research" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Candidate 1: V5 Alakazam Master
CANDIDATE_1_PATH = ROOT_DIR / "project_mew_v5_alakazam_master_challenger.tar.gz"
CANDIDATE_1_CLAIMED_SHA = "2906bbd8acf0a4c5cde8f0ea91ed4134a3342b44d110c01cd1add092fca9d7b3"
CANDIDATE_1_MSG = "Project Mew V5 Alakazam Master Challenger (SHA: 2906bbd8acf0a4c5cde8f0ea91ed4134a3342b44d110c01cd1add092fca9d7b3)"

# Candidate 2: Corrected V4 Control
CANDIDATE_2_PATH = ROOT_DIR / "project_mew_v4_corrected_candidate.tar.gz"
CANDIDATE_2_CLAIMED_SHA = "44456613a43b0be713894393334e72271ab10b730f3076ba71a7c7b9733a6261"
CANDIDATE_2_MSG = "Project Mew Corrected V4 Control E19 (SHA: 44456613a43b0be713894393334e72271ab10b730f3076ba71a7c7b9733a6261)"

def get_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def execute_live_submissions():
    print("===================================================================")
    print("PROJECT MEW — FINAL LIVE SUBMISSION EXECUTION")
    print("===================================================================")
    print("Timestamp (Local):", datetime.now().isoformat())
    print("Timestamp (UTC):  ", datetime.now(timezone.utc).isoformat())

    results = {}

    # -------------------------------------------------------------
    # SUBMISSION #1: V5 ALAKAZAM MASTER (PRIMARY)
    # -------------------------------------------------------------
    print("\n--- SUBMISSION #1: V5 ALAKAZAM MASTER (PRIMARY) ---")
    assert CANDIDATE_1_PATH.exists(), f"File {CANDIDATE_1_PATH} does not exist!"
    c1_sha = get_sha256(CANDIDATE_1_PATH)
    c1_size = CANDIDATE_1_PATH.stat().st_size
    print(f"  Archive:     {CANDIDATE_1_PATH.name}")
    print(f"  Size:        {c1_size:,} bytes")
    print(f"  Actual SHA:  {c1_sha}")
    print(f"  Claimed SHA: {CANDIDATE_1_CLAIMED_SHA}")
    assert c1_sha == CANDIDATE_1_CLAIMED_SHA, f"CANDIDATE 1 SHA MISMATCH! {c1_sha} != {CANDIDATE_1_CLAIMED_SHA}"
    print("  SHA256 Verification: [PASSED - EXACT MATCH]")

    print(f"  Uploading Candidate 1 to Kaggle...")
    t0 = time.time()
    cmd1 = [
        sys.executable, "-m", "kaggle", "competitions", "submit",
        "pokemon-tcg-ai-battle",
        "-f", str(CANDIDATE_1_PATH),
        "-m", CANDIDATE_1_MSG
    ]
    p1 = subprocess.run(cmd1, capture_output=True, text=True)
    t1 = time.time()
    print(f"  Upload completed in {t1 - t0:.2f}s (Exit code: {p1.returncode})")
    print(f"  STDOUT: {p1.stdout.strip()}")
    if p1.stderr.strip():
        print(f"  STDERR: {p1.stderr.strip()}")

    results["submission_1_v5_alakazam"] = {
        "candidate": "V5 Alakazam Master (Primary)",
        "archive_file": CANDIDATE_1_PATH.name,
        "size_bytes": c1_size,
        "sha256": c1_sha,
        "status": "SUCCESS" if p1.returncode == 0 else "FAILED",
        "stdout": p1.stdout.strip(),
        "stderr": p1.stderr.strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    # Brief delay between submissions
    time.sleep(5)

    # -------------------------------------------------------------
    # SUBMISSION #2: CORRECTED V4 CONTROL (SECOND)
    # -------------------------------------------------------------
    print("\n--- SUBMISSION #2: CORRECTED V4 CONTROL (SECOND) ---")
    assert CANDIDATE_2_PATH.exists(), f"File {CANDIDATE_2_PATH} does not exist!"
    c2_sha = get_sha256(CANDIDATE_2_PATH)
    c2_size = CANDIDATE_2_PATH.stat().st_size
    print(f"  Archive:     {CANDIDATE_2_PATH.name}")
    print(f"  Size:        {c2_size:,} bytes")
    print(f"  Actual SHA:  {c2_sha}")
    print(f"  Claimed SHA: {CANDIDATE_2_CLAIMED_SHA}")
    assert c2_sha == CANDIDATE_2_CLAIMED_SHA, f"CANDIDATE 2 SHA MISMATCH! {c2_sha} != {CANDIDATE_2_CLAIMED_SHA}"
    print("  SHA256 Verification: [PASSED - EXACT MATCH]")

    print(f"  Uploading Candidate 2 to Kaggle...")
    t2 = time.time()
    cmd2 = [
        sys.executable, "-m", "kaggle", "competitions", "submit",
        "pokemon-tcg-ai-battle",
        "-f", str(CANDIDATE_2_PATH),
        "-m", CANDIDATE_2_MSG
    ]
    p2 = subprocess.run(cmd2, capture_output=True, text=True)
    t3 = time.time()
    print(f"  Upload completed in {t3 - t2:.2f}s (Exit code: {p2.returncode})")
    print(f"  STDOUT: {p2.stdout.strip()}")
    if p2.stderr.strip():
        print(f"  STDERR: {p2.stderr.strip()}")

    results["submission_2_corrected_v4"] = {
        "candidate": "Corrected V4 Control (Second)",
        "archive_file": CANDIDATE_2_PATH.name,
        "size_bytes": c2_size,
        "sha256": c2_sha,
        "status": "SUCCESS" if p2.returncode == 0 else "FAILED",
        "stdout": p2.stdout.strip(),
        "stderr": p2.stderr.strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    # -------------------------------------------------------------
    # SUBMISSION #3: UNUSED / RESERVED
    # -------------------------------------------------------------
    print("\n--- SUBMISSION #3: UNUSED / RESERVED ---")
    print("  Status: 100% UNUSED / RESERVED. No third candidate submitted.")
    results["submission_3_status"] = "RESERVED / UNUSED"

    # Brief delay before fetching updated submission list
    time.sleep(5)

    print("\n--- FETCHING LIVE SUBMISSION IDs FROM KAGGLE API ---")
    cmd_list = [sys.executable, "-m", "kaggle", "competitions", "submissions", "-c", "pokemon-tcg-ai-battle"]
    p_list = subprocess.run(cmd_list, capture_output=True, text=True)
    print("Updated Submissions List:")
    for line in p_list.stdout.splitlines()[:15]:
        print(" ", line)

    results["updated_submissions_table"] = p_list.stdout

    # Save summary
    out_file = REPORTS_DIR / "final_live_submission_log.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSubmission log saved to {out_file}")
    return results

if __name__ == "__main__":
    execute_live_submissions()
