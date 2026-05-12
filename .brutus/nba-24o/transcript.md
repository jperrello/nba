# infra-lane (nba-24o) red transcript

*2026-05-12T18:24:34Z by Showboat 0.6.1*
<!-- showboat-id: df3b4846-a971-4f2a-87f9-3c5f3c6b6b4e -->

Spec: infra/launchd/com.nba.ingest.live.plist with __HOME__ placeholder + Makefile install-daemon/uninstall-daemon targets. Stub plist has Label + parse-validity only; implementer fills RunAtLoad, KeepAlive, StandardOutPath/StandardErrorPath (both with __HOME__), ProgramArguments invoking 'nba ingest live'. Makefile install-daemon must sed __HOME__ → $HOME at install time.

```bash
python3 -m pytest tests/test_infra_daemon.py --no-header --tb=line -q 2>&1 | tail -15
```

```output
     +    and   re.MULTILINE = re.MULTILINE
/Users/jperr/Documents/nba/tests/test_infra_daemon.py:119: AssertionError: Makefile must declare an `uninstall-daemon:` target
E   AssertionError: install-daemon target body must be present
    assert None
/Users/jperr/Documents/nba/tests/test_infra_daemon.py:133: AssertionError: install-daemon target body must be present
=========================== short test summary info ============================
FAILED tests/test_infra_daemon.py::test_plist_run_at_load_true - AssertionErr...
FAILED tests/test_infra_daemon.py::test_plist_keep_alive_true - AssertionErro...
FAILED tests/test_infra_daemon.py::test_plist_standard_out_path_uses_home_placeholder
FAILED tests/test_infra_daemon.py::test_plist_standard_error_path_uses_home_placeholder
FAILED tests/test_infra_daemon.py::test_plist_program_arguments_invokes_nba_ingest_live
FAILED tests/test_infra_daemon.py::test_makefile_has_install_daemon_target - ...
FAILED tests/test_infra_daemon.py::test_makefile_has_uninstall_daemon_target
FAILED tests/test_infra_daemon.py::test_makefile_install_daemon_substitutes_home_placeholder
8 failed, 2 passed in 0.01s
```
