"""Checkpoint sync between the two lab PCs (git-backed, small-file channel).

Checkpoints are ~116 KB npz — tiny — so a dedicated git branch is the simplest
robust channel both labs already have tooling for: no extra infra, atomic,
versioned, and it works over the same auth the repo uses. Every 30 min (or on
checkpoint save) each lab PUSHES its new checkpoints and PULLS the peer's.

Channel layout (orphan branch `ppo-checkpoints` on a shared remote):
    <lab_id>/policy_iter###.npz      # exported ship-format weights
    <lab_id>/history.json           # that lab's training curve
    <lab_id>/STATUS                 # one-line heartbeat: iter, games, winrate

USER ACTION REQUIRED (flagged in the 06:00 status report): set a shared remote
both labs can push to and configure its credentials, then export:
    PTCG_SYNC_REMOTE=<git url>     (e.g. a private GitHub repo or a bare repo)
    PTCG_SYNC_LAB=<thefool00|sanjay>
Without PTCG_SYNC_REMOTE this module is a no-op that logs the missing config,
so training is never blocked by sync being unconfigured.

    python -m stage4.rl_ours.lab.sync push --run stage4/rl_ours/runs/run1
    python -m stage4.rl_ours.lab.sync pull --dest stage4/rl_ours/peer
    python -m stage4.rl_ours.lab.sync daemon --run <dir> --interval 1800
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BRANCH = os.environ.get("PTCG_SYNC_BRANCH", "ppo-checkpoints")


def _cfg():
    remote = os.environ.get("PTCG_SYNC_REMOTE")
    lab = os.environ.get("PTCG_SYNC_LAB", "lab")
    return remote, lab


def _git(args, cwd, check=True):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr.strip()))
    return r


def _clone_channel():
    """Shallow-clone (or init) the checkpoint branch into a temp workdir."""
    remote, _lab = _cfg()
    if not remote:
        return None
    wd = tempfile.mkdtemp(prefix="ppo_sync_")
    r = _git(["clone", "--depth", "1", "--branch", BRANCH, remote, wd],
             cwd=".", check=False)
    if r.returncode != 0:
        # branch doesn't exist yet — init an orphan
        _git(["clone", "--depth", "1", remote, wd], cwd=".")
        _git(["checkout", "--orphan", BRANCH], cwd=wd)
        _git(["rm", "-rf", "."], cwd=wd, check=False)
    return wd


def push(run_dir):
    remote, lab = _cfg()
    if not remote:
        print("[sync] PTCG_SYNC_REMOTE unset — push skipped (training unaffected)")
        return False
    wd = _clone_channel()
    dst = Path(wd) / lab
    dst.mkdir(parents=True, exist_ok=True)
    run = Path(run_dir)
    copied = 0
    for f in list(run.glob("policy_iter*.npz")) + list(run.glob("history.json")):
        shutil.copy2(f, dst / f.name)
        copied += 1
    status = dst / "STATUS"
    hist = run / "history.json"
    if hist.exists():
        status.write_text("pushed %s from %s\n" % (time.strftime("%Y-%m-%dT%H:%M"), lab))
    _git(["add", "-A"], cwd=wd)
    r = _git(["commit", "-m", "sync %s %s" % (lab, time.strftime("%H:%M"))],
             cwd=wd, check=False)
    if r.returncode == 0:
        _git(["push", "origin", BRANCH], cwd=wd)
        print("[sync] pushed %d files as lab=%s" % (copied, lab))
    else:
        print("[sync] nothing new to push")
    shutil.rmtree(wd, ignore_errors=True)
    return True


def pull(dest):
    remote, lab = _cfg()
    if not remote:
        print("[sync] PTCG_SYNC_REMOTE unset — pull skipped")
        return False
    wd = _clone_channel()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    pulled = 0
    for peer in Path(wd).iterdir():
        if peer.is_dir() and peer.name != lab and not peer.name.startswith("."):
            tgt = dest / peer.name
            tgt.mkdir(exist_ok=True)
            for f in peer.glob("*"):
                shutil.copy2(f, tgt / f.name)
                pulled += 1
    print("[sync] pulled %d peer files into %s" % (pulled, dest))
    shutil.rmtree(wd, ignore_errors=True)
    return True


def daemon(run_dir, dest, interval):
    print("[sync] daemon every %ds (Ctrl-C to stop)" % interval)
    while True:
        try:
            push(run_dir)
            pull(dest)
        except Exception as e:
            print("[sync] cycle error (continuing): %r" % e)
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("push"); p.add_argument("--run", required=True)
    q = sub.add_parser("pull"); q.add_argument("--dest", default="stage4/rl_ours/peer")
    d = sub.add_parser("daemon")
    d.add_argument("--run", required=True)
    d.add_argument("--dest", default="stage4/rl_ours/peer")
    d.add_argument("--interval", type=int, default=1800)
    args = ap.parse_args()
    if args.cmd == "push":
        push(args.run)
    elif args.cmd == "pull":
        pull(args.dest)
    else:
        daemon(args.run, args.dest, args.interval)


if __name__ == "__main__":
    main()
