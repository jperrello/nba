from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

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
CORE_BASE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"


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


def _fetch_team_coach(team_id: int, season: int, cache_root: Path) -> dict | None:
    cache = cache_root / "coach" / f"{team_id}-{season}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    list_url = f"{CORE_BASE}/seasons/{season}/teams/{team_id}/coaches"
    with httpx.Client(timeout=30.0, headers={"User-Agent": "Mozilla/5.0"}) as c:
        r = c.get(list_url)
        if r.status_code != 200:
            return None
        items = (r.json() or {}).get("items") or []
        if not items:
            return None
        ref = (items[0] or {}).get("$ref")
        if not ref:
            return None
        r2 = c.get(ref.replace("http://", "https://"))
        if r2.status_code != 200:
            return None
        detail = r2.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(detail))
    return detail


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
    rosters_seen: dict[tuple[int, int, int], dict] = {}
    game_rows: list[dict] = []
    pbp_rows: list[dict] = []
    games_thin = 0

    schedule_cache = cache_root / "schedule" / f"{team_id}-{season}.json"
    if dry_run and not schedule_cache.exists():
        warnings.append(Warning(
            code="empty_cache",
            message=f"schedule for team={team} season={season} not in cache; dry-run produced empty counts",
            context={"team": team, "season": season, "cache_path": str(cache_root)},
        ))
        return _envelope(team, season, dry_run, cache_root, started, warnings,
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
            pbp_rows.extend(parse.parse_pbp(summary, game_id))

        game_rows.append(game_row)
        for p in parse.parse_players(summary):
            players_seen[p["player_id"]] = p
        for r in parse.parse_rosters(summary, season, season_start):
            rosters_seen[(r["season"], r["team_id"], r["player_id"])] = r

    coach_row: dict | None = None
    if not dry_run:
        coach_detail = _fetch_team_coach(team_id, season, cache_root)
        if coach_detail:
            coach_row = {
                "coach_id": int(coach_detail["id"]),
                "full_name": f"{coach_detail.get('firstName','').strip()} {coach_detail.get('lastName','').strip()}".strip(),
                "first_name": coach_detail.get("firstName"),
                "last_name": coach_detail.get("lastName"),
                "espn_slug": coach_detail.get("shortName"),
            }

    coach_games_count = 0
    if not dry_run:
        coach_games_count = _persist(
            list(teams_seen.values()),
            list(players_seen.values()),
            game_rows,
            list(rosters_seen.values()),
            pbp_rows,
            coach_row,
            team_id,
        )
    else:
        coach_games_count = len(game_rows) if coach_row else 0

    return _envelope(
        team, season, dry_run, cache_root, started, warnings,
        teams=len(teams_seen),
        players=len(players_seen),
        games=len(game_rows),
        rosters=len(rosters_seen),
        pbp=len(pbp_rows),
        coach_games=coach_games_count,
        thin=games_thin,
    )


def _envelope(
    team: str, season: int, dry_run: bool, cache_root: Path,
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
    teams: list[dict],
    players: list[dict],
    games: list[dict],
    rosters: list[dict],
    pbp_events: list[dict],
    coach: dict | None,
    team_id_of_interest: int,
) -> int:
    import psycopg
    from psycopg.types.json import Jsonb

    from nba.config import db

    cfg = db()
    coach_games_written = 0
    with psycopg.connect(cfg.url) as conn:
        with conn.cursor() as cur:
            if teams:
                cur.executemany(
                    """
                    INSERT INTO teams (team_id, abbreviation, full_name, conference, division)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (team_id) DO NOTHING
                    """,
                    [(t["team_id"], t["abbreviation"], t["full_name"], t["conference"], t["division"]) for t in teams],
                )
            if players:
                cur.executemany(
                    """
                    INSERT INTO players (player_id, full_name, first_name, last_name, position, espn_slug)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_id) DO NOTHING
                    """,
                    [(p["player_id"], p["full_name"], p["first_name"], p["last_name"], p["position"], p["espn_slug"]) for p in players],
                )
            if games:
                cur.executemany(
                    """
                    INSERT INTO games
                        (game_id, season, season_type, game_date, tipoff_at, home_team_id, away_team_id,
                         home_score, away_score, venue, attendance, status, pbp_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id) DO UPDATE SET
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        status = EXCLUDED.status,
                        attendance = EXCLUDED.attendance,
                        pbp_status = EXCLUDED.pbp_status,
                        updated_at = now()
                    """,
                    [(g["game_id"], g["season"], g["season_type"], g["game_date"], g["tipoff_at"],
                      g["home_team_id"], g["away_team_id"], g["home_score"], g["away_score"],
                      g["venue"], g["attendance"], g["status"], g["pbp_status"]) for g in games],
                )
            if rosters:
                cur.executemany(
                    """
                    INSERT INTO rosters (season, team_id, player_id, jersey, start_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (season, team_id, player_id, start_date) DO NOTHING
                    """,
                    [(r["season"], r["team_id"], r["player_id"], r.get("jersey"), r["start_date"]) for r in rosters],
                )
            if coach:
                cur.execute(
                    """
                    INSERT INTO coaches (coach_id, full_name, first_name, last_name, espn_slug)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (coach_id) DO NOTHING
                    """,
                    (coach["coach_id"], coach["full_name"], coach["first_name"], coach["last_name"], coach["espn_slug"]),
                )
                coach_rows = [(coach["coach_id"], g["game_id"], team_id_of_interest, "head") for g in games]
                cur.executemany(
                    """
                    INSERT INTO coach_games (coach_id, game_id, team_id, role)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (game_id, team_id, role) DO NOTHING
                    """,
                    coach_rows,
                )
                coach_games_written = len(coach_rows)
            if pbp_events:
                empty = Jsonb([])
                valid_pids = {p["player_id"] for p in players}
                rows = [
                    (
                        e["game_id"], e["sequence_no"], e["quarter"], e["clock_seconds"],
                        e["wall_clock_at"], e["team_id"],
                        e["player_id"] if e["player_id"] in valid_pids else None,
                        e["assist_player_id"] if e["assist_player_id"] in valid_pids else None,
                        e["event_type"], e["points_scored"], e["home_score"], e["away_score"],
                        e["description"], empty, Jsonb(e["raw"]),
                    )
                    for e in pbp_events
                ]
                cur.executemany(
                    """
                    INSERT INTO pbp_events
                        (game_id, sequence_no, quarter, clock_seconds, wall_clock_at,
                         team_id, player_id, assist_player_id, event_type, points_scored,
                         home_score, away_score, description, players_on_floor, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id, sequence_no) DO NOTHING
                    """,
                    rows,
                )
        conn.commit()
    return coach_games_written
