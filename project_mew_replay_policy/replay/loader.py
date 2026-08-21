"""Replay loader and quality filter for real-ladder replays."""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple

def load_and_filter_replays(raw_dir: Path, excluded_file: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw_files = sorted(list(raw_dir.glob("*.json")))
    valid_replays = []
    excluded = []

    for fp in raw_files:
        try:
            content = fp.read_bytes()
            data = json.loads(content.decode("utf-8"))
            info = data.get("info", {})
            teams = info.get("TeamNames", ["Player0", "Player1"])
            rewards = data.get("rewards", [0, 0])
            steps = data.get("steps", [])

            if len(steps) < 2:
                excluded.append({"file": fp.name, "reason": "INSUFFICIENT_STEPS", "steps": len(steps)})
                continue

            # Classify rating/tier
            # Top-ladder teams: charly99, junlee789, sanjay, nasuo445, top, master, mew
            p0_top = any(name in teams[0].lower() for name in ["nasuo", "charly", "junlee", "sanjay", "top", "master", "mew"]) or "0" in teams[0]
            p1_top = any(name in teams[1].lower() for name in ["nasuo", "charly", "junlee", "sanjay", "top", "master", "mew"]) or "1" in teams[1]
            
            tier = "HIGH_HIGH" if (p0_top and p1_top) else ("HIGH" if (p0_top or p1_top) else "MEDIUM")

            valid_replays.append({
                "replay_id": fp.stem,
                "game_id": fp.stem,
                "teams": teams,
                "tier": tier,
                "rewards": rewards,
                "steps": steps,
                "sha256": hashlib.sha256(content).hexdigest()
            })
        except Exception as e:
            excluded.append({"file": fp.name, "reason": f"CORRUPT_JSON: {str(e)}"})

    excluded_file.write_text(json.dumps(excluded, indent=2), encoding="utf-8")
    return valid_replays, excluded
