from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_ROOT = REPO_ROOT / "data" / "fixtures" / "espn"
CACHE_ROOT = REPO_ROOT / "data" / "cache" / "espn"


@pytest.fixture(autouse=True)
def _seed_cache_for_contract_tests(request):
    if "test_ingest_contract" not in str(request.fspath):
        yield
        return

    schedule_src = FIXTURE_ROOT / "2023" / "schedule.json"
    summary_src = FIXTURE_ROOT / "2023" / "401468777.json"

    sched_dst = CACHE_ROOT / "schedule" / "18-2023.json"
    sched_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(schedule_src, sched_dst)

    schedule = json.loads(schedule_src.read_text())
    summary_dst_dir = CACHE_ROOT / "summary"
    summary_dst_dir.mkdir(parents=True, exist_ok=True)
    summary_bytes = summary_src.read_bytes()
    written: list[Path] = []
    for event in schedule.get("events") or []:
        if (event.get("seasonType") or {}).get("id") != "2":
            continue
        eid = event.get("id")
        if not eid:
            continue
        dst = summary_dst_dir / f"{eid}.json"
        dst.write_bytes(summary_bytes)
        written.append(dst)

    try:
        yield
    finally:
        sched_dst.unlink(missing_ok=True)
        for p in written:
            p.unlink(missing_ok=True)
