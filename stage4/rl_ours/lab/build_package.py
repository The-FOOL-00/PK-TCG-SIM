"""Build a self-contained lab package: exactly the files a fresh PC needs to
run the preflight gates and the PPO trainer. Identical for both labs.

    python -m stage4.rl_ours.lab.build_package --out dist/lab_package.tar.gz

Produces the tarball + a MANIFEST listing every file and a sha256. Verifies
each source exists before writing (a missing file is a hard error, not a
silent gap). Torch and kaggle-environments are pip-installed at the lab per
requirements_lab.txt — not vendored (torch is too large to ship in a tar).
"""

import argparse
import hashlib
import io
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Files the package needs. Globs expand relative to REPO.
INCLUDE = [
    "main.py",
    "card_data.json",
    "requirements.txt",
    # decks: learner + every league/gate opponent
    "deck.csv",
    "stage4/deck_list0.csv",
    "metaC_garchomp_nasuo.csv",
    "metaB_alakazam.csv",
    "metaC_kangaskhan.csv",
    "metaD_mewtwo_kashiwashira.csv",
    # weights: policy warm-start, value warm-start, incumbent BC bundle
    "bc_weights_list0_b.npz",
    "bc_weights_garchomp_full.npz",
    "value_weights_mlp.npz",
    # engine harness + gate tooling (tools/__init__.py injected below)
    "tools/deck_compare.py",
    "tools/ab_gate.py",
    # the PPO stack + lab scripts
    "stage4/rl_ours/ppo/*.py",
    "stage4/rl_ours/lab/*.py",
    "stage4/rl_ours/lab/FIRST_ACTION.md",
    "stage4/rl_ours/lab/requirements_lab.txt",
    "stage4/rl_ours/algorithm_survey.md",
    "stage4/rl_ours/scoping.md",
]


def resolve():
    files = []
    for pat in INCLUDE:
        matches = sorted(REPO.glob(pat)) if any(c in pat for c in "*?[") \
            else [REPO / pat]
        if not matches:
            raise SystemExit("MISSING: no match for %r" % pat)
        for m in matches:
            if not m.exists():
                raise SystemExit("MISSING: %s" % m)
            files.append(m)
    # dedupe, keep order
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def build(out_path):
    files = resolve()
    manifest = ["# Lab package MANIFEST", "# %d files" % len(files), ""]
    total = 0

    def add_bytes(tar, name, data):
        ti = tarfile.TarInfo(name=name)
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_path, "w:gz") as tar:
        for f in files:
            rel = f.relative_to(REPO)
            data = f.read_bytes()
            total += len(data)
            sha = hashlib.sha256(data).hexdigest()[:16]
            manifest.append("%s  %8d  %s" % (sha, len(data), rel.as_posix()))
            add_bytes(tar, rel.as_posix(), data)
        # tools/ is a namespace package in-repo; ship an explicit __init__ so
        # the extracted tree imports it identically on any Python.
        add_bytes(tar, "tools/__init__.py", b"")
        add_bytes(tar, "MANIFEST.txt", "\n".join(manifest).encode("utf-8"))
    print("built %s" % out_path)
    print("  %d files, %.1f MB" % (len(files), total / 1e6))
    print("  extract: tar xzf %s -C <dir> && cd <dir>" % out_path.name)
    print("  then:    python -m stage4.rl_ours.lab.preflight")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/lab_package.tar.gz")
    args = ap.parse_args()
    out = args.out if Path(args.out).is_absolute() else REPO / args.out
    build(out)


if __name__ == "__main__":
    main()
