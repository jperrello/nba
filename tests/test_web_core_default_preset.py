from __future__ import annotations

import re
from pathlib import Path

PRESETS_TS = Path(__file__).parent.parent / "web" / "src" / "data" / "presets.ts"


def test_default_preset_id_is_knicks_2026_vs_celtics_2026():
    # web-core-lane (nba-mcv): DEFAULT_PRESET_ID flips to the 2026 matchup.
    # Celtics-as-opponent is overseer-locked (spec dictates season=2026, not
    # teams; web-core-lane already committed to Celtics in their plan).
    src = PRESETS_TS.read_text()
    assert 'export const DEFAULT_PRESET_ID = "knicks-2026_vs_celtics-2026"' in src, (
        "DEFAULT_PRESET_ID must be flipped to 'knicks-2026_vs_celtics-2026'"
    )
    assert 'export const DEFAULT_PRESET_ID = "knicks-2024_vs_pacers-2024"' not in src, (
        "Stale 2024 default must be removed"
    )


def test_default_preset_entry_exists_with_2026_seasons():
    # The preset matching the locked default id must be defined in PRESETS
    # with both home and away season fields == 2026.
    src = PRESETS_TS.read_text()
    block = re.search(
        r'\{\s*id:\s*"knicks-2026_vs_celtics-2026".*?^\s*\}',
        src,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert block, "Preset entry 'knicks-2026_vs_celtics-2026' must be a member of PRESETS"
    body = block.group(0)
    assert re.search(r'team:\s*"knicks".*?season:\s*2026', body, flags=re.DOTALL), (
        "Knicks side of the default preset must have season: 2026"
    )
    assert re.search(r'team:\s*"celtics".*?season:\s*2026', body, flags=re.DOTALL), (
        "Celtics side of the default preset must have season: 2026"
    )
