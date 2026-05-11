# brutus contract nba-bbq: embeddings_player post-train smoke (red phase)

*2026-05-11T20:32:58Z by Showboat 0.6.1*
<!-- showboat-id: ceb7b5d0-c054-4c53-a1e0-ee295d37276a -->

DB-state contract, NOT CLI shape (nba/contracts.py untouched — frozen surface). Gated by NBA_EMBEDDINGS_SMOKE=1 + live local Postgres at nba.config.db().url. Test file: tests/test_embeddings_smoke.py. Pinned assertions: (1) row count for season=2023 latest-model_version filtered to NYK 2022-23 roster cohort == COUNT(DISTINCT player_id) FROM rosters WHERE season=2023 AND team_id=18 (currently 19); (2) embedding dim == 128 via vector_dims(); (3) each embedding L2-normalized to unit length (||v||-1 < 1e-3); (4) season column value == 2023 (D1 end-year) on every row + never NULL. Filed per D4 ruling — training is a script entrypoint, not a CLI subcommand. Red below: embeddings_player is empty (0 rows) before ml-lane runs training.

```bash
NBA_EMBEDDINGS_SMOKE=1 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest tests/test_embeddings_smoke.py -v --tb=short --no-header
```

```output
============================= test session starts ==============================
collecting ... collected 5 items

tests/test_embeddings_smoke.py::test_row_count_matches_rostered_players ERROR [ 20%]
tests/test_embeddings_smoke.py::test_embedding_dim_is_128 ERROR          [ 40%]
tests/test_embeddings_smoke.py::test_vectors_are_l2_normalized ERROR     [ 60%]
tests/test_embeddings_smoke.py::test_season_column_value_is_end_year ERROR [ 80%]
tests/test_embeddings_smoke.py::test_season_column_never_null ERROR      [100%]

==================================== ERRORS ====================================
__________ ERROR at setup of test_row_count_matches_rostered_players ___________
tests/test_embeddings_smoke.py:67: in latest_model_version
    pytest.fail(
E   Failed: embeddings_player has no rows for season=2023; ml-lane training has not produced output yet.
_________________ ERROR at setup of test_embedding_dim_is_128 __________________
tests/test_embeddings_smoke.py:67: in latest_model_version
    pytest.fail(
E   Failed: embeddings_player has no rows for season=2023; ml-lane training has not produced output yet.
_______________ ERROR at setup of test_vectors_are_l2_normalized _______________
tests/test_embeddings_smoke.py:67: in latest_model_version
    pytest.fail(
E   Failed: embeddings_player has no rows for season=2023; ml-lane training has not produced output yet.
____________ ERROR at setup of test_season_column_value_is_end_year ____________
tests/test_embeddings_smoke.py:67: in latest_model_version
    pytest.fail(
E   Failed: embeddings_player has no rows for season=2023; ml-lane training has not produced output yet.
_______________ ERROR at setup of test_season_column_never_null ________________
tests/test_embeddings_smoke.py:67: in latest_model_version
    pytest.fail(
E   Failed: embeddings_player has no rows for season=2023; ml-lane training has not produced output yet.
=========================== short test summary info ============================
ERROR tests/test_embeddings_smoke.py::test_row_count_matches_rostered_players
ERROR tests/test_embeddings_smoke.py::test_embedding_dim_is_128 - Failed: emb...
ERROR tests/test_embeddings_smoke.py::test_vectors_are_l2_normalized - Failed...
ERROR tests/test_embeddings_smoke.py::test_season_column_value_is_end_year - ...
ERROR tests/test_embeddings_smoke.py::test_season_column_never_null - Failed:...
============================== 5 errors in 0.11s ===============================
```

GREEN PHASE — ml-lane closed nba-ibw at 7bed00c. embeddings_player now has 463 rows (model_version=embeddings-v0-randinit, dim=128, L2-norm within 1e-7), all 19 NYK 2022-23 rostered players covered, season=2023 on every row.

```bash
NBA_EMBEDDINGS_SMOKE=1 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest tests/test_embeddings_smoke.py -v --tb=short --no-header
```

```output
============================= test session starts ==============================
collecting ... collected 5 items

tests/test_embeddings_smoke.py::test_row_count_matches_rostered_players PASSED [ 20%]
tests/test_embeddings_smoke.py::test_embedding_dim_is_128 PASSED         [ 40%]
tests/test_embeddings_smoke.py::test_vectors_are_l2_normalized PASSED    [ 60%]
tests/test_embeddings_smoke.py::test_season_column_value_is_end_year PASSED [ 80%]
tests/test_embeddings_smoke.py::test_season_column_never_null PASSED     [100%]

============================== 5 passed in 0.08s ===============================
```
