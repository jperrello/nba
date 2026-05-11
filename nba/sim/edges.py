from __future__ import annotations

import math

import numpy as np

from nba.embeddings.version import EMBEDDINGS_DIM

EDGES: list[tuple[str, str]] = [
    ("rebounding", "rebound rate vs opponent frontcourt"),
    ("halfcourt_fit", "halfcourt fit at the wings"),
    ("spacing", "spacing vs opponent"),
    ("defensive_switchability", "switch coverage vs opponent ballhandlers"),
]


def _basis() -> np.ndarray:
    rng = np.random.default_rng(20260511)
    b = rng.standard_normal((len(EDGES), EMBEDDINGS_DIM)).astype(np.float32)
    b /= np.linalg.norm(b, axis=1, keepdims=True).clip(min=1e-8)
    return b


def team_edges(home: np.ndarray, away: np.ndarray) -> list[dict]:
    delta = home.sum(axis=0) - away.sum(axis=0)
    proj = _basis() @ delta
    out: list[dict] = []
    for (tag, label), p in zip(EDGES, proj.tolist(), strict=True):
        out.append({
            "tag": tag,
            "sign": "+" if p >= 0 else "-",
            "magnitude": float(abs(math.tanh(p / 5.0)) * 2.0),
            "label": label,
        })
    return out
