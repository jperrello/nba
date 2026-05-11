from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from nba.config import db
from nba.embeddings.version import EMBEDDINGS_DIM, EMBEDDINGS_VERSION


@dataclass
class Stints:
    game_ids: np.ndarray  # (N,)
    home_lineup: np.ndarray  # (N, 5) of player_id
    away_lineup: np.ndarray  # (N, 5)
    pts: np.ndarray  # (N,) home_pts - away_pts
    duration: np.ndarray  # (N,) seconds
    season: np.ndarray  # (N,)


def load_embeddings(season: int, model_version: str = EMBEDDINGS_VERSION) -> tuple[dict[int, int], np.ndarray]:
    with psycopg.connect(db().url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, embedding FROM embeddings_player "
                "WHERE season = %s AND model_version = %s ORDER BY player_id",
                (season, model_version),
            )
            rows = cur.fetchall()
    if not rows:
        raise RuntimeError(f"no embeddings for season={season} model_version={model_version!r}")
    idx_of = {int(pid): i for i, (pid, _) in enumerate(rows)}
    table = np.stack([np.asarray(vec, dtype=np.float32) for _, vec in rows])
    assert table.shape == (len(rows), EMBEDDINGS_DIM)
    return idx_of, table


def load_stints(season: int, game_ids: set[int]) -> Stints:
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT game_id, home_lineup, away_lineup, home_pts, away_pts, duration_seconds, season "
            "FROM lineup_stints "
            "WHERE season = %s AND game_id = ANY(%s) AND duration_seconds > 0 "
            "ORDER BY game_id, stint_id",
            (season, list(game_ids)),
        )
        rows = cur.fetchall()
    if not rows:
        return Stints(
            game_ids=np.array([], dtype=np.int64),
            home_lineup=np.zeros((0, 5), dtype=np.int64),
            away_lineup=np.zeros((0, 5), dtype=np.int64),
            pts=np.array([], dtype=np.float32),
            duration=np.array([], dtype=np.float32),
            season=np.array([], dtype=np.int64),
        )
    return Stints(
        game_ids=np.array([r[0] for r in rows], dtype=np.int64),
        home_lineup=np.array([r[1] for r in rows], dtype=np.int64),
        away_lineup=np.array([r[2] for r in rows], dtype=np.int64),
        pts=np.array([r[3] - r[4] for r in rows], dtype=np.float32),
        duration=np.array([r[5] for r in rows], dtype=np.float32),
        season=np.array([r[6] for r in rows], dtype=np.int64),
    )
