from __future__ import annotations

import psycopg
from pgvector.psycopg import register_vector

from nba.config import db


def rostered_players(season: int, team_abbr: str | None = None) -> list[int]:
    sql = "SELECT DISTINCT player_id FROM rosters WHERE season = %s"
    params: list[object] = [season]
    if team_abbr is not None:
        sql += " AND team_id = (SELECT team_id FROM teams WHERE abbreviation = %s)"
        params.append(team_abbr)
    sql += " ORDER BY player_id"
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [row[0] for row in cur.fetchall()]


def minutes_per_player(player_ids: list[int], season: int) -> dict[int, int]:
    if not player_ids:
        return {}
    sql = """
    WITH side AS (
      SELECT unnest(home_lineup) AS player_id, duration_seconds FROM lineup_stints WHERE season = %s
      UNION ALL
      SELECT unnest(away_lineup) AS player_id, duration_seconds FROM lineup_stints WHERE season = %s
    )
    SELECT player_id, CAST(SUM(duration_seconds) / 60.0 AS INTEGER) AS minutes
    FROM side
    WHERE player_id = ANY(%s)
    GROUP BY player_id;
    """
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(sql, [season, season, player_ids])
        return dict(cur.fetchall())


def upsert(
    rows: list[tuple[int, int, str, list[float], int | None]],
) -> int:
    if not rows:
        return 0
    sql = """
    INSERT INTO embeddings_player (player_id, season, model_version, embedding, minutes_sample)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (player_id, season, model_version) DO UPDATE
    SET embedding      = EXCLUDED.embedding,
        minutes_sample = EXCLUDED.minutes_sample;
    """
    with psycopg.connect(db().url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    return len(rows)
