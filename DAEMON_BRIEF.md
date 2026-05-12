# Live Ingest Daemon — Run Brief (overseer)

User-out-of-loop autonomous build. Spec verbatim is in the user message that
started this run; this file is the operational distillation lanes read before
working. **Don't relitigate the spec — execute it.** All design questions
already resolved.

Current date: **2026-05-12** (playoffs in progress, current season = 2026).

## What we're building

1. `nba ingest live` — long-running data daemon. Scoreboard poll → STATUS_FINAL
   detect → summary fetch → reuse existing ingest write path. Self-heals on
   every launch (walk earliest-missing-game → today, then enter live mode).
2. `nba train embeddings` and `nba train predictor` — manual CLI subcommands
   that retrain on current DB state and bump version fields.
3. macOS launchd lifecycle — `make install-daemon` / `make uninstall-daemon`,
   `com.nba.ingest.live.plist`, `RunAtLoad=true`, `KeepAlive=true`.
4. Web UI default season picker → current real-world season (2026), playoffs
   included. ~20 LOC across `web/src/pages/Lineups.tsx`,
   `web/src/pages/Players.tsx`, and the hero matchup card preset.

## Hard rules (from spec — do not change)

- Poll cadence: **30s** on scoreboard endpoint during game-scheduled days.
- Game-scheduled days only: once-per-hour scoreboard probe, then 30s polling
  from 1h-before-tipoff until 30min-after-last-final, else idle.
- STATUS_FINAL detection: `events[].status.type.state == "post"` **AND**
  `status.type.completed == true`. Both required.
- Cache write guard: `data/raw/espn/summary/<game_id>.json` is **only** written
  after STATUS_FINAL. If we ever fetch for a non-final game, do NOT cache it.
- Self-heal on every daemon start. Walks schedule from earliest-missing-game
  to today, fills gaps, then enters live mode.
- Idempotency: re-ingesting same game is no-op (existing `ON CONFLICT DO
  NOTHING` covers it — do not invent new dedupe).
- Hard-failure surface: 10+ consecutive ESPN 5xx/429s, daemon crash, or parse
  exception → macOS `osascript` notification + `bd create` issue. Soft
  transients stay silent (existing backoff handles them).
- Structured log at `~/.nba/ingest.log` — append-only JSON lines every poll
  cycle + every ingest result + every failure with traceback.
- CLI conventions: JSON by default; `--human` flag pretty-prints to stderr.

## Coordination substrate

- **bd issues are canonical.** Lane-specific issue IDs are listed below; every
  worker appends notes to its bead.
- **This file** is the shared spec digest — read it first, don't paste the
  whole user spec into messages.
- **Router** = athena. All inter-lane handoffs go through her.
- **Test-first** = brutus. Every implementer lane gets a CONTRACT.md from
  brutus before writing code.

## Lane map

| Lane            | Beads issue | Scope                                                                                         |
| --------------- | ----------- | --------------------------------------------------------------------------------------------- |
| espn-lane       | nba-rmn     | Ingest daemon innards: scoreboard poller, STATUS_FINAL state machine, status-aware cache guard, self-heal walker. Inside `nba/ingest/`. |
| cli-lane        | nba-2fz     | Typer surface: `nba ingest live` (with `--human`), `nba train embeddings`, `nba train predictor`. Structured `~/.nba/ingest.log` JSON-line writer. macOS osascript notify + `bd create` on hard fail. |
| ml-lane         | nba-1ab     | Underlying training callables `nba.train.embeddings.run()` and `nba.train.predictor.run()` that the CLI shells into. Bump `EMBEDDINGS_VERSION` in `nba/embeddings/version.py` and `model_version` in `data/models/predictor_latest.json` on each run. |
| infra-lane      | nba-24o     | `make install-daemon` / `make uninstall-daemon`, `com.nba.ingest.live.plist`, ensures `~/.nba/` exists. |
| web-core-lane   | nba-mcv     | Default preset + hero `MatchupCard` default season → 2026. Update `web/src/data/presets.ts` `DEFAULT_PRESET_ID` (or current preset season fields). |
| web-pages-lane  | nba-ngc     | `web/src/pages/Lineups.tsx:36` `useState(2024)` → `useState(2026)` and any Players.tsx default-season fallback. |
| brutus          | (gates)     | Writes failing tests *before* each implementer lane runs. CONTRACT.md per lane. |
| athena          | (router)    | Dispatches, tracks idle/working, brokers handoffs. |

## Files lanes will touch (anchor map)

- `nba/ingest/espn.py` — `_get`, `_read_cache`, `_write_cache`, `fetch_boxscore`. Add `fetch_scoreboard(date)` + status-aware cache guard.
- `nba/ingest/season.py` — reusable `ingest_game(game_id)` factor-out if needed.
- `nba/ingest/live.py` — NEW. Daemon loop, scoreboard poll, STATUS_FINAL detect, self-heal walk, log writer.
- `nba/cli/main.py` — register `ingest live`, `train embeddings`, `train predictor`. Imports lazy.
- `nba/train/embeddings.py` and `nba/train/predictor.py` — NEW or refactor existing. Expose `run(...) -> dict` returning new version string.
- `nba/embeddings/version.py` — `EMBEDDINGS_VERSION` becomes mutable via `bump()` helper.
- `data/models/predictor_latest.json` — written each predictor train run; bump `model_version`.
- `web/src/data/presets.ts` — bring default preset into 2026.
- `web/src/pages/Lineups.tsx`, `web/src/pages/Players.tsx`.
- `Makefile` — `install-daemon`, `uninstall-daemon` targets.
- `infra/launchd/com.nba.ingest.live.plist` — NEW.

## Escalation rules

User is **out-of-loop**. All judgment calls flow to the parent (overseer) via
athena. No worker may escalate to the user. No worker may relitigate spec
decisions (cadence, lifecycle, cache semantics, etc.). If a worker hits a
blocker, route to athena with a one-line ask; athena either reroutes or pings
overseer.

## Done condition

- `nba ingest live` runs as a launchd-managed process; first run backfills
  2024+2025+2026-to-date for 30 teams; subsequent ticks detect STATUS_FINAL
  flips within 30s and ingest within ~150s of buzzer.
- `nba train embeddings` and `nba train predictor` produce new model artifacts
  and bump version fields.
- Web default-season pickers all show 2026.
- All work pushed to `main`; bd issues closed; sim_cache invalidation note
  filed (cache misses on version-mismatched rows are correct behavior — no
  code change needed there).
