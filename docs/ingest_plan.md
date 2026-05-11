# `nba ingest season` — implementation plan (nba-kve, PREP)

**Status:** plan only. Bead is BLOCKED on nba-c1s (infra docker+config) and nba-tt4 (schema migrations/0002). Migration 0002 already exists (`pbp_status` column landed) but schema-lane has not signed off on the wider review yet.
**Author:** espn-lane
**Updated:** 2026-05-11
**Refs:** OVERSEER_BRIEF.md Lane A items 3+4, `nba/ingest/espn.py`, `migrations/0001_init.sql`, `migrations/0002_pbp_status.sql`, `docs/schema.md`, `docs/p0_espn_coverage.md`

## Goal

A single new CLI subcommand:

```
nba ingest season --team NYK --season 2023 [--dry-run]
```

Wires the existing `nba/ingest/espn.py` fetcher to local Postgres. Populates `teams`, `players`, `games`, `coaches`, `coach_games`, `rosters`, `pbp_events`. Lane B owns `lineup_stints` (separate bead, separate driver). Idempotent: re-running on the same (team, season) is a no-op against the DB.

## Coordination + open decisions

### D1 — Season convention mismatch (BLOCKING; needs schema-lane / overseer adjudication)

- ESPN: `season=YYYY` is the **season-end** year. 2022-23 → `season=2023`.
- `docs/schema.md`: `season` is the **season-start** year. "2023 means the 2023-24 season."

OVERSEER_BRIEF says `--season 2023` for "NYK 2022-23" — which only parses under ESPN's convention. I propose:

**A) CLI accepts season-end year (`--season 2023` = 2022-23), and the schema doc is amended to match.** Reason: the user-facing CLI matches ESPN's natural call and how basketball fans say "the '23 Knicks." Internal storage can either follow CLI/ESPN or do a (-1) translation at insert time. Schema-lane signs off in 0003 (or just fixes the doc — no DDL impact, it's the *interpretation* of the int).

Until D1 is resolved I'll write `--season N → ESPN season=N → schema games.season = N` everywhere (option A). If schema-lane insists on B), one-line change in the loader.

### D2 — `pbp_events.players_on_floor` NOT NULL vs. write order

- Schema 0001 declares `players_on_floor JSONB NOT NULL`.
- Lane A (this bead) writes `pbp_events` rows during ingest. Lane B computes on-floor lineups during stint derivation, **after** ingest.

Two options:

- **A) Insert `'[]'::jsonb` placeholder during ingest; Lane B fills it in via `UPDATE`.** Cheapest. Constraint shape unchanged. Need a contract that Lane B treats `'[]'` as "not yet derived" and Lane B-or-stint-querying CLI checks for that sentinel. **Recommend.**
- **B) Make column nullable in migration 0003 and let Lane B's UPDATE set it.** Cleaner semantics ("NULL = not yet derived"). Requires schema-lane work and a new migration.

I'll propose A) and ship; if schema-lane prefers B), one DDL line plus one ingest change.

### D3 — Cache path

OVERSEER_BRIEF + dispatch say `data/cache/espn/`. Current `nba/ingest/espn.py` default is `data/raw/espn/`. Decision: the **ingest driver** always passes `cache_root=Path("data/cache/espn")` explicitly. Leave the fetcher default untouched (preserves existing tests + the b4o fixture path). Migration of any existing cached blobs is a no-op — fresh dir.

### D4 — Throttle

OVERSEER_BRIEF says 30s. Fetcher default is `THROTTLE_SEC = 1.0` (test-friendly). Decision: at the start of the ingest CLI entry, set `espn.THROTTLE_SEC = 30.0`. No new fetcher knob. Smoke test overrides back to 0.

### D5 — Coordination with brutus on nba-5ve

I need brutus to ratify the JSON-output contract (proposed shape below) **before** I write the implementation. Routing separately.

## Architecture sketch

New files:

```
nba/ingest/season.py          # the orchestrator, called by the CLI command
nba/ingest/parse.py           # pure-function ESPN-JSON → typed-dict mappers
nba/ingest/db.py              # psycopg connection helpers + UPSERT statements
nba/cli/main.py               # add `nba ingest season` typer subcommand (edit)
tests/test_ingest_smoke.py    # env-gated live ingest sanity check
tests/test_ingest_parse.py    # respx-free, fixture-driven mapper tests
```

`nba/ingest/espn.py` is **not modified**. It already exposes `fetch_schedule`, `fetch_boxscore`, `fetch_pbp`. The orchestrator imports it. (One small possible addition: `fetch_coaches(team_id, season)` for the season-coaches endpoint — see C2 below — but I lean toward inlining that as a private helper in `season.py` to keep the fetcher's surface tight and its tests stable.)

### Module boundaries

- **`espn.py` (existing):** HTTP + cache. No DB knowledge.
- **`parse.py` (new):** raw ESPN payload → typed dicts shaped like the DB tables. Pure functions, no I/O. Easy to unit-test with the 9 fixtures already on disk.
- **`db.py` (new):** psycopg3 connection from `nba.config`, prepared `INSERT ... ON CONFLICT` statements per table. No business logic.
- **`season.py` (new):** orchestrator. Walks the schedule, fetches each summary, parses, upserts. Per-game transaction. Aggregates the run summary.
- **`cli/main.py`:** thin entry that calls `season.ingest_season(team, season, dry_run)` and emits the contract JSON.

## Data flow per `nba ingest season --team NYK --season 2023`

```
schedule = espn.fetch_schedule("18", 2023)      # 82 reg-season events
upsert teams (NYK + every opponent encountered)
for event in schedule.events filtered to seasontype=2:
    BEGIN TRANSACTION
    summary = espn.fetch_boxscore(event_id)
    upsert games row (header + linescore + venue + attendance + pbp_status)
    upsert players from boxscore.players[].statistics[0].athletes[]
    upsert rosters (season, team_id, player_id, start_date=season_first_game_date)
    upsert coach_games via _resolve_coach(team_id, season, game_date)
    plays = summary["plays"]
    if len(plays) < 50:
        UPDATE games SET pbp_status='thin' WHERE game_id=...
        log structured warning, append to warnings[]
        # do NOT insert pbp_events for this game; Lane B will skip it
    else:
        upsert pbp_events with (game_id, sequence_no) conflict-do-nothing
    COMMIT  (or ROLLBACK on exception)
emit JSON summary
```

If `--dry-run`: wrap the whole season loop in one outer transaction and `ROLLBACK` at the end. Same code path, same counts (UPSERTs return what they would have done via `INSERT ... ON CONFLICT ... RETURNING xmax = 0`).

## Idempotency strategy

UPSERT by natural key on every table. Re-running ingest after a successful first pass returns the same counts and produces **zero** row mutations (verify with `txid_current()` diff in a sanity check).

| Table | Conflict target | Update set / behavior |
|---|---|---|
| `teams` | `(team_id)` | UPDATE name/abbrev/conference/division/updated_at |
| `players` | `(player_id)` | UPDATE name fields, position, espn_slug, height/weight if non-null, updated_at |
| `coaches` | `(coach_id)` | UPDATE name fields, espn_slug, updated_at |
| `games` | `(game_id)` | UPDATE scores, status, attendance, pbp_status, updated_at |
| `coach_games` | `(game_id, team_id, role)` | DO NOTHING (immutable per-game assignment) |
| `rosters` | `(season, team_id, player_id, start_date)` | DO NOTHING (we use the season-start date as a stable key; trades within season handled in slice 3) |
| `pbp_events` | `(game_id, sequence_no)` | DO NOTHING (PBP events are immutable) |

### Deterministic IDs

All IDs except `lineup_stints.stint_id` come from ESPN — natural keys, deterministic by construction:

- `team_id` ← ESPN team id (`teams/18` = NYK)
- `player_id` ← ESPN athlete id (already used in `pbp_events.participants[].athlete.id`)
- `coach_id` ← ESPN coach id (resolved via `seasons/{Y}/teams/{T}/coaches` $ref)
- `game_id` ← ESPN event id (9-digit numeric, fits BIGINT)
- `sequence_no` ← `int(plays[i].sequenceNumber)`

No hashing / synthetic IDs needed at this layer. `lineup_stints` (Lane B) is the only table that needs deterministic synthetic keys — its `home_lineup_hash`/`away_lineup_hash` are sha256 of sorted player IDs, already in 0001.

## Bad-PBP handling

Per the b4o report, thin PBP is a per-game data hole, never a season-wide signal.

- **Threshold:** `len(plays) < 50` (per OVERSEER_BRIEF). Distinct from the fetcher's `THIN_PBP_THRESHOLD = 5` "this is broken" floor — the 50 cutoff is "this won't yield useful stints."
- **Action when thin:**
  1. Mark `games.pbp_status = 'thin'`
  2. Append a structured warning: `{"code": "thin_pbp", "message": "game <id> has <n> plays", "context": {"game_id": "<id>", "plays": <n>, "team": "<abbr>", "date": "<YYYY-MM-DD>"}}`
  3. **Still** upsert `games`, `players`, `rosters`, `coach_games` rows (boxscore data is fine).
  4. **Skip** `pbp_events` for this game.
  5. **Do not raise.** Continue to the next game.
- Lane B's stint deriver reads `WHERE pbp_status = 'ok'` and skips thin games. Its CLI returns the same warning shape if asked to process a thin game directly.

## Field-by-field mapping (ESPN → schema)

### `teams`
- `team_id` ← `header.competitions[0].competitors[].team.id` (int)
- `abbreviation` ← `.team.abbreviation`
- `full_name` ← `.team.displayName`
- `conference` / `division` ← null on first ingest; backfill from `sports.core.api.espn.com/.../teams/{id}` later

### `players`
- `player_id` ← `boxscore.players[].statistics[0].athletes[].athlete.id`
- `full_name` ← `athlete.displayName`
- `first_name` / `last_name` / `position` / `espn_slug` ← `athlete.firstName` / `athlete.lastName` / `athlete.position.abbreviation` / `athlete.shortName`-derived
- `height_inches`, `weight_lbs`, `birth_date`, `handedness` ← null in v0 (would need `athletes/{id}` per-player call; out of scope)

### `coaches` + `coach_games`
- Coach **not** in the summary endpoint (confirmed by P0 doc).
- Per-team ingest fetches `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/{Y}/teams/{team_id}/coaches` → list of `$ref` → follow each.
- Mid-season changes return >1 coach. v1 attribution: take the *first* (longest-tenured) head coach and assign role=`'head'` to every game in that team's season. Document this as a known v0 limitation; v1 will date-disambiguate.
- `coach_games (game_id, team_id, role='head', coach_id)` upsert per game.

### `games`
- `game_id` ← event id (int)
- `season` ← `--season` arg (CLI input; see D1)
- `season_type` ← `'regular'` (we filter to seasontype=2)
- `game_date` ← ISO-parse `header.competitions[0].date`, convert UTC → `America/New_York`, take the date part
- `tipoff_at` ← UTC timestamp as-is
- `home_team_id` / `away_team_id` ← from `competitors[]` where `homeAway`
- `home_score` / `away_score` ← `competitors[].score` (int)
- `venue` ← `gameInfo.venue.fullName`
- `attendance` ← `gameInfo.attendance`
- `status` ← `'final'` if `competitions[0].status.type.name == 'STATUS_FINAL'` else `'postponed'`/`'scheduled'`
- `pbp_status` ← `'ok'` by default; set `'thin'` if `len(plays) < 50`

### `rosters`
- For each (team, season) we enumerate the **union** of all `athlete.id` across the team's 82 games' boxscores.
- `start_date` ← the team's first regular-season game date in that season (constant per team-season). This gives stable row keys; mid-season acquisitions get the same date in v0. Trades are slice 3.
- `acquired_via` ← null in v0.

### `pbp_events`
- `game_id` ← event id
- `sequence_no` ← `int(play.sequenceNumber)`
- `quarter` ← `play.period.number`
- `clock_seconds` ← parse `play.clock.displayValue` as `MM:SS` → `M*60 + S`
- `wall_clock_at` ← `play.wallclock` (TIMESTAMPTZ) if present (2018+ only per P0 doc); else null
- `team_id` ← `play.team.id` (null on meta plays)
- `player_id` ← `play.participants[0].athlete.id` if present
- `assist_player_id` ← `play.participants[1].athlete.id` for assist events; for substitutions this is the out-player; mapping table:
  | event_type (ESPN text) | participants[0] | participants[1] |
  |---|---|---|
  | shooting plays | shooter | assister (if any) |
  | Substitution | player-in | player-out |
  | Personal Foul / Shooting Foul | fouler | drawn-by (if any) |
  | Block | shot-blocker | shooter |
  | Steal | stealer | turnover-source |
  | Turnover (lost ball / bad pass) | committer | stealer (if any) |
  - For v0, store `participants[0]` in `player_id` and `participants[1]` in `assist_player_id` unconditionally and let downstream consumers interpret per `event_type`. This matches ESPN's "primary then secondary actor" convention closely enough; Lane B's stint deriver uses the SUBs specifically, where the semantic is well-defined.
- `event_type` ← `play.type.text`
- `points_scored` ← `play.scoreValue` (0/2/3, plus 1 for FT-makes)
- `home_score` / `away_score` ← `play.homeScore` / `awayScore` (running totals)
- `description` ← `play.text`
- `players_on_floor` ← `'[]'::jsonb` (Lane B fills in via UPDATE — see D2)
- `raw` ← the entire `play` dict, for debuggability

## Rate limit + cache

- `espn.THROTTLE_SEC = 30.0` at CLI entry. One season = 1 schedule call + 82 summary calls + 1-3 coach calls ≈ 85 calls × 30s ≈ 43 min wall-clock first run. Re-runs from cache are ~instant.
- Cache root: `data/cache/espn/{summary,schedule,coaches}/<key>.json`. Gitignored (existing `data/raw/` doesn't catch it — add `data/cache/` to .gitignore in this lane's PR).
- A schedule that's already cached short-circuits the run; ditto for summaries. Re-fetch only on cache miss.

## CLI surface — proposed JSON contract (for brutus to ratify in nba-5ve)

stdout, exit 0:

```json
{
  "data": {
    "season": 2023,
    "team": "NYK",
    "team_id": 18,
    "games_total": 82,
    "games_inserted": 82,
    "games_updated": 0,
    "games_thin_pbp": 1,
    "games_failed": 0,
    "players_upserted": 18,
    "rosters_upserted": 18,
    "coach_games_inserted": 82,
    "pbp_events_inserted": 38241,
    "dry_run": false
  },
  "warnings": [
    {"code": "thin_pbp", "message": "game 230126018 has 1 play", "context": {"game_id": 230126018, "plays": 1, "team": "NYK", "date": "2003-01-25"}}
  ],
  "meta": {
    "schema_version": "0002",
    "data_versions": {"espn": "site.api.espn.com@2026-05-11"},
    "model_versions": null,
    "cache_hit": false,
    "cached": false,
    "elapsed_ms": 2598123.4,
    "generated_at": "2026-05-11T18:32:14.117823+00:00"
  }
}
```

`--dry-run`: same shape, with `data.dry_run = true`. Counts reflect what would be inserted/updated; the transaction rolls back. No mutation visible to other connections.

Exit codes:
- `0` success (including a run where some games were thin)
- `1` generic ingest failure (DB connection down, schedule fetch fails)
- `3` `InvalidTeamError` — unknown `--team` abbreviation
- `4` `EraOutOfRangeError` — season outside the supported range (P0 says 2003+)
- `5` `InsufficientDataError` — schedule returned 0 regular-season events

Typed errors emit `ErrorPayload` JSON to stderr, matching the existing nba/contracts.py shape.

## Smoke test (`tests/test_ingest_smoke.py`)

Env-gated by `NBA_INGEST_SMOKE=1`. Skips otherwise. CI never sets it.

```python
def test_smoke_nyk_2022_23(pg_conn):
    # Run the CLI: `nba ingest season --team NYK --season 2023`
    # (no --dry-run; this is the real smoke test)
    rc = subprocess.run(["nba", "ingest", "season", "--team", "NYK", "--season", "2023"]).returncode
    assert rc == 0
    cur = pg_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games WHERE season=2023 AND (home_team_id=18 OR away_team_id=18)")
    assert cur.fetchone()[0] == 82
    cur.execute(
        "SELECT COUNT(*) FROM pbp_events WHERE game_id IN "
        "(SELECT game_id FROM games WHERE season=2023 AND (home_team_id=18 OR away_team_id=18) AND pbp_status='ok')"
    )
    n = cur.fetchone()[0]
    assert 35_000 <= n <= 40_000, f"pbp_events count {n} outside expected range"
    cur.execute("SELECT COUNT(DISTINCT player_id) FROM rosters WHERE season=2023 AND team_id=18")
    n_players = cur.fetchone()[0]
    assert 15 <= n_players <= 20, f"distinct NYK roster size {n_players} outside expected range"
```

Run twice on the same DB: assert zero diffs on the second run (idempotency).

## Unit tests (not gated)

`tests/test_ingest_parse.py` — feed each of the 9 already-committed fixtures into the mapper, assert table-row dicts shape match. Covers the 2003 / 2008 / 2013 / 2018 / 2023 era variants. Pure-function tests, no DB, no network.

## Implementation order (when unblocked)

1. Wait for **nba-c1s** signal (Postgres docker + `nba/config.py`).
2. Wait for **nba-tt4** signal (0002 already shipped; confirm schema-lane is done with their review and decide D2).
3. Coordinate D1 + D2 + nba-5ve contract with brutus / overseer.
4. Land `nba/ingest/parse.py` + `tests/test_ingest_parse.py` first — pure functions, easiest to verify.
5. Land `nba/ingest/db.py` + `nba/ingest/season.py`.
6. Wire `nba/cli/main.py` ingest subcommand.
7. Run the smoke test against local Postgres. Verify counts. Verify idempotency.
8. Document any schema deltas discovered (likely a 0003 if D2-B is chosen, or just an amendment to schema.md if D1 needs reconciliation).
9. Close bead with commit SHA + smoke counts.

## Risks / unknowns

- **Schedule pagination.** Unverified: does `season=YYYY` ever paginate? P0 says 82 events returned in one response; sample size = 5. Watch for >82 events suggesting include of preseason/playoffs (filter on `seasonType.id == "2"`).
- **Coach mid-season changes.** Documented as v0 limitation. May need 0003 to add date columns on `coach_games` if Lane B's per-stint coach lookup demands per-game accuracy.
- **Rate-limit at 30s × 82 games = 41 minutes first run.** No good way around this without parallel fetches against an unofficial API. Cached re-runs are fast. Acceptable per OVERSEER_BRIEF.
- **`players_on_floor` constraint** (D2). Recommend solving by writing `[]` placeholder and revisiting in slice 3.
- **Season convention** (D1). Needs adjudication before code lands.
