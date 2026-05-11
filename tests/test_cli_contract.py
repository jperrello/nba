"""Brutus contract nba-3fv. Pin the JSON output shape of the nba CLI before cli-lane
implements anything. Each test is black-box: invoke via CliRunner, parse stdout as
JSON, validate against the pydantic models in nba.contracts. Errors land on stderr
as a single JSON line with a typed error code and non-zero exit.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from nba.cli.main import app
from nba.contracts import (
    ErrorPayload,
    LineupStatsOutput,
    PlayersShowOutput,
    SchemaOutput,
    SimOutput,
    SqlOutput,
)

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


# nba schema

# pinned to docs/schema.md v1 (nba-byh closed at 9cc00b1)
EXPECTED_TABLES = {
    "players",
    "teams",
    "games",
    "coaches",
    "coach_games",
    "rosters",
    "pbp_events",
    "lineup_stints",
    "facts",
    "sim_cache",
    "embeddings_player",
}


def test_schema_returns_valid_shape():
    result = runner.invoke(app, ["schema"])
    payload = _stdout_json(result)
    parsed = SchemaOutput.model_validate(payload)
    assert parsed.data.pgvector_dims == 128, (
        f"pgvector_dims pinned to 128 by docs/schema.md, got {parsed.data.pgvector_dims}"
    )
    names = {t.name for t in parsed.data.tables}
    assert names == EXPECTED_TABLES, (
        f"nba schema must return exactly the tables in docs/schema.md v1.\n"
        f"missing: {EXPECTED_TABLES - names}\nextra: {names - EXPECTED_TABLES}"
    )
    for table in parsed.data.tables:
        assert table.columns, f"table {table.name} must declare columns"
        assert table.primary_key, f"table {table.name} must declare a primary key"
        for col in table.columns:
            assert col.name
            assert col.type
            assert isinstance(col.nullable, bool)


def test_schema_table_filter_restricts_output():
    result = runner.invoke(app, ["schema", "--table", "players"])
    payload = _stdout_json(result)
    parsed = SchemaOutput.model_validate(payload)
    names = {t.name for t in parsed.data.tables}
    assert names == {"players"}, (
        f"--table players must return only the players table, got {names}"
    )


# nba sql

def test_sql_select_returns_valid_shape():
    result = runner.invoke(app, ["sql", "SELECT 1"])
    payload = _stdout_json(result)
    parsed = SqlOutput.model_validate(payload)
    assert parsed.data.row_count == len(parsed.data.rows)
    assert isinstance(parsed.meta.cached, bool)
    assert isinstance(parsed.meta.elapsed_ms, (int, float))


def test_sql_multistatement_is_rejected():
    result = runner.invoke(app, ["sql", "SELECT 1; DROP TABLE players"])
    _stderr_error(result, exit_code=2, error_code="MultiStatementError")


# nba lineup stats

def test_lineup_stats_returns_valid_shape():
    result = runner.invoke(
        app,
        [
            "lineup",
            "stats",
            "--players",
            "brunson",
            "--players",
            "anunoby",
            "--players",
            "bridges",
            "--players",
            "hart",
            "--players",
            "towns",
            "--season",
            "2024",
        ],
    )
    payload = _stdout_json(result)
    parsed = LineupStatsOutput.model_validate(payload)
    assert parsed.data.stint_count >= 0
    assert parsed.data.possessions >= 0
    assert isinstance(parsed.data.net_rating, (int, float))


def test_lineup_stats_pre_2003_season_raises_era_error():
    result = runner.invoke(
        app,
        [
            "lineup",
            "stats",
            "--players",
            "p1",
            "--players",
            "p2",
            "--players",
            "p3",
            "--players",
            "p4",
            "--players",
            "p5",
            "--season",
            "1999",
        ],
    )
    _stderr_error(result, exit_code=4, error_code="EraOutOfRangeError")


# nba sim

SIM_ARGS = [
    "sim",
    "--team1",
    "knicks-2024[swap=kat->randle,divincenzo]",
    "--team2",
    "pacers-2024",
]


def test_sim_returns_valid_shape():
    result = runner.invoke(app, SIM_ARGS)
    payload = _stdout_json(result)
    parsed = SimOutput.model_validate(payload)
    assert parsed.data.score.home >= 0
    assert parsed.data.score.away >= 0
    assert 0.0 <= parsed.data.win_prob.value <= 1.0
    assert parsed.data.win_prob.ci >= 0.0
    assert len(parsed.data.matchups) == 5, "matchups must Hungarian-assign 5 pairings"
    for m in parsed.data.matchups:
        assert m.home_player
        assert m.away_player
    for edge in parsed.data.team_edges:
        assert edge.sign in {"+", "-"}
        assert edge.magnitude >= 0.0
    assert parsed.meta.cached in (True, False)
    assert parsed.meta.model_versions, "meta.model_versions must be populated"


def test_sim_with_scouting_includes_take():
    result = runner.invoke(app, SIM_ARGS)
    payload = _stdout_json(result)
    parsed = SimOutput.model_validate(payload)
    assert isinstance(parsed.data.scouting_take, str)
    assert parsed.data.scouting_take.strip(), "scouting_take must be non-empty"


def test_sim_no_scouting_omits_take_and_skips_lm(monkeypatch):
    """Contract: --no-scouting must (a) leave scouting_take null and (b) not invoke
    the scouting LM. Mechanism: implementer must expose the LM entrypoint as
    `nba.cli.main.generate_scouting_take` so it can be patched for verification."""
    calls = {"n": 0}

    def fake(*args, **kwargs):
        calls["n"] += 1
        return "should-not-be-called"

    monkeypatch.setattr(
        "nba.cli.main.generate_scouting_take", fake, raising=False
    )
    result = runner.invoke(app, SIM_ARGS + ["--no-scouting"])
    payload = _stdout_json(result)
    parsed = SimOutput.model_validate(payload)
    assert parsed.data.scouting_take is None, (
        f"--no-scouting must null scouting_take, got {parsed.data.scouting_take!r}"
    )
    assert calls["n"] == 0, (
        f"--no-scouting must not call the LM, but generate_scouting_take ran {calls['n']}x"
    )


# nba players show

def test_players_show_returns_valid_shape():
    result = runner.invoke(app, ["players", "show", "--name", "jalen brunson"])
    payload = _stdout_json(result)
    parsed = PlayersShowOutput.model_validate(payload)
    assert parsed.data.player_id
    assert parsed.data.name.lower().startswith("jalen")
    assert parsed.data.seasons, "player must have at least one season"


def test_players_show_unknown_player_raises_invalid_player_error():
    result = runner.invoke(app, ["players", "show", "--name", "zzz nobody"])
    parsed = _stderr_error(result, exit_code=3, error_code="InvalidPlayerError")
    assert "zzz nobody" in parsed.message.lower() or "zzz nobody" in str(parsed.context)


# warnings

def test_sparse_data_emits_structured_warning():
    """Sparse lineup data must surface as a structured warning with code=sparse_data
    and a numeric n_effective in context. Forced here by a contrived 5-man lineup
    that's guaranteed to be thin (random-noise player ids)."""
    result = runner.invoke(
        app,
        [
            "lineup",
            "stats",
            "--players",
            "obscure1",
            "--players",
            "obscure2",
            "--players",
            "obscure3",
            "--players",
            "obscure4",
            "--players",
            "obscure5",
            "--season",
            "2024",
        ],
    )
    payload = _stdout_json(result)
    parsed = LineupStatsOutput.model_validate(payload)
    sparse = [w for w in parsed.warnings if w.code == "sparse_data"]
    assert sparse, f"expected a sparse_data warning, got warnings={parsed.warnings}"
    assert "n_effective" in sparse[0].context
    assert isinstance(sparse[0].context["n_effective"], (int, float))


# pydantic guards (these fail at import time if the model surface drifts)

def test_contract_models_importable():
    """Smoke: the pydantic shapes the rest of the suite asserts on are present."""
    for cls in (
        SchemaOutput,
        SqlOutput,
        LineupStatsOutput,
        SimOutput,
        PlayersShowOutput,
        ErrorPayload,
    ):
        assert hasattr(cls, "model_validate")


def test_error_payload_rejects_unknown_error_code():
    with pytest.raises(ValidationError):
        ErrorPayload.model_validate(
            {"error": "NotAThing", "message": "x", "context": {}}
        )
