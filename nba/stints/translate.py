from __future__ import annotations

import hashlib
from collections.abc import Iterable

REG_QUARTER_LEN = 720
OT_QUARTER_LEN = 300


def quarter_len(quarter: int) -> int:
    return REG_QUARTER_LEN if quarter <= 4 else OT_QUARTER_LEN


def _prior_seconds(quarter: int) -> int:
    return sum(quarter_len(q) for q in range(1, quarter))


def game_to_wall(quarter: int, clock_seconds: int) -> float:
    return float(_prior_seconds(quarter) + (quarter_len(quarter) - clock_seconds))


def wall_to_game(quarter: int, wall_seconds: float) -> int:
    return int(round(quarter_len(quarter) - (wall_seconds - _prior_seconds(quarter))))


def lineup_hash(lineup: Iterable[int | str]) -> str:
    canon = ",".join(str(p) for p in sorted(int(x) for x in lineup))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
