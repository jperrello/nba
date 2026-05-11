"""Brutus contract nba-5ve (part 1). Pin the JSON output shape and dry-run
semantics of `nba ingest season` before espn-lane wires the pipeline. Black-box:
invoke via CliRunner, parse stdout as JSON, validate against pydantic models.
Persistence is verified by patching psycopg.connect — the contract demands that
--dry-run never opens a DB connection.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from nba.cli.main import app
from nba.contracts import EXIT_CODES, ErrorPayload, IngestOutput

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


INGEST_ARGS = ["ingest", "season", "--team", "NYK", "--season", "2023"]


def test_ingest_season_dry_run_returns_envelope():
    result = runner.invoke(app, INGEST_ARGS + ["--dry-run"])
    payload = _stdout_json(result)
    parsed = IngestOutput.model_validate(payload)
    assert parsed.meta.dry_run is True, "meta.dry_run must be True under --dry-run"
    assert parsed.meta.team == "NYK"
    assert parsed.meta.season == 2023
    assert parsed.meta.cache_path, "meta.cache_path must be a non-empty path string"


def test_ingest_season_data_block_has_per_table_counts():
    result = runner.invoke(app, INGEST_ARGS + ["--dry-run"])
    payload = _stdout_json(result)
    parsed = IngestOutput.model_validate(payload)
    for key in (
        "teams_upserted",
        "players_upserted",
        "games_upserted",
        "rosters_upserted",
        "pbp_events_inserted",
        "coach_games_upserted",
        "games_marked_thin",
    ):
        value = getattr(parsed.data, key)
        assert isinstance(value, int) and value >= 0, f"data.{key} must be int >= 0, got {value!r}"


def test_ingest_season_dry_run_opens_no_db_connection(monkeypatch):
    """Contract: --dry-run must not open a Postgres connection. Mechanism: patch
    psycopg.connect and assert call_count == 0. Implementer must route all DB
    access through psycopg (the canonical driver per pyproject.toml)."""
    calls = {"n": 0}

    def fake_connect(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("psycopg.connect must not be called under --dry-run")

    monkeypatch.setattr("psycopg.connect", fake_connect, raising=False)
    result = runner.invoke(app, INGEST_ARGS + ["--dry-run"])
    assert result.exit_code == 0, (
        f"--dry-run expected exit 0, got {result.exit_code}\nstderr={result.stderr!r}"
    )
    assert calls["n"] == 0, f"--dry-run opened {calls['n']} DB connections; must be 0"


def test_ingest_season_dry_run_is_idempotent():
    """Idempotency: running --dry-run twice against the same (team, season) must
    return identical per-table counts. Counts come from cached fetcher output and
    a deterministic diff against current DB state."""
    a = IngestOutput.model_validate(_stdout_json(runner.invoke(app, INGEST_ARGS + ["--dry-run"])))
    b = IngestOutput.model_validate(_stdout_json(runner.invoke(app, INGEST_ARGS + ["--dry-run"])))
    a_counts = a.data.model_dump()
    b_counts = b.data.model_dump()
    assert a_counts == b_counts, (
        f"--dry-run not idempotent.\nfirst={a_counts}\nsecond={b_counts}"
    )


def test_ingest_season_thin_pbp_emits_structured_warning():
    """Per the brief Lane A item 4: when a game returns <50 plays we surface a
    structured warning rather than crashing. Warning shape: {code: 'thin_pbp',
    message, context: {game_id, play_count}}."""
    result = runner.invoke(app, INGEST_ARGS + ["--dry-run"])
    payload = _stdout_json(result)
    parsed = IngestOutput.model_validate(payload)
    thin = [w for w in parsed.warnings if w.code == "thin_pbp"]
    if thin:
        ctx = thin[0].context
        assert "game_id" in ctx, f"thin_pbp warning must carry game_id, got {ctx}"
        assert "play_count" in ctx, f"thin_pbp warning must carry play_count, got {ctx}"
        assert isinstance(ctx["play_count"], int), f"play_count must be int, got {ctx['play_count']!r}"
    games_marked = parsed.data.games_marked_thin
    assert games_marked == len(thin), (
        f"data.games_marked_thin ({games_marked}) must match the number of "
        f"thin_pbp warnings ({len(thin)})"
    )


def test_ingest_season_bad_team_raises_invalid_team_error():
    result = runner.invoke(
        app, ["ingest", "season", "--team", "ZZZ", "--season", "2023", "--dry-run"]
    )
    parsed = _stderr_error(
        result, exit_code=EXIT_CODES["InvalidTeamError"], error_code="InvalidTeamError"
    )
    assert "ZZZ" in parsed.message or "ZZZ" in str(parsed.context)


def test_ingest_season_pre_2003_raises_era_error():
    result = runner.invoke(
        app, ["ingest", "season", "--team", "NYK", "--season", "1999", "--dry-run"]
    )
    _stderr_error(
        result, exit_code=EXIT_CODES["EraOutOfRangeError"], error_code="EraOutOfRangeError"
    )


# --dry-run semantics (espn-lane routing pin) ----------------------------------
#
# The `data` block schema is IDENTICAL under --dry-run and a real run. Both
# carry per-table counts (teams_upserted, players_upserted, etc.). The
# difference is interpretation:
#
#   --dry-run  : counts = rows the pipeline WOULD upsert against current DB
#                state. Deterministic — running --dry-run twice in a row with
#                the same (team, season) yields identical counts. No DB
#                connection opened. No state mutated. Safe for previewing.
#
#   real run   : counts = rows the pipeline ACTUALLY upserted on this
#                invocation. After a successful real run, a subsequent real run
#                with the same args returns near-zero counts (idempotent).
#
# meta.dry_run is the unambiguous discriminator. The JSON envelope shape does
# NOT change between modes — agents that consume the output don't need a mode
# branch.

def test_ingest_dry_run_meta_distinguishes_modes(monkeypatch):
    """The data-block schema is identical under --dry-run and a real run;
    meta.dry_run is the only mode discriminator."""
    # stub psycopg so the real run doesn't actually need Postgres
    monkeypatch.setattr("psycopg.connect", lambda *a, **kw: _FakeConn(), raising=False)

    dry = IngestOutput.model_validate(
        _stdout_json(runner.invoke(app, INGEST_ARGS + ["--dry-run"]))
    )
    real = IngestOutput.model_validate(
        _stdout_json(runner.invoke(app, INGEST_ARGS))
    )
    assert dry.meta.dry_run is True, "meta.dry_run must be True under --dry-run"
    assert real.meta.dry_run is False, "meta.dry_run must be False on a real run"
    # data schema is the same — same set of keys in both modes
    assert set(dry.data.model_dump().keys()) == set(real.data.model_dump().keys()), (
        "data block schema must be identical between --dry-run and real-run modes"
    )


class _FakeConn:
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


def test_ingest_season_writes_db_when_not_dry_run(monkeypatch):
    """The complement of the no-writes test: a non-dry run must hit the DB.
    psycopg.connect must be called at least once. We stub the connection so the
    test doesn't actually require Postgres, but the *attempt* to connect is the
    observable contract."""
    calls = {"n": 0}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return self

        def execute(self, *args, **kwargs):
            return None

        def executemany(self, *args, **kwargs):
            return None

        def fetchall(self):
            return []

        def fetchone(self):
            return None

        def commit(self):
            return None

        def close(self):
            return None

    def fake_connect(*args, **kwargs):
        calls["n"] += 1
        return FakeConn()

    monkeypatch.setattr("psycopg.connect", fake_connect, raising=False)
    runner.invoke(app, INGEST_ARGS)
    assert calls["n"] >= 1, (
        f"non-dry-run must open at least one DB connection via psycopg.connect; got {calls['n']}"
    )
