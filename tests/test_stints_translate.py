from __future__ import annotations

import hashlib

import pytest

from nba.stints.translate import (
    EVENT_TYPE_DROP,
    EVENT_TYPE_MAP,
    game_to_wall,
    lineup_hash,
    pbp_rows_to_events,
    quarter_len,
    wall_to_game,
)


def _row(**kw):
    base = {
        "sequence_no": 1,
        "quarter": 1,
        "clock_seconds": 720,
        "team_id": None,
        "player_id": None,
        "assist_player_id": None,
        "event_type": "jumpball",
        "points_scored": 0,
        "home_score": 0,
        "away_score": 0,
    }
    base.update(kw)
    return base


def test_quarter_len_regulation_and_ot():
    assert quarter_len(1) == 720
    assert quarter_len(4) == 720
    assert quarter_len(5) == 300
    assert quarter_len(7) == 300


@pytest.mark.parametrize(
    "quarter,clock,expected_wall",
    [
        (1, 720, 0.0),
        (1, 0, 720.0),
        (2, 720, 720.0),
        (2, 0, 1440.0),
        (4, 0, 2880.0),
        (5, 300, 2880.0),
        (5, 0, 3180.0),
        (6, 0, 3480.0),
    ],
)
def test_game_to_wall(quarter, clock, expected_wall):
    assert game_to_wall(quarter, clock) == expected_wall


@pytest.mark.parametrize(
    "quarter,wall,expected_clock",
    [
        (1, 0.0, 720),
        (1, 720.0, 0),
        (2, 720.0, 720),
        (2, 1440.0, 0),
        (4, 2880.0, 0),
        (5, 2880.0, 300),
        (5, 3180.0, 0),
    ],
)
def test_wall_to_game(quarter, wall, expected_clock):
    assert wall_to_game(quarter, wall) == expected_clock


def test_clock_roundtrip():
    for q in (1, 2, 3, 4, 5, 6):
        for c in (0, 1, 47, 300, 600, 720):
            if c > quarter_len(q):
                continue
            assert wall_to_game(q, game_to_wall(q, c)) == c


def test_lineup_hash_is_sha256_hex():
    h = lineup_hash([3, 1, 2, 4, 5])
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_lineup_hash_is_order_independent():
    a = lineup_hash([3, 1, 2, 4, 5])
    b = lineup_hash([5, 4, 3, 2, 1])
    c = lineup_hash([1, 2, 3, 4, 5])
    assert a == b == c


def test_lineup_hash_differs_for_different_players():
    a = lineup_hash([1, 2, 3, 4, 5])
    b = lineup_hash([1, 2, 3, 4, 6])
    assert a != b


def test_lineup_hash_matches_known_canonical():
    canon = "1,2,3,4,5"
    expected = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    assert lineup_hash([5, 4, 3, 2, 1]) == expected


def test_lineup_hash_accepts_string_ids():
    a = lineup_hash([1, 2, 3, 4, 5])
    b = lineup_hash(["1", "2", "3", "4", "5"])
    assert a == b


def test_event_type_map_covers_stint_relevant_canonical_set():
    must_map = {
        "made_2pt", "made_3pt", "missed_2pt", "missed_3pt",
        "ft_made", "ft_missed",
        "offensive_rebound", "defensive_rebound",
        "turnover",
        "shooting_foul",
        "substitution",
        "period_end", "game_end",
    }
    assert must_map.issubset(EVENT_TYPE_MAP.keys())


def test_drop_set_contains_irrelevant_types():
    assert "personal_foul" in EVENT_TYPE_DROP
    assert "jumpball" in EVENT_TYPE_DROP
    assert "timeout" in EVENT_TYPE_DROP
    assert "unknown" in EVENT_TYPE_DROP


def test_pbp_rows_drops_irrelevant_types():
    events = pbp_rows_to_events(
        [
            _row(event_type="jumpball"),
            _row(event_type="timeout"),
            _row(event_type="personal_foul"),
            _row(event_type="unknown"),
        ],
        home_team_id=18,
    )
    assert events == []


def test_pbp_rows_renames_to_deriver_vocab():
    rows = [
        _row(event_type="made_2pt", team_id=18, clock_seconds=700),
        _row(event_type="ft_missed", team_id=11, clock_seconds=600),
        _row(event_type="offensive_rebound", team_id=18, clock_seconds=590),
        _row(event_type="defensive_rebound", team_id=18, clock_seconds=580),
        _row(event_type="substitution", team_id=18, player_id=1, assist_player_id=2, clock_seconds=500),
    ]
    events = pbp_rows_to_events(rows, home_team_id=18)
    types = [e["type"] for e in events]
    assert types == ["made_2pt", "ft_miss", "rebound_off", "rebound_def", "sub"]


def test_pbp_rows_team_side_mapping():
    rows = [
        _row(event_type="made_2pt", team_id=18, clock_seconds=700),
        _row(event_type="made_2pt", team_id=11, clock_seconds=600),
        _row(event_type="period_end", team_id=None, clock_seconds=0),
    ]
    events = pbp_rows_to_events(rows, home_team_id=18)
    assert [e["team"] for e in events] == ["home", "away", None]


def test_pbp_rows_sub_carries_in_and_out_ids():
    rows = [_row(event_type="substitution", team_id=18, player_id=100, assist_player_id=200, clock_seconds=400)]
    events = pbp_rows_to_events(rows, home_team_id=18)
    assert events[0]["type"] == "sub"
    assert events[0]["player_in"] == 100
    assert events[0]["player_out"] == 200


def test_pbp_rows_wall_clock_is_ascending_within_quarter():
    rows = [
        _row(event_type="made_2pt", team_id=18, quarter=1, clock_seconds=720),
        _row(event_type="made_2pt", team_id=11, quarter=1, clock_seconds=600),
        _row(event_type="made_2pt", team_id=18, quarter=2, clock_seconds=720),
        _row(event_type="period_end", quarter=2, clock_seconds=0),
    ]
    events = pbp_rows_to_events(rows, home_team_id=18)
    assert events[0]["t"] == 0.0
    assert events[1]["t"] == 120.0
    assert events[2]["t"] == 720.0
    assert events[3]["t"] == 1440.0
