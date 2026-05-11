# Postgres schema (v1)

Target: **Postgres 16 + pgvector**. Migration: `migrations/0001_init.sql`. No Alembic — plain SQL files, applied with `psql -1 -f`.

This document is the narrative companion to the DDL. Read it top-to-bottom before touching the migration. When a downstream lane needs to add a column or table, update this doc *first*, then ship a new numbered migration file.

## Conventions

- IDs are `BIGINT` if they come from ESPN's athlete/event namespace, `INT` for team IDs (small, finite set), `BIGSERIAL` for synthetic rows we mint ourselves.
- `season` is the **season-start calendar year**: `2023` means the 2023–24 season. Used everywhere a player or game is tied to a season.
- `clock_seconds` is **seconds remaining in the current period**, descending from 720 (regulation) or 300 (OT) to 0. Stints sort by `(quarter ASC, start_clock_seconds DESC)`.
- `*_at` columns are `TIMESTAMPTZ`. Wall-clock dates that don't need a zone (`game_date`, `birth_date`, `valid_from`, `valid_to`) are `DATE`.
- All tables get `created_at` defaulting to `now()`; mutable tables also get `updated_at`. We do not install row-update triggers in this migration — writers set `updated_at` explicitly.
- Strings are `TEXT` (no `VARCHAR(n)`) unless there's a hard reason.
- JSONB columns are documented inline with their expected shape. Treat the shape as a contract; if you change it, ship a migration that backfills.

## Enums

- `subject_type` — one of `player`, `team`, `lineup`, `coach`. Drives `facts.subject_type` so the row knows how to interpret `subject_id`.
- `season_type` — one of `regular`, `preseason`, `playoffs`, `play_in`. Drives `games.season_type`.

## Tables

### `players`

Single source of truth for a person. **One row per person**, not per (player, season) — the per-season unit lives in `rosters` and `embeddings_player`.

| column | type | notes |
|---|---|---|
| `player_id` | `BIGINT PRIMARY KEY` | ESPN athlete ID. |
| `full_name` | `TEXT NOT NULL` | Display name as ESPN serves it. |
| `first_name` | `TEXT` | |
| `last_name` | `TEXT` | |
| `birth_date` | `DATE` | |
| `height_inches` | `INT` | |
| `weight_lbs` | `INT` | |
| `position` | `TEXT` | ESPN's coarse position string. |
| `handedness` | `TEXT` | `L` / `R` / `A` (ambidextrous). |
| `espn_slug` | `TEXT` | URL slug for cross-referencing scraped pages. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

**Writes:** the ESPN ingest job (espn-ingest crew). **Reads:** every CLI command that resolves a player; the player-embedding trainer; the scouting LM's facts retrieval path. No FKs from this table — players are leaves.

### `teams`

One row per franchise. We do not version franchises across relocations (Seattle Sonics → OKC) — those are two rows with different IDs. ESPN's IDs handle this for us.

| column | type | notes |
|---|---|---|
| `team_id` | `INT PRIMARY KEY` | ESPN team ID. |
| `abbreviation` | `TEXT NOT NULL UNIQUE` | Three-letter code (`NYK`, `BOS`). |
| `full_name` | `TEXT NOT NULL` | `New York Knicks`. |
| `conference` | `TEXT` | `East` / `West`. |
| `division` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

### `games`

One row per game.

| column | type | notes |
|---|---|---|
| `game_id` | `BIGINT PRIMARY KEY` | ESPN event ID. |
| `season` | `INT NOT NULL` | Season-start year. |
| `season_type` | `season_type NOT NULL` | enum. |
| `game_date` | `DATE NOT NULL` | Local date of tipoff. |
| `tipoff_at` | `TIMESTAMPTZ` | |
| `home_team_id` | `INT NOT NULL REFERENCES teams(team_id)` | |
| `away_team_id` | `INT NOT NULL REFERENCES teams(team_id)` | |
| `home_score` | `INT` | Nullable until finalized. |
| `away_score` | `INT` | |
| `venue` | `TEXT` | |
| `attendance` | `INT` | |
| `status` | `TEXT NOT NULL DEFAULT 'final'` | `final` / `scheduled` / `postponed`. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Indices:

- `games (season, game_date)` — date-range scans for backfill and rolling-window queries.
- `games (home_team_id, season)` and `games (away_team_id, season)` — team schedule lookups.

### `coaches`

One row per head/associate coach.

| column | type | notes |
|---|---|---|
| `coach_id` | `BIGINT PRIMARY KEY` | ESPN coach ID if available, else synthetic. |
| `full_name` | `TEXT NOT NULL` | |
| `first_name` | `TEXT` | |
| `last_name` | `TEXT` | |
| `birth_date` | `DATE` | |
| `espn_slug` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

### `coach_games`

Per-game coach mapping. Mid-season firings, interims, and associate-as-acting-HC stints all live here. The predictor reads this to attach a coach categorical feature to each lineup stint via the stint's `game_id`.

| column | type | notes |
|---|---|---|
| `coach_id` | `BIGINT NOT NULL REFERENCES coaches(coach_id)` | |
| `game_id` | `BIGINT NOT NULL REFERENCES games(game_id)` | |
| `team_id` | `INT NOT NULL REFERENCES teams(team_id)` | The team they coached *that game*. |
| `role` | `TEXT NOT NULL` | `head` / `interim` / `associate`. |
| `PRIMARY KEY` | `(game_id, team_id, role)` | One head per team per game (interims still bind under `head` if acting). |

Index on `(coach_id, team_id)` for "every game coach X was on the sideline for team Y".

### `rosters`

One row per (player on team within a date range in a season). Mid-season trades produce two rows for the same `(season, player_id)` with different `team_id`s and overlapping but non-equal date ranges.

| column | type | notes |
|---|---|---|
| `season` | `INT NOT NULL` | |
| `team_id` | `INT NOT NULL REFERENCES teams(team_id)` | |
| `player_id` | `BIGINT NOT NULL REFERENCES players(player_id)` | |
| `jersey` | `TEXT` | |
| `start_date` | `DATE NOT NULL` | First date eligible to play. |
| `end_date` | `DATE` | NULL = still rostered at season end. |
| `acquired_via` | `TEXT` | `draft` / `trade` / `free_agent` / `waiver` / `two_way` / `ten_day`. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `PRIMARY KEY` | `(season, team_id, player_id, start_date)` | |

Index on `(player_id, season)` for "every team player X was on in season Y".

### `pbp_events`

One row per play-by-play event. The `players_on_floor` JSONB is critical: it's what `lineup_stints` is *derived from*, and it's how every downstream consumer reconstructs who was on the floor when something happened without re-running stint logic.

| column | type | notes |
|---|---|---|
| `game_id` | `BIGINT NOT NULL REFERENCES games(game_id)` | |
| `sequence_no` | `INT NOT NULL` | Strictly increasing within `game_id`. |
| `quarter` | `INT NOT NULL` | 1–4 regulation, 5+ OT. |
| `clock_seconds` | `INT NOT NULL` | Descending within quarter. |
| `wall_clock_at` | `TIMESTAMPTZ` | If ESPN provides it. |
| `team_id` | `INT REFERENCES teams(team_id)` | Acting team. NULL for neutral events (period boundaries, jumpballs). |
| `player_id` | `BIGINT REFERENCES players(player_id)` | Primary actor. |
| `assist_player_id` | `BIGINT REFERENCES players(player_id)` | Convenience denorm; assists also appear as their own event. |
| `event_type` | `TEXT NOT NULL` | `made_2pt` / `missed_2pt` / `made_3pt` / `missed_3pt` / `ft_made` / `ft_missed` / `rebound_off` / `rebound_def` / `assist` / `steal` / `block` / `turnover` / `foul` / `sub_in` / `sub_out` / `period_start` / `period_end` / `timeout` / `jumpball`. |
| `points_scored` | `SMALLINT NOT NULL DEFAULT 0` | 0 / 1 / 2 / 3. |
| `home_score` | `SMALLINT NOT NULL` | After this event. |
| `away_score` | `SMALLINT NOT NULL` | After this event. |
| `description` | `TEXT` | ESPN's freeform string. |
| `players_on_floor` | `JSONB NOT NULL` | Shape: `{"home": [p, p, p, p, p], "away": [p, p, p, p, p]}`. Player IDs sorted ascending within each side. |
| `raw` | `JSONB` | Full ESPN payload for forensic re-derivation. |
| `PRIMARY KEY` | `(game_id, sequence_no)` | |

Index on `(game_id, quarter, clock_seconds)` — the spec's required ordering for time-window scans.

### `lineup_stints`

A "stint" is a maximal contiguous interval within a game where both lineups stay constant. The PBP-to-stint derivation prototype (separate bead) writes this table; the predictor trains on it.

| column | type | notes |
|---|---|---|
| `stint_id` | `BIGSERIAL PRIMARY KEY` | |
| `game_id` | `BIGINT NOT NULL REFERENCES games(game_id)` | |
| `season` | `INT NOT NULL` | Denormalized from games for index efficiency and so `lineup_hash` can be computed without a join. |
| `quarter` | `INT NOT NULL` | |
| `start_clock_seconds` | `INT NOT NULL` | Period seconds remaining when the stint begins. |
| `end_clock_seconds` | `INT NOT NULL` | Period seconds remaining when the stint ends. Less than `start_clock_seconds`. |
| `duration_seconds` | `SMALLINT NOT NULL` | `start - end`. Stored to avoid recompute in every query. |
| `home_team_id` | `INT NOT NULL REFERENCES teams(team_id)` | |
| `away_team_id` | `INT NOT NULL REFERENCES teams(team_id)` | |
| `home_lineup` | `INTEGER[] NOT NULL` | Length exactly 5. Sorted ascending. CHECK enforces. |
| `away_lineup` | `INTEGER[] NOT NULL` | Length exactly 5. Sorted ascending. CHECK enforces. |
| `home_lineup_hash` | `TEXT NOT NULL` | SHA256 hex per the spec at the bottom of this file. Computed from `(player_id, season)` tuples. |
| `away_lineup_hash` | `TEXT NOT NULL` | Same. |
| `home_pts` | `SMALLINT NOT NULL DEFAULT 0` | Points scored *by the home team* during the stint. |
| `away_pts` | `SMALLINT NOT NULL DEFAULT 0` | Points scored *by the away team* during the stint. |
| `pts` | `SMALLINT NOT NULL DEFAULT 0` | `home_pts - away_pts`. Signed point differential, home perspective. Stored to keep the predictor's training query trivial. |
| `possessions` | `SMALLINT NOT NULL DEFAULT 0` | Total possessions across both teams. |
| `possessions_home` | `SMALLINT NOT NULL DEFAULT 0` | |
| `possessions_away` | `SMALLINT NOT NULL DEFAULT 0` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Indices:

- `lineup_stints (game_id, quarter, start_clock_seconds)` — spec-required, supports per-game timeline reconstruction.
- `lineup_stints (home_lineup_hash, season)` and `lineup_stints (away_lineup_hash, season)` — "every stint this exact 5-man unit ever played" lookups for the data-app mode and shrinkage priors.
- `lineup_stints (season)` — bulk seasonal training cuts.

**Why store both `home_pts` / `away_pts` and `pts`?** `pts` is the predictor's training target (per-possession point diff, home perspective); `home_pts`/`away_pts` keep the raw splits available for analytics queries without forcing a PBP re-derivation. The redundancy is paid for once at write time and saves every read.

### `facts`

The curated facts table — ground-truth structured statements the scouting LM retrieves at inference time. Schema is intentionally narrow and JSONB-backed so we don't have to ship a migration every time we add a new fact kind.

| column | type | notes |
|---|---|---|
| `fact_id` | `BIGSERIAL PRIMARY KEY` | |
| `subject_type` | `subject_type NOT NULL` | enum. |
| `subject_id` | `TEXT NOT NULL` | `player_id` / `team_id` / `coach_id` as text; `lineup` subjects use the `lineup_hash` directly. |
| `fact_key` | `TEXT NOT NULL` | `career_ppg`, `season_avg_3pt`, `role_descriptor`, `award_dpoy_year`, etc. |
| `fact_value` | `JSONB NOT NULL` | Shape depends on `fact_key`; document new keys in this file. |
| `source` | `TEXT NOT NULL` | `espn-derived` / `manual-seed` / `bbref-derived` / etc. |
| `season` | `INT` | NULL = season-agnostic (career fact). |
| `valid_from` | `DATE` | NULL = no start bound. |
| `valid_to` | `DATE` | NULL = current / unbounded. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Index: `facts (subject_type, subject_id, fact_key)` — spec-required; the canonical lookup path.

A partial unique constraint enforces "no duplicate fact per subject+key per season": `UNIQUE (subject_type, subject_id, fact_key, COALESCE(season, -1))` — see DDL. Using a sentinel `-1` for NULL avoids the multi-NULL-uniqueness quirk in btree.

**Empty in this migration.** Population is a downstream bead.

### `sim_cache`

Lookup cache for simulation results. Rust gateway checks this before forwarding to the predictor.

| column | type | notes |
|---|---|---|
| `cache_id` | `BIGSERIAL PRIMARY KEY` | |
| `lineup1_hash` | `TEXT NOT NULL` | The team-1 lineup (typically home, but orientation is encoded in `context_hash`). |
| `lineup2_hash` | `TEXT NOT NULL` | The team-2 lineup. |
| `context_hash` | `TEXT NOT NULL` | SHA256 hex of the canonicalized JSON `{era, home_away, coach_home, coach_away, days_rest_home, days_rest_away, season_type}` (writer-defined; document the canonical form when the predictor lane lands). |
| `model_versions` | `JSONB NOT NULL` | `{"predictor": "vX.Y", "embeddings": "vA.B", "lm": "vC"}`. |
| `result` | `JSONB NOT NULL` | The full sim payload — score, win prob, matchups, edges, narrative. Shape is whatever `nba sim` returns under `data`. |
| `hit_count` | `BIGINT NOT NULL DEFAULT 0` | Incremented on each cache hit. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `last_hit_at` | `TIMESTAMPTZ` | |
| `UNIQUE (lineup1_hash, lineup2_hash, context_hash)` | | Spec-required. |

**Orientation note.** `(lineup1, lineup2)` is *not* commutative — home/away affects the predictor, and `context_hash` carries that orientation bit. The Rust gateway must hash with a stable orientation rule (e.g., team-1 is always the team the user names first); document the convention when the gateway lane lands.

### `embeddings_player`

One vector per `(player, season, model_version)`. pgvector-backed.

| column | type | notes |
|---|---|---|
| `player_id` | `BIGINT NOT NULL REFERENCES players(player_id)` | |
| `season` | `INT NOT NULL` | |
| `model_version` | `TEXT NOT NULL` | Bumped on every retrain — old vectors stay queryable until pruned. |
| `embedding` | `vector(128) NOT NULL` | Dim **128** chosen as a placeholder; document the chosen value once trainer lane finalizes. |
| `minutes_sample` | `INT` | Minutes played that informed this embedding — sparse-data flag for the warning system. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `PRIMARY KEY` | `(player_id, season, model_version)` | |

Indices:

- `embeddings_player USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)` — spec-required; cosine matches the matchup-module's distance metric.
- `embeddings_player (model_version)` — fast "all vectors from the current model" sweep when computing lineup features.

**Why dim 128?** Placeholder. The predictor lane will tune. Retraining bumps `model_version`; if dim changes, ship a new migration that adds a parallel column (`embedding_v2 vector(N)`) or a new table — pgvector ivfflat indexes are bound to a specific dimension.

**Empty in this migration.** Population is a downstream bead.

## Foreign-key graph

```
teams ────────────┐
   ▲              ▼
   │     games ──▶ pbp_events ──▶ players
   │       ▲                       ▲
   │       │                       │
   ├── rosters ────────────────────┤
   │                               │
   ├── coach_games ──▶ coaches     │
   │                               │
   ▼                               ▼
lineup_stints ──── (no FK; arrays/hashes hold lineup membership)
embeddings_player ────────────────▶ players
facts ─────────────── (polymorphic subject; no FK)
sim_cache ─────────── (hashes; no FK)
```

Lineups, facts, and sim cache deliberately avoid FKs into players/lineups because:

- **lineup_stints.home_lineup**: array-typed; Postgres can't FK array elements.
- **facts.subject_id**: polymorphic.
- **sim_cache**: hashes are stand-ins for lineups that *may not have ever existed historically* (counterfactual sims).

This means orphan rows are possible after a deletion. Don't hard-delete from `players` or `teams`; if you must, sweep dependents first.

## `lineup_hash` specification

Implementers will reproduce this byte-for-byte. Match it exactly.

**Inputs.** A lineup is an unordered set of five `(player_id, season)` tuples. `player_id` is the integer from `players.player_id`. `season` is the integer season-start year (e.g., `2023`).

**Algorithm.**

1. For each `(player_id, season)` tuple, format the token as the **decimal string of `player_id`**, then a literal colon `:`, then the **decimal string of `season`**. No padding, no leading zeros, no whitespace.
   - Example: `(3704, 2023)` → `"3704:2023"`.
2. Collect the five tokens into a list. **Sort them lexicographically (Unicode code-point order)** — i.e., Python's default `sorted()` on `str`. *Do not* sort by integer player ID; the canonical form is string-sorted so any language with default string ordering reproduces it. Be aware: `"1234:2023"` sorts *before* `"987:2023"` because `'1' < '9'` lex-wise.
3. Join the sorted tokens with the literal pipe character `|` (U+007C). No surrounding delimiters.
4. UTF-8 encode the joined string.
5. Compute `SHA-256` over those bytes.
6. The hash is the **lowercase hex** digest (64 chars, `[0-9a-f]+`).

**Reference implementation (Python).**

```python
import hashlib

def lineup_hash(lineup: list[tuple[int, int]]) -> str:
    tokens = sorted(f"{pid}:{season}" for pid, season in lineup)
    return hashlib.sha256("|".join(tokens).encode("utf-8")).hexdigest()
```

**Properties.**

- **Orientation-agnostic for the 5 players.** Reordering the input list does not change the hash — the sort enforces canonical order.
- **Cross-season distinction.** `2016 Curry` and `2026 Curry` are different tokens, so a lineup with `2016 Curry` hashes differently from the same four teammates with `2026 Curry`. Required for the cross-era sim story.
- **Stable across languages.** Lex sort + UTF-8 + SHA-256 + lowercase hex are spec'd unambiguously so Python, Rust, and SQL (`encode(digest(..., 'sha256'), 'hex')`) all agree byte-for-byte.

**Where it's used.**

- `lineup_stints.home_lineup_hash` / `away_lineup_hash` — written at stint-derivation time.
- `sim_cache.lineup1_hash` / `lineup2_hash` — written at sim time.
- `facts.subject_id` when `subject_type = 'lineup'` — same hash.

**Test fixture.** A unit test under `tests/` must lock the following expected value (the stint-derivation lane should land it):

```
lineup = [(977, 2023), (3032976, 2023), (3133628, 2023), (3147657, 2023), (3998191, 2023)]
expected = sha256("3032976:2023|3133628:2023|3147657:2023|3998191:2023|977:2023") in lowercase hex
```

(Note: `977` sorts *after* the seven-digit IDs because `'9' > '3'`.)

## Migration 0002 — `pbp_status`

**File:** `migrations/0002_pbp_status.sql`. Adds one column to `games`:

| column | type | notes |
|---|---|---|
| `pbp_status` | `TEXT NOT NULL DEFAULT 'ok' CHECK (pbp_status IN ('ok', 'thin'))` | Quality flag for the game's play-by-play data. |

A partial index covers the non-`ok` rows:

```sql
CREATE INDEX games_pbp_status_thin_idx
    ON games (pbp_status)
    WHERE pbp_status <> 'ok';
```

**Why this exists.** ESPN's PBP feed is incomplete for a non-trivial slice of games — sometimes the endpoint returns a single play, sometimes a handful, sometimes nothing usable at all. The known canary is game `230126018`, which has a **1-play PBP** payload. We cannot ingest stints from these games, but we still want the boxscore row and we still want the rest of the season to land cleanly. Hard-crashing the ingest when one game out of 1,230 has a broken feed is the wrong default.

**How it's set.** Detection is by **row count, not by game ID**. The ingest path (`nba ingest season` per `OVERSEER_BRIEF.md` Lane A item 4) writes:

- `pbp_status = 'ok'` when `len(plays) >= 50` — the threshold below which stint reconstruction is unreliable. (Real games have ~400-500 plays; 50 is a generous floor that flags pathologically incomplete feeds.)
- `pbp_status = 'thin'` when `len(plays) < 50`. Ingest still writes the `games` row + boxscore-derived `rosters` + `coach_games`. It logs a structured warning and **skips** stint derivation for that game.

Storing by row count (not by hardcoded ID) means new bad games discovered in future seasons are caught automatically — the `230126018` case is the *kind* this catches, not the specific case.

**Downstream contract.**

- `lineup_stints` writers MUST filter `games.pbp_status = 'ok'` before deriving stints.
- The predictor's training query MUST join through `games` and exclude `pbp_status = 'thin'` rows. The `lineup_stints` table itself has no `pbp_status` column — joining through the game is the canonical filter.
- The `nba lineup stats` SQL queries are unaffected (they read from `lineup_stints`, which is already empty for thin games).

**Future values.** If we discover other failure modes (boxscore-missing, schedule-only stubs, postponed-not-played) and need to distinguish them, extend the CHECK constraint in a follow-up migration rather than re-typing the column. `TEXT + CHECK` was chosen over an `ENUM` precisely because adding values to a CHECK is a one-line `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT` and doesn't require a `pg_enum` mutation.

**Idempotency.** Uses `ADD COLUMN IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` — safe to re-run.
