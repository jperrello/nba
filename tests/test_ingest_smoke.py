from __future__ import annotations

import os

import pytest

SMOKE_ENABLED = os.getenv("NBA_INGEST_SMOKE") == "1"


pytestmark = pytest.mark.skipif(
    not SMOKE_ENABLED,
    reason="set NBA_INGEST_SMOKE=1 to run; requires local Postgres + ESPN network",
)


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
def nyk_2023(conn):
    """Run the ingest once per test module so the row-count assertions read the
    same DB state. Re-run is idempotent — second invocation is essentially a
    no-op on the row counts."""
    from nba.ingest.season import ingest_season

    out = ingest_season("NYK", 2023, dry_run=False)
    return out


def test_nyk_2022_23_games_total(conn, nyk_2023):
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM games "
        "WHERE season = 2023 AND (home_team_id = 18 OR away_team_id = 18)"
    )
    n = cur.fetchone()[0]
    assert n == 82, f"NYK 2022-23 should have 82 regular-season games, got {n}"


def test_nyk_2022_23_pbp_events_in_range(conn, nyk_2023):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM pbp_events
        WHERE game_id IN (
            SELECT game_id FROM games
            WHERE season = 2023
              AND (home_team_id = 18 OR away_team_id = 18)
              AND pbp_status = 'ok'
        )
        """
    )
    n = cur.fetchone()[0]
    assert 35_000 <= n <= 40_000, f"pbp_events for NYK 2022-23 ok games = {n}, expected 35k-40k"


def test_nyk_2022_23_roster_size(conn, nyk_2023):
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT player_id) FROM rosters "
        "WHERE season = 2023 AND team_id = 18"
    )
    n = cur.fetchone()[0]
    assert 15 <= n <= 20, f"NYK 2022-23 distinct roster size = {n}, expected 15-20"


def test_pbp_events_have_jsonb_placeholder(conn, nyk_2023):
    """Per D2: ingest writes [] sentinel, never NULL. Stints deriver fills later."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM pbp_events
        WHERE game_id IN (SELECT game_id FROM games WHERE season=2023
                                 AND (home_team_id=18 OR away_team_id=18))
          AND players_on_floor IS NULL
        """
    )
    assert cur.fetchone()[0] == 0, "ingest must never write NULL players_on_floor"


def test_idempotent_rerun(conn, nyk_2023):
    """Re-running ingest must not change game / pbp row counts."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games WHERE season=2023")
    g_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pbp_events")
    p_before = cur.fetchone()[0]

    from nba.ingest.season import ingest_season

    ingest_season("NYK", 2023, dry_run=False)

    cur.execute("SELECT COUNT(*) FROM games WHERE season=2023")
    g_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pbp_events")
    p_after = cur.fetchone()[0]

    assert g_before == g_after, f"games row count drifted on re-run: {g_before} → {g_after}"
    assert p_before == p_after, f"pbp_events row count drifted on re-run: {p_before} → {p_after}"


def test_thin_pbp_games_skipped_for_pbp(conn, nyk_2023):
    """Thin games still get a games row but no pbp_events rows."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT game_id FROM games
        WHERE season=2023
          AND (home_team_id=18 OR away_team_id=18)
          AND pbp_status='thin'
        """
    )
    thin_ids = [r[0] for r in cur.fetchall()]
    if not thin_ids:
        pytest.skip("no thin games in this season; nothing to assert")
    cur.execute(
        "SELECT game_id, COUNT(*) FROM pbp_events WHERE game_id = ANY(%s) GROUP BY game_id",
        (thin_ids,),
    )
    leakage = cur.fetchall()
    assert leakage == [], f"thin games must not have pbp_events rows; got {leakage}"
