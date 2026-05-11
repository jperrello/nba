"""Stub signature for derive_stints. Body is owned by stints-lane (nba-8gq);
brutus pins the public surface so the contract tests can collect and execute.
See CONTRACT_STINTS.md."""
from __future__ import annotations

from typing import Any


def derive_stints(
    events: list[dict[str, Any]],
    starters_home: list[str],
    starters_away: list[str],
) -> list[Any]:
    raise NotImplementedError(
        "derive_stints is not implemented yet. See CONTRACT_STINTS.md "
        "(brutus contract nba-6gz). stints-lane (nba-8gq) owns the body."
    )
