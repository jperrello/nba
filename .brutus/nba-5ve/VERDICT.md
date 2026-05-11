# VERDICT — nba-5ve: slice-2 contracts (ingest + stints CLI + typed errors)

**Status:** GREEN — confirmed by brutus.
**Verifier:** brutus.
**Verified at commit:** `8b3e44c` (tip of main at verification time).
**Transcript:** `.brutus/nba-5ve/transcript.md` (red + green phases).

## Slice results

| slice | tests | implementer | commit |
|---|---|---|---|
| `tests/test_ingest_contract.py` | 9/9 | espn-lane | `2059fa2` |
| `tests/test_stints_cli_contract.py` | 11/11 | cli-lane + stints-lane | `8b3e44c` (built on `112f415`) |
| `tests/test_typed_errors_contract.py` | 21/21 | cli-lane | `d5acc0a` (+ sweep at `8b3e44c`) |
| `tests/test_cli_contract.py` (slice-1 regression net) | 14/14 | — | unchanged, no regression |

Full repo suite: **169/169** at `8b3e44c`.

## Pins satisfied

- **Exit-code table** `nba.contracts.EXIT_CODES` 2..9 distinct, every declared
  `ErrorCode` mapped, every parse error routes through `ErrorPayload` JSON on
  stderr. No Python tracebacks leak. Carried bug `nba sim --team1 wat` →
  `InvalidTeamError` exit 6 ✓.
- **Ingest** `--dry-run` opens zero psycopg connections; data-block schema
  identical across modes; `meta.dry_run` is the sole discriminator. Idempotent.
- **Stints** persistence preserves per-side `pts_home`/`pts_away` (not collapsed
  to signed margin); routed through `nba.cli.main.persist_stints` seam.

## Caveat (carried from sign-off message, not brutus's concern)

`nba-kve` (espn-lane ingest impl) is functionally green on the contract but the
bead remains `in_progress` pending D1/D2 overseer ruling on the real-DB UPSERT
path + smoke test. That's an espn-lane / overseer matter; the **contract** side
of `nba-5ve` is closed.

Contract closed.
