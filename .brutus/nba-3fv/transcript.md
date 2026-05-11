# brutus contract nba-3fv: nba CLI JSON output shape (red phase)

*2026-05-11T18:44:48Z by Showboat 0.6.1*
<!-- showboat-id: 4c983315-9133-4a29-b2d8-add74a5bb64b -->

Contract: nba CLI must return typed JSON via the envelope {data,warnings,meta} for each subcommand (schema, sql, lineup stats, sim, players show), with typed errors on stderr and stable exit codes. Pydantic shapes live in nba/contracts.py. Red phase below: all subcommand tests fail because the Typer app exposes no subcommands yet (Click exits 2 with 'No such command'). 2 smoke tests (model importability, error-code validation) pass — those are non-behavior assertions.

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest tests/test_cli_contract.py -v --tb=short --no-header
```

```output
============================= test session starts ==============================
collecting ... collected 14 items

tests/test_cli_contract.py::test_schema_returns_valid_shape FAILED       [  7%]
tests/test_cli_contract.py::test_schema_table_filter_restricts_output FAILED [ 14%]
tests/test_cli_contract.py::test_sql_select_returns_valid_shape FAILED   [ 21%]
tests/test_cli_contract.py::test_sql_multistatement_is_rejected FAILED   [ 28%]
tests/test_cli_contract.py::test_lineup_stats_returns_valid_shape FAILED [ 35%]
tests/test_cli_contract.py::test_lineup_stats_pre_2003_season_raises_era_error FAILED [ 42%]
tests/test_cli_contract.py::test_sim_returns_valid_shape FAILED          [ 50%]
tests/test_cli_contract.py::test_sim_with_scouting_includes_take FAILED  [ 57%]
tests/test_cli_contract.py::test_sim_no_scouting_omits_take_and_skips_lm FAILED [ 64%]
tests/test_cli_contract.py::test_players_show_returns_valid_shape FAILED [ 71%]
tests/test_cli_contract.py::test_players_show_unknown_player_raises_invalid_player_error FAILED [ 78%]
tests/test_cli_contract.py::test_sparse_data_emits_structured_warning FAILED [ 85%]
tests/test_cli_contract.py::test_contract_models_importable PASSED       [ 92%]
tests/test_cli_contract.py::test_error_payload_rejects_unknown_error_code PASSED [100%]

=================================== FAILURES ===================================
_______________________ test_schema_returns_valid_shape ________________________
tests/test_cli_contract.py:66: in test_schema_returns_valid_shape
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'schema'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
__________________ test_schema_table_filter_restricts_output ___________________
tests/test_cli_contract.py:87: in test_schema_table_filter_restricts_output
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'schema'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
_____________________ test_sql_select_returns_valid_shape ______________________
tests/test_cli_contract.py:99: in test_sql_select_returns_valid_shape
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'sql'.                                                       │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
_____________________ test_sql_multistatement_is_rejected ______________________
tests/test_cli_contract.py:108: in test_sql_multistatement_is_rejected
    _stderr_error(result, exit_code=2, error_code="MultiStatementError")
tests/test_cli_contract.py:40: in _stderr_error
    payload = json.loads(result.stderr.strip().splitlines()[-1])
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/json/__init__.py:352: in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/json/decoder.py:345: in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/json/decoder.py:363: in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
E   json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
____________________ test_lineup_stats_returns_valid_shape _____________________
tests/test_cli_contract.py:133: in test_lineup_stats_returns_valid_shape
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'lineup'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
______________ test_lineup_stats_pre_2003_season_raises_era_error ______________
tests/test_cli_contract.py:160: in test_lineup_stats_pre_2003_season_raises_era_error
    _stderr_error(result, exit_code=4, error_code="EraOutOfRangeError")
tests/test_cli_contract.py:36: in _stderr_error
    assert result.exit_code == exit_code, (
E   AssertionError: expected exit 4, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'lineup'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 4
E    +  where 2 = <Result SystemExit(2)>.exit_code
_________________________ test_sim_returns_valid_shape _________________________
tests/test_cli_contract.py:176: in test_sim_returns_valid_shape
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'sim'.                                                       │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
_____________________ test_sim_with_scouting_includes_take _____________________
tests/test_cli_contract.py:195: in test_sim_with_scouting_includes_take
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'sim'.                                                       │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
_________________ test_sim_no_scouting_omits_take_and_skips_lm _________________
tests/test_cli_contract.py:215: in test_sim_no_scouting_omits_take_and_skips_lm
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'sim'.                                                       │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
____________________ test_players_show_returns_valid_shape _____________________
tests/test_cli_contract.py:229: in test_players_show_returns_valid_shape
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'players'.                                                   │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
_________ test_players_show_unknown_player_raises_invalid_player_error _________
tests/test_cli_contract.py:238: in test_players_show_unknown_player_raises_invalid_player_error
    parsed = _stderr_error(result, exit_code=3, error_code="InvalidPlayerError")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:36: in _stderr_error
    assert result.exit_code == exit_code, (
E   AssertionError: expected exit 3, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'players'.                                                   │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 3
E    +  where 2 = <Result SystemExit(2)>.exit_code
__________________ test_sparse_data_emits_structured_warning ___________________
tests/test_cli_contract.py:267: in test_sparse_data_emits_structured_warning
    payload = _stdout_json(result)
              ^^^^^^^^^^^^^^^^^^^^
tests/test_cli_contract.py:28: in _stdout_json
    assert result.exit_code == 0, (
E   AssertionError: expected exit 0, got 2
E     stdout=''
E     stderr="Usage: root [OPTIONS] COMMAND [ARGS]...\nTry 'root --help' for help.\n╭─ Error ──────────────────────────────────────────────────────────────────────╮\n│ No such command 'lineup'.                                                    │\n╰──────────────────────────────────────────────────────────────────────────────╯\n"
E   assert 2 == 0
E    +  where 2 = <Result SystemExit(2)>.exit_code
=========================== short test summary info ============================
FAILED tests/test_cli_contract.py::test_schema_returns_valid_shape - Assertio...
FAILED tests/test_cli_contract.py::test_schema_table_filter_restricts_output
FAILED tests/test_cli_contract.py::test_sql_select_returns_valid_shape - Asse...
FAILED tests/test_cli_contract.py::test_sql_multistatement_is_rejected - json...
FAILED tests/test_cli_contract.py::test_lineup_stats_returns_valid_shape - As...
FAILED tests/test_cli_contract.py::test_lineup_stats_pre_2003_season_raises_era_error
FAILED tests/test_cli_contract.py::test_sim_returns_valid_shape - AssertionEr...
FAILED tests/test_cli_contract.py::test_sim_with_scouting_includes_take - Ass...
FAILED tests/test_cli_contract.py::test_sim_no_scouting_omits_take_and_skips_lm
FAILED tests/test_cli_contract.py::test_players_show_returns_valid_shape - As...
FAILED tests/test_cli_contract.py::test_players_show_unknown_player_raises_invalid_player_error
FAILED tests/test_cli_contract.py::test_sparse_data_emits_structured_warning
========================= 12 failed, 2 passed in 0.18s =========================
```
