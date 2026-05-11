from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psycopg
import torch
from pgvector.psycopg import register_vector

from nba.config import db
from nba.embeddings.version import EMBEDDINGS_VERSION
from nba.predictor.model import Predictor

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "models" / "predictor_latest.json"


@dataclass
class TeamView:
    team_id: int
    team_abbr: str
    full_name: str
    season_used: int
    season_requested: int
    starter_player_ids: list[int]
    starter_names: list[str]
    embeddings: np.ndarray  # (5, 128)


class ResolveError(Exception):
    pass


def resolve_team(name: str) -> tuple[int, str, str]:
    q = name.strip().lower()
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute("SELECT team_id, abbreviation, full_name FROM teams")
        for tid, abbr, full in cur.fetchall():
            if q == abbr.lower() or q in full.lower():
                return int(tid), abbr, full
    raise ResolveError(f"no team matches {name!r}")


def nearest_season(team_id: int, requested: int, model_version: str = EMBEDDINGS_VERSION) -> int:
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT ep.season FROM embeddings_player ep "
            "WHERE ep.model_version = %s "
            "AND EXISTS (SELECT 1 FROM rosters r WHERE r.player_id = ep.player_id AND r.season = ep.season AND r.team_id = %s)",
            (model_version, team_id),
        )
        avail = sorted({int(s) for (s,) in cur.fetchall()})
    if not avail:
        raise ResolveError(f"no embeddings for team_id={team_id}")
    if requested in avail:
        return requested
    return min(avail, key=lambda s: (abs(s - requested), -s))


def top_starters(team_id: int, season: int, k: int = 5) -> tuple[list[int], list[str]]:
    sql = """
    WITH side AS (
      SELECT unnest(home_lineup) AS player_id, duration_seconds
      FROM lineup_stints WHERE season = %s AND home_team_id = %s
      UNION ALL
      SELECT unnest(away_lineup) AS player_id, duration_seconds
      FROM lineup_stints WHERE season = %s AND away_team_id = %s
    ),
    by_player AS (
      SELECT side.player_id, SUM(duration_seconds) AS sec
      FROM side
      JOIN rosters r ON r.player_id = side.player_id AND r.season = %s AND r.team_id = %s
      GROUP BY side.player_id
    )
    SELECT bp.player_id, COALESCE(p.full_name, 'Player ' || bp.player_id::text)
    FROM by_player bp
    LEFT JOIN players p ON p.player_id = bp.player_id
    ORDER BY bp.sec DESC NULLS LAST
    LIMIT %s;
    """
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(sql, (season, team_id, season, team_id, season, team_id, k))
        rows = cur.fetchall()
    if len(rows) < k:
        sql_fallback = """
        SELECT r.player_id, COALESCE(p.full_name, 'Player ' || r.player_id::text)
        FROM rosters r
        LEFT JOIN players p ON p.player_id = r.player_id
        WHERE r.season = %s AND r.team_id = %s
        ORDER BY r.player_id
        LIMIT %s;
        """
        with psycopg.connect(db().url) as conn, conn.cursor() as cur:
            cur.execute(sql_fallback, (season, team_id, k))
            rows = cur.fetchall()
    return [int(r[0]) for r in rows], [str(r[1]) for r in rows]


def load_player_embeddings(player_ids: list[int], season: int, model_version: str = EMBEDDINGS_VERSION) -> np.ndarray:
    with psycopg.connect(db().url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, embedding FROM embeddings_player "
                "WHERE season = %s AND model_version = %s AND player_id = ANY(%s)",
                (season, model_version, player_ids),
            )
            rows = {int(pid): np.asarray(vec, dtype=np.float32) for pid, vec in cur.fetchall()}
    out: list[np.ndarray] = []
    for pid in player_ids:
        if pid in rows:
            out.append(rows[pid])
        else:
            v = np.random.default_rng(pid).normal(size=128).astype(np.float32)
            v /= max(float(np.linalg.norm(v)), 1e-8)
            out.append(v)
    return np.stack(out)


def view(team_name: str, season: int) -> TeamView:
    team_id, abbr, full = resolve_team(team_name)
    used = nearest_season(team_id, season)
    pids, names = top_starters(team_id, used)
    embs = load_player_embeddings(pids, used)
    return TeamView(
        team_id=team_id,
        team_abbr=abbr,
        full_name=full,
        season_used=used,
        season_requested=season,
        starter_player_ids=pids,
        starter_names=names,
        embeddings=embs,
    )


def load_predictor() -> tuple[Predictor, dict] | tuple[None, None]:
    if not MANIFEST.exists():
        return None, None
    manifest = json.loads(MANIFEST.read_text())
    model = Predictor()
    state = torch.load(manifest["weights_path"], map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model, manifest
