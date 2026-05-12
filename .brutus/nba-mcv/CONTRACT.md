# CONTRACT — nba-mcv (web-core-lane)

**Brutus contract.** Implementer = web-core-lane. No bypass.

## Spec restatement (falsifiable)

`web/src/data/presets.ts` exposes a 2026-current default preset:
- A `Preset` entry with `id: "knicks-2026_vs_celtics-2026"`, home `team:
  "knicks", season: 2026`, away `team: "celtics", season: 2026`.
- `DEFAULT_PRESET_ID` flipped from `"knicks-2024_vs_pacers-2024"` to
  `"knicks-2026_vs_celtics-2026"`.

This is the overseer-locked rename — Celtics as the 2026 opponent was
web-core-lane's pre-resolved choice (spec dictates season=2026, not
teams). The fact was locked into the `nba-mcv` bead notes before this
contract; the contract is the canonical version.

## Oracle definition

Two tests against `web/src/data/presets.ts`:

1. `DEFAULT_PRESET_ID` literal flipped — text assertion that the new
   constant value is present and the old (`knicks-2024_vs_pacers-2024`)
   is absent.
2. The preset entry with the locked id exists in `PRESETS` and contains
   `team: "knicks"` + `season: 2026` for one side and `team: "celtics"`
   + `season: 2026` for the other. Tested via regex matching the
   preset's brace-delimited block.

Implementer is free to either rename the existing
`knicks-2024_vs_pacers-2024` entry or insert a fresh entry and remove
the old one — the test only checks that the new entry is correctly
shaped and the default points at it.

## Test files

- `tests/test_web_core_default_preset.py` — 2 tests.

## Run command

```bash
python3 -m pytest tests/test_web_core_default_preset.py -v
```

Green oracle: 2 passed, 0 failed.

## Captured red output

```
tests/test_web_core_default_preset.py FF                                 [100%]
FAILED tests/test_web_core_default_preset.py::test_default_preset_id_is_knicks_2026_vs_celtics_2026
FAILED tests/test_web_core_default_preset.py::test_default_preset_entry_exists_with_2026_seasons
2 failed in 0.01s
```

"Behavior missing" — current source has the 2024 preset id and no 2026
celtics entry.

## Out of scope

- **Do not** touch `Home.tsx` — it already consumes `DEFAULT_PRESET_ID`
  via `import` (see `web/src/pages/Home.tsx:6,17,20`). Flipping the
  constant in `presets.ts` propagates automatically.
- **Do not** delete or reorder the cross-era historical presets
  (Warriors 2016, Lakers 2010, etc.) — those serve the MatchupsRail.
- **Do not** alter the `Preset` type definition or `presetById` helper.
- **Do not** add a `Players.tsx` change here — that's `nba-ngc` scope
  (web-pages-lane), and `Players.tsx` actually needs no change at all.
- **Do not** also touch `MatchupCard.tsx` — the hero card reads its
  season from the resolved preset, so flipping the default propagates.

## Hand-off

```
bash ~/.claude/skills/crew/crew.sh clear-and-talk web-core-lane "brutus contract at .brutus/nba-mcv/CONTRACT.md. Single-file change: web/src/data/presets.ts. (1) add or rename a preset entry to id='knicks-2026_vs_celtics-2026' with both teams at season 2026; (2) flip DEFAULT_PRESET_ID to that id. Green these tests: python3 -m pytest tests/test_web_core_default_preset.py -v."
```

## Implementer

`web-core-lane`. Route via athena.

## Transcript

`.brutus/nba-mcv/transcript.md`.
