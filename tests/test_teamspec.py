from __future__ import annotations

import pytest

from nba.cli.teamspec import parse, render


def test_plain_team_season():
    assert parse("pacers-2024") == {"team": "pacers", "season": 2024, "swaps": []}


def test_single_swap_single_replacement():
    spec = parse("knicks-2024[swap=kat->randle]")
    assert spec == {
        "team": "knicks",
        "season": 2024,
        "swaps": [{"out": "kat", "in": ["randle"]}],
    }


def test_single_swap_multiple_replacements():
    spec = parse("knicks-2024[swap=kat->randle,divincenzo]")
    assert spec == {
        "team": "knicks",
        "season": 2024,
        "swaps": [{"out": "kat", "in": ["randle", "divincenzo"]}],
    }


def test_multiple_swap_clauses_separated_by_semicolon():
    spec = parse("knicks-2024[swap=kat->randle;hart->divincenzo]")
    assert spec["swaps"] == [
        {"out": "kat", "in": ["randle"]},
        {"out": "hart", "in": ["divincenzo"]},
    ]


def test_round_trip():
    original = "knicks-2024[swap=kat->randle,divincenzo]"
    assert render(parse(original)) == original


def test_round_trip_no_swap():
    assert render(parse("pacers-2024")) == "pacers-2024"


def test_whitespace_in_player_names_is_stripped():
    spec = parse("knicks-2024[swap=kat -> randle , divincenzo]")
    assert spec["swaps"][0]["out"] == "kat"
    assert spec["swaps"][0]["in"] == ["randle", "divincenzo"]


def test_unterminated_swap_block_raises():
    with pytest.raises(ValueError, match="unterminated"):
        parse("knicks-2024[swap=kat->randle")


def test_missing_arrow_in_swap_raises():
    with pytest.raises(ValueError, match="missing '->'"):
        parse("knicks-2024[swap=katrandle]")


def test_non_integer_season_raises():
    with pytest.raises(ValueError, match="season"):
        parse("knicks-XXII")


def test_multi_hyphen_team_name_keeps_team():
    spec = parse("portland-trail-blazers-2024")
    assert spec == {"team": "portland-trail-blazers", "season": 2024, "swaps": []}
