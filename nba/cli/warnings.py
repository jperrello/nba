from __future__ import annotations


def sparse(n_effective: float | int) -> dict:
    return {
        "code": "sparse_data",
        "message": (
            f"lineup support is thin (n_effective ≈ {n_effective}); "
            "result blends real observations with player-level priors."
        ),
        "context": {"n_effective": n_effective},
    }
