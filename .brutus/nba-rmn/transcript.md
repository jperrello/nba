# espn-lane (nba-rmn) red transcript

*2026-05-12T18:02:42Z by Showboat 0.6.1*
<!-- showboat-id: 33d7a710-9489-428c-be61-cb280d0e9a12 -->

Spec (brutus restatement): nba.ingest.live exposes (1) fetch_scoreboard(date) -> dict with events list, (2) is_final(event) -> bool returning True iff event.status.type.state == 'post' AND event.status.type.completed is True, (3) ingest_if_final(event, cache_root) writing summary cache only for finals, (4) self_heal_walk(team, season, today, cache_root) returning chronologically-ordered missing game_ids from regular-season schedule up to today, (5) tick(now) -> TickResult dict with exact 5 keys {polled, finals_detected, ingested, errors, duration_ms} and loop() honoring POLL_INTERVAL_SEC=30 in active window / IDLE_INTERVAL_SEC=3600 when idle, with sleeper + now_provider DI for test.

```bash
python3 -m pytest tests/test_ingest_live.py --no-header --tb=line -q 2>&1 | tail -30
```

```output
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:30: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:39: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:39: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:50: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:50: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:59: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:70: NotImplementedError: brutus contract nba-rmn: implementer must complete
E   NotImplementedError: brutus contract nba-rmn: implementer must complete
/Users/jperr/Documents/nba/nba/ingest/live.py:70: NotImplementedError: brutus contract nba-rmn: implementer must complete
=========================== short test summary info ============================
FAILED tests/test_ingest_live.py::test_fetch_scoreboard_shape - NotImplemente...
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[post-True-True]
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[post-False-False]
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[in-False-False]
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[pre-False-False]
FAILED tests/test_ingest_live.py::test_write_cache_guard_blocks_non_final - N...
FAILED tests/test_ingest_live.py::test_write_cache_guard_allows_final - NotIm...
FAILED tests/test_ingest_live.py::test_self_heal_walk_returns_ordered_missing
FAILED tests/test_ingest_live.py::test_self_heal_walk_skips_future_games - No...
FAILED tests/test_ingest_live.py::test_tick_returns_tickresult_shape - NotImp...
FAILED tests/test_ingest_live.py::test_loop_polls_every_30s_in_active_window
FAILED tests/test_ingest_live.py::test_loop_polls_hourly_when_idle - NotImple...
12 failed in 0.03s
```
