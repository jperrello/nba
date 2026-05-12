# web-core-lane (nba-mcv) red transcript

*2026-05-12T18:24:34Z by Showboat 0.6.1*
<!-- showboat-id: 12dded97-912d-4f3c-a951-925562ede440 -->

Spec: web/src/data/presets.ts — rename existing 'knicks-2024_vs_pacers-2024' default preset to 'knicks-2026_vs_celtics-2026' (Celtics as 2026 opponent is overseer-locked per web-core-lane's plan), flip DEFAULT_PRESET_ID, both teams season=2026.

```bash
python3 -m pytest tests/test_web_core_default_preset.py --no-header --tb=line -q 2>&1 | tail -5
```

```output
/Users/jperr/Documents/nba/tests/test_web_core_default_preset.py:31: AssertionError: Preset entry 'knicks-2026_vs_celtics-2026' must be a member of PRESETS
=========================== short test summary info ============================
FAILED tests/test_web_core_default_preset.py::test_default_preset_id_is_knicks_2026_vs_celtics_2026
FAILED tests/test_web_core_default_preset.py::test_default_preset_entry_exists_with_2026_seasons
2 failed in 0.01s
```
