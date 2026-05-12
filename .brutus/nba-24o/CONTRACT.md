# CONTRACT — nba-24o (infra-lane)

**Brutus contract.** Implementer = infra-lane. No bypass.

## Spec restatement (falsifiable)

Two deliverables:

1. **`infra/launchd/com.nba.ingest.live.plist`** — a launchd property list
   for the live ingest daemon. Stub in place; implementer fills the
   required keys. The plist source uses `__HOME__` as a placeholder for
   `$HOME`; the Makefile substitutes at install time.

2. **`Makefile`** — adds `install-daemon` and `uninstall-daemon` targets.
   `install-daemon` does the `__HOME__` → `$HOME` sed substitution and
   places the rendered plist into `$(LAUNCHD_DEST)` (default
   `$(HOME)/Library/LaunchAgents`). `uninstall-daemon` removes it.
   `install-daemon` must be idempotent: unload-before-load so re-installs
   over an existing service don't fail.

## Oracle definition

Eleven tests in `tests/test_infra_daemon.py`. Key invariants:

**Plist content** (after rendering `__HOME__ → /Users/test`):
- File exists at `infra/launchd/com.nba.ingest.live.plist` and parses
  with `plistlib`.
- `Label == "com.nba.ingest.live"` (exact).
- `RunAtLoad is True`.
- `KeepAlive is True` (or a non-empty policy dict).
- `StandardOutPath` is a non-empty string and **contains the substituted
  home path** (i.e. the source plist used `__HOME__` and the substitution
  worked).
- `StandardErrorPath` is a non-empty string and contains the substituted
  home path.
- `ProgramArguments` is a non-empty list and its joined string contains
  `"nba"`, `"ingest"`, `"live"` (in any order, any positions).

**Makefile content**:
- Has an `install-daemon:` target line.
- Has an `uninstall-daemon:` target line.
- The `install-daemon` target body references `__HOME__` or `HOME` (i.e.
  performs the home-substitution step).

## Test files

- `tests/test_infra_daemon.py` — 11 tests.

## Run command

```bash
python3 -m pytest tests/test_infra_daemon.py -v
```

Green oracle: 11 passed, 0 failed.

## Captured red output

```
tests/test_infra_daemon.py ..FFFFFFFFFF                                  [100%]
short test summary info:
FAILED tests/test_infra_daemon.py::test_plist_run_at_load_true
FAILED tests/test_infra_daemon.py::test_plist_keep_alive_true
FAILED tests/test_infra_daemon.py::test_plist_standard_out_path_uses_home_placeholder
FAILED tests/test_infra_daemon.py::test_plist_standard_error_path_uses_home_placeholder
FAILED tests/test_infra_daemon.py::test_plist_program_arguments_invokes_nba_ingest_live
FAILED tests/test_infra_daemon.py::test_makefile_has_install_daemon_target
FAILED tests/test_infra_daemon.py::test_makefile_has_uninstall_daemon_target
FAILED tests/test_infra_daemon.py::test_makefile_install_daemon_substitutes_home_placeholder
8 failed, 2 passed (scaffold) in 0.01s
```

The 2 green are scaffold tests — plist source exists and parses, plist
Label is the locked literal. Brutus wrote a minimal stub that satisfies
those; implementer fills the remaining required keys + adds the Makefile
targets.

## Out of scope

- **Do not** load the plist into launchd inside Makefile targets when
  `LAUNCHD_DEST` is overridden — the install target should write the
  rendered file but skip `launchctl load` when destination isn't the
  default user agents dir. (Recommended pattern: a `LAUNCHCTL ?= launchctl`
  variable that tests can override to `:` to no-op.)
- **Do not** add CI-only test infrastructure — tests run against the
  Makefile + plist source files directly. No `make install-daemon`
  invocation in the test suite.
- **Do not** change `Label` from `"com.nba.ingest.live"` — that's
  load-bearing for launchd service identification and for any future
  monitoring scripts.
- **Do not** ship a non-`__HOME__` placeholder. The placeholder is what
  proves the install-time substitution happened.
- **Do not** wire log rotation, NotifyOnExit, throttle policies, or any
  other launchd advanced features unless they're in the spec — keep the
  plist minimal.

## Suggested plist body (non-binding — implementer may rearrange)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nba.ingest.live</string>
    <key>ProgramArguments</key>
    <array>
        <string>__HOME__/.local/bin/nba</string>
        <string>ingest</string>
        <string>live</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__HOME__/.nba/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/.nba/launchd.err.log</string>
</dict>
</plist>
```

## Suggested Makefile targets (non-binding)

```make
LAUNCHD_DEST ?= $(HOME)/Library/LaunchAgents
LAUNCHCTL    ?= launchctl

install-daemon:
	@mkdir -p $(LAUNCHD_DEST) $(HOME)/.nba
	@sed "s|__HOME__|$(HOME)|g" infra/launchd/com.nba.ingest.live.plist \
	    > $(LAUNCHD_DEST)/com.nba.ingest.live.plist
	@$(LAUNCHCTL) unload $(LAUNCHD_DEST)/com.nba.ingest.live.plist 2>/dev/null || true
	@$(LAUNCHCTL) load $(LAUNCHD_DEST)/com.nba.ingest.live.plist
	@echo "installed: $(LAUNCHD_DEST)/com.nba.ingest.live.plist"

uninstall-daemon:
	@$(LAUNCHCTL) unload $(LAUNCHD_DEST)/com.nba.ingest.live.plist 2>/dev/null || true
	@rm -f $(LAUNCHD_DEST)/com.nba.ingest.live.plist
	@echo "uninstalled: $(LAUNCHD_DEST)/com.nba.ingest.live.plist"
```

Add both targets to `.PHONY`.

## Hand-off

```
bash ~/.claude/skills/crew/crew.sh clear-and-talk infra-lane "brutus contract at .brutus/nba-24o/CONTRACT.md. Two files: infra/launchd/com.nba.ingest.live.plist (stub exists; fill ProgramArguments + RunAtLoad + KeepAlive + StandardOutPath/StandardErrorPath using __HOME__ placeholder) and Makefile (add install-daemon + uninstall-daemon targets with sed __HOME__→\$HOME substitution + unload-before-load for idempotency). Green these tests: python3 -m pytest tests/test_infra_daemon.py -v."
```

## Implementer

`infra-lane`. Route via athena.

## Transcript

`.brutus/nba-24o/transcript.md`.
