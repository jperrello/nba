from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from nba.cli.main import app

runner = CliRunner()

TICKRESULT_KEYS = {"polled", "finals_detected", "ingested", "errors", "duration_ms"}


def _good_tick() -> dict[str, Any]:
    return {
        "polled": 1,
        "finals_detected": ["401705100"],
        "ingested": ["401705100"],
        "errors": [],
        "duration_ms": 47,
    }


def _bad_tick() -> dict[str, Any]:
    return {
        "polled": 1,
        "finals_detected": [],
        "ingested": [],
        "errors": ["scoreboard:status 503 at https://espn/..."],
        "duration_ms": 12,
    }


# ---------------------------------------------------------------------------
# (1) --help surface: `nba ingest` lists `live`; `nba train` lists
# `embeddings` and `predictor`. cli-lane's surface is registered on app.
# ---------------------------------------------------------------------------

def test_ingest_help_lists_live():
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0, result.output
    assert "live" in result.output, "`nba ingest live` must appear in `nba ingest --help`"


def test_train_help_lists_embeddings_and_predictor():
    result = runner.invoke(app, ["train", "--help"])
    assert result.exit_code == 0, result.output
    assert "embeddings" in result.output
    assert "predictor" in result.output


def test_app_help_lists_train():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "train" in result.output


# ---------------------------------------------------------------------------
# (2) `nba train embeddings` invokes nba.train.embeddings.run() and emits
# its 4-key envelope to stdout as JSON. ml-lane's run() shape is locked
# upstream — cli-lane just shells into it and JSON-dumps the return.
# ---------------------------------------------------------------------------

def test_train_embeddings_emits_run_envelope(monkeypatch):
    # Two-layer indirection: cli-lane implements run_train_embeddings (a
    # cli-side adapter that shells into nba.train.embeddings.run() and
    # returns its envelope). Tests monkeypatch the adapter so this lane
    # is independent of ml-lane's run() body.
    import nba.cli.live as live

    fake = {
        "version": "embeddings-v1-trained-deadbeef",
        "n_players": 463,
        "train_loss": 0.0421,
        "artifact_path": "/tmp/test-embeddings.pt",
    }
    monkeypatch.setattr(live, "run_train_embeddings", lambda: fake)

    result = runner.invoke(app, ["train", "embeddings"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed == fake
    assert set(parsed.keys()) == {"version", "n_players", "train_loss", "artifact_path"}


def test_train_predictor_emits_run_envelope(monkeypatch):
    import nba.cli.live as live

    fake = {
        "version": "predictor-v1-trained-cafebabe",
        "n_players": 14821,
        "train_loss": 0.183,
        "val_mse": 0.241,
        "artifact_path": "data/models/predictor_v17.pt",
    }
    monkeypatch.setattr(live, "run_train_predictor", lambda: fake)

    result = runner.invoke(app, ["train", "predictor"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed == fake
    assert set(parsed.keys()) == {
        "version", "n_players", "train_loss", "val_mse", "artifact_path"
    }


def test_train_embeddings_unmonkeypatched_raises(monkeypatch):
    # Sanity: until cli-lane wires run_train_embeddings to ml-lane's
    # nba.train.embeddings.run(), invocation must NOT silently succeed.
    result = runner.invoke(app, ["train", "embeddings"])
    assert result.exit_code != 0, (
        "with no monkeypatch, train embeddings must propagate the "
        "NotImplementedError from the cli-side adapter"
    )


def test_train_predictor_unmonkeypatched_raises(monkeypatch):
    result = runner.invoke(app, ["train", "predictor"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# (3) Structured log writer: every tick produces exactly one JSONL line at
# the configured log path. Each line is parseable JSON, has the envelope
# keys (type=tick, ts), and a superset of the 5 TickResult keys.
# ---------------------------------------------------------------------------

def test_daemon_writes_one_jsonl_line_per_tick(monkeypatch, tmp_path):
    import nba.cli.live as live

    monkeypatch.setattr(live, "_tick", lambda now: _good_tick())
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: None)
    monkeypatch.setattr(live, "_bd_create", lambda t, b: "nba-test")

    log_path = tmp_path / "ingest.log"
    result = runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "3", "--log-path", str(log_path)]
    )
    assert result.exit_code == 0, result.output
    assert log_path.exists(), "log file must be written"
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 3, f"expected 3 JSONL lines, got {len(lines)}"
    for raw in lines:
        rec = json.loads(raw)
        assert rec["type"] == "tick"
        assert "ts" in rec
        # superset: tick lines contain the 5 TickResult keys verbatim
        assert TICKRESULT_KEYS.issubset(rec.keys()), (
            f"tick line must contain all 5 TickResult keys; missing "
            f"{TICKRESULT_KEYS - set(rec.keys())}"
        )
        assert rec["polled"] == 1
        assert rec["finals_detected"] == ["401705100"]
        assert isinstance(rec["duration_ms"], int)


def test_daemon_log_line_is_pure_json(monkeypatch, tmp_path):
    # Cli-lane upstream note (1): tick().errors is pre-stringified and
    # JSON-safe. The full TickResult must drop into one json.dumps() call
    # with no serialization shim.
    import nba.cli.live as live

    monkeypatch.setattr(live, "_tick", lambda now: _good_tick())
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: None)
    monkeypatch.setattr(live, "_bd_create", lambda t, b: "nba-test")

    log_path = tmp_path / "ingest.log"
    runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "1", "--log-path", str(log_path)]
    )
    raw = log_path.read_text().strip()
    # If errors are unserializable, this fails. Round-trip must be lossless.
    rec = json.loads(raw)
    assert isinstance(rec, dict)
    assert json.dumps(rec)  # asserts re-serialization works without exception


# ---------------------------------------------------------------------------
# (4) Hard-fail surface: 10 consecutive failure ticks (errors non-empty)
# fires _notify exactly once AND _bd_create exactly once. Counter resets
# on any successful tick (errors empty).
# ---------------------------------------------------------------------------

def test_hard_fail_fires_notify_and_bd_after_10_consecutive(monkeypatch, tmp_path):
    import nba.cli.live as live

    notify_calls: list[str] = []
    bd_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(live, "_tick", lambda now: _bad_tick())
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: notify_calls.append(m))
    monkeypatch.setattr(
        live, "_bd_create", lambda t, b: (bd_calls.append((t, b)), "nba-hardfail")[1]
    )

    log_path = tmp_path / "ingest.log"
    result = runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "10", "--log-path", str(log_path)]
    )
    assert result.exit_code == 0, result.output
    assert len(notify_calls) == 1, (
        f"hard-fail must fire osascript notify exactly once at threshold; got {len(notify_calls)}"
    )
    assert len(bd_calls) == 1, (
        f"hard-fail must invoke bd create exactly once at threshold; got {len(bd_calls)}"
    )
    # Locked title — implementer must use this exact title so the issue
    # is findable across sessions.
    assert bd_calls[0][0] == live.BD_HARD_FAIL_TITLE


def test_hard_fail_does_not_fire_below_threshold(monkeypatch, tmp_path):
    import nba.cli.live as live

    notify_calls: list[str] = []
    bd_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(live, "_tick", lambda now: _bad_tick())
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: notify_calls.append(m))
    monkeypatch.setattr(live, "_bd_create", lambda t, b: (bd_calls.append((t, b)), "x")[1])

    log_path = tmp_path / "ingest.log"
    result = runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "9", "--log-path", str(log_path)]
    )
    assert result.exit_code == 0, result.output
    # 9 ticks must have been recorded (proves the daemon actually ran 9
    # iterations and the empty notify_calls/bd_calls aren't a false negative).
    assert log_path.exists()
    assert len(log_path.read_text().strip().splitlines()) == 9
    assert notify_calls == [], "must NOT fire below threshold (9 < 10)"
    assert bd_calls == [], "must NOT fire below threshold (9 < 10)"


def test_hard_fail_counter_resets_on_clean_tick(monkeypatch, tmp_path):
    import nba.cli.live as live

    # 9 bad ticks, 1 good tick, 9 bad ticks → counter resets at the good
    # tick; the second run of 9 bad ticks must NOT trigger.
    sequence = [_bad_tick()] * 9 + [_good_tick()] + [_bad_tick()] * 9
    it = iter(sequence)
    notify_calls: list[str] = []
    bd_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(live, "_tick", lambda now: next(it))
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: notify_calls.append(m))
    monkeypatch.setattr(live, "_bd_create", lambda t, b: (bd_calls.append((t, b)), "x")[1])

    log_path = tmp_path / "ingest.log"
    result = runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "19", "--log-path", str(log_path)]
    )
    assert result.exit_code == 0, result.output
    # All 19 ticks must have been recorded — proves the daemon ran the
    # full sequence (not bailed early), making the empty-call assertions
    # meaningful.
    assert log_path.exists()
    assert len(log_path.read_text().strip().splitlines()) == 19
    assert notify_calls == [], (
        "consecutive-failure counter must reset on any clean tick (errors empty)"
    )
    assert bd_calls == []


def test_hard_fail_on_tick_raising(monkeypatch, tmp_path):
    # Cli-lane upstream note (2): tick() can raise on unexpected exceptions.
    # Daemon must catch, log a hard_fail line with traceback, and count
    # toward the threshold (10 consecutive raises → notify + bd_create).
    import nba.cli.live as live

    def raising_tick(now):
        raise RuntimeError("simulated parse_exception")

    notify_calls: list[str] = []
    bd_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(live, "_tick", raising_tick)
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: notify_calls.append(m))
    monkeypatch.setattr(live, "_bd_create", lambda t, b: (bd_calls.append((t, b)), "x")[1])

    log_path = tmp_path / "ingest.log"
    result = runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "10", "--log-path", str(log_path)]
    )
    assert result.exit_code == 0, (
        f"daemon must NOT crash on tick exceptions; got exit {result.exit_code}"
    )
    # 10 consecutive raises = 10 consecutive failures → threshold reached.
    assert len(notify_calls) == 1
    assert len(bd_calls) == 1
    # Every line should be hard_fail (or whatever cli-lane's failure type
    # name is); critically each must contain a `traceback` field.
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 10
    for raw in lines:
        rec = json.loads(raw)
        assert rec["type"] in {"hard_fail", "ingest_fail"}, (
            f"raised-tick log lines must be type=hard_fail or ingest_fail; got {rec['type']}"
        )
        assert "traceback" in rec, "raised-tick log lines must include a traceback field"
        assert "RuntimeError" in rec["traceback"]


# ---------------------------------------------------------------------------
# (5) JSONL structural invariant: every line is parseable JSON. (Sanity
# check against future drift toward non-JSON formats.)
# ---------------------------------------------------------------------------

def test_every_log_line_parses_as_json(monkeypatch, tmp_path):
    import nba.cli.live as live

    sequence = [_good_tick(), _bad_tick(), _good_tick()]
    it = iter(sequence)
    monkeypatch.setattr(live, "_tick", lambda now: next(it))
    monkeypatch.setattr(live, "_sleeper", lambda s: None)
    monkeypatch.setattr(live, "_notify", lambda m: None)
    monkeypatch.setattr(live, "_bd_create", lambda t, b: "x")

    log_path = tmp_path / "ingest.log"
    runner.invoke(
        app, ["ingest", "live", "--stop-after-ticks", "3", "--log-path", str(log_path)]
    )
    for raw in log_path.read_text().strip().splitlines():
        rec = json.loads(raw)
        assert isinstance(rec, dict)
        assert "type" in rec
        assert "ts" in rec
