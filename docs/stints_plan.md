# Lane B plan — stints at scale + real `nba lineup stats`

**Owner:** stints-lane
**Beads:** nba-8oj (drivers + SQL), nba-9b2 (CtG/PBPStats validation)
**Blocked on:** nba-kve (espn-lane: one full NYK 2022-23 ingest into Postgres)
**Coordinates with:** brutus on nba-5ve (CLI contract for `nba stints derive`)

This is the *prep plan* written while Lane A is still ingesting. Implementation
fires the moment espn-lane signals nba-kve done.

## Goal of this lane (one sentence)

Turn the fixture-green `derive_stints()` into a season-wide pipeline that
writes `lineup_stints` rows for every NYK 2022-23 game, and replace the stub
in `nba lineup stats` with a real SQL query — values that survive a side-by-side
comparison with Cleaning the Glass and PBPStats.

## Surface I already own

- `nba/stints/derive.py` — pure function, 9/9 green on `tests/fixtures/pbp_minigame.json`.
  Wall-clock ascending input, returns `list[Stint]` dataclass.
- Contract pinned in `CONTRACT_STINTS.md` (brutus, nba-6gz).

## What needs to exist before I can move (gate)

From Lane A (nba-kve), with full NYK 2022-23 ingested (see `docs/ingest_plan.md` for espn-lane's plan):
- `games` table — 82 rows for NYK 2022-23 regular season, joining team_id.
- `pbp_events` table — ~35-40k rows. **`event_type` is stored as raw ESPN
  `play.type.text` strings** (e.g. `'Substitution'`, `'Made Shot'`,
  `'Shooting Foul'`, `'End Period'`). My translator normalizes these to
  the canonical lowercase vocabulary defined in `CONTRACT_STINTS.md`
  (`tipoff`, `made_2pt`, `made_3pt`, `missed_2pt`, `missed_3pt`, `ft_made`,
  `ft_miss`, `rebound_off`, `rebound_def`, `turnover`, `shooting_foul`,
  `sub`, `period_end`, `game_end`).
- Sub rows (per espn-lane Q1 answer @ 20a28d9): `event_type = 'Substitution'`,
  `player_id` = player **IN**, `assist_player_id` = player **OUT**.
  No JSON extraction needed; both ids are first-class columns.
- `players_on_floor` JSONB is populated with `'[]'::jsonb` placeholder
  (espn-lane decision D2/option A). My deriver does **not** read this
  column — it computes lineups itself from starters + sub events. I may
  optionally back-fill it post-derive as a separate concern (out of scope
  this lane; file a follow-up bead if useful).
- Cached `data/cache/espn/summary/{game_id}.json` files (note: espn-lane
  decision D3 moved this from `data/raw/espn/` to `data/cache/espn/`).
  I'll read starters from
  `boxscore.players[].statistics[0].athletes[]` filtered to where
  `starter == true`.
- `games.pbp_status` — skip rows where `pbp_status = 'thin'`. Do not
  crash; emit a structured warning and continue.

**Open question NEW for espn-lane (route via athena):** the full
enumeration of `play.type.text` strings that appear in real ESPN PBP for
2022-23. I need it to write the canonical-vocabulary mapping. Specifically
the strings used for: tip-off, made/missed 2pt FG, made/missed 3pt FG,
made/missed FT, offensive rebound, defensive rebound, turnover, shooting
foul (distinct from non-shooting personal foul, which should NOT trigger
FT carry), end-of-period, end-of-game. If espn-lane can't enumerate up
front, I'll `SELECT DISTINCT event_type FROM pbp_events` once a single
game lands and round-trip with them. Either is fine — but the deriver
won't process real data until this vocab is pinned.

**Q1 (sub representation) — RESOLVED** @ 20a28d9.
**Q2 (pts semantics + dry-run JSON) — PENDING** brutus on nba-5ve.

## Two drivers (the new CLI surface)

```
nba stints derive --game-id <X> [--dry-run]
nba stints derive --season 2023 --team NYK [--dry-run] [--skip-existing]
```

Exit codes follow the existing typed-error convention in `nba/cli/main.py`.

### Single-game mode

1. Open one transaction.
2. `DELETE FROM lineup_stints WHERE game_id = $1` (idempotency).
3. Load:
   - `games` row → home_team_id, away_team_id, season.
   - All `pbp_events` for the game, ordered by `(quarter, sequence_no)`.
   - Starters from the cached summary JSON.
4. Translate DB rows → fixture-style event dicts (see "translator" below).
5. Call `derive_stints(events, starters_home, starters_away)`.
6. For each returned `Stint`:
   - `wall_start`/`wall_end` → game-clock `start_clock_seconds`/`end_clock_seconds`.
   - `home`/`away` tuples → `INTEGER[]` arrays + sha256 hashes.
   - `home_pts`/`away_pts` → store as-is. `pts = home_pts + away_pts`
     (total scored in stint). **Confirm with brutus** — `pts` is ambiguous
     between "total" and "signed margin"; flag in nba-5ve.
   - `possessions = possessions_home + possessions_away`.
7. Bulk INSERT. Commit.

### Season+team mode

Just a loop wrapper:
```
SELECT game_id FROM games
 WHERE season = $1
   AND (home_team_id = $team OR away_team_id = $team)
   AND pbp_status = 'ok'
 ORDER BY game_date
```
Drive each game with the single-game path. Continue on per-game failure with
a structured warning (do not abort the run).

`--skip-existing`: skip games where `SELECT 1 FROM lineup_stints WHERE
game_id = $1 LIMIT 1` already returns a row. Useful for resumable runs.
`--dry-run`: do the derivation and print row counts; rollback instead of commit.

## DB-row → event-dict translator

Lives in `nba/stints/translate.py`. **Partial implementation landed** —
clock-math helpers + `lineup_hash` are in place and unit-tested (`tests/
test_stints_translate.py`, 22 tests). What remains is the event-type
vocabulary mapping + the row-to-event-dict function, both blocked on
ESPN vocab enumeration (see open Q above).

Final public API:

```python
def pbp_rows_to_events(
    rows: list[dict],         # DB rows as dicts (psycopg row_factory=dict_row)
    home_team_id: int,
) -> list[dict]:
    ...
```

Per-row mapping:
- `t` = `game_to_wall(quarter, clock_seconds)` — see helpers (already
  landed and tested).
- `period` = `quarter`.
- `type` = `CANONICAL_TYPE[event_type]` (lookup table; unknown ESPN strings
  → drop the event with a structured warning so the deriver doesn't see
  rows it can't handle).
- `team` = `"home"` if `team_id == home_team_id` else `"away"`, or `None`
  for period boundaries / tipoff (team_id will be NULL there).
- `player` = `player_id`.
- For `sub` (canonical), unpack ESPN's convention:
  `player_in = row["player_id"]`, `player_out = row["assist_player_id"]`.
- For made/missed shots, **disambiguate 2pt vs 3pt** by `points_scored`:
  - `event_type='Made Shot'` + `points_scored=2` → `made_2pt`
  - `event_type='Made Shot'` + `points_scored=3` → `made_3pt`
  - `event_type='Missed Shot'` → look at the description / shot type
    (`raw->>'shootingPlay'` or similar — TBD with espn-lane); fallback
    is to emit `missed_2pt` since that's the modal case. Pin during vocab
    confirmation.
- `home_score`/`away_score` pass through.

Clock math (already implemented in `nba/stints/translate.py`):
- `game_to_wall(quarter, clock_seconds)` — DB game-clock → deriver wall-clock.
- `wall_to_game(quarter, wall_seconds)` — deriver wall-clock → DB game-clock.
- Regulation quarters = 720s, OT = 300s, supports any `quarter >= 1`.

`Stint.wall_start` < `wall_end` (ascending) → in game-clock,
`start_clock_seconds` > `end_clock_seconds` (descending), which satisfies the
schema `CHECK (start_clock_seconds >= end_clock_seconds)`.

## Lineup hash

**Landed in `nba/stints/translate.py`**, unit-tested (order-independence,
sha256 hex shape, schema regex match, accepts int or str input).

Canonicalization: sort player ids numerically, stringify, join with `,`,
sha256 hex. Same 5 players in any order produce the same hash — load-bearing
for the `nba lineup stats` query.

Pure-Python rather than `pgcrypto digest()` so the hash semantics live in
one place (Python) and the same function is used at write-time (driver)
and read-time (CLI query resolution).

## Real `nba lineup stats` SQL

Current stub at `nba/cli/main.py:149-180` returns hardcoded
`{stint_count: 12, possessions: 340, net_rating: 3.1, off_rating: 114.2,
def_rating: 111.1}`. Keep the JSON shape (frozen by slice-1 contract);
swap in real numbers.

Algorithm:
1. Resolve `--players P1..P5` to player_ids. Today the resolver is
   `_resolve_player(name)` against a hardcoded `KNOWN_PLAYERS` set. Replace
   with a query against `players.full_name` ILIKE (fuzzy on last name,
   exact on full name if provided). InvalidPlayerError on miss.
2. Compute the target hash from the 5 resolved player_ids.
3. Aggregate query — appears symmetrically for both sides:
   ```sql
   WITH side AS (
     SELECT
       'home'::text AS side,
       stint_id, season, possessions_home AS poss,
       possessions_away AS opp_poss,
       home_pts AS pts, away_pts AS opp_pts,
       duration_seconds
     FROM lineup_stints
     WHERE home_lineup_hash = $1 AND season = $2
     UNION ALL
     SELECT
       'away', stint_id, season, possessions_away,
       possessions_home, away_pts, home_pts, duration_seconds
     FROM lineup_stints
     WHERE away_lineup_hash = $1 AND season = $2
   )
   SELECT
     COUNT(*)                         AS stint_count,
     COALESCE(SUM(poss), 0)           AS possessions,
     COALESCE(SUM(opp_poss), 0)       AS opp_possessions,
     COALESCE(SUM(pts), 0)            AS pts_for,
     COALESCE(SUM(opp_pts), 0)        AS pts_against,
     COALESCE(SUM(duration_seconds),0)AS seconds
   FROM side;
   ```
4. Derived ratings:
   - `off_rating  = 100.0 * pts_for / possessions` (guard /0).
   - `def_rating  = 100.0 * pts_against / opp_possessions` (guard /0).
   - `net_rating  = off_rating - def_rating`.
5. Sparse-data check: if `possessions < 100` (≈ ⅔ of a game), keep the
   sparse warning that's already emitted but populate `n_effective` from
   the real number rather than the hardcoded `50 + 80*n_known` heuristic.
   The slice-1 contract test (`test_sparse_data_emits_structured_warning`)
   only checks the *shape* of the warning, so the number swap is safe.

## Schema validations to add (assertions, not migrations)

Pre-insert sanity:
- `home_lineup` has exactly 5 unique ints, all > 0. (Schema enforces length;
  uniqueness is extra defense — the deriver returns `frozenset` semantics
  but we materialize back to a sorted list of ints.)
- `start_clock_seconds >= end_clock_seconds >= 0`.
- `duration_seconds = (start_clock_seconds - end_clock_seconds)`.
- `home_team_id`/`away_team_id` match the game row.
- Sum-of-stints invariant per game (cheap post-insert): `SUM(home_pts +
  away_pts) == games.home_score + games.away_score`. **Warn**, do not
  abort — the deriver might be ±1 from a stat-correction edge case I
  haven't seen yet; that's exactly what the nba-9b2 gate exists to catch.

## nba-9b2 — validation against CtG + PBPStats

Two lineups to compare. Both are well-documented 2022-23 NYK lineups:

1. **Brunson – Quickley – Hart – Randle – Robinson**
   - The "small Robinson" closing group post-deadline (Feb 9 OG Anunoby
     trade was 2023-24, so for 2022-23 the analog is the trade-deadline
     Hart-inclusive starting unit). Cleaning the Glass lineup page lists
     per-100 off/def/net + possessions for this exact 5-man unit.
2. **Brunson – Quickley – Barrett – Randle – Robinson**
   - Pre-deadline starters (RJ Barrett at SF). High-minute lineup; ample
     CtG sample.

Source: cleaningtheglass.com requires login but the per-100 numbers are
visible; I'll cache screenshots / manual transcription into
`docs/stints_validation.md`. PBPStats is public for some endpoints —
https://www.pbpstats.com/wowy-combos/ supports lineup queries by team and
season. Manual lookup is fine per OVERSEER_BRIEF.

Tolerance from OVERSEER_BRIEF:
- ±5% — accept.
- ±5-10% — investigate but don't block.
- >10% — deriver bug; file a follow-up bead with a concrete game/stint
  where the divergence shows up.

Deliverables (gate the bead won't close without):
- `docs/stints_validation.md` with: two lineup-id rows; my numbers; CtG
  numbers; PBPStats numbers; deltas; verdict per row.
- One commit per row showing the SQL I ran to extract my numbers so future
  re-runs are reproducible.

## Coordination with brutus on nba-5ve

What I need brutus to pin in the contract test:
1. **Exit codes**: 0 success, 2 multi-statement (already standard), 3
   InvalidPlayerError, 4 EraOutOfRangeError, 5 InsufficientDataError (this
   one for "stint count too low" warnings; not used by `derive` itself).
2. **JSON shape for `nba stints derive --dry-run`**:
   ```json
   {
     "data": {"game_id": "...", "stints": <int>, "rows_written": 0},
     "warnings": [...],
     "meta": {...}
   }
   ```
3. **JSON shape for `nba stints derive --season ... --team ...`**:
   ```json
   {
     "data": {
       "season": 2023, "team": "NYK", "games_processed": 82,
       "games_skipped_thin": <int>, "stints_written": <int>
     },
     "warnings": [...],
     "meta": {...}
   }
   ```
4. **`pts` semantics in `lineup_stints`**: total scored vs. signed margin.
   My plan assumes total. Pin it.
5. **Sub player_in/out column or JSON path** — pin this via Lane A's
   contract, not mine, but the stints CLI contract should reference
   whichever it ends up being so the integration is testable.

Send these as one message to brutus via athena when nba-kve is close;
brutus likes to write the red phase before the lane starts.

## File layout

```
nba/stints/
  derive.py        # exists; 9/9 green; signature widened to Iterable[Any]
                   # starters so DB integer ids type-check.
  translate.py     # LANDED: clock math, lineup_hash, EVENT_TYPE_MAP /
                   # EVENT_TYPE_DROP for the 21 canonical strings, and
                   # pbp_rows_to_events(rows, home_team_id).
  persist.py       # LANDED: persist_stints(conn, stints) → int.
                   # DELETE-then-INSERT idempotency per game_id.
  drivers.py       # LANDED: derive_for_game(conn, game_id) and
                   # derive_for_season(conn, season, team_id). Tolerant of
                   # missing data; CLI handles InvalidGameError up front.
nba/cli/
  main.py          # cli-lane: register `nba stints derive`; replace
                   # lineup_stats stub. Re-export persist_stints.
docs/
  stints_plan.md          # THIS FILE
  stints_cli_seam.md      # NEW: integration contract for cli-lane
  stints_validation.md    # TODO: nba-9b2 deliverable
tests/
  test_stints.py            # 9/9 green (brutus nba-6gz)
  test_stints_translate.py  # 36 tests: clock math + hash + vocab + rows
  test_stints_persist.py    # 11 tests: idempotency + clock + hash + shape
  test_stints_drivers.py    # 5 tests: thin / missing-starters / live-fixture
```

`drivers.py` is the only module that touches both the deriver and the DB;
keep it the only one that knows about transactions. `derive.py` and
`translate.py` stay pure-fn / DB-agnostic.

## Sequencing

1. ✅ plan + bd notes; coordinate with brutus.
2. ✅ translate.py partial: clock math + lineup_hash + unit tests (no DB).
3. (gate) wait on nba-kve **and** ESPN vocab confirmation.
4. translate.py complete: add `CANONICAL_TYPE` lookup + `pbp_rows_to_events`.
   Unit-test against fixture rows shaped like real DB rows.
5. persist.py + unit tests for INSERT + idempotency (psycopg over a
   transactional fixture, infra-lane's local Postgres).
6. drivers.py — single-game first; manual smoke against one ingested NYK
   game.
7. season loop. Smoke against full NYK 2022-23.
8. Replace `lineup_stats` stub. Slice-1 contract tests stay green.
9. nba-9b2 validation; commit `docs/stints_validation.md`.
10. Hand off to athena; Lane C unblocks.

## Risks I'm tracking

- **Sub representation in pbp_events.** Open Q with espn-lane.
- **Event-type vocabulary.** Lane A's normalization must hit our canonical
  set exactly or the deriver no-ops on unknown types. Coordinate via brutus's
  contract.
- **Free-throw carry across subs.** Already handled in the deriver; just
  noting that real PBP has 1-shot / 2-shot / 3-shot / and-1 patterns that
  the fixture doesn't fully exercise. The Oliver formula has ±1 tolerance,
  but the *attribution* edge case (which stint owns the FT) needs spot-
  checking in a real game where this happens late in a stint. Cherry-pick
  one such game in the smoke test.
- **OT periods.** Quarter length 300s, not 720s. `_wall` / `_game_clock`
  branch on `quarter > 4`. Add a real-OT-game to the smoke test if NYK
  played any in 2022-23 (they did — file the game_id in this doc once
  ingest lands).
- **CtG / PBPStats sample-size mismatch.** They include playoffs / different
  cut dates. Pin a date range in the validation queries so the comparison
  is apples-to-apples.
