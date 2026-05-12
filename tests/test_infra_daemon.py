from __future__ import annotations

import plistlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PLIST_SRC = REPO_ROOT / "infra" / "launchd" / "com.nba.ingest.live.plist"
MAKEFILE = REPO_ROOT / "Makefile"


def _load_plist_with_home(home: str = "/Users/test") -> dict:
    """Substitute __HOME__ → home and parse the rendered plist."""
    raw = PLIST_SRC.read_text().replace("__HOME__", home)
    return plistlib.loads(raw.encode())


# ---------------------------------------------------------------------------
# (1) Plist source must exist and parse.
# ---------------------------------------------------------------------------

def test_plist_source_exists_and_parses():
    assert PLIST_SRC.exists(), (
        f"infra/launchd/com.nba.ingest.live.plist must exist at {PLIST_SRC}"
    )
    data = _load_plist_with_home()
    assert isinstance(data, dict)


def test_plist_label_locked():
    data = _load_plist_with_home()
    assert data.get("Label") == "com.nba.ingest.live", (
        "plist Label must be exactly 'com.nba.ingest.live' (matches launchd "
        "service identifier and Makefile target naming)"
    )


# ---------------------------------------------------------------------------
# (2) launchd lifecycle keys — RunAtLoad + KeepAlive both required per
# DAEMON_BRIEF. These are the spec hard rules for daemon lifecycle.
# ---------------------------------------------------------------------------

def test_plist_run_at_load_true():
    data = _load_plist_with_home()
    assert data.get("RunAtLoad") is True, (
        "RunAtLoad must be True — daemon must launch at load time per "
        "DAEMON_BRIEF hard rule"
    )


def test_plist_keep_alive_true():
    data = _load_plist_with_home()
    # KeepAlive may be a bool or a dict (launchd allows either). Both forms
    # must evaluate to "keep this running."
    ka = data.get("KeepAlive")
    assert ka is True or (isinstance(ka, dict) and ka), (
        "KeepAlive must be True (or a non-empty dict policy) — daemon must "
        "be respawned on exit per DAEMON_BRIEF hard rule"
    )


# ---------------------------------------------------------------------------
# (3) Structured logging paths — both stdout and stderr must be redirected
# to files under the user's home directory.
# ---------------------------------------------------------------------------

def test_plist_standard_out_path_uses_home_placeholder():
    raw = PLIST_SRC.read_text()
    assert "__HOME__" in raw, (
        "plist must use __HOME__ placeholder for portability; Makefile "
        "substitutes at install time"
    )
    data = _load_plist_with_home("/Users/test")
    out = data.get("StandardOutPath", "")
    assert isinstance(out, str) and out, "StandardOutPath must be a non-empty string"
    assert "/Users/test" in out, (
        "StandardOutPath must include the substituted home path (use "
        "__HOME__ placeholder in source)"
    )


def test_plist_standard_error_path_uses_home_placeholder():
    data = _load_plist_with_home("/Users/test")
    err = data.get("StandardErrorPath", "")
    assert isinstance(err, str) and err, "StandardErrorPath must be a non-empty string"
    assert "/Users/test" in err


# ---------------------------------------------------------------------------
# (4) Program arguments — must invoke `nba ingest live`.
# ---------------------------------------------------------------------------

def test_plist_program_arguments_invokes_nba_ingest_live():
    data = _load_plist_with_home()
    args = data.get("ProgramArguments")
    assert isinstance(args, list) and args, (
        "ProgramArguments must be a non-empty list"
    )
    joined = " ".join(args)
    assert "nba" in joined and "ingest" in joined and "live" in joined, (
        f"ProgramArguments must invoke `nba ingest live`; got: {args!r}"
    )


# ---------------------------------------------------------------------------
# (5) Makefile lifecycle targets — install-daemon + uninstall-daemon must
# exist and be declared in .PHONY.
# ---------------------------------------------------------------------------

def test_makefile_has_install_daemon_target():
    src = MAKEFILE.read_text()
    assert re.search(r"^install-daemon\s*:", src, flags=re.MULTILINE), (
        "Makefile must declare an `install-daemon:` target"
    )


def test_makefile_has_uninstall_daemon_target():
    src = MAKEFILE.read_text()
    assert re.search(r"^uninstall-daemon\s*:", src, flags=re.MULTILINE), (
        "Makefile must declare an `uninstall-daemon:` target"
    )


def test_makefile_install_daemon_substitutes_home_placeholder():
    # install-daemon must perform the __HOME__ → $HOME substitution at
    # install time (sed or equivalent). Test searches the target body.
    src = MAKEFILE.read_text()
    install_block = re.search(
        r"^install-daemon\s*:.*?(?=^[A-Za-z_][A-Za-z0-9_-]*\s*:|\Z)",
        src,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert install_block, "install-daemon target body must be present"
    body = install_block.group(0)
    assert "__HOME__" in body or "HOME" in body, (
        "install-daemon must substitute __HOME__ → $HOME at install time "
        "(sed or equivalent)"
    )
