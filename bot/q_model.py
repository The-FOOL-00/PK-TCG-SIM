"""Fast numpy inference loader for Action-Conditioned Q-Network.

Evaluates Q(state, phase, action) = P(win | state, phase, action).
"""

import os
import sys
from typing import List, Optional
import numpy as np


class QModel:
    """Action-conditioned Q-Network evaluator."""

    def __init__(self, weights_path: str = "q_weights.npz"):
        self.weights_path = weights_path
        self.layers = []
        self.n_features = 246
        self.loaded = False
        self._load()

    def _load(self):
        if not os.path.isfile(self.weights_path):
            # Check parent directories
            alt = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.weights_path)
            if os.path.isfile(alt):
                self.weights_path = alt
            else:
                return

        try:
            d = np.load(self.weights_path)
            n_layers = int(d["n_layers"])
            self.n_features = int(d["n_features"])
            self.layers = []
            for i in range(n_layers):
                w = d[f"W{i}"].astype(np.float32)
                b = d[f"b{i}"].astype(np.float32)
                self.layers.append((w, b))
            self.loaded = True
        except Exception as e:
            print(f"[q_model] failed to load {self.weights_path}: {e}", file=sys.stderr, flush=True)

    def predict_q(self, feature_matrix: np.ndarray) -> np.ndarray:
        """Forward pass on a batch of [K, 246] combined (state, phase, action) vectors."""
        if not self.loaded:
            raise RuntimeError("QModel weights not loaded")

        h = feature_matrix
        for w, b in self.layers[:-1]:
            h = np.maximum(h @ w + b, 0.0)
        w, b = self.layers[-1]
        z = (h @ w + b).ravel()
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        return p
