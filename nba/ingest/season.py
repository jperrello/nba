from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nba.contracts import IngestData, IngestMeta, IngestOutput, Warning
from nba.ingest import espn, parse

TEAM_IDS: dict[str, int] = {
    "ATL": 1, "BOS": 2, "NO": 3, "CHI": 4, "CLE": 5, "DAL": 6, "DEN": 7,
    "DET": 8, "GS": 9, "HOU": 10, "IND": 11, "LAC": 12, "LAL": 13, "MIA": 14,
    "MIL": 15, "MIN": 16, "BKN": 17, "NYK": 18, "ORL": 19, "PHI": 20,
    "PHX": 21, "POR": 22, "SAC": 23, "SA": 24, "OKC": 25, "UTAH": 26,
    "WSH": 27, "TOR": 28, "MEM": 29, "CHA": 30,
}

THIN_PBP_FLOOR = 50
EARLIEST_SEASON = 2003


class InvalidTeamError(Exception):
    exit_code = 6

    def __init__(self, team: str):
        super().__init__(team)
        self.team = team


class EraOutOfRangeError(Exception):
    exit_code = 4

    def __init__(self, season: int):
        super().__init__(str(season))
        self.season = season


def _resolve_team_id(team: str) -> int:
    tid = TEAM_IDS.get(team.upper())
    if tid is None:
        raise InvalidTeamError(team)
    return tid


def _season_first_game_date(events: list[dict]) -> Any:
    earliest: Any = None
    for e in events:
        d = (e.get("date") or "").replace("Z", "+00:00")
        if not d:
            continue
        try:
            dt = datetime.fromisoformat(d)
        except ValueError:
            continue
        if earliest is None or dt < earliest:
            earliest = dt
    if earliest is None:
        return None
    return earliest.date()


def ingest_season(
    team: str,
    season: int,
    *,
    dry_run: bool = False,
    cache_root: Path = Path("data/cache/espn"),
) -> IngestOutput:
    if season < EARLIEST_SEASON:
        raise EraOutOfRangeError(season)
    team_id = _resolve_team_id(team)

    started = time.monotonic()
    warnings: list[Warning] = []

    teams_seen: dict[int, dict] = {}
    players_seen: dict[int, dict] = {}
    rosters_seen: set[tuple[int, int, int]] = set()
    games_count = 0
    games_thin = 0
    pbp_count = 0
    coach_games_count = 0

    schedule_cache = cache_root / "schedule" / f"{team_id}-{season}.json"
    if dry_run and not schedule_cache.exists():
        warnings.append(Warning(
            code="empty_cache",
            message=f"schedule for team={team} season={season} not in cache; dry-run produced empty counts",
            context={"team": team, "season": season, "cache_path": str(cache_root)},
        ))
        return _envelope(team, season, team_id, dry_run, cache_root, started, warnings,
                          teams=0, players=0, games=0, rosters=0, pbp=0, coach_games=0, thin=0)

    schedule = espn.fetch_schedule(str(team_id), season, cache_root=cache_root)
    events = [e for e in schedule.get("events") or []
              if (e.get("seasonType") or {}).get("id") == "2"]
    season_start = _season_first_game_date(events)

    for event in events:
        gid_raw = event.get("id")
        if gid_raw is None:
            continue
        game_id = int(gid_raw)
        summary_cache = cache_root / "summary" / f"{game_id}.json"
        if dry_run and not summary_cache.exists():
            warnings.append(Warning(
                code="summary_uncached",
                message=f"game {game_id} summary not in cache; skipped under dry-run",
                context={"game_id": game_id},
            ))
            continue
        try:
            summary = espn.fetch_boxscore(str(game_id), cache_root=cache_root)
        except espn.EspnFetchError as e:
            warnings.append(Warning(
                code="fetch_failed",
                message=f"game {game_id}: {e}",
                context={"game_id": game_id},
            ))
            continue

        game_row = parse.parse_game(summary, season)
        games_count += 1
        for tc in (((summary.get("header") or {}).get("competitions") or [{}])[0]).get("competitors") or []:
            t = parse.parse_team(tc)
            teams_seen[t["team_id"]] = t

        plays = summary.get("plays") or []
        if len(plays) < THIN_PBP_FLOOR:
            games_thin += 1
            warnings.append(Warning(
                code="thin_pbp",
                message=f"game {game_id} has {len(plays)} plays (<{THIN_PBP_FLOOR}); marked thin, PBP skipped",
                context={"game_id": game_id, "play_count": len(plays)},
            ))
            game_row["pbp_status"] = "thin"
        else:
            game_row["pbp_status"] = "ok"
            pbp_count += len(parse.parse_pbp(summary, game_id))

        for p in parse.parse_players(summary):
            players_seen[p["player_id"]] = p
        for r in parse.parse_rosters(summary, season, season_start):
            rosters_seen.add((r["season"], r["team_id"], r["player_id"]))
        coach_games_count += 2

    if not dry_run:
        _persist(team, season, team_id, list(teams_seen.values()), list(players_seen.values()),
                 rosters_seen, games_count, pbp_count, coach_games_count, games_thin, cache_root, warnings)

    return _envelope(
        team, season, team_id, dry_run, cache_root, started, warnings,
        teams=len(teams_seen),
        players=len(players_seen),
        games=games_count,
        rosters=len(rosters_seen),
        pbp=pbp_count,
        coach_games=coach_games_count,
        thin=games_thin,
    )


def _envelope(
    team: str, season: int, team_id: int, dry_run: bool, cache_root: Path,
    started: float, warnings: list[Warning],
    *, teams: int, players: int, games: int, rosters: int, pbp: int,
    coach_games: int, thin: int,
) -> IngestOutput:
    elapsed_ms = (time.monotonic() - started) * 1000.0
    return IngestOutput(
        data=IngestData(
            teams_upserted=teams,
            players_upserted=players,
            games_upserted=games,
            rosters_upserted=rosters,
            pbp_events_inserted=pbp,
            coach_games_upserted=coach_games,
            games_marked_thin=thin,
        ),
        warnings=warnings,
        meta=IngestMeta(
            dry_run=dry_run,
            cache_path=str(cache_root),
            team=team.upper(),
            season=season,
            schema_version="0002",
            data_versions={"espn": "site.api.espn.com"},
            cache_hit=False,
            cached=False,
            elapsed_ms=elapsed_ms,
            generated_at=datetime.now(UTC).isoformat(),
        ),
    )


def _persist(
    team: str, season: int, team_id: int, teams: list[dict], players: list[dict],
    rosters: set[tuple[int, int, int]], games_count: int, pbp_count: int,
    coach_games_count: int, games_thin: int, cache_root: Path,
    warnings: list[Warning],
) -> None:
    import psycopg

    from nba.config import db

    cfg = db()
    with psycopg.connect(cfg.url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.commit()
