from __future__ import annotations

import json
from pathlib import Path

import psycopg

from nba.config import ESPN_CACHE_DIR, db

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "espn"


def from_db(game_id: int) -> tuple[list[int], list[int]]:
    sql = """
    SELECT home_lineup, away_lineup
    FROM lineup_stints
    WHERE game_id = %s
    ORDER BY quarter ASC, start_clock_seconds DESC, stint_id ASC
    LIMIT 1;
    """
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(sql, (game_id,))
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"no lineup_stints for game_id={game_id}")
    return list(row[0]), list(row[1])


def _from_summary_json(path: Path) -> tuple[list[int], list[int]]:
    payload = json.loads(path.read_text())
    teams = payload.get("boxscore", {}).get("players", [])
    sides: list[list[int]] = []
    for team_block in teams:
        starters: list[int] = []
        stats = team_block.get("statistics") or []
        if not stats:
            continue
        athletes = stats[0].get("athletes") or []
        for ath in athletes:
            if ath.get("starter"):
                pid = ath.get("athlete", {}).get("id")
                if pid is not None:
                    starters.append(int(pid))
        if len(starters) >= 5:
            sides.append(starters[:5])
    if len(sides) != 2:
        raise RuntimeError(f"boxscore at {path} did not yield 2x5 starters; got {[len(s) for s in sides]}")
    home_first = payload.get("header", {}).get("competitions", [{}])[0]
    home_is_first = False
    for comp in [home_first]:
        for team in comp.get("competitors", []):
            if team.get("homeAway") == "home":
                home_is_first = comp.get("competitors", [{}])[0].get("homeAway") == "home"
    return (sides[0], sides[1]) if home_is_first else (sides[1], sides[0])


def from_summary_cache(game_id: int, season: int | None = None) -> tuple[list[int], list[int]]:
    candidates: list[Path] = [
        ESPN_CACHE_DIR / "summary" / f"{game_id}.json",
        ESPN_CACHE_DIR / f"summary_{game_id}.json",
    ]
    if season is not None:
        candidates.append(FIXTURES_DIR / str(season) / f"{game_id}.json")
    for path in candidates:
        if path.exists():
            return _from_summary_json(path)
    raise FileNotFoundError(f"no ESPN summary cache for game_id={game_id} (looked in {[str(p) for p in candidates]})")


def get_starters(game_id: int, season: int | None = None) -> tuple[list[int], list[int]]:
    try:
        return from_summary_cache(game_id, season=season)
    except (FileNotFoundError, RuntimeError):
        return from_db(game_id)
