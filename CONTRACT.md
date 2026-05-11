# CONTRACT — nba-3fv: nba CLI JSON output shape

**Author:** brutus
**Implementer:** cli-lane (nba-zg0)
**Status:** red captured. Tests must turn green by satisfying the shape below.

## Spec restatement

The `nba` CLI is agent-facing. Every successful subcommand prints exactly one JSON
document to **stdout** with the envelope `{data, warnings, meta}`. Typed errors
print a single JSON line to **stderr** with `{error, message, context}` and exit
non-zero with a code that's stable per error type. Pydantic models in
`nba/contracts.py` are the canonical shape — tests validate the JSON against
those models, and *passing* means the JSON parses cleanly into them with no
extra-field surprises.

## Files

- `nba/contracts.py` — pydantic shape models (SchemaOutput, SqlOutput,
  LineupStatsOutput, SimOutput with nested Score/WinProb/Matchup/TeamEdge,
  PlayersShowOutput, ErrorPayload).
- `tests/test_cli_contract.py` — black-box CliRunner tests asserting each
  subcommand's shape and each error's exit code.

## Run command

```bash
pytest tests/test_cli_contract.py -v
```

## Exit-code table

| code | meaning                                  |
|------|------------------------------------------|
| 0    | success                                  |
| 2    | MultiStatementError (nba sql)            |
| 3    | InvalidPlayerError (player not found)    |
| 4    | EraOutOfRangeError (season < 2003)       |

## Subcommand contracts

### `nba schema [--table NAME]`
Returns `SchemaOutput`:
```
{
  data: {
    tables: [{name, columns: [{name, type, nullable, fk}], primary_key, indices}],
    pgvector_dims: int
  },
  warnings: [],
  meta: {schema_version, ...}
}
```

Pinned to **docs/schema.md v1** (landed nba-byh @ 9cc00b1):
- `data.tables` is **exactly** the set `{players, teams, games, coaches,
  coach_games, rosters, pbp_events, lineup_stints, facts, sim_cache,
  embeddings_player}` — no more, no fewer.
- `data.pgvector_dims == 128`.
- Every table declares a non-empty `primary_key`.

`--table NAME` filters the `tables` list to exactly `[{name: NAME, ...}]`.

### `nba sql 'SELECT ...'`
Returns `SqlOutput`:
```
{
  data: {rows, columns, row_count},
  warnings: [],
  meta: {cached: bool, elapsed_ms: float, ...}
}
```
Multi-statement input (`SELECT 1; DROP TABLE x`) → exit 2, stderr JSON line
`{"error": "MultiStatementError", ...}`.

### `nba lineup stats --players P1 --players P2 ... --season Y`
Returns `LineupStatsOutput`:
```
{
  data: {stint_count: int, possessions: int, net_rating: float, ...},
  warnings: [...],
  meta: {...}
}
```
Pre-2003 season → exit 4, stderr `{"error": "EraOutOfRangeError", ...}`.
Sparse lineup → `warnings[]` contains `{"code": "sparse_data", "message": ..., "context": {"n_effective": <number>}}`.

### `nba sim --team1 SPEC --team2 SPEC [--no-scouting]`
Team spec example: `knicks-2024[swap=kat->randle,divincenzo]`.
Returns `SimOutput`:
```
{
  data: {
    score: {home, away},
    win_prob: {value, ci},
    matchups: [{home_player, away_player, edge, note} x5],
    team_edges: [{tag, sign, magnitude, label}],
    scouting_take: str | null
  },
  warnings: [...],
  meta: {model_versions: {...}, cached: bool, ...}
}
```
`--no-scouting` → `scouting_take` is null AND the LM is not called. Tests verify
no-LM-call by monkeypatching `nba.cli.main.generate_scouting_take` and asserting
call count zero. **Implementer requirement:** the scouting LM call site must live
behind a name resolvable at `nba.cli.main.generate_scouting_take` (re-export from
wherever, but expose that path for testability).

### `nba players show --name 'jalen brunson'`
Returns `PlayersShowOutput`:
```
{
  data: {player_id, name, seasons: [...]},
  warnings: [],
  meta: {...}
}
```
Unknown player → exit 3, stderr `{"error": "InvalidPlayerError", ...}` with the
queried name surfaced in `message` or `context`.

## Oracle

A run is "correct" when:
1. Every `_stdout_json` call returns exit 0 and JSON that parses cleanly into the
   declared pydantic model.
2. Every `_stderr_error` call returns the declared exit code and the last line of
   stderr parses into `ErrorPayload` with the matching `error` discriminator.
3. The `--no-scouting` test sees `scouting_take is None` AND `calls['n'] == 0`.
4. The sparse-data test finds at least one warning with `code == "sparse_data"`
   and a numeric `n_effective` in `context`.

## Out of scope

- Real data. Stubbed/placeholder values are fine as long as the shape is honored.
- Live LM, live DB. Tests are pure black-box on the JSON envelope.
- `--human` pretty-printed mode. That's a phase-2 surface and is not under
  contract here.
- Performance, caching strategy, model selection. Only the SHAPE is pinned.

## Red transcript

Captured at `.brutus/nba-3fv/transcript.md` (see "red sha" in bead notes).
