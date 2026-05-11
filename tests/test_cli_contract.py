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
    PlayersCareerOutput,
    PlayersSearchOutput,
    PlayersShowOutput,
    SchemaOutput,
    SimOutput,
    SimilarOutput,
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


# nba players similar / search / career (brutus contract nba-v0n)
#
# These three subcommands feed the web GUI picker. The shape lives in
# nba/contracts.py — SimilarOutput, PlayersSearchOutput, PlayersCareerOutput —
# and the assertions below are intentionally black-box: invoke via CliRunner,
# parse stdout JSON, validate against the model, never reach behind the CLI.
# Stubbed data is fine; missing data is signaled via the documented warning
# codes (random_init_embeddings, no_matches, facts_table_empty).

KNOWN_PLAYER_ID = "stub-brunson"


def test_players_similar_returns_valid_shape():
    result = runner.invoke(
        app, ["players", "similar", "--id", KNOWN_PLAYER_ID, "--k", "5"]
    )
    payload = _stdout_json(result)
    parsed = SimilarOutput.model_validate(payload)
    assert len(parsed.data.neighbors) <= 5, (
        f"--k 5 caps neighbors at 5, got {len(parsed.data.neighbors)}"
    )
    distances = [n.distance for n in parsed.data.neighbors]
    assert distances == sorted(distances), (
        f"neighbors must be ascending by distance, got {distances}"
    )
    for n in parsed.data.neighbors:
        assert n.player_id
        assert n.name
        assert isinstance(n.season, int)
        assert isinstance(n.distance, float)


def test_players_similar_honors_k():
    result = runner.invoke(
        app, ["players", "similar", "--id", KNOWN_PLAYER_ID, "--k", "2"]
    )
    payload = _stdout_json(result)
    parsed = SimilarOutput.model_validate(payload)
    assert len(parsed.data.neighbors) <= 2, (
        f"--k 2 caps neighbors at 2, got {len(parsed.data.neighbors)}"
    )


def test_players_similar_random_init_warning_is_allowed():
    """Until real embeddings land, the implementer may stub neighbors and emit a
    random_init_embeddings warning. The web GUI keys off this code to render an
    empty-state hint in the picker. Tolerate either: a warning with this code OR
    no warning at all — but if the warning exists it must validate."""
    result = runner.invoke(
        app, ["players", "similar", "--id", KNOWN_PLAYER_ID, "--k", "5"]
    )
    payload = _stdout_json(result)
    parsed = SimilarOutput.model_validate(payload)
    rnd = [w for w in parsed.warnings if w.code == "random_init_embeddings"]
    for w in rnd:
        assert w.message


def test_players_similar_unknown_id_raises_invalid_player_error():
    result = runner.invoke(
        app, ["players", "similar", "--id", "zzz-not-a-player", "--k", "5"]
    )
    parsed = _stderr_error(result, exit_code=3, error_code="InvalidPlayerError")
    assert "zzz-not-a-player" in parsed.message.lower() or (
        "zzz-not-a-player" in str(parsed.context)
    )


def test_players_search_returns_valid_shape():
    result = runner.invoke(app, ["players", "search", "--q", "brunson"])
    payload = _stdout_json(result)
    parsed = PlayersSearchOutput.model_validate(payload)
    for r in parsed.data.results:
        assert r.player_id
        assert r.name
        assert isinstance(r.season, int)


def test_players_search_empty_query_returns_envelope_no_error():
    """Empty/no-match queries must NOT raise. An empty results list is the
    contract; a no_matches warning is optional. Web GUI renders the empty state
    on len(results) == 0."""
    result = runner.invoke(app, ["players", "search", "--q", "zzznoonezzz"])
    payload = _stdout_json(result)
    parsed = PlayersSearchOutput.model_validate(payload)
    if not parsed.data.results:
        nm = [w for w in parsed.warnings if w.code == "no_matches"]
        for w in nm:
            assert w.message


def test_players_career_returns_valid_shape():
    result = runner.invoke(app, ["players", "career", "--id", KNOWN_PLAYER_ID])
    payload = _stdout_json(result)
    parsed = PlayersCareerOutput.model_validate(payload)
    assert parsed.data.player_id
    assert parsed.data.name
    for s in parsed.data.seasons:
        assert isinstance(s.season, int)
        assert s.team
        for stat in (s.games, s.mpg, s.ppg, s.rpg, s.apg):
            assert stat is None or isinstance(stat, (int, float))


def test_players_career_facts_table_empty_warning_is_allowed():
    """Until facts is populated, the implementer may return seasons with null
    stats and emit a facts_table_empty warning. Validate the shape either way."""
    result = runner.invoke(app, ["players", "career", "--id", KNOWN_PLAYER_ID])
    payload = _stdout_json(result)
    parsed = PlayersCareerOutput.model_validate(payload)
    fte = [w for w in parsed.warnings if w.code == "facts_table_empty"]
    for w in fte:
        assert w.message


def test_players_career_unknown_id_raises_invalid_player_error():
    result = runner.invoke(app, ["players", "career", "--id", "zzz-not-a-player"])
    parsed = _stderr_error(result, exit_code=3, error_code="InvalidPlayerError")
    assert "zzz-not-a-player" in parsed.message.lower() or (
        "zzz-not-a-player" in str(parsed.context)
    )


# pydantic guards (these fail at import time if the model surface drifts)

def test_contract_models_importable():
    """Smoke: the pydantic shapes the rest of the suite asserts on are present."""
    for cls in (
        SchemaOutput,
        SqlOutput,
        LineupStatsOutput,
        SimOutput,
        PlayersShowOutput,
        SimilarOutput,
        PlayersSearchOutput,
        PlayersCareerOutput,
        ErrorPayload,
    ):
        assert hasattr(cls, "model_validate")


def test_error_payload_rejects_unknown_error_code():
    with pytest.raises(ValidationError):
        ErrorPayload.model_validate(
            {"error": "NotAThing", "message": "x", "context": {}}
        )
