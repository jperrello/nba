from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from nba.ingest import espn
from nba.ingest.espn import (
    EspnFetchError,
    fetch_boxscore,
    fetch_pbp,
    fetch_schedule,
)

REAL_FIXTURE = Path(__file__).parent.parent / "data" / "fixtures" / "espn" / "2023" / "401468777.json"


@pytest.fixture
def summary():
    return json.loads(REAL_FIXTURE.read_text())


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(espn, "THROTTLE_SEC", 0.0)
    monkeypatch.setattr(espn, "_last_request", 0.0)
    monkeypatch.setattr(espn.time, "sleep", lambda _s: None)


def _summary_url(gid):
    return f"{espn.SITE_BASE}/summary?event={gid}"


def _schedule_url(team_id, season):
    return f"{espn.SITE_BASE}/teams/{team_id}/schedule?season={season}&seasontype=2"


# (1) cache miss -> mock URL hit, file written

def test_cache_miss_writes_file(tmp_path, summary):
    gid = "401468777"
    with respx.mock(assert_all_called=True) as m:
        route = m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json=summary))
        out = fetch_boxscore(gid, cache_root=tmp_path)
    assert route.called
    cache_file = tmp_path / "summary" / f"{gid}.json"
    assert cache_file.exists()
    assert json.loads(cache_file.read_text()) == summary
    assert out["plays"][0]["sequenceNumber"] == summary["plays"][0]["sequenceNumber"]


# (2) cache hit -> no network call

def test_cache_hit_skips_network(tmp_path, summary):
    gid = "401468777"
    cache_file = tmp_path / "summary" / f"{gid}.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(json.dumps(summary))
    with respx.mock(assert_all_called=False) as m:
        route = m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json={"bad": "should not see this"}))
        out = fetch_boxscore(gid, cache_root=tmp_path)
    assert not route.called
    assert out == summary


# (3) 429 -> retry -> 200

def test_retries_on_429(tmp_path, summary):
    gid = "401468777"
    with respx.mock() as m:
        m.get(_summary_url(gid)).mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(429),
                httpx.Response(200, json=summary),
            ]
        )
        out = fetch_boxscore(gid, cache_root=tmp_path)
    assert out == summary
    assert (tmp_path / "summary" / f"{gid}.json").exists()


# (4) 500 -> retry -> 200

def test_retries_on_500(tmp_path, summary):
    gid = "401468777"
    with respx.mock() as m:
        m.get(_summary_url(gid)).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=summary)]
        )
        out = fetch_boxscore(gid, cache_root=tmp_path)
    assert out == summary


# (5) non-retriable 404 -> EspnFetchError

def test_404_raises_typed_error(tmp_path):
    gid = "000000000"
    with respx.mock() as m:
        m.get(_summary_url(gid)).mock(return_value=httpx.Response(404))
        with pytest.raises(EspnFetchError) as ei:
            fetch_boxscore(gid, cache_root=tmp_path)
    assert "404" in str(ei.value)
    assert not (tmp_path / "summary" / f"{gid}.json").exists()


# (6) exhausting retry budget -> EspnFetchError mentions status

def test_retry_exhaustion_raises(tmp_path):
    gid = "401468777"
    with respx.mock() as m:
        m.get(_summary_url(gid)).mock(return_value=httpx.Response(429))
        with pytest.raises(EspnFetchError) as ei:
            fetch_boxscore(gid, cache_root=tmp_path)
    assert "429" in str(ei.value)


# (7) fetch_pbp returns the plays list from the cached summary, no extra HTTP

def test_fetch_pbp_reuses_summary(tmp_path, summary):
    gid = "401468777"
    with respx.mock() as m:
        m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json=summary))
        plays = fetch_pbp(gid, cache_root=tmp_path)
    assert isinstance(plays, list)
    assert len(plays) == len(summary["plays"])

    with respx.mock(assert_all_called=False) as m:
        route = m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json={}))
        plays_again = fetch_pbp(gid, cache_root=tmp_path)
    assert not route.called
    assert plays_again == plays


# (8) thin PBP logs a warning but does not raise

def test_thin_pbp_warns_not_raises(tmp_path, caplog):
    gid = "thin-game"
    thin_summary = {"plays": [{"id": "x", "type": {"text": "Start Period"}}]}
    with respx.mock() as m:
        m.get(_summary_url(gid)).mock(return_value=httpx.Response(200, json=thin_summary))
        with caplog.at_level("WARNING", logger="nba.ingest.espn"):
            plays = fetch_pbp(gid, cache_root=tmp_path)
    assert plays == thin_summary["plays"]
    assert any("thin_pbp" in r.message for r in caplog.records)


# (9) fetch_schedule keys cache by team_id + season

def test_fetch_schedule_caches_per_team_season(tmp_path):
    payload = {"events": [{"id": "401468777"}], "requestedSeason": {"year": 2023}}
    with respx.mock() as m:
        m.get(_schedule_url("18", 2023)).mock(return_value=httpx.Response(200, json=payload))
        out = fetch_schedule("18", 2023, cache_root=tmp_path)
    assert out == payload
    assert (tmp_path / "schedule" / "18-2023.json").exists()

    with respx.mock(assert_all_called=False) as m:
        route = m.get(_schedule_url("18", 2023)).mock(return_value=httpx.Response(200, json={}))
        out_cached = fetch_schedule("18", 2023, cache_root=tmp_path)
    assert not route.called
    assert out_cached == payload
