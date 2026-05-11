from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from nba.ingest.parse import (
    normalize_event_type,
    parse_game,
    parse_pbp,
    parse_players,
    parse_rosters,
)

FIXTURES = Path(__file__).parent.parent / "data" / "fixtures" / "espn"

YEARS = [
    (2003, "221214018"),
    (2008, "280125018"),
    (2013, "400278363"),
    (2018, "400975369"),
    (2023, "401468777"),
]


@pytest.fixture(params=YEARS, ids=[str(y) for y, _ in YEARS])
def summary(request):
    y, gid = request.param
    return y, gid, json.loads((FIXTURES / str(y) / f"{gid}.json").read_text())


def test_parse_game_basics(summary):
    y, gid, s = summary
    row = parse_game(s, y)
    assert row["game_id"] == int(gid)
    assert row["season"] == y
    assert row["season_type"] == "regular"
    assert row["status"] in {"final", "postponed", "scheduled", "in_progress", "canceled"}
    assert row["home_team_id"] > 0 and row["away_team_id"] > 0
    assert row["home_team_id"] != row["away_team_id"]
    assert isinstance(row["game_date"], date)


def test_parse_players_yields_per_team_roster(summary):
    _y, _gid, s = summary
    rows = parse_players(s)
    assert len(rows) >= 20
    ids = {r["player_id"] for r in rows}
    assert len(ids) == len(rows)


def test_parse_rosters_one_row_per_team_player(summary):
    y, _gid, s = summary
    rows = parse_rosters(s, y, date(y - 1, 10, 1))
    keys = {(r["season"], r["team_id"], r["player_id"]) for r in rows}
    assert len(keys) == len(rows)
    assert all(r["season"] == y for r in rows)


def test_parse_pbp_event_types_are_canonical(summary):
    y, gid, s = summary
    rows = parse_pbp(s, int(gid))
    canonical = {
        "period_start", "period_end", "game_end", "jumpball", "substitution",
        "timeout", "violation", "technical_foul", "ft_made", "ft_missed",
        "offensive_rebound", "defensive_rebound", "turnover", "shooting_foul",
        "offensive_foul", "personal_foul", "flagrant_foul", "made_2pt", "made_3pt",
        "missed_2pt", "missed_3pt", "unknown",
    }
    seen = {r["event_type"] for r in rows}
    extras = seen - canonical
    assert not extras, f"non-canonical event types: {extras}"


def test_substitution_participants_are_in_then_out(summary):
    _y, gid, s = summary
    rows = parse_pbp(s, int(gid))
    subs = [r for r in rows if r["event_type"] == "substitution"]
    if not subs:
        pytest.skip("no subs in this fixture")
    for r in subs:
        assert r["player_id"] is not None, "sub must carry player_in (player_id)"
        assert r["assist_player_id"] is not None, "sub must carry player_out (assist_player_id)"


def test_normalize_event_type_distinguishes_shooting_from_personal_foul():
    assert normalize_event_type({"type": {"text": "Shooting Foul"}})[0] == "shooting_foul"
    assert normalize_event_type({"type": {"text": "Personal Foul"}})[0] == "personal_foul"
    assert normalize_event_type({"type": {"text": "Loose Ball Foul"}})[0] == "personal_foul"
    assert normalize_event_type({"type": {"text": "Offensive Foul"}})[0] == "offensive_foul"


def test_normalize_event_type_made_vs_missed_shot():
    made_3 = {"type": {"text": "Jump Shot"}, "scoringPlay": True, "scoreValue": 3, "pointsAttempted": 3}
    missed_3 = {"type": {"text": "Jump Shot"}, "scoringPlay": False, "scoreValue": 0, "pointsAttempted": 3}
    made_2 = {"type": {"text": "Layup Shot"}, "scoringPlay": True, "scoreValue": 2, "pointsAttempted": 2}
    missed_2 = {"type": {"text": "Layup Shot"}, "scoringPlay": False, "scoreValue": 0, "pointsAttempted": 2}
    assert normalize_event_type(made_3) == ("made_3pt", 3)
    assert normalize_event_type(missed_3) == ("missed_3pt", 0)
    assert normalize_event_type(made_2) == ("made_2pt", 2)
    assert normalize_event_type(missed_2) == ("missed_2pt", 0)


def test_normalize_event_type_2003_missed_3pt_text_fallback():
    """2003 fixtures have pointsAttempted=0 — falls back to text parse."""
    play = {
        "type": {"text": "Jump Shot"},
        "scoringPlay": False,
        "scoreValue": 0,
        "pointsAttempted": 0,
        "text": "Paul Pierce missed 25 ft Three Point Jumper.",
    }
    assert normalize_event_type(play) == ("missed_3pt", 0)


def test_normalize_event_type_free_throws():
    made_ft = {"type": {"text": "Free Throw - 1 of 2"}, "scoringPlay": True, "scoreValue": 1}
    missed_ft = {"type": {"text": "Free Throw - 1 of 1"}, "scoringPlay": False, "scoreValue": 0}
    assert normalize_event_type(made_ft) == ("ft_made", 1)
    assert normalize_event_type(missed_ft) == ("ft_missed", 0)
