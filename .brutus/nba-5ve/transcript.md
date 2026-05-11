# brutus contract nba-5ve: slice-2 contracts (ingest + stints CLI + typed errors) — red phase

*2026-05-11T19:50:57Z by Showboat 0.6.1*
<!-- showboat-id: aec2c072-0b23-4f1c-86c1-07bb25ff6410 -->

Three contracts bundled. (1) tests/test_ingest_contract.py: nba ingest season --team NYK --season 2023 [--dry-run] envelope, idempotency, dry-run no-DB-connect via psycopg.connect monkeypatch, thin_pbp warning shape, InvalidTeamError exit 6, EraOutOfRangeError exit 4. (2) tests/test_stints_cli_contract.py: nba stints derive in two modes (--game-id | --season+--team), persistence via psycopg.connect + nba.cli.main.persist_stints seam, idempotency, InvalidGameError exit 8, and the stints-lane pin: per-side pts_home/pts_away preserved through persistence (NOT collapsed to signed margin). (3) tests/test_typed_errors_contract.py: every parse error wraps to ErrorPayload JSON on stderr with stable exit codes from nba.contracts.EXIT_CODES (2-9 distinct). No Python tracebacks. Covers the carried 'nba sim --team1 wat' bug. New error codes: InvalidTeamError(6), InvalidSeasonError(7), InvalidGameError(8), IngestError(9). Slice-1 14/14 stays green throughout (no regression).

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest tests/test_ingest_contract.py tests/test_stints_cli_contract.py tests/test_typed_errors_contract.py tests/test_cli_contract.py --tb=no --no-header -q
```

```output
FFFFFFFFFFFFFFFFFFFF..FFFFFF....FF.F...FF..............                  [100%]
=========================== short test summary info ============================
FAILED tests/test_ingest_contract.py::test_ingest_season_dry_run_returns_envelope
FAILED tests/test_ingest_contract.py::test_ingest_season_data_block_has_per_table_counts
FAILED tests/test_ingest_contract.py::test_ingest_season_dry_run_opens_no_db_connection
FAILED tests/test_ingest_contract.py::test_ingest_season_dry_run_is_idempotent
FAILED tests/test_ingest_contract.py::test_ingest_season_thin_pbp_emits_structured_warning
FAILED tests/test_ingest_contract.py::test_ingest_season_bad_team_raises_invalid_team_error
FAILED tests/test_ingest_contract.py::test_ingest_season_pre_2003_raises_era_error
FAILED tests/test_ingest_contract.py::test_ingest_dry_run_meta_distinguishes_modes
FAILED tests/test_ingest_contract.py::test_ingest_season_writes_db_when_not_dry_run
FAILED tests/test_stints_cli_contract.py::test_stints_derive_by_game_id_returns_envelope
FAILED tests/test_stints_cli_contract.py::test_stints_derive_by_season_team_returns_envelope
FAILED tests/test_stints_cli_contract.py::test_stints_derive_data_block_has_counts
FAILED tests/test_stints_cli_contract.py::test_stints_derive_writes_to_db - A...
FAILED tests/test_stints_cli_contract.py::test_stints_derive_idempotent - Ass...
FAILED tests/test_stints_cli_contract.py::test_stints_derive_neither_mode_raises_invalid_team_error
FAILED tests/test_stints_cli_contract.py::test_stints_derive_both_modes_raises_typed_error
FAILED tests/test_stints_cli_contract.py::test_stints_derive_bad_team_raises_invalid_team_error
FAILED tests/test_stints_cli_contract.py::test_stints_derive_pre_2003_raises_era_error
FAILED tests/test_stints_cli_contract.py::test_stints_derive_bad_game_id_raises_invalid_game_error
FAILED tests/test_stints_cli_contract.py::test_stints_persistence_preserves_per_side_pts_not_margin
FAILED tests/test_typed_errors_contract.py::test_sim_malformed_teamspec_returns_typed_error[wat-InvalidTeamError]
FAILED tests/test_typed_errors_contract.py::test_sim_malformed_teamspec_returns_typed_error[knicks--InvalidSeasonError]
FAILED tests/test_typed_errors_contract.py::test_sim_malformed_teamspec_returns_typed_error[knicks-abc-InvalidSeasonError]
FAILED tests/test_typed_errors_contract.py::test_sim_malformed_teamspec_returns_typed_error[knicks-2024[swap=kat->randle-InvalidTeamError]
FAILED tests/test_typed_errors_contract.py::test_sim_malformed_teamspec_returns_typed_error[knicks-2024[swap=kat:randle]-InvalidTeamError]
FAILED tests/test_typed_errors_contract.py::test_sim_malformed_teamspec_returns_typed_error[knicks-2024[swap=kat->zzznobody]-InvalidPlayerError]
FAILED tests/test_typed_errors_contract.py::test_no_python_traceback_leaks_on_typed_error[argv0]
FAILED tests/test_typed_errors_contract.py::test_no_python_traceback_leaks_on_typed_error[argv1]
FAILED tests/test_typed_errors_contract.py::test_no_python_traceback_leaks_on_typed_error[argv3]
FAILED tests/test_typed_errors_contract.py::test_no_python_traceback_leaks_on_typed_error[argv7]
FAILED tests/test_typed_errors_contract.py::test_no_python_traceback_leaks_on_typed_error[argv8]
31 failed, 24 passed in 0.26s
```
