"""Brutus contract nba-5ve (part 2). Pin the JSON output shape and persistence
semantics of `nba stints derive` before stints-lane + cli-lane wire it. Two
modes: --game-id and --season+--team. Black-box: invoke via CliRunner, parse
stdout JSON, validate against pydantic models. Persistence is verified by
patching psycopg.connect (canonical driver, per pyproject.toml).
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from nba.cli.main import app
from nba.contracts import EXIT_CODES, ErrorPayload, StintsDeriveOutput

runner = CliRunner()


def _stdout_json(result):
    assert result.exit_code == 0, (
        f"expected exit 0, got {result.exit_code}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    return json.loads(result.stdout)


def _stderr_error(result, exit_code, error_code):
    assert result.exit_code == exit_code, (
        f"expected exit {exit_code}, got {result.exit_code}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    payload = json.loads(result.stderr.strip().splitlines()[-1])
    parsed = ErrorPayload.model_validate(payload)
    assert parsed.error == error_code, f"expected {error_code}, got {parsed.error}"
    return parsed


GAME_ARGS = ["stints", "derive", "--game-id", "401467916"]
SEASON_ARGS = ["stints", "derive", "--season", "2023", "--team", "NYK"]


def _stub_psycopg(monkeypatch):
    """Install a no-op psycopg fake so derive doesn't try to talk to Postgres."""

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            return self

        def execute(self, *a, **kw):
            return None

        def executemany(self, *a, **kw):
            return None

        def fetchall(self):
            return []

        def fetchone(self):
            return None

        def commit(self):
            return None

        def close(self):
            return None

    calls = {"n": 0}

    def fake_connect(*a, **kw):
        calls["n"] += 1
        return FakeConn()

    monkeypatch.setattr("psycopg.connect", fake_connect, raising=False)
    return calls


def test_stints_derive_by_game_id_returns_envelope(monkeypatch):
    _stub_psycopg(monkeypatch)
    result = runner.invoke(app, GAME_ARGS)
    payload = _stdout_json(result)
    parsed = StintsDeriveOutput.model_validate(payload)
    assert parsed.data.mode == "game"
    assert parsed.meta.mode == "game"
    assert parsed.meta.game_id == "401467916"
    assert parsed.meta.season is None
    assert parsed.meta.team is None


def test_stints_derive_by_season_team_returns_envelope(monkeypatch):
    _stub_psycopg(monkeypatch)
    result = runner.invoke(app, SEASON_ARGS)
    payload = _stdout_json(result)
    parsed = StintsDeriveOutput.model_validate(payload)
    assert parsed.data.mode == "season"
    assert parsed.meta.mode == "season"
    assert parsed.meta.season == 2023
    assert parsed.meta.team == "NYK"
    assert parsed.meta.game_id is None


def test_stints_derive_data_block_has_counts(monkeypatch):
    _stub_psycopg(monkeypatch)
    result = runner.invoke(app, SEASON_ARGS)
    payload = _stdout_json(result)
    parsed = StintsDeriveOutput.model_validate(payload)
    for key in ("stints_persisted", "games_processed", "games_skipped_thin_pbp"):
        v = getattr(parsed.data, key)
        assert isinstance(v, int) and v >= 0, f"data.{key} must be int >= 0, got {v!r}"


def test_stints_derive_writes_to_db(monkeypatch):
    """Persistence assertion: a successful derive must open at least one DB
    connection. Implementer routes writes through psycopg; the connect-count is
    the observable seam."""
    calls = _stub_psycopg(monkeypatch)
    result = runner.invoke(app, GAME_ARGS)
    assert result.exit_code == 0, (
        f"expected exit 0, got {result.exit_code}\nstderr={result.stderr!r}"
    )
    assert calls["n"] >= 1, (
        f"stints derive must open a DB connection (read game + write stints); "
        f"got {calls['n']} psycopg.connect calls"
    )


def test_stints_derive_idempotent(monkeypatch):
    """Re-running with the same args must not double-insert. On the second run,
    stints_persisted should report only newly-written rows; if everything is
    already persisted, it must be 0. Either way, the count is non-negative and
    no error is raised."""
    _stub_psycopg(monkeypatch)
    a_result = runner.invoke(app, GAME_ARGS)
    a = StintsDeriveOutput.model_validate(_stdout_json(a_result))
    b_result = runner.invoke(app, GAME_ARGS)
    b = StintsDeriveOutput.model_validate(_stdout_json(b_result))
    assert b.data.stints_persisted <= a.data.stints_persisted, (
        f"second run persisted MORE stints than first ({b.data.stints_persisted} > "
        f"{a.data.stints_persisted}); derive is not idempotent"
    )


def test_stints_derive_neither_mode_raises_invalid_team_error():
    """Neither --game-id nor (--season+--team) is given — usage error. The CLI
    must surface this as a typed JSON error (InvalidGameError discriminates the
    case of 'mode could not be determined'), exit code stable per EXIT_CODES."""
    result = runner.invoke(app, ["stints", "derive"])
    assert result.exit_code != 0, "missing mode must be non-zero exit"
    last_stderr = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
    payload = json.loads(last_stderr)
    parsed = ErrorPayload.model_validate(payload)
    assert parsed.error in {"InvalidGameError", "InvalidTeamError"}, (
        f"expected InvalidGameError or InvalidTeamError for missing mode, got {parsed.error}"
    )


def test_stints_derive_both_modes_raises_typed_error():
    """Both modes set at once is a usage error. Must be typed."""
    result = runner.invoke(
        app,
        ["stints", "derive", "--game-id", "401467916", "--season", "2023", "--team", "NYK"],
    )
    assert result.exit_code != 0, "both modes must be a non-zero exit"
    last_stderr = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
    payload = json.loads(last_stderr)
    parsed = ErrorPayload.model_validate(payload)
    assert parsed.error in {"InvalidGameError", "InvalidTeamError"}, (
        f"expected InvalidGameError or InvalidTeamError for conflicting modes, got {parsed.error}"
    )


def test_stints_derive_bad_team_raises_invalid_team_error():
    result = runner.invoke(
        app, ["stints", "derive", "--season", "2023", "--team", "ZZZ"]
    )
    parsed = _stderr_error(
        result, exit_code=EXIT_CODES["InvalidTeamError"], error_code="InvalidTeamError"
    )
    assert "ZZZ" in parsed.message or "ZZZ" in str(parsed.context)


def test_stints_derive_pre_2003_raises_era_error():
    result = runner.invoke(
        app, ["stints", "derive", "--season", "1999", "--team", "NYK"]
    )
    _stderr_error(
        result, exit_code=EXIT_CODES["EraOutOfRangeError"], error_code="EraOutOfRangeError"
    )


def test_stints_derive_bad_game_id_raises_invalid_game_error():
    """A game id that doesn't exist in the local DB must surface as
    InvalidGameError, NOT as a raw psycopg error or a crash."""
    result = runner.invoke(app, ["stints", "derive", "--game-id", "0000000000"])
    parsed = _stderr_error(
        result, exit_code=EXIT_CODES["InvalidGameError"], error_code="InvalidGameError"
    )
    assert "0000000000" in parsed.message or "0000000000" in str(parsed.context)


# Persistence semantics — pinned per docs/schema.md v1 (0001_init.sql).
#
# lineup_stints DB columns are: home_pts, away_pts, pts (signed margin),
# possessions, possessions_home, possessions_away. The derive_stints output
# (frozen by contract nba-6gz) uses pts_home/pts_away naming. The persistence
# layer is the translation seam — it must preserve per-side totals AND can
# additionally compute the signed margin. It must NOT collapse the two into a
# single margin field.

def test_stints_persistence_preserves_per_side_pts_not_margin(monkeypatch):
    """Stints-lane routing pin (raised by stints-lane during nba-8oj planning):
    pts in lineup_stints is split into per-side totals (home_pts, away_pts),
    NOT a single signed margin. derive_stints already emits pts_home/pts_away
    separately (contract nba-6gz). Persistence must preserve both.

    Mechanism: implementer must expose the stint-writing entry point as
    `nba.cli.main.persist_stints(conn, stints)` — same module-level seam pattern
    used for `generate_scouting_take` in slice 1. Test patches the seam,
    captures the stints argument, and inspects per-stint shape.
    """
    captured: list = []

    def fake_persist(conn, stints):
        captured.extend(stints)
        return len(list(stints))

    monkeypatch.setattr("nba.cli.main.persist_stints", fake_persist, raising=False)
    _stub_psycopg(monkeypatch)
    result = runner.invoke(app, GAME_ARGS)
    if result.exit_code != 0:
        # contract is about the call shape, not whether the impl succeeds end-to-end
        # here; if exit != 0 the broader red catches it. but we still want this test
        # to be a meaningful red until the seam exists.
        assert False, (
            f"persist_stints seam was not invoked or command failed: "
            f"exit={result.exit_code}, captured={len(captured)}, stderr={result.stderr!r}"
        )
    assert captured, (
        "expected at least one stint passed to nba.cli.main.persist_stints; got 0. "
        "implementer must route stint persistence through this seam."
    )
    for s in captured:
        pts_home = s.get("pts_home") if isinstance(s, dict) else getattr(s, "pts_home", None)
        pts_away = s.get("pts_away") if isinstance(s, dict) else getattr(s, "pts_away", None)
        assert pts_home is not None, (
            f"stint missing pts_home (per-side home total); got {s!r}"
        )
        assert pts_away is not None, (
            f"stint missing pts_away (per-side away total); got {s!r}"
        )
        assert isinstance(pts_home, int) and isinstance(pts_away, int), (
            f"pts_home/pts_away must be integer per-side totals; got "
            f"pts_home={pts_home!r}, pts_away={pts_away!r}"
        )
        # the stint object itself must NOT collapse to a single 'margin' or
        # signed 'pts' field that hides the per-side breakdown. (The DB row
        # MAY additionally store pts = home_pts - away_pts per the schema, but
        # the in-flight stint object reaching persistence must carry both.)
        has_only_margin = (
            isinstance(s, dict)
            and "margin" in s
            and "pts_home" not in s
        )
        assert not has_only_margin, (
            f"stint object must carry per-side pts_home/pts_away, not a "
            f"collapsed 'margin' field; got {s!r}"
        )
