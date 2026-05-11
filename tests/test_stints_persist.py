from __future__ import annotations

from typing import Any

from nba.stints.persist import persist_stints
from nba.stints.translate import lineup_hash


class FakeCursor:
    def __init__(self, log: list[tuple[str, Any]]):
        self._log = log

    def execute(self, sql: str, params: Any = None) -> None:
        self._log.append(("execute", sql, params))

    def executemany(self, sql: str, seq: list[Any]) -> None:
        self._log.append(("executemany", sql, list(seq)))


class FakeConn:
    def __init__(self) -> None:
        self.log: list[tuple[str, Any]] = []
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.log)

    def commit(self) -> None:
        self.commits += 1


def _stint(
    *,
    game_id: int = 401467916,
    season: int = 2023,
    period: int = 1,
    wall_start: float = 0.0,
    wall_end: float = 30.0,
    home: tuple[int, ...] = (1, 2, 3, 4, 5),
    away: tuple[int, ...] = (10, 20, 30, 40, 50),
    pts_home: int = 5,
    pts_away: int = 4,
    possessions_home: int = 2,
    possessions_away: int = 3,
    home_team_id: int = 18,
    away_team_id: int = 11,
) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "season": season,
        "period": period,
        "wall_start": wall_start,
        "wall_end": wall_end,
        "home": home,
        "away": away,
        "pts_home": pts_home,
        "pts_away": pts_away,
        "possessions_home": possessions_home,
        "possessions_away": possessions_away,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
    }


def test_empty_input_returns_zero_and_does_not_touch_conn():
    conn = FakeConn()
    n = persist_stints(conn, [])
    assert n == 0
    assert conn.log == []
    assert conn.commits == 0


def test_persist_returns_row_count():
    conn = FakeConn()
    n = persist_stints(conn, [_stint(), _stint(wall_start=30.0, wall_end=60.0)])
    assert n == 2


def test_persist_issues_delete_before_insert_per_game():
    conn = FakeConn()
    persist_stints(conn, [_stint(), _stint(wall_start=30, wall_end=60)])
    ops = [(op, sql) for (op, sql, _) in conn.log]
    delete_idx = next(i for i, (op, sql) in enumerate(ops) if op == "execute" and "DELETE" in sql)
    insert_idx = next(i for i, (op, sql) in enumerate(ops) if op == "executemany" and "INSERT" in sql)
    assert delete_idx < insert_idx


def test_persist_one_delete_per_distinct_game():
    conn = FakeConn()
    persist_stints(
        conn,
        [
            _stint(game_id=1, wall_start=0, wall_end=30),
            _stint(game_id=1, wall_start=30, wall_end=60),
            _stint(game_id=2, wall_start=0, wall_end=30),
        ],
    )
    deletes = [params for (op, sql, params) in conn.log if op == "execute" and "DELETE" in sql]
    assert deletes == [(1,), (2,)]


def test_persist_commits_on_success():
    conn = FakeConn()
    persist_stints(conn, [_stint()])
    assert conn.commits == 1


def test_row_includes_signed_margin_and_total_possessions():
    conn = FakeConn()
    persist_stints(
        conn,
        [_stint(pts_home=5, pts_away=4, possessions_home=2, possessions_away=3)],
    )
    insertmany = next(p for (op, _, p) in conn.log if op == "executemany")
    row = insertmany[0]
    assert row["home_pts"] == 5
    assert row["away_pts"] == 4
    assert row["pts"] == 1
    assert row["possessions"] == 5
    assert row["possessions_home"] == 2
    assert row["possessions_away"] == 3


def test_row_clock_translation_wall_to_game():
    conn = FakeConn()
    persist_stints(conn, [_stint(period=1, wall_start=0.0, wall_end=30.0)])
    row = next(p for (op, _, p) in conn.log if op == "executemany")[0]
    assert row["start_clock_seconds"] == 720
    assert row["end_clock_seconds"] == 690
    assert row["duration_seconds"] == 30
    assert row["start_clock_seconds"] >= row["end_clock_seconds"]


def test_row_handles_ot_quarter_length():
    conn = FakeConn()
    persist_stints(conn, [_stint(period=5, wall_start=2880.0, wall_end=2920.0)])
    row = next(p for (op, _, p) in conn.log if op == "executemany")[0]
    assert row["start_clock_seconds"] == 300
    assert row["end_clock_seconds"] == 260
    assert row["duration_seconds"] == 40


def test_row_includes_canonical_lineup_hashes():
    conn = FakeConn()
    persist_stints(conn, [_stint(home=(5, 3, 1, 4, 2), away=(50, 30, 10, 40, 20))])
    row = next(p for (op, _, p) in conn.log if op == "executemany")[0]
    assert row["home_lineup"] == [1, 2, 3, 4, 5]
    assert row["away_lineup"] == [10, 20, 30, 40, 50]
    assert row["home_lineup_hash"] == lineup_hash([1, 2, 3, 4, 5])
    assert row["away_lineup_hash"] == lineup_hash([10, 20, 30, 40, 50])


def test_idempotent_second_run_writes_same_count():
    a_conn = FakeConn()
    b_conn = FakeConn()
    payload = [_stint(), _stint(wall_start=30, wall_end=60)]
    n1 = persist_stints(a_conn, payload)
    n2 = persist_stints(b_conn, payload)
    assert n1 == n2 == 2


def test_persist_accepts_object_with_attrs():
    class StintObj:
        def __init__(self, **kw: Any) -> None:
            for k, v in kw.items():
                setattr(self, k, v)

    conn = FakeConn()
    n = persist_stints(conn, [StintObj(**_stint())])
    assert n == 1
    row = next(p for (op, _, p) in conn.log if op == "executemany")[0]
    assert row["home_pts"] == 5
