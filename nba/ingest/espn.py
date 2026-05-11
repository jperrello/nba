from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
USER_AGENT = "Mozilla/5.0"
TIMEOUT = 30.0
THROTTLE_SEC = 1.0
MAX_RETRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}
THIN_PBP_THRESHOLD = 5
DEFAULT_CACHE_ROOT = Path("data/raw/espn")


class EspnFetchError(RuntimeError):
    pass


_last_request: float = 0.0


def _throttle() -> None:
    global _last_request
    wait = THROTTLE_SEC - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _cache_path(endpoint: str, key: str, root: Path) -> Path:
    return root / endpoint / f"{key}.json"


def _read_cache(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        log.warning("espn cache corrupt at %s; ignoring", p)
        return None


def _write_cache(p: Path, payload: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))


def _get(url: str, client: httpx.Client | None) -> dict:
    own = client is None
    c = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    try:
        for attempt in range(MAX_RETRIES):
            _throttle()
            try:
                r = c.get(url)
            except httpx.HTTPError as e:
                if attempt == MAX_RETRIES - 1:
                    raise EspnFetchError(f"transport error after {MAX_RETRIES} attempts at {url}: {e}") from e
                time.sleep(2**attempt)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code in RETRY_STATUS:
                if attempt == MAX_RETRIES - 1:
                    raise EspnFetchError(f"status {r.status_code} after {MAX_RETRIES} attempts at {url}")
                time.sleep(2**attempt)
                continue
            raise EspnFetchError(f"status {r.status_code} at {url}")
        raise EspnFetchError(f"retry budget exhausted at {url}")
    finally:
        if own:
            c.close()


def fetch_boxscore(
    game_id: str,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> dict:
    cache = _cache_path("summary", game_id, cache_root)
    hit = _read_cache(cache)
    if hit is not None:
        return hit
    data = _get(f"{SITE_BASE}/summary?event={game_id}", client)
    _write_cache(cache, data)
    return data


def fetch_pbp(
    game_id: str,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> list[dict]:
    summary = fetch_boxscore(game_id, client=client, cache_root=cache_root)
    plays = summary.get("plays") or []
    if len(plays) < THIN_PBP_THRESHOLD:
        log.warning("thin_pbp game_id=%s plays=%d (per-game hole, not raising)", game_id, len(plays))
    return plays


def fetch_schedule(
    team_id: str,
    season: int,
    *,
    client: httpx.Client | None = None,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> dict:
    key = f"{team_id}-{season}"
    cache = _cache_path("schedule", key, cache_root)
    hit = _read_cache(cache)
    if hit is not None:
        return hit
    data = _get(f"{SITE_BASE}/teams/{team_id}/schedule?season={season}&seasontype=2", client)
    _write_cache(cache, data)
    return data
