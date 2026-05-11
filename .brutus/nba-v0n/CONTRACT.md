# CONTRACT — nba-v0n: nba players similar / search / career

**Author:** brutus
**Implementer:** cli-lane (nba-g0s) via athena
**Status:** red captured. Tests must turn green by satisfying the shape below.

## Spec restatement

Three new `nba players` subcommands feed the web GUI picker. Each must emit
exactly one JSON document on **stdout** with the standard `{data, warnings,
meta}` envelope from `nba/contracts.py`, and must parse cleanly into the new
pydantic models added there: `SimilarOutput`, `PlayersSearchOutput`,
`PlayersCareerOutput`. Typed errors print one JSON line on **stderr** with
`{error, message, context}` and exit non-zero per the existing `EXIT_CODES`
table.

Stubbed data is fine as long as the shape is honored and the documented
warning codes are used to signal missing real data.

## Files

- `nba/contracts.py` — adds `SimilarNeighbor`, `SimilarData`, `SimilarOutput`,
  `PlayersSearchResult`, `PlayersSearchData`, `PlayersSearchOutput`,
  `PlayersCareerSeason`, `PlayersCareerData`, `PlayersCareerOutput`.
- `tests/test_cli_contract.py` — adds 9 new black-box tests covering shape,
  ordering, k-cap, optional warnings, and unknown-id errors.

## Run command

```bash
.venv/bin/python -m pytest tests/test_cli_contract.py -v \
    -k "players_similar or players_search or players_career or contract_models_importable"
```

(or the full file: `.venv/bin/python -m pytest tests/test_cli_contract.py -v`)

## Subcommand contracts

### `nba players similar --id ID --k K`

Returns `SimilarOutput`:
```
{
  data: {neighbors: [{player_id, name, season, distance: float} ...]},
  warnings: [...],
  meta: {...}
}
```

Pinned behavior:
- `len(neighbors) <= K`.
- `neighbors` sorted **ascending** by `distance`.
- Unknown id → exit 3, stderr `{"error": "InvalidPlayerError", ...}` with the
  queried id surfaced in `message` or `context`.
- May emit a `random_init_embeddings` warning until real embeddings land. The
  web GUI keys off this code to render an empty-state hint in the Similar tab.

### `nba players search --q QUERY`

Returns `PlayersSearchOutput`:
```
{
  data: {results: [{player_id, name, season} ...]},
  warnings: [...],
  meta: {...}
}
```

Pinned behavior:
- Empty `results` is valid; no error is raised on no-match queries.
- May emit a `no_matches` warning when `results` is empty. The web GUI keys
  off `len(results) == 0` for the empty state.

### `nba players career --id ID`

Returns `PlayersCareerOutput`:
```
{
  data: {
    player_id, name,
    seasons: [{season, team, games, mpg, ppg, rpg, apg} ...]
  },
  warnings: [...],
  meta: {...}
}
```

Pinned behavior:
- `games`, `mpg`, `ppg`, `rpg`, `apg` may each be `null` independently.
- Unknown id → exit 3 `InvalidPlayerError` (same shape as `players show`).
- May emit a `facts_table_empty` warning when all stats are null.

## Oracle

A run is "correct" when:

1. Every `_stdout_json` call returns exit 0 and JSON that parses cleanly into
   the declared model (`SimilarOutput` / `PlayersSearchOutput` /
   `PlayersCareerOutput`).
2. `test_players_similar_returns_valid_shape` sees neighbors sorted ascending
   by distance and `len <= K`.
3. `test_players_similar_honors_k` sees `len(neighbors) <= 2` for `--k 2`.
4. `test_players_search_empty_query_returns_envelope_no_error` returns exit 0
   for a junk query — no exception, no error envelope.
5. Both unknown-id tests return exit 3 with `error == "InvalidPlayerError"`
   and surface the queried id in `message` or `context`.
6. If any of the optional warning codes (`random_init_embeddings`,
   `no_matches`, `facts_table_empty`) are emitted, each warning's `message`
   field is non-empty.

## Out of scope

- Real embeddings, real facts table. Stubbed/random neighbors and null stats
  are fine as long as the shape is honored.
- The web GUI itself — web-core-lane consumes this CLI; cli-lane does not
  touch frontend code.
- `--human` pretty-printed mode. Phase-2 surface, not under contract here.
- Changing existing subcommand shapes (`schema`, `sql`, `lineup stats`, `sim`,
  `players show`, `ingest season`, `stints derive`). This addendum is purely
  additive.

## Red transcript

`.brutus/nba-v0n/transcript.md` — 9 failing tests, 1 passing model-importability
smoke. All 9 failures are `"No such command 'similar' / 'search' / 'career'"`
from Typer (exit 2 from the parent `players` group). That's the right red:
the behavior is missing.

## Addendum to top-level CONTRACT.md

See the `## Addendum: nba-v0n (players similar / search / career)` section
appended to the project-root `CONTRACT.md` for the user-facing exit-code and
shape summary that mirrors this contract.
