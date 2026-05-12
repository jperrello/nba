from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import httpx
import pytest
import respx

from nba.ingest import espn, live
from nba.ingest.live import (
    IDLE_INTERVAL_SEC,
    POLL_INTERVAL_SEC,
    fetch_scoreboard,
    ingest_if_final,
    is_final,
    loop,
    self_heal_walk,
    tick,
)

FIX = Path(__file__).parent.parent / ".brutus" / "nba-rmn" / "fixtures"


@pytest.fixture
def sb_final():
    return json.loads((FIX / "scoreboard_final.json").read_text())


@pytest.fixture
def sb_in_progress():
    return json.loads((FIX / "scoreboard_in_progress.json").read_text())


@pytest.fixture
def sb_pre():
    return json.loads((FIX / "scoreboard_pre.json").read_text())


@pytest.fixture
def sb_mixed():
    return json.loads((FIX / "scoreboard_mixed.json").read_text())


@pytest.fixture
def summary_payload():
    real = Path(__file__).parent.parent / "data" / "fixtures" / "espn" / "2023" / "401468777.json"
    return json.loads(real.read_text())


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(espn, "THROTTLE_SEC", 0.0)
    monkeypatch.setattr(espn, "_last_request", 0.0)
    monkeypatch.setattr(espn.time, "sleep", lambda _s: None)


def _scoreboard_url(d: _dt.date) -> str:
    return f"{espn.SITE_BASE}/scoreboard?dates={d.strftime('%Y%m%d')}"


def _summary_url(gid: str) -> str:
    return f"{espn.SITE_BASE}/summary?event={gid}"


# ---------------------------------------------------------------------------
# (1) fetch_scoreboard shape — date arg → ESPN ?dates=YYYYMMDD; returns
# dict with "events": list[dict] and each event exposes id + status.type.
# ---------------------------------------------------------------------------

def test_fetch_scoreboard_shape(tmp_path, sb_mixed):
    d = _dt.date(2026, 5, 12)
    with respx.mock(assert_all_called=True) as m:
        route = m.get(_scoreboard_url(d)).mock(return_value=httpx.Response(200, json=sb_mixed))
        out = fetch_scoreboard(d, cache_root=tmp_path)
    assert route.called, "fetch_scoreboard must hit ESPN scoreboard endpoint with ?dates=YYYYMMDD"
    assert isinstance(out, dict)
    assert "events" in out and isinstance(out["events"], list)
    assert len(out["events"]) == 3
    ev = out["events"][0]
    assert "id" in ev
    assert ev["status"]["type"]["state"] in {"post", "in", "pre"}
    assert isinstance(ev["status"]["type"]["completed"], bool)


# ---------------------------------------------------------------------------
# (2) is_final truth table — BOTH state == "post" AND completed == True
# required. This is the hard rule from the spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "state,completed,expected",
    [
        ("post", True, True),     # canonical STATUS_FINAL
        ("post", False, False),   # delayed-flip edge: state flipped but not committed
        ("in", False, False),     # live game
        ("pre", False, False),    # scheduled, not started
    ],
)
def test_is_final_requires_post_and_completed(state, completed, expected):
    event = {"id": "x", "status": {"type": {"state": state, "completed": completed}}}
    assert is_final(event) is expected


# ---------------------------------------------------------------------------
# (3) Cache write guard — ingest_if_final MUST NOT write a summary cache
# file for non-final events, even if a summary URL would respond 200.
# Spec hard rule: "If we ever fetch for a non-final game, do NOT cache it."
# ---------------------------------------------------------------------------

def test_write_cache_guard_blocks_non_final(tmp_path, sb_in_progress, summary_payload):
    event = sb_in_progress["events"][0]
    gid = event["id"]
    with respx.mock(assert_all_called=False) as m:
        # If implementer wrongly fetches summary, this route would let them
        # cache it. Test asserts no cache file appears regardless.
        m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json=summary_payload))
        result = ingest_if_final(event, cache_root=tmp_path)
    assert result is None, "non-final event must not yield a game_id"
    cache = tmp_path / "summary" / f"{gid}.json"
    assert not cache.exists(), "non-final game must NEVER produce a summary cache file"


def test_write_cache_guard_allows_final(tmp_path, sb_final, summary_payload):
    event = sb_final["events"][0]
    gid = event["id"]
    with respx.mock(assert_all_called=True) as m:
        m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json=summary_payload))
        result = ingest_if_final(event, cache_root=tmp_path)
    assert result == gid, "final event must yield its game_id"
    cache = tmp_path / "summary" / f"{gid}.json"
    assert cache.exists(), "final game must produce a summary cache file"
    assert json.loads(cache.read_text()) == summary_payload


# ---------------------------------------------------------------------------
# (4) self_heal_walk — returns chronologically ordered list of game_ids
# from the team's regular-season schedule that have no cached summary.
# Walks earliest-missing → today; today defaults to date.today() if omitted.
# ---------------------------------------------------------------------------

def test_self_heal_walk_returns_ordered_missing(tmp_path):
    # Synthetic schedule: 5 regular-season games for BOS (team_id=2), increasing dates.
    schedule = {
        "events": [
            {"id": "g1", "date": "2026-04-01T23:00Z", "seasonType": {"id": "2"}},
            {"id": "g2", "date": "2026-04-03T23:00Z", "seasonType": {"id": "2"}},
            {"id": "g3", "date": "2026-04-05T23:00Z", "seasonType": {"id": "2"}},
            {"id": "g4", "date": "2026-04-07T23:00Z", "seasonType": {"id": "2"}},
            {"id": "g5", "date": "2026-04-09T23:00Z", "seasonType": {"id": "2"}},
            # Preseason game should be excluded:
            {"id": "g0", "date": "2026-03-25T23:00Z", "seasonType": {"id": "1"}},
        ]
    }
    # Pre-populate g1 and g3 in the cache → expect [g2, g4, g5] missing.
    (tmp_path / "summary").mkdir(parents=True)
    (tmp_path / "summary" / "g1.json").write_text("{}")
    (tmp_path / "summary" / "g3.json").write_text("{}")

    today = _dt.date(2026, 4, 10)  # all five games are in the past
    with respx.mock() as m:
        m.get(f"{espn.SITE_BASE}/teams/2/schedule?season=2026&seasontype=2").mock(
            return_value=httpx.Response(200, json=schedule)
        )
        missing = self_heal_walk("BOS", 2026, today=today, cache_root=tmp_path)

    assert missing == ["g2", "g4", "g5"], (
        "must return missing game_ids in chronological order, regular-season only"
    )


def test_self_heal_walk_skips_future_games(tmp_path):
    # Game scheduled for tomorrow must NOT be in the self-heal walk —
    # the walker stops at today.
    schedule = {
        "events": [
            {"id": "past", "date": "2026-05-10T23:00Z", "seasonType": {"id": "2"}},
            {"id": "future", "date": "2026-05-15T23:00Z", "seasonType": {"id": "2"}},
        ]
    }
    today = _dt.date(2026, 5, 12)
    with respx.mock() as m:
        m.get(f"{espn.SITE_BASE}/teams/2/schedule?season=2026&seasontype=2").mock(
            return_value=httpx.Response(200, json=schedule)
        )
        missing = self_heal_walk("BOS", 2026, today=today, cache_root=tmp_path)
    assert "future" not in missing
    assert missing == ["past"]


# ---------------------------------------------------------------------------
# (5) tick + loop cadence — TickResult shape (5-key set equality) and
# loop honors 30s gap between ticks on a game-day, 3600s when idle.
# ---------------------------------------------------------------------------

EXPECTED_TICKRESULT_KEYS = {"polled", "finals_detected", "ingested", "errors", "duration_ms"}


def test_tick_returns_tickresult_shape(tmp_path, sb_mixed):
    d = _dt.date(2026, 5, 12)
    now = _dt.datetime(2026, 5, 12, 23, 45, tzinfo=_dt.UTC)
    with respx.mock() as m:
        m.get(_scoreboard_url(d)).mock(return_value=httpx.Response(200, json=sb_mixed))
        # Mock summary fetch for the lone final game in sb_mixed (gid 401705100).
        m.get(_summary_url("401705100")).mock(return_value=httpx.Response(200, json={"plays": []}))
        result = tick(now, cache_root=tmp_path)
    assert isinstance(result, dict)
    assert set(result.keys()) == EXPECTED_TICKRESULT_KEYS, (
        f"TickResult key set must be exactly {EXPECTED_TICKRESULT_KEYS}; "
        f"got {set(result.keys())}"
    )
    assert isinstance(result["polled"], int)
    assert isinstance(result["finals_detected"], list)
    assert isinstance(result["ingested"], list)
    assert isinstance(result["errors"], list)
    assert isinstance(result["duration_ms"], int)


def test_loop_polls_every_30s_in_active_window(tmp_path, sb_mixed):
    # In active window: a game in progress means we poll at POLL_INTERVAL_SEC.
    sleeps: list[float] = []
    times = iter([
        _dt.datetime(2026, 5, 12, 23, 45, 0, tzinfo=_dt.UTC),
        _dt.datetime(2026, 5, 12, 23, 45, 30, tzinfo=_dt.UTC),
        _dt.datetime(2026, 5, 12, 23, 46, 0, tzinfo=_dt.UTC),
    ])
    d = _dt.date(2026, 5, 12)
    with respx.mock(assert_all_called=False) as m:
        m.get(_scoreboard_url(d)).mock(return_value=httpx.Response(200, json=sb_mixed))
        m.get(_summary_url("401705100")).mock(return_value=httpx.Response(200, json={"plays": []}))
        loop(
            stop_after_ticks=3,
            now_provider=lambda: next(times),
            sleeper=lambda s: sleeps.append(s),
            cache_root=tmp_path,
        )
    # Two sleeps between three ticks; both must be POLL_INTERVAL_SEC (30s).
    assert sleeps == [float(POLL_INTERVAL_SEC), float(POLL_INTERVAL_SEC)], (
        f"active-window loop must sleep {POLL_INTERVAL_SEC}s between ticks; got {sleeps}"
    )


def test_loop_polls_hourly_when_idle(tmp_path):
    # No games on this date → idle cadence = IDLE_INTERVAL_SEC (3600s).
    empty_scoreboard = {"events": []}
    sleeps: list[float] = []
    times = iter([
        _dt.datetime(2026, 7, 4, 12, 0, 0, tzinfo=_dt.UTC),   # off-season
        _dt.datetime(2026, 7, 4, 13, 0, 0, tzinfo=_dt.UTC),
        _dt.datetime(2026, 7, 4, 14, 0, 0, tzinfo=_dt.UTC),
    ])
    d = _dt.date(2026, 7, 4)
    with respx.mock(assert_all_called=False) as m:
        m.get(_scoreboard_url(d)).mock(return_value=httpx.Response(200, json=empty_scoreboard))
        loop(
            stop_after_ticks=3,
            now_provider=lambda: next(times),
            sleeper=lambda s: sleeps.append(s),
            cache_root=tmp_path,
        )
    assert sleeps == [float(IDLE_INTERVAL_SEC), float(IDLE_INTERVAL_SEC)], (
        f"idle loop must sleep {IDLE_INTERVAL_SEC}s between ticks; got {sleeps}"
    )
