from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from nba.stints.translate import lineup_hash, wall_to_game

INSERT_SQL = """
INSERT INTO lineup_stints (
    game_id, season, quarter,
    start_clock_seconds, end_clock_seconds, duration_seconds,
    home_team_id, away_team_id,
    home_lineup, away_lineup,
    home_lineup_hash, away_lineup_hash,
    home_pts, away_pts, pts,
    possessions, possessions_home, possessions_away
) VALUES (
    %(game_id)s, %(season)s, %(quarter)s,
    %(start_clock_seconds)s, %(end_clock_seconds)s, %(duration_seconds)s,
    %(home_team_id)s, %(away_team_id)s,
    %(home_lineup)s, %(away_lineup)s,
    %(home_lineup_hash)s, %(away_lineup_hash)s,
    %(home_pts)s, %(away_pts)s, %(pts)s,
    %(possessions)s, %(possessions_home)s, %(possessions_away)s
)
"""

DELETE_SQL = "DELETE FROM lineup_stints WHERE game_id = %s"


def _field(rec: Any, name: str) -> Any:
    if isinstance(rec, dict):
        return rec.get(name)
    return getattr(rec, name, None)


def _row(rec: Any) -> dict[str, Any]:
    period = int(_field(rec, "period"))
    home = sorted(int(p) for p in _field(rec, "home"))
    away = sorted(int(p) for p in _field(rec, "away"))
    start = wall_to_game(period, float(_field(rec, "wall_start")))
    end = wall_to_game(period, float(_field(rec, "wall_end")))
    pts_home = int(_field(rec, "pts_home"))
    pts_away = int(_field(rec, "pts_away"))
    poss_home = int(_field(rec, "possessions_home"))
    poss_away = int(_field(rec, "possessions_away"))
    return {
        "game_id": int(_field(rec, "game_id")),
        "season": int(_field(rec, "season")),
        "quarter": period,
        "start_clock_seconds": start,
        "end_clock_seconds": end,
        "duration_seconds": start - end,
        "home_team_id": int(_field(rec, "home_team_id")),
        "away_team_id": int(_field(rec, "away_team_id")),
        "home_lineup": home,
        "away_lineup": away,
        "home_lineup_hash": lineup_hash(home),
        "away_lineup_hash": lineup_hash(away),
        "home_pts": pts_home,
        "away_pts": pts_away,
        "pts": pts_home - pts_away,
        "possessions_home": poss_home,
        "possessions_away": poss_away,
        "possessions": poss_home + poss_away,
    }


def persist_stints(conn: Any, stints: Iterable[Any]) -> int:
    records = list(stints)
    if not records:
        return 0
    rows = [_row(r) for r in records]
    game_ids = sorted({r["game_id"] for r in rows})
    cur = conn.cursor()
    for gid in game_ids:
        cur.execute(DELETE_SQL, (gid,))
    cur.executemany(INSERT_SQL, rows)
    conn.commit()
    return len(rows)
