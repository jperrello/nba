# CONTRACT — nba-ngc (web-pages-lane)

**Brutus contract.** Implementer = web-pages-lane. No bypass.

## Spec restatement (falsifiable)

`web/src/pages/Lineups.tsx` initializes the season state to the current
real-world season (2026, per `DAEMON_BRIEF.md`). Line 36 currently reads
`useState(2024)`; flip it to `useState(2026)`. Remove the stale literal.

**Players.tsx note:** `DAEMON_BRIEF.md` mentioned "any Players.tsx
default-season fallback" but recon confirms `Players.tsx` has no default-
season state (no `useState(2024)`, no `defaultSeason`, no `DEFAULT_SEASON`
constant). **Players.tsx requires no edits.** The contract only tests
`Lineups.tsx`.

## Oracle definition

Two text assertions against the source file:
1. `useState(2026)` is present in `Lineups.tsx`
2. `useState(2024)` is absent from `Lineups.tsx`

No vitest exists in the web setup (`web/package.json` has only tsc + vite).
The contract uses pytest text-grep assertions — right size for a 1-LOC
change.

## Test files

- `tests/test_web_pages_default_season.py` — 1 test with 2 assertions.

## Run command

```bash
python3 -m pytest tests/test_web_pages_default_season.py -v
```

Green oracle: 1 passed, 0 failed.

## Captured red output

```
tests/test_web_pages_default_season.py F                                 [100%]
FAILED tests/test_web_pages_default_season.py::test_lineups_default_season_is_2026
1 failed in 0.00s
```

`useState(2024)` still present at `Lineups.tsx:36`; `useState(2026)` absent.
"Behavior missing" red.

## Out of scope

- **Do not** touch `Players.tsx` — no default-season state to fix.
- **Do not** alter any other state initializers in `Lineups.tsx` (slots,
  result, err, loading, recent, namecache). Only the season default.
- **Do not** introduce a constant `DEFAULT_SEASON = 2026` — that's an
  unnecessary refactor; just inline the literal `2026`. (If you want to
  hoist it as a follow-up, file a separate bead.)
- **Do not** touch the `setSeason(prefill.season)` line — the prefill
  override stays as-is; only the initial state literal changes.

## Hand-off

```
bash ~/.claude/skills/crew/crew.sh clear-and-talk web-pages-lane "brutus contract at .brutus/nba-ngc/CONTRACT.md. One-line change: web/src/pages/Lineups.tsx line 36, useState(2024) → useState(2026). Players.tsx requires no edits (no default-season state exists there). Green this test: python3 -m pytest tests/test_web_pages_default_season.py -v."
```

## Implementer

`web-pages-lane`. Route via athena.

## Transcript

`.brutus/nba-ngc/transcript.md`.
