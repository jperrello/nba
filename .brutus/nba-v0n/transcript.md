# nba-v0n: players similar/search/career — red phase

*2026-05-11T22:19:37Z by Showboat 0.6.1*
<!-- showboat-id: 3e0ca3f2-dbd9-4611-ac02-c185ff69809b -->

Spec (falsifiable): three new `nba players` subcommands must each emit the standard {data,warnings,meta} envelope per nba/contracts.py and validate against three new pydantic models (SimilarOutput, PlayersSearchOutput, PlayersCareerOutput).

- `nba players similar --id ID --k K` → data.neighbors=[{player_id,name,season,distance:float}], len≤K, ascending distance. Unknown id → exit 3 InvalidPlayerError. Optional warning code 'random_init_embeddings'.
- `nba players search --q QUERY` → data.results=[{player_id,name,season}]. Empty list OK. Optional warning code 'no_matches'.
- `nba players career --id ID` → data={player_id,name,seasons:[{season,team,games|null,mpg|null,ppg|null,rpg|null,apg|null}]}. Unknown id → exit 3 InvalidPlayerError. Optional warning code 'facts_table_empty'.

Red oracle: pytest -k 'players_similar or players_search or players_career' must fail because the typer subcommands do not exist ("No such command 'similar' / 'search' / 'career'"), not because of any test-side import/typo error. The contract_models_importable smoke test is allowed to pass — that's by design (the models were added in nba/contracts.py before the implementer touches anything).

```bash
.venv/bin/python -m pytest tests/test_cli_contract.py -v -k 'players_similar or players_search or players_career or contract_models_importable' 2>&1 | tail -60
```

```output
    def test_players_career_facts_table_empty_warning_is_allowed():
        """Until facts is populated, the implementer may return seasons with null
        stats and emit a facts_table_empty warning. Validate the shape either way."""
        result = runner.invoke(app, ["players", "career", "--id", KNOWN_PLAYER_ID])
>       payload = _stdout_json(result)
                  ^^^^^^^^^^^^^^^^^^^^

tests/test_cli_contract.py:386: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = <Result SystemExit(2)>

    def _stdout_json(result):
>       assert result.exit_code == 0, (
            f"expected exit 0, got {result.exit_code}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
E       AssertionError: expected exit 0, got 2
E         stdout=''
E         stderr="Usage: root players [OPTIONS] COMMAND [ARGS]...\nTry 'root players --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'career'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E       assert 2 == 0
E        +  where 2 = <Result SystemExit(2)>.exit_code

tests/test_cli_contract.py:31: AssertionError
__________ test_players_career_unknown_id_raises_invalid_player_error __________

    def test_players_career_unknown_id_raises_invalid_player_error():
        result = runner.invoke(app, ["players", "career", "--id", "zzz-not-a-player"])
>       parsed = _stderr_error(result, exit_code=3, error_code="InvalidPlayerError")
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_cli_contract.py:395: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = <Result SystemExit(2)>, exit_code = 3
error_code = 'InvalidPlayerError'

    def _stderr_error(result, exit_code, error_code):
>       assert result.exit_code == exit_code, (
            f"expected exit {exit_code}, got {result.exit_code}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
E       AssertionError: expected exit 3, got 2
E         stdout=''
E         stderr="Usage: root players [OPTIONS] COMMAND [ARGS]...\nTry 'root players --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'career'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E       assert 2 == 3
E        +  where 2 = <Result SystemExit(2)>.exit_code

tests/test_cli_contract.py:39: AssertionError
=========================== short test summary info ============================
FAILED tests/test_cli_contract.py::test_players_similar_returns_valid_shape
FAILED tests/test_cli_contract.py::test_players_similar_honors_k - AssertionE...
FAILED tests/test_cli_contract.py::test_players_similar_random_init_warning_is_allowed
FAILED tests/test_cli_contract.py::test_players_similar_unknown_id_raises_invalid_player_error
FAILED tests/test_cli_contract.py::test_players_search_returns_valid_shape - ...
FAILED tests/test_cli_contract.py::test_players_search_empty_query_returns_envelope_no_error
FAILED tests/test_cli_contract.py::test_players_career_returns_valid_shape - ...
FAILED tests/test_cli_contract.py::test_players_career_facts_table_empty_warning_is_allowed
FAILED tests/test_cli_contract.py::test_players_career_unknown_id_raises_invalid_player_error
================== 9 failed, 1 passed, 13 deselected in 0.31s ==================
```

Green phase — cli-lane landed implementation at 36e40e4. Re-running the contract suite against the same -k filter used to capture red.

```bash
.venv/bin/python -m pytest tests/test_cli_contract.py -v -k 'players_similar or players_search or players_career or contract_models_importable' 2>&1 | tail -20
```

```output
platform darwin -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0 -- /Users/jperr/Documents/nba/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/jperr/Documents/nba
configfile: pyproject.toml
plugins: asyncio-1.3.0, respx-0.23.1, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 23 items / 13 deselected / 10 selected

tests/test_cli_contract.py::test_players_similar_returns_valid_shape PASSED [ 10%]
tests/test_cli_contract.py::test_players_similar_honors_k PASSED         [ 20%]
tests/test_cli_contract.py::test_players_similar_random_init_warning_is_allowed PASSED [ 30%]
tests/test_cli_contract.py::test_players_similar_unknown_id_raises_invalid_player_error PASSED [ 40%]
tests/test_cli_contract.py::test_players_search_returns_valid_shape PASSED [ 50%]
tests/test_cli_contract.py::test_players_search_empty_query_returns_envelope_no_error PASSED [ 60%]
tests/test_cli_contract.py::test_players_career_returns_valid_shape PASSED [ 70%]
tests/test_cli_contract.py::test_players_career_facts_table_empty_warning_is_allowed PASSED [ 80%]
tests/test_cli_contract.py::test_players_career_unknown_id_raises_invalid_player_error PASSED [ 90%]
tests/test_cli_contract.py::test_contract_models_importable PASSED       [100%]

====================== 10 passed, 13 deselected in 0.16s =======================
```
