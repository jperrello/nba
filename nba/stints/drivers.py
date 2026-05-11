from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nba.stints.derive import derive_stints
from nba.stints.translate import pbp_rows_to_events

DEFAULT_CACHE_ROOT = Path("data/cache/espn")


def _starters_from_boxscore(
    game_id: int,
    home_team_id: int,
    away_team_id: int,
    cache_root: Path,
) -> tuple[list[int], list[int]] | None:
    path = cache_root / "summary" / f"{game_id}.json"
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    teams = doc.get("boxscore", {}).get("players", [])
    home: list[int] = []
    away: list[int] = []
    for block in teams:
        team_id = int((block.get("team") or {}).get("id", -1))
        stats = block.get("statistics") or []
        if not stats:
            continue
        athletes = stats[0].get("athletes") or []
        side = home if team_id == home_team_id else away if team_id == away_team_id else None
        if side is None:
            continue
        for a in athletes:
            if not a.get("starter"):
                continue
            try:
                side.append(int(a["athlete"]["id"]))
            except (KeyError, TypeError, ValueError):
                continue
    if len(home) != 5 or len(away) != 5:
        return None
    return home, away


def _records_from_stints(
    stints: list[Any],
    *,
    game_id: int,
    season: int,
    home_team_id: int,
    away_team_id: int,
) -> list[dict[str, Any]]:
    return [
        {
            "game_id": game_id,
            "season": season,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "period": s.period,
            "wall_start": s.wall_start,
            "wall_end": s.wall_end,
            "home": tuple(s.home),
            "away": tuple(s.away),
            "pts_home": s.pts_home,
            "pts_away": s.pts_away,
            "possessions_home": s.possessions_home,
            "possessions_away": s.possessions_away,
        }
        for s in stints
    ]


def derive_for_game(
    conn: Any,
    game_id: int,
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> dict[str, Any]:
    """Load one game's PBP from the DB, derive stints, return persist-ready records.

    Tolerant of empty/missing data: callers that need a hard "game not found"
    signal (e.g. CLI surfacing InvalidGameError) should validate up front.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT season, home_team_id, away_team_id, pbp_status "
        "FROM games WHERE game_id = %s",
        (game_id,),
    )
    row = cur.fetchone()
    if row is None:
        return {
            "records": [],
            "games_processed": 0,
            "games_skipped_thin_pbp": 0,
            "warnings": [],
        }
    season, home_team_id, away_team_id, pbp_status = row
    if pbp_status == "thin":
        return {
            "records": [],
            "games_processed": 1,
            "games_skipped_thin_pbp": 1,
            "warnings": [
                {
                    "code": "thin_pbp",
                    "message": f"game {game_id} has thin PBP; skipping stint derivation",
                    "context": {"game_id": game_id},
                }
            ],
        }
    starters = _starters_from_boxscore(game_id, home_team_id, away_team_id, cache_root)
    if starters is None:
        return {
            "records": [],
            "games_processed": 1,
            "games_skipped_thin_pbp": 0,
            "warnings": [
                {
                    "code": "missing_starters",
                    "message": f"cannot locate starters for game {game_id} in cached boxscore",
                    "context": {"game_id": game_id, "cache_root": str(cache_root)},
                }
            ],
        }
    starters_home, starters_away = starters
    cur.execute(
        "SELECT sequence_no, quarter, clock_seconds, team_id, player_id, "
        "assist_player_id, event_type, points_scored, home_score, away_score "
        "FROM pbp_events WHERE game_id = %s ORDER BY quarter, sequence_no",
        (game_id,),
    )
    cols: tuple[str, ...] = (
        "sequence_no", "quarter", "clock_seconds", "team_id", "player_id",
        "assist_player_id", "event_type", "points_scored", "home_score", "away_score",
    )
    rows: list[dict[str, Any]] = [
        dict(zip(cols, r, strict=False)) for r in cur.fetchall()
    ]
    if not rows:
        return {
            "records": [],
            "games_processed": 1,
            "games_skipped_thin_pbp": 0,
            "warnings": [],
        }
    events = pbp_rows_to_events(rows, home_team_id=home_team_id)
    stints = derive_stints(events, starters_home=starters_home, starters_away=starters_away)
    records = _records_from_stints(
        stints,
        game_id=game_id,
        season=season,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )
    return {
        "records": records,
        "games_processed": 1,
        "games_skipped_thin_pbp": 0,
        "warnings": [],
    }


def derive_for_season(
    conn: Any,
    season: int,
    team_id: int,
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> dict[str, Any]:
    cur = conn.cursor()
    cur.execute(
        "SELECT game_id FROM games "
        "WHERE season = %s AND (home_team_id = %s OR away_team_id = %s) "
        "ORDER BY game_date, game_id",
        (season, team_id, team_id),
    )
    game_ids = [int(r[0]) for r in cur.fetchall()]
    total_records: list[dict[str, Any]] = []
    games_processed = 0
    games_skipped_thin = 0
    warnings: list[dict[str, Any]] = []
    for gid in game_ids:
        result = derive_for_game(conn, gid, cache_root=cache_root)
        total_records.extend(result["records"])
        games_processed += result["games_processed"]
        games_skipped_thin += result["games_skipped_thin_pbp"]
        warnings.extend(result["warnings"])
    return {
        "records": total_records,
        "games_processed": games_processed,
        "games_skipped_thin_pbp": games_skipped_thin,
        "warnings": warnings,
    }
