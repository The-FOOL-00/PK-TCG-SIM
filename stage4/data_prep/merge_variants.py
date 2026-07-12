"""Merge per-pilot extraction npz into the three training-set variants:
  a_majkel            (clean fast-policy baseline)
  b_majkel_yushin     (top-3 pilots)
  c_majkel_yushin_bono(full volume)
Each variant dir gets main.npz + card.npz in the trainer's expected schema.
Concatenation is safe: game_id = episode id (globally unique across pilots).
"""

import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "bc_v2"
VARIANTS = {
    "a_majkel": ["majkel"],
    "b_majkel_yushin": ["majkel", "yushin"],
    "c_majkel_yushin_bono": ["majkel", "yushin", "bono"],
}
MAIN_KEYS = ("state", "n_options", "label", "turn", "game_id", "opt_x")
CARD_KEYS = MAIN_KEYS + ("ctx", "dom_area")


def merge(files, keys, out):
    parts = [np.load(f) for f in files]
    np.savez_compressed(out, **{k: np.concatenate([p[k] for p in parts])
                                for k in keys})
    d = np.load(out)
    return len(d["label"]), len(set(d["game_id"].tolist()))


for var, pilots in VARIANTS.items():
    vd = BASE / var
    vd.mkdir(parents=True, exist_ok=True)
    n, g = merge([BASE / f"decisions_{p}.npz" for p in pilots], MAIN_KEYS,
                 vd / "main.npz")
    nc, gc = merge([BASE / f"card_{p}.npz" for p in pilots], CARD_KEYS,
                   vd / "card.npz")
    print(f"{var:22s} MAIN {n:5d} dec / {g:3d} games   CARD {nc:5d} steps")
