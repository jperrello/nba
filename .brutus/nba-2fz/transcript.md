# cli-lane (nba-2fz) red transcript

*2026-05-12T18:14:52Z by Showboat 0.6.1*
<!-- showboat-id: a73ff179-b8a6-4f6a-bcd3-c98ce0e6d744 -->

Spec (brutus restatement): nba.cli.live exposes (1) run_daemon(*, stop_after_ticks, log_path, human, now_provider) wrapping public live.tick() in a while-True with try/except, derives cadence from scoreboard signals (POLL_INTERVAL_SEC in active window, IDLE_INTERVAL_SEC otherwise), writes one JSONL line per cycle to log_path with envelope {type, ts, ...TickResult} for ticks and {type, ts, traceback} for failures; (2) hard-fail counter increments on errors-non-empty ticks AND on tick() raising, fires _notify+_bd_create exactly once at threshold=10 consecutive, resets on any clean tick; (3) run_train_embeddings/run_train_predictor adapters shell into nba.train.embeddings.run / nba.train.predictor.run and return their envelopes. Seams (_tick, _sleeper, _notify, _bd_create) are module attrs monkeypatched in tests.

```bash
python3 -m pytest tests/test_cli_live.py --no-header --tb=line -q 2>&1 | tail -25
```

```output
     +  where 1 = <Result NotImplementedError('brutus contract nba-2fz: implementer must complete')>.exit_code
/Users/jperr/Documents/nba/tests/test_cli_live.py:206: AssertionError:
E   AssertionError: 
    assert 1 == 0
     +  where 1 = <Result NotImplementedError('brutus contract nba-2fz: implementer must complete')>.exit_code
/Users/jperr/Documents/nba/tests/test_cli_live.py:232: AssertionError:
E   AssertionError: 
    assert 1 == 0
     +  where 1 = <Result NotImplementedError('brutus contract nba-2fz: implementer must complete')>.exit_code
/Users/jperr/Documents/nba/tests/test_cli_live.py:259: AssertionError:
E   AssertionError: daemon must NOT crash on tick exceptions; got exit 1
    assert 1 == 0
     +  where 1 = <Result NotImplementedError('brutus contract nba-2fz: implementer must complete')>.exit_code
/Users/jperr/Documents/nba/tests/test_cli_live.py:291: AssertionError: daemon must NOT crash on tick exceptions; got exit 1
E   FileNotFoundError: [Errno 2] No such file or directory: '/private/var/folders/zs/6ms437qs2nd0sdk8knf1lgwr0000gp/T/pytest-of-jperr/pytest-9/test_every_log_line_parses_as_0/ingest.log'
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:771: FileNotFoundError: [Errno 2] No such file or directory: '/private/var/folders/zs/6ms437qs2nd0sdk8knf1lgwr0000gp/T/pytest-of-jperr/pytest-9/test_every_log_line_parses_as_0/ingest.log'
=========================== short test summary info ============================
FAILED tests/test_cli_live.py::test_daemon_writes_one_jsonl_line_per_tick - A...
FAILED tests/test_cli_live.py::test_daemon_log_line_is_pure_json - FileNotFou...
FAILED tests/test_cli_live.py::test_hard_fail_fires_notify_and_bd_after_10_consecutive
FAILED tests/test_cli_live.py::test_hard_fail_does_not_fire_below_threshold
FAILED tests/test_cli_live.py::test_hard_fail_counter_resets_on_clean_tick - ...
FAILED tests/test_cli_live.py::test_hard_fail_on_tick_raising - AssertionErro...
FAILED tests/test_cli_live.py::test_every_log_line_parses_as_json - FileNotFo...
7 failed, 7 passed in 0.15s
```
