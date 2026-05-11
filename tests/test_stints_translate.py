from __future__ import annotations

import hashlib

import pytest

from nba.stints.translate import (
    game_to_wall,
    lineup_hash,
    quarter_len,
    wall_to_game,
)


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
