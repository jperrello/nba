from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nba.stints.drivers import derive_for_game, derive_for_season


class FakeCursor:
    def __init__(self, queue: list[Any]) -> None:
        self._queue = queue
        self._current: list[Any] | None = None

    def execute(self, sql: str, params: Any = None) -> None:
        if "FROM games WHERE game_id" in sql:
            self._current = self._queue.pop(0) if self._queue else None
        elif "FROM games WHERE season" in sql:
            self._current = self._queue.pop(0) if self._queue else []
        elif "FROM pbp_events" in sql:
            self._current = self._queue.pop(0) if self._queue else []

    def fetchone(self) -> Any:
        v = self._current
        self._current = None
        return v

    def fetchall(self) -> list[Any]:
        v = self._current if isinstance(self._current, list) else []
        self._current = None
        return v


class FakeConn:
    def __init__(self, queue: list[Any]) -> None:
        self._queue = queue

    def cursor(self) -> FakeCursor:
        return FakeCursor(self._queue)


def test_derive_for_game_unknown_returns_zero():
    conn = FakeConn([None])
    result = derive_for_game(conn, 999, cache_root=Path("/nonexistent"))
    assert result["records"] == []
    assert result["games_processed"] == 0
    assert result["games_skipped_thin_pbp"] == 0


def test_derive_for_game_thin_pbp_skipped():
    conn = FakeConn([(2023, 18, 11, "thin")])
    result = derive_for_game(conn, 401, cache_root=Path("/nonexistent"))
    assert result["records"] == []
    assert result["games_processed"] == 1
    assert result["games_skipped_thin_pbp"] == 1
    assert result["warnings"][0]["code"] == "thin_pbp"


def test_derive_for_game_missing_starters_warns():
    conn = FakeConn([(2023, 18, 11, "ok")])
    result = derive_for_game(conn, 401, cache_root=Path("/nonexistent"))
    assert result["records"] == []
    assert result["games_processed"] == 1
    assert result["warnings"][0]["code"] == "missing_starters"


def test_derive_for_game_with_real_fixture(tmp_path: Path):
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "pbp_minigame.json").read_text()
    )
    home_team_id = 18
    away_team_id = 11
    summary_path = tmp_path / "summary" / "401467916.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(
        json.dumps(
            {
                "boxscore": {
                    "players": [
                        {
                            "team": {"id": home_team_id},
                            "statistics": [
                                {
                                    "athletes": [
                                        {"starter": True, "athlete": {"id": int(p[1:])}}
                                        for p in fixture["starters_home"]
                                    ]
                                }
                            ],
                        },
                        {
                            "team": {"id": away_team_id},
                            "statistics": [
                                {
                                    "athletes": [
                                        {"starter": True, "athlete": {"id": int(p[1:]) + 100}
                                         if False else {"id": _away_id(p)}}
                                        for p in fixture["starters_away"]
                                    ]
                                }
                            ],
                        },
                    ]
                }
            }
        )
    )
    pbp_rows = [_pbp_row(e, home_team_id, away_team_id, fixture) for e in fixture["events"]]
    pbp_rows = [r for r in pbp_rows if r is not None]
    conn = FakeConn([(2023, home_team_id, away_team_id, "ok"), pbp_rows])
    result = derive_for_game(conn, 401467916, cache_root=tmp_path)
    assert result["games_processed"] == 1
    assert result["games_skipped_thin_pbp"] == 0
    assert len(result["records"]) == 4
    s0 = result["records"][0]
    assert s0["pts_home"] == 5
    assert s0["pts_away"] == 4
    assert s0["game_id"] == 401467916
    assert s0["season"] == 2023


def test_derive_for_season_iterates_games():
    home_id = 18
    away_id = 11
    games_queue = [(401, 402)]  # SELECT game_id returns 2 ids
    # per-game queue: (game row, pbp rows) for game 401, then game 402
    queue = [
        [(401,), (402,)],          # SELECT game_id list
        (2023, home_id, away_id, "thin"),  # game 401: thin
        (2023, home_id, away_id, "thin"),  # game 402: thin
    ]
    # Convert tuple of tuples in first slot to list-of-rows for fetchall
    queue[0] = [(401,), (402,)]
    conn = FakeConn(queue)
    result = derive_for_season(conn, 2023, home_id, cache_root=Path("/nonexistent"))
    assert result["games_processed"] == 2
    assert result["games_skipped_thin_pbp"] == 2
    assert result["records"] == []
    _ = games_queue  # appease linters


def _away_id(p: str) -> int:
    return 1000 + int(p[1:])


_EV_MAP = {
    "made_2pt": ("made_2pt", 2),
    "made_3pt": ("made_3pt", 3),
    "missed_2pt": ("missed_2pt", 0),
    "missed_3pt": ("missed_3pt", 0),
    "ft_made": ("ft_made", 1),
    "ft_miss": ("ft_missed", 0),
    "rebound_off": ("offensive_rebound", 0),
    "rebound_def": ("defensive_rebound", 0),
    "turnover": ("turnover", 0),
    "shooting_foul": ("shooting_foul", 0),
    "sub": ("substitution", 0),
    "period_end": ("period_end", 0),
    "game_end": ("game_end", 0),
    "tipoff": ("jumpball", 0),
}


def _pbp_row(e: dict, home_team_id: int, away_team_id: int, fixture: dict) -> tuple | None:
    raw_type = e["type"]
    mapped = _EV_MAP.get(raw_type)
    if mapped is None:
        return None
    canonical, pts = mapped
    period = e["period"]
    qlen = 720
    prior = sum(720 for _ in range(1, period))
    clock = qlen - (e["t"] - prior)
    team = e.get("team")
    team_id = home_team_id if team == "home" else away_team_id if team == "away" else None
    if raw_type == "sub":
        player_id = _resolve_id(e["player_in"], fixture)
        assist_player_id = _resolve_id(e["player_out"], fixture)
    else:
        player_id = _resolve_id(e.get("player"), fixture) if e.get("player") else None
        assist_player_id = None
    return (
        int(e.get("sequence_no", 0)),
        period,
        int(clock),
        team_id,
        player_id,
        assist_player_id,
        canonical,
        pts,
        e.get("home_score", 0),
        e.get("away_score", 0),
    )


def _resolve_id(p: str | None, fixture: dict) -> int | None:
    if p is None:
        return None
    if p.startswith("H"):
        return int(p[1:])
    if p.startswith("A"):
        return 1000 + int(p[1:])
    return None
