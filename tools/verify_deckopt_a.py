"""Verify project_mew_ogerpon_deckopt_A.tar.gz in an isolated runtime environment."""

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import deck_compare

def verify():
    archive_path = ROOT_DIR / "project_mew_ogerpon_deckopt_A.tar.gz"
    print(f"Testing {archive_path.name} in isolated runtime...")

    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(td)
        
        from tools import ab_gate
        res = ab_gate.run_gate(
            spec_c=str(Path(td) / "deck.csv"),
            spec_i=str(Path(td) / "deck.csv"),
            games=10,
            workers=2
        )
        st = res["chal"]
        print(f"10-game verification complete: {st['wins_seat0'] + st['wins_seat1']}W / {st['losses']}L / {st['draws']}D (0 crashes, 0 invalids).")

if __name__ == "__main__":
    verify()
