from __future__ import annotations

from pathlib import Path

LINEUPS_TSX = Path(__file__).parent.parent / "web" / "src" / "pages" / "Lineups.tsx"


def test_lineups_default_season_is_2026():
    # web-pages-lane (nba-ngc): the Lineups picker's default season must
    # reflect the current real-world season (2026, playoffs in progress
    # per DAEMON_BRIEF). Current code has `useState(2024)` at line 36.
    src = LINEUPS_TSX.read_text()
    assert "useState(2026)" in src, (
        "Lineups.tsx must initialize season state to 2026 "
        "(current real-world season per DAEMON_BRIEF)"
    )
    assert "useState(2024)" not in src, (
        "Stale `useState(2024)` must be removed — replace with useState(2026)"
    )
