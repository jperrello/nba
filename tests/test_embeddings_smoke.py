"""Brutus contract nba-bbq. Post-train smoke for `embeddings_player`. DB-state
contract — does NOT touch the CLI surface (nba/contracts.py stays frozen).

Gated by NBA_EMBEDDINGS_SMOKE=1 + a live local Postgres at the URL returned by
nba.config.db(), with `embeddings_player` populated by ml-lane's training
script. Filed per D4 ruling: training is a `python -m nba.train.embeddings` /
`scripts/` entrypoint, not a CLI subcommand.

Pinned assertions:
1. row count for season=2023 latest-model_version (filtered to the NYK 2022-23
   roster cohort) == COUNT(DISTINCT player_id) FROM rosters WHERE season=2023
   AND team_id=18.
2. every embedding has dim == 128.
3. every embedding is L2-normalized to unit length (||v|| − 1 < 1e-3).
4. season column carries value 2023 on every row in the cohort (D1 end-year
   convention) — and is never NULL.
"""
from __future__ import annotations

import math
import os

import pytest

SMOKE_ENABLED = os.getenv("NBA_EMBEDDINGS_SMOKE") == "1"

pytestmark = pytest.mark.skipif(
    not SMOKE_ENABLED,
    reason="set NBA_EMBEDDINGS_SMOKE=1 to run; requires local Postgres + ml-lane training output",
)


NYK_TEAM_ID = 18
SEASON = 2023
DIM_EXPECTED = 128
L2_TOL = 1e-3


@pytest.fixture(scope="module")
def conn():
    import psycopg

    from nba.config import db

    cfg = db()
    c = psycopg.connect(cfg.url)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture(scope="module")
def latest_model_version(conn):
    """Pick the most recently created model_version for season=2023. If the
    table has no rows for the season, fail loudly — every dependent test will
    error against the same root cause."""
    cur = conn.cursor()
    cur.execute(
        "SELECT model_version FROM embeddings_player "
        "WHERE season = %s "
        "ORDER BY created_at DESC LIMIT 1",
        (SEASON,),
    )
    row = cur.fetchone()
    if row is None:
        pytest.fail(
            f"embeddings_player has no rows for season={SEASON}; "
            f"ml-lane training has not produced output yet."
        )
    return row[0]


@pytest.fixture(scope="module")
def expected_player_count(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT player_id) FROM rosters "
        "WHERE season = %s AND team_id = %s",
        (SEASON, NYK_TEAM_ID),
    )
    return cur.fetchone()[0]


def test_row_count_matches_rostered_players(conn, latest_model_version, expected_player_count):
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM embeddings_player "
        "WHERE season = %s AND model_version = %s "
        "AND player_id IN (SELECT player_id FROM rosters "
        "                  WHERE season = %s AND team_id = %s)",
        (SEASON, latest_model_version, SEASON, NYK_TEAM_ID),
    )
    actual = cur.fetchone()[0]
    assert actual == expected_player_count, (
        f"embeddings_player rows for NYK season={SEASON} model_version="
        f"{latest_model_version!r} = {actual}, expected {expected_player_count} "
        f"(COUNT DISTINCT player_id FROM rosters)"
    )


def test_embedding_dim_is_128(conn, latest_model_version):
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT vector_dims(embedding) FROM embeddings_player "
        "WHERE season = %s AND model_version = %s",
        (SEASON, latest_model_version),
    )
    dims = [r[0] for r in cur.fetchall()]
    assert dims, (
        f"no embeddings_player rows for season={SEASON} "
        f"model_version={latest_model_version!r}"
    )
    assert dims == [DIM_EXPECTED], (
        f"expected all embedding vectors to have dim={DIM_EXPECTED}, got {dims}"
    )


def test_vectors_are_l2_normalized(conn, latest_model_version):
    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, embedding FROM embeddings_player "
        "WHERE season = %s AND model_version = %s "
        "AND player_id IN (SELECT player_id FROM rosters "
        "                  WHERE season = %s AND team_id = %s)",
        (SEASON, latest_model_version, SEASON, NYK_TEAM_ID),
    )
    rows = cur.fetchall()
    assert rows, "no NYK-cohort embedding rows to check L2 norm against"
    bad = []
    for player_id, vec in rows:
        if isinstance(vec, str):
            vec = [float(x) for x in vec.strip("[]").split(",")]
        norm = math.sqrt(sum(float(x) * float(x) for x in vec))
        if abs(norm - 1.0) > L2_TOL:
            bad.append((player_id, norm))
    assert not bad, (
        f"{len(bad)}/{len(rows)} embedding vectors not L2-normalized "
        f"(tol={L2_TOL}); sample (player_id, ||v||) = {bad[:5]}"
    )


def test_season_column_value_is_end_year(conn, latest_model_version):
    """D1 convention: season=2023 means the 2022-23 NBA season (end-year).
    Every NYK-cohort embedding row must carry season=2023."""
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT season FROM embeddings_player "
        "WHERE model_version = %s "
        "AND player_id IN (SELECT player_id FROM rosters "
        "                  WHERE season = %s AND team_id = %s)",
        (latest_model_version, SEASON, NYK_TEAM_ID),
    )
    seasons = [r[0] for r in cur.fetchall()]
    assert seasons == [SEASON], (
        f"NYK 2022-23 cohort must have season={SEASON} on every row "
        f"(D1 end-year); got distinct seasons={seasons}"
    )


def test_season_column_never_null(conn, latest_model_version):
    """Defense in depth — schema declares `season INT NOT NULL`, but pin it
    here too so a future migration that loosens the constraint is caught."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM embeddings_player "
        "WHERE model_version = %s AND season IS NULL",
        (latest_model_version,),
    )
    n = cur.fetchone()[0]
    assert n == 0, f"{n} embeddings_player rows have NULL season under latest model_version"
