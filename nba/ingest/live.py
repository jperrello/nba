from __future__ import annotations

import datetime as _dt
import logging
import time as _time
from pathlib import Path
from typing import Any, Callable

import httpx

from nba.ingest import espn
from nba.ingest.espn import DEFAULT_CACHE_ROOT, SITE_BASE
from nba.ingest.season import TEAM_IDS

log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 30
IDLE_INTERVAL_SEC = 3600
CONSECUTIVE_FAIL_THRESHOLD = 10

TickResult = dict[str, Any]

_ACTIVE_STATES = {"pre", "in"}


def fetch_scoreboard(
    d: _dt.date,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> dict:
    url = f"{SITE_BASE}/scoreboard?dates={d.strftime('%Y%m%d')}"
    return espn._get(url, client)


def is_final(event: dict) -> bool:
    t = ((event or {}).get("status") or {}).get("type") or {}
    return t.get("state") == "post" and t.get("completed") is True


def ingest_if_final(
    event: dict,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> str | None:
    if not is_final(event):
        return None
    gid = event["id"]
    espn.fetch_boxscore(str(gid), client=client, cache_root=cache_root)
    return gid


def self_heal_walk(
    team: str,
    season: int,
    *,
    today: _dt.date | None = None,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> list[str]:
    if today is None:
        today = _dt.date.today()
    team_id = TEAM_IDS[team.upper()]
    schedule = espn.fetch_schedule(str(team_id), season, client=client, cache_root=cache_root)
    summary_dir = cache_root / "summary"
    out: list[tuple[str, str]] = []
    for ev in schedule.get("events") or []:
        if (ev.get("seasonType") or {}).get("id") != "2":
            continue
        date_str = ev.get("date") or ""
        if len(date_str) < 10:
            continue
        try:
            ev_date = _dt.date.fromisoformat(date_str[:10])
        except ValueError:
            continue
        if ev_date > today:
            continue
        gid = ev.get("id")
        if gid is None:
            continue
        gid = str(gid)
        if (summary_dir / f"{gid}.json").exists():
            continue
        out.append((date_str, gid))
    out.sort(key=lambda x: x[0])
    return [gid for _, gid in out]


def _tick(
    now: _dt.datetime,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> tuple[TickResult, dict]:
    started = _time.monotonic()
    finals: list[str] = []
    ingested: list[str] = []
    errors: list[str] = []
    scoreboard: dict
    try:
        scoreboard = fetch_scoreboard(now.date(), client=client, cache_root=cache_root)
    except Exception as e:
        errors.append(f"scoreboard:{e}")
        scoreboard = {"events": []}
    for ev in scoreboard.get("events") or []:
        if is_final(ev):
            finals.append(str(ev.get("id")))
        try:
            gid = ingest_if_final(ev, client=client, cache_root=cache_root)
            if gid is not None:
                ingested.append(str(gid))
        except Exception as e:
            errors.append(f"{ev.get('id')}:{e}")
    result: TickResult = {
        "polled": 1,
        "finals_detected": finals,
        "ingested": ingested,
        "errors": errors,
        "duration_ms": int((_time.monotonic() - started) * 1000),
    }
    return result, scoreboard


def tick(
    now: _dt.datetime,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> TickResult:
    result, _ = _tick(now, client=client, cache_root=cache_root)
    return result


def _is_active(scoreboard: dict) -> bool:
    for ev in scoreboard.get("events") or []:
        state = ((ev.get("status") or {}).get("type") or {}).get("state")
        if state in _ACTIVE_STATES:
            return True
    return False


def loop(
    *,
    stop_after_ticks: int | None = None,
    now_provider: Callable[[], _dt.datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> list[TickResult]:
    if now_provider is None:
        now_provider = lambda: _dt.datetime.now(_dt.UTC)
    if sleeper is None:
        sleeper = _time.sleep
    results: list[TickResult] = []
    i = 0
    while True:
        now = now_provider()
        result, scoreboard = _tick(now, client=client, cache_root=cache_root)
        results.append(result)
        i += 1
        if stop_after_ticks is not None and i >= stop_after_ticks:
            break
        interval = POLL_INTERVAL_SEC if _is_active(scoreboard) else IDLE_INTERVAL_SEC
        sleeper(float(interval))
    return results
