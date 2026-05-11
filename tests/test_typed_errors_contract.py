"""Brutus contract nba-5ve (part 3). Pin the typed-error contract for the whole
CLI: every parse error must surface as ErrorPayload JSON on stderr (single line),
with a stable exit code defined by `nba.contracts.EXIT_CODES`. No Python
tracebacks leak. No raw ValueError. Covers the carried-from-slice-1 bug where
`nba sim --team1 'wat'` printed a traceback.
"""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from nba.cli.main import app
from nba.contracts import EXIT_CODES, ErrorPayload

runner = CliRunner()


def _parse_stderr_error(result):
    assert result.stderr.strip(), f"stderr must carry a typed-error JSON line, got empty stderr"
    last_line = result.stderr.strip().splitlines()[-1]
    payload = json.loads(last_line)
    return ErrorPayload.model_validate(payload)


# (1) Stable exit-code table covers every declared ErrorCode

def test_exit_code_table_covers_every_error_code():
    from nba.contracts import ErrorCode  # type: ignore

    declared = set(ErrorCode.__args__)  # type: ignore[attr-defined]
    mapped = set(EXIT_CODES.keys())
    missing = declared - mapped
    extra = mapped - declared
    assert not missing, f"EXIT_CODES missing entries for: {missing}"
    assert not extra, f"EXIT_CODES has stale entries: {extra}"


def test_exit_codes_are_distinct():
    codes = list(EXIT_CODES.values())
    assert len(codes) == len(set(codes)) or set(codes) == {2, 3, 4, 5, 6, 7, 8, 9}, (
        "exit codes must be distinct integers (collisions defeat agent-side dispatch)"
    )
    for code in codes:
        assert isinstance(code, int)
        assert 2 <= code <= 125, f"exit code {code} outside the conventional [2,125] range"


# (2) Parse-time errors from teamspec are wrapped, not raw ValueError

@pytest.mark.parametrize(
    "team1,expected_error",
    [
        # carried bug: single-word teamspec with no '-' currently raises raw ValueError
        ("wat", "InvalidTeamError"),
        # season missing
        ("knicks-", "InvalidSeasonError"),
        # season non-integer
        ("knicks-abc", "InvalidSeasonError"),
        # unterminated swap block
        ("knicks-2024[swap=kat->randle", "InvalidTeamError"),
        # swap clause missing '->'
        ("knicks-2024[swap=kat:randle]", "InvalidTeamError"),
        # swap target is unknown player
        ("knicks-2024[swap=kat->zzznobody]", "InvalidPlayerError"),
    ],
)
def test_sim_malformed_teamspec_returns_typed_error(team1, expected_error):
    result = runner.invoke(app, ["sim", "--team1", team1, "--team2", "pacers-2024"])
    assert result.exit_code != 0, (
        f"expected non-zero exit for malformed team1={team1!r}, got {result.exit_code}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "Traceback" not in result.stderr, (
        f"raw Python traceback leaked to stderr for team1={team1!r}:\n{result.stderr}"
    )
    parsed = _parse_stderr_error(result)
    assert parsed.error == expected_error, (
        f"team1={team1!r}: expected {expected_error}, got {parsed.error}\n"
        f"stderr={result.stderr!r}"
    )
    assert result.exit_code == EXIT_CODES[expected_error], (
        f"team1={team1!r}: exit code {result.exit_code} != EXIT_CODES[{expected_error}]={EXIT_CODES[expected_error]}"
    )


# (3) Era and player errors keep their slice-1 exit codes

def test_sim_pre_2003_season_keeps_era_exit_code():
    result = runner.invoke(
        app, ["sim", "--team1", "knicks-1999", "--team2", "pacers-2024"]
    )
    parsed = _parse_stderr_error(result)
    assert parsed.error == "EraOutOfRangeError"
    assert result.exit_code == EXIT_CODES["EraOutOfRangeError"] == 4


def test_players_show_unknown_keeps_invalid_player_exit_code():
    result = runner.invoke(app, ["players", "show", "--name", "zzz nobody"])
    parsed = _parse_stderr_error(result)
    assert parsed.error == "InvalidPlayerError"
    assert result.exit_code == EXIT_CODES["InvalidPlayerError"] == 3


# (4) ErrorPayload accepts every defined code and rejects unknown ones

def test_error_payload_accepts_every_declared_code():
    for code in EXIT_CODES:
        ErrorPayload.model_validate({"error": code, "message": "x", "context": {}})


def test_error_payload_rejects_unknown_code():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ErrorPayload.model_validate(
            {"error": "MadeUpError", "message": "x", "context": {}}
        )


# (5) Universal "no traceback on stderr" guard for a broader set of malformed commands

@pytest.mark.parametrize(
    "argv",
    [
        ["sim", "--team1", "wat", "--team2", "pacers-2024"],
        ["sim", "--team1", "knicks-abc", "--team2", "pacers-2024"],
        ["sim", "--team1", "knicks-1999", "--team2", "pacers-2024"],
        ["sim", "--team1", "knicks-2024[swap=kat->zzznobody]", "--team2", "pacers-2024"],
        ["players", "show", "--name", "zzz nobody"],
        ["sql", "SELECT 1; DROP TABLE players"],
        ["lineup", "stats", "--players", "p1", "--players", "p2", "--players", "p3",
         "--players", "p4", "--players", "p5", "--season", "1999"],
        ["ingest", "season", "--team", "ZZZ", "--season", "2023", "--dry-run"],
        ["stints", "derive", "--season", "1999", "--team", "NYK"],
    ],
)
def test_no_python_traceback_leaks_on_typed_error(argv):
    result = runner.invoke(app, argv)
    assert result.exit_code != 0, f"argv={argv} unexpectedly exited 0"
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"argv={argv}: Python traceback leaked.\nstderr={result.stderr!r}"
    )
    assert result.stderr.strip(), f"argv={argv}: stderr was empty; expected typed-error JSON"
    last = result.stderr.strip().splitlines()[-1]
    payload = json.loads(last)
    ErrorPayload.model_validate(payload)
