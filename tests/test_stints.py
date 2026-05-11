"""Brutus contract nba-6gz. Pin the correctness of PBP -> stint derivation against
the hand-crafted fixture in tests/fixtures/pbp_minigame.json. Each test asserts on
the public surface `nba.stints.derive.derive_stints(pbp_events, starters_home,
starters_away)`. Tests are black-box and assume each returned stint exposes
`period`, `wall_start`, `wall_end`, `home`, `away`, `pts_home`, `pts_away`,
`possessions_home`, `possessions_away`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nba.stints.derive import derive_stints

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pbp_minigame.json"


@pytest.fixture(scope="module")
def fixture():
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture(scope="module")
def derived(fixture):
    return derive_stints(
        fixture["events"],
        starters_home=fixture["starters_home"],
        starters_away=fixture["starters_away"],
    )


def _attr(stint, name):
    if hasattr(stint, name):
        return getattr(stint, name)
    return stint[name]


def _lineup(stint, side):
    raw = _attr(stint, side)
    return tuple(sorted(raw))


# (1) stint count == subs + quarter boundaries + 1

def test_stint_count_matches_subs_plus_quarter_boundaries(fixture, derived):
    n_subs = sum(1 for e in fixture["events"] if e["type"] == "sub")
    n_period_boundaries = sum(1 for e in fixture["events"] if e["type"] == "period_end")
    expected = n_subs + n_period_boundaries + 1
    assert len(derived) == expected, (
        f"expected {expected} stints (subs={n_subs} + period_ends={n_period_boundaries} + initial), "
        f"got {len(derived)}"
    )
    assert len(derived) == len(fixture["_expected_stints"])


# (2) every stint has 5 home + 5 away player ids

def test_each_stint_has_five_on_five(derived):
    for i, s in enumerate(derived):
        assert len(set(_attr(s, "home"))) == 5, (
            f"stint {i} home lineup must be 5 unique players, got {_attr(s, 'home')}"
        )
        assert len(set(_attr(s, "away"))) == 5, (
            f"stint {i} away lineup must be 5 unique players, got {_attr(s, 'away')}"
        )


# (3) boundaries at sub timestamps + period ends

def test_boundaries_align_with_subs_and_period_ends(fixture, derived):
    expected_boundaries = sorted(
        e["t"] for e in fixture["events"] if e["type"] in {"sub", "period_end"}
    )
    actual_boundaries = sorted(_attr(s, "wall_end") for s in derived[:-1])
    assert actual_boundaries == expected_boundaries, (
        f"stint boundaries {actual_boundaries} do not match sub+period_end times {expected_boundaries}"
    )


# (4) scoring is attributed to the active stint

def test_scoring_attributed_to_active_stint(fixture, derived):
    for expected, actual in zip(fixture["_expected_stints"], derived, strict=True):
        assert _attr(actual, "pts_home") == expected["pts_home"], (
            f"stint {expected['idx']} pts_home: expected {expected['pts_home']}, "
            f"got {_attr(actual, 'pts_home')}"
        )
        assert _attr(actual, "pts_away") == expected["pts_away"], (
            f"stint {expected['idx']} pts_away: expected {expected['pts_away']}, "
            f"got {_attr(actual, 'pts_away')}"
        )


# (5) Oliver possession estimate within +-1

def test_possessions_match_oliver_formula(fixture, derived):
    for expected, actual in zip(fixture["_expected_stints"], derived, strict=True):
        for side in ("home", "away"):
            key = f"possessions_{side}"
            got = _attr(actual, key)
            want = expected[key]
            assert abs(got - want) <= 1, (
                f"stint {expected['idx']} {key}: expected ~{want} (+-1), got {got}"
            )


# (6) sum of stint pts_home equals box pts_home (and same for away)

def test_stint_points_sum_to_box_score(fixture, derived):
    sum_home = sum(_attr(s, "pts_home") for s in derived)
    sum_away = sum(_attr(s, "pts_away") for s in derived)
    assert sum_home == fixture["final_box"]["pts_home"], (
        f"sum stint pts_home = {sum_home}, box pts_home = {fixture['final_box']['pts_home']}"
    )
    assert sum_away == fixture["final_box"]["pts_away"], (
        f"sum stint pts_away = {sum_away}, box pts_away = {fixture['final_box']['pts_away']}"
    )


# (7) no stint crosses a quarter boundary

def test_no_stint_crosses_period_boundary(derived):
    for i, s in enumerate(derived):
        period = _attr(s, "period")
        assert isinstance(period, int), f"stint {i} period must be int, got {period!r}"
    for i, s in enumerate(derived[:-1]):
        nxt = derived[i + 1]
        if _attr(s, "period") != _attr(nxt, "period"):
            assert _attr(s, "wall_end") == _attr(nxt, "wall_start"), (
                f"stint {i} period boundary not aligned with stint {i+1}"
            )


# (8) sub mid-possession: stint ends at sub, but the in-flight possession's points
# accrue to the stint at possession START. Concretely: shooting foul at t=29
# (stint 0) -> sub at t=30 (boundary) -> FTs at t=31-32 land in stint 0, NOT stint 1.

def test_sub_mid_possession_attributes_to_stint_at_possession_start(derived, fixture):
    stint0_expected = fixture["_expected_stints"][0]
    stint1_expected = fixture["_expected_stints"][1]

    # boundary still falls at the sub timestamp
    assert _attr(derived[0], "wall_end") == 30, (
        f"sub at t=30 must end stint 0, got wall_end={_attr(derived[0], 'wall_end')}"
    )
    assert _attr(derived[1], "wall_start") == 30

    # the two FTs at t=31-32 sit in stint 1's wall-clock window but their points
    # accrue to stint 0 (possession started in stint 0)
    assert _attr(derived[0], "pts_away") == stint0_expected["pts_away"] == 4, (
        f"stint 0 must absorb the post-sub FT points; expected pts_away=4, "
        f"got {_attr(derived[0], 'pts_away')}"
    )
    assert _attr(derived[1], "pts_away") == stint1_expected["pts_away"] == 5, (
        f"stint 1 must NOT count the carry-over FT points; expected pts_away=5, "
        f"got {_attr(derived[1], 'pts_away')}"
    )


# expected lineup composition per stint

def test_lineups_match_expected(fixture, derived):
    for expected, actual in zip(fixture["_expected_stints"], derived, strict=True):
        assert _lineup(actual, "home") == tuple(sorted(expected["home"])), (
            f"stint {expected['idx']} home lineup mismatch: "
            f"expected {sorted(expected['home'])}, got {sorted(_attr(actual, 'home'))}"
        )
        assert _lineup(actual, "away") == tuple(sorted(expected["away"])), (
            f"stint {expected['idx']} away lineup mismatch: "
            f"expected {sorted(expected['away'])}, got {sorted(_attr(actual, 'away'))}"
        )
