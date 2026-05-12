from __future__ import annotations

import datetime as _dt
import json
import shutil
import subprocess
import sys
import time as _time
import traceback as _tb
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nba.ingest import live as _live

HARD_FAIL_THRESHOLD = 10
DEFAULT_LOG_PATH = Path.home() / ".nba" / "ingest.log"
BD_HARD_FAIL_TITLE = "live ingest daemon: hard-fail threshold reached"

TickResult = dict[str, Any]

_BRUTUS = "brutus contract nba-2fz: implementer must complete"


def _default_tick(now: _dt.datetime) -> TickResult:
    return _live.tick(now)


def _default_sleeper(seconds: float) -> None:
    _time.sleep(seconds)


def _default_notify(message: str) -> None:
    if shutil.which("osascript") is None:
        return
    safe = message.replace('"', "'").replace("\n", " ")
    script = f'display notification "{safe}" with title "nba ingest daemon"'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _default_bd_create(title: str, body: str) -> str:
    if shutil.which("bd") is None:
        return "bd-unavailable"
    proc = subprocess.run(
        ["bd", "create", "--title", title, "--description", body,
         "--type", "bug", "--priority", "1", "--json"],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return "bd-error"
    try:
        return str(json.loads(proc.stdout).get("id", "bd-unknown"))
    except (json.JSONDecodeError, AttributeError):
        return "bd-unknown"


_tick: Callable[[_dt.datetime], TickResult] = _default_tick
_sleeper: Callable[[float], None] = _default_sleeper
_notify: Callable[[str], None] = _default_notify
_bd_create: Callable[[str, str], str] = _default_bd_create


def _ts(now: _dt.datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.UTC)
    return now.isoformat()


def _human(line: dict[str, Any]) -> str:
    t = line.get("type")
    ts = line.get("ts", "")
    if t == "tick":
        return (
            f"[{ts}] tick polled={line.get('polled')} "
            f"finals={len(line.get('finals_detected') or [])} "
            f"ingested={len(line.get('ingested') or [])} "
            f"errors={len(line.get('errors') or [])} "
            f"dur={line.get('duration_ms')}ms"
        )
    return f"[{ts}] {t}: {(line.get('traceback') or '').splitlines()[-1] if line.get('traceback') else ''}"


def run_daemon(
    *,
    stop_after_ticks: int | None = None,
    log_path: str | None = None,
    human: bool = False,
    now_provider: Callable[[], _dt.datetime] | None = None,
) -> None:
    path = Path(log_path) if log_path else DEFAULT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    def _now() -> _dt.datetime:
        return _dt.datetime.now(_dt.UTC)

    if now_provider is None:
        now_provider = _now

    consecutive = 0
    fired = False
    i = 0

    with path.open("a", encoding="utf-8") as fh:
        while True:
            now = now_provider()
            try:
                result = _tick(now)
                line: dict[str, Any] = {"type": "tick", "ts": _ts(now), **result}
                failed = bool(result.get("errors"))
            except Exception:
                line = {
                    "type": "ingest_fail",
                    "ts": _ts(now),
                    "traceback": _tb.format_exc(),
                }
                failed = True

            fh.write(json.dumps(line, separators=(",", ":")) + "\n")
            fh.flush()

            if human:
                sys.stderr.write(_human(line) + "\n")
                sys.stderr.flush()

            if failed:
                consecutive += 1
                if consecutive >= HARD_FAIL_THRESHOLD and not fired:
                    msg = (
                        f"{HARD_FAIL_THRESHOLD} consecutive failed ticks; "
                        f"daemon continues, see ~/.nba/ingest.log"
                    )
                    _notify(msg)
                    body = (
                        f"Hard-fail threshold ({HARD_FAIL_THRESHOLD}) reached at "
                        f"{line['ts']}. Last log line: {json.dumps(line)}"
                    )
                    _bd_create(BD_HARD_FAIL_TITLE, body)
                    fired = True
                    consecutive = 0
            else:
                consecutive = 0
                fired = False

            i += 1
            if stop_after_ticks is not None and i >= stop_after_ticks:
                return

            active = bool(
                line.get("finals_detected")
                or line.get("ingested")
                or line.get("errors")
                or line.get("type") != "tick"
            )
            _sleeper(float(_live.POLL_INTERVAL_SEC if active else _live.IDLE_INTERVAL_SEC))


def run_train_embeddings() -> dict[str, Any]:
    from nba.train.embeddings import run  # type: ignore[attr-defined]
    return run()


def run_train_predictor() -> dict[str, Any]:
    from nba.train.predictor import run  # type: ignore[attr-defined]
    return run()
