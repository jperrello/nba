from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

PERIOD_TYPES = {
    "Start Period": "period_start",
    "End Period": "period_end",
    "End Game": "game_end",
}
TIMEOUT_TYPES = {"Full Timeout", "Short Timeout", "Official Time Out"}
VIOLATION_TYPES = {"Kicked Ball", "Defensive Goaltending", "Delay of Game"}
TECHNICAL_TYPES = {"Technical Foul", "Double Technical Foul", "Defensive 3-Seconds Technical"}
JUMPBALL_TYPES = {"Jump Ball", "Jumpball"}
TURNOVER_EXTRA = {"Traveling", "Offensive Charge", "No Turnover"}
_SHOT_TOKENS = ("Shot", "Layup", "Dunk", "Hook", "Finger Roll")


def _is_shot(t: str) -> bool:
    return any(tok in t for tok in _SHOT_TOKENS)


def normalize_event_type(play: dict) -> tuple[str, int]:
    t = (play.get("type") or {}).get("text") or ""
    scoring = bool(play.get("scoringPlay"))
    sv = int(play.get("scoreValue") or 0)
    pa = int(play.get("pointsAttempted") or 0)
    txt = play.get("text") or ""

    if t in PERIOD_TYPES:
        return PERIOD_TYPES[t], 0
    if t in JUMPBALL_TYPES:
        return "jumpball", 0
    if t == "Substitution":
        return "substitution", 0
    if t in TIMEOUT_TYPES:
        return "timeout", 0
    if t in TECHNICAL_TYPES:
        return "technical_foul", 0
    if t in VIOLATION_TYPES:
        return "violation", 0
    if t.startswith("Free Throw"):
        return ("ft_made" if scoring else "ft_missed"), sv
    if t == "Offensive Rebound":
        return "offensive_rebound", 0
    if t == "Defensive Rebound":
        return "defensive_rebound", 0
    if "Turnover" in t or t in TURNOVER_EXTRA:
        return "turnover", 0
    if t == "Shooting Foul":
        return "shooting_foul", 0
    if t == "Offensive Foul":
        return "offensive_foul", 0
    if t.startswith("Flagrant"):
        return "flagrant_foul", 0
    if "Foul" in t:
        return "personal_foul", 0
    if _is_shot(t):
        if scoring:
            return ("made_3pt" if sv == 3 else "made_2pt"), sv
        if pa == 3 or "Three Point" in txt or "3pt" in txt or "3 pt" in txt:
            return "missed_3pt", 0
        return "missed_2pt", 0
    return "unknown", 0


def _clock_to_seconds(clock: dict | None) -> int:
    if not clock:
        return 0
    dv = clock.get("displayValue") or "0:00"
    parts = dv.split(":")
    if len(parts) != 2:
        return 0
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return 0


def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def parse_team(competitor: dict) -> dict[str, Any]:
    team = competitor.get("team") or {}
    return {
        "team_id": int(team["id"]),
        "abbreviation": team.get("abbreviation") or team.get("shortDisplayName") or "",
        "full_name": team.get("displayName") or team.get("name") or "",
        "conference": None,
        "division": None,
    }


def parse_game(summary: dict, season: int) -> dict[str, Any]:
    hdr = summary.get("header") or {}
    comps = hdr.get("competitions") or [{}]
    comp = comps[0]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    tip_utc = _parse_iso_utc(comp.get("date"))
    game_date = tip_utc.astimezone(ET).date() if tip_utc else None

    status_name = ((comp.get("status") or {}).get("type") or {}).get("name") or ""
    status_map = {
        "STATUS_FINAL": "final",
        "STATUS_POSTPONED": "postponed",
        "STATUS_SCHEDULED": "scheduled",
        "STATUS_IN_PROGRESS": "in_progress",
        "STATUS_CANCELED": "canceled",
    }
    status = status_map.get(status_name, "final")

    gi = summary.get("gameInfo") or {}
    venue = (gi.get("venue") or {}).get("fullName")
    attendance = gi.get("attendance")

    return {
        "game_id": int(hdr["id"]),
        "season": season,
        "season_type": "regular",
        "game_date": game_date,
        "tipoff_at": tip_utc,
        "home_team_id": int(home.get("team", {}).get("id") or 0),
        "away_team_id": int(away.get("team", {}).get("id") or 0),
        "home_score": int(home["score"]) if home.get("score") not in (None, "") else None,
        "away_score": int(away["score"]) if away.get("score") not in (None, "") else None,
        "venue": venue,
        "attendance": attendance,
        "status": status,
    }


def parse_players(summary: dict) -> list[dict[str, Any]]:
    out = []
    for tp in (summary.get("boxscore") or {}).get("players") or []:
        for stat_block in tp.get("statistics") or []:
            for ath in stat_block.get("athletes") or []:
                a = ath.get("athlete") or {}
                aid = a.get("id")
                if aid is None:
                    continue
                out.append({
                    "player_id": int(aid),
                    "full_name": a.get("displayName") or "",
                    "first_name": a.get("firstName"),
                    "last_name": a.get("lastName"),
                    "position": (a.get("position") or {}).get("abbreviation"),
                    "espn_slug": a.get("shortName"),
                })
    return out


def parse_rosters(summary: dict, season: int, season_start_date) -> list[dict[str, Any]]:
    rows = []
    seen: set[tuple[int, int]] = set()
    for tp in (summary.get("boxscore") or {}).get("players") or []:
        team = tp.get("team") or {}
        tid = int(team.get("id") or 0)
        if tid == 0:
            continue
        for stat_block in tp.get("statistics") or []:
            for ath in stat_block.get("athletes") or []:
                a = ath.get("athlete") or {}
                aid = a.get("id")
                if aid is None:
                    continue
                pid = int(aid)
                if (tid, pid) in seen:
                    continue
                seen.add((tid, pid))
                rows.append({
                    "season": season,
                    "team_id": tid,
                    "player_id": pid,
                    "jersey": ath.get("jersey"),
                    "start_date": season_start_date,
                })
    return rows


def parse_pbp(summary: dict, game_id: int) -> list[dict[str, Any]]:
    rows = []
    for play in summary.get("plays") or []:
        seq_raw = play.get("sequenceNumber")
        if seq_raw is None:
            continue
        try:
            seq_no = int(seq_raw)
        except (TypeError, ValueError):
            continue
        event_type, points = normalize_event_type(play)
        participants = play.get("participants") or []
        player_id = None
        assist_player_id = None
        if len(participants) >= 1:
            pid = ((participants[0] or {}).get("athlete") or {}).get("id")
            if pid is not None:
                player_id = int(pid)
        if len(participants) >= 2:
            aid = ((participants[1] or {}).get("athlete") or {}).get("id")
            if aid is not None:
                assist_player_id = int(aid)
        team = (play.get("team") or {}).get("id")
        rows.append({
            "game_id": game_id,
            "sequence_no": seq_no,
            "quarter": int((play.get("period") or {}).get("number") or 0),
            "clock_seconds": _clock_to_seconds(play.get("clock")),
            "wall_clock_at": _parse_iso_utc(play.get("wallclock")),
            "team_id": int(team) if team else None,
            "player_id": player_id,
            "assist_player_id": assist_player_id,
            "event_type": event_type,
            "points_scored": points,
            "home_score": int(play.get("homeScore") or 0),
            "away_score": int(play.get("awayScore") or 0),
            "description": play.get("text"),
            "players_on_floor": [],
            "raw": play,
        })
    return rows
