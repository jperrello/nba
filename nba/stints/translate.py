from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

REG_QUARTER_LEN = 720
OT_QUARTER_LEN = 300


# espn-lane canonical event_type (docs/event_types.md) → derive_stints fixture vocab
# (CONTRACT_STINTS.md). The deriver's contract is frozen against the fixture names,
# so we rename at the translation seam rather than touching derive.py.
EVENT_TYPE_MAP: dict[str, str] = {
    "made_2pt": "made_2pt",
    "made_3pt": "made_3pt",
    "missed_2pt": "missed_2pt",
    "missed_3pt": "missed_3pt",
    "ft_made": "ft_made",
    "ft_missed": "ft_miss",
    "offensive_rebound": "rebound_off",
    "defensive_rebound": "rebound_def",
    "turnover": "turnover",
    "shooting_foul": "shooting_foul",
    "substitution": "sub",
    "period_end": "period_end",
    "game_end": "game_end",
}

# Canonical event_types that translate.py drops on the floor — either no-op for
# the deriver (period_start is implicit; jumpball/tipoff is implicit from starters)
# or genuinely irrelevant to stint correctness (timeouts, non-shooting fouls,
# violations, technicals — the FT carry is keyed on shooting_foul alone).
EVENT_TYPE_DROP: frozenset[str] = frozenset({
    "period_start",
    "jumpball",
    "personal_foul",
    "offensive_foul",
    "technical_foul",
    "flagrant_foul",
    "timeout",
    "violation",
    "unknown",
})


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


def pbp_rows_to_events(rows: Iterable[dict[str, Any]], home_team_id: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        raw_type = row["event_type"]
        if raw_type in EVENT_TYPE_DROP:
            continue
        canon = EVENT_TYPE_MAP.get(raw_type)
        if canon is None:
            continue
        period = int(row["quarter"])
        clock = int(row["clock_seconds"])
        team_id = row.get("team_id")
        side: str | None
        if team_id is None:
            side = None
        elif int(team_id) == int(home_team_id):
            side = "home"
        else:
            side = "away"
        evt: dict[str, Any] = {
            "t": game_to_wall(period, clock),
            "period": period,
            "type": canon,
            "team": side,
            "player": row.get("player_id"),
            "home_score": row.get("home_score"),
            "away_score": row.get("away_score"),
        }
        if canon == "sub":
            evt["player_in"] = row.get("player_id")
            evt["player_out"] = row.get("assist_player_id")
        out.append(evt)
    return out
