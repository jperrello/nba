from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


def assign(home: np.ndarray, away: np.ndarray) -> list[tuple[int, int, float]]:
    # Cosine distance (vectors are unit-normalized at persist time).
    sim = home @ away.T  # (5, 5) cosine similarity in [-1, 1]
    cost = 1.0 - sim
    row, col = linear_sum_assignment(cost)
    return [(int(i), int(j), float(sim[i, j])) for i, j in zip(row, col, strict=True)]
