# CONTRACT — nba-rmn (espn-lane)

**Brutus contract.** Implementer = espn-lane. No bypass.

## Spec restatement (falsifiable)

Implement `nba.ingest.live` with six callables and two module constants. Each
must satisfy a concrete observable assertion below; passing all 12 tests in
`tests/test_ingest_live.py` is the green oracle.

Surface (signatures already locked in `nba/ingest/live.py` skeleton — do
**not** change them; only fill the bodies):

```python
POLL_INTERVAL_SEC = 30
IDLE_INTERVAL_SEC = 3600

def fetch_scoreboard(d: datetime.date, *, client=None, cache_root=DEFAULT_CACHE_ROOT) -> dict
def is_final(event: dict) -> bool
def ingest_if_final(event: dict, *, client=None, cache_root=DEFAULT_CACHE_ROOT) -> str | None
def self_heal_walk(team: str, season: int, *, today=None, client=None, cache_root=DEFAULT_CACHE_ROOT) -> list[str]
def tick(now: datetime.datetime, *, client=None, cache_root=DEFAULT_CACHE_ROOT) -> TickResult
def loop(*, stop_after_ticks=None, now_provider=None, sleeper=None, client=None, cache_root=DEFAULT_CACHE_ROOT) -> list[TickResult]
```

`TickResult = dict[str, Any]` with **exactly** these five keys:

| key              | type        | meaning                                        |
| ---------------- | ----------- | ---------------------------------------------- |
| `polled`         | `int`       | scoreboard poll attempts this tick             |
| `finals_detected`| `list[str]` | game_ids that flipped to FINAL this tick       |
| `ingested`       | `list[str]` | game_ids whose summary was cached this tick    |
| `errors`         | `list[str]` | string-formatted error messages (JSON-safe)    |
| `duration_ms`    | `int`       | wall-clock duration of this tick in ms         |

`cli-lane` will write `~/.nba/ingest.log` JSON lines using this exact shape.
Set-equality, not subset. Do not add keys.

## Oracle definition

Per-function "correct" behavior:

1. **`fetch_scoreboard(d)`** — issues GET to
   `{SITE_BASE}/scoreboard?dates={d:%Y%m%d}`; returns the parsed JSON. Must
   accept `datetime.date` (not str). Tests do **not** require caching the
   scoreboard payload (it's a live signal), but if you do cache, cache it
   under a status-aware key and never persist a non-final-derived view.

2. **`is_final(event)`** — returns `True` **iff** both
   `event["status"]["type"]["state"] == "post"` AND
   `event["status"]["type"]["completed"] is True`. Both required. The
   `post + completed=False` edge case (rare delayed-flip from ESPN) must
   return `False`. This is the spec's literal hard rule.

3. **`ingest_if_final(event, cache_root)`** — if `is_final(event)`,
   call `espn.fetch_boxscore(event["id"], cache_root=cache_root)` (which
   writes `cache_root/summary/<game_id>.json`) and return the `game_id`.
   Otherwise return `None` and write nothing. Never write a summary file
   for a non-final event, even if ESPN returns 200 to a summary request.

4. **`self_heal_walk(team, season, today, cache_root)`** — call
   `espn.fetch_schedule(str(team_id), season, cache_root=cache_root)` (use
   `nba.ingest.season.TEAM_IDS` to resolve `team` → `team_id`), filter to
   regular-season events (`seasonType.id == "2"`), keep events whose date is
   `<= today`, drop events whose `event["id"]` is already cached as
   `cache_root/summary/<id>.json`, and return the remaining `event["id"]`s
   sorted ascending by `event["date"]`. Default `today = datetime.date.today()`.

5. **`tick(now)`** — fetch today's scoreboard (`fetch_scoreboard(now.date())`),
   call `ingest_if_final` for each event, accumulate into the five-key
   TickResult, measure wall time. Errors during a single event's ingest go
   into `errors` as strings (do not raise). `polled` counts scoreboard
   fetches issued this tick (typically 1).

6. **`loop(stop_after_ticks, now_provider, sleeper, ...)`** — call `tick()`
   repeatedly. Between ticks, call `sleeper(POLL_INTERVAL_SEC)` if any event
   in the just-polled scoreboard has `state in {"pre","in"}` OR the last
   final's `status.type.completed` flipped within `30*60` seconds (active
   window); otherwise call `sleeper(IDLE_INTERVAL_SEC)`. Stop after
   `stop_after_ticks` ticks if provided; otherwise run forever. Time and
   sleep are injected via `now_provider` and `sleeper` for testability;
   default to `datetime.datetime.now(UTC)` and `time.sleep`.

## Test files

- `tests/test_ingest_live.py` — 12 test cases (5 parametrize expansions in
  the `is_final` truth table).
- `.brutus/nba-rmn/fixtures/` — four hand-crafted scoreboard JSON fixtures:
  `scoreboard_final.json`, `scoreboard_in_progress.json`,
  `scoreboard_pre.json`, `scoreboard_mixed.json`. **Implementer reads these
  via the test file; do not modify them.**

## Run command

```bash
python3 -m pytest tests/test_ingest_live.py -v
```

Green oracle: 12 passed, 0 failed, 0 errors.

## Captured red output

```
collected 12 items

tests/test_ingest_live.py FFFFFFFFFFFF                                  [100%]

short test summary info:
FAILED tests/test_ingest_live.py::test_fetch_scoreboard_shape - NotImplementedError
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[post-True-True]
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[post-False-False]
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[in-False-False]
FAILED tests/test_ingest_live.py::test_is_final_requires_post_and_completed[pre-False-False]
FAILED tests/test_ingest_live.py::test_write_cache_guard_blocks_non_final - NotImplementedError
FAILED tests/test_ingest_live.py::test_write_cache_guard_allows_final - NotImplementedError
FAILED tests/test_ingest_live.py::test_self_heal_walk_returns_ordered_missing
FAILED tests/test_ingest_live.py::test_self_heal_walk_skips_future_games - NotImplementedError
FAILED tests/test_ingest_live.py::test_tick_returns_tickresult_shape - NotImplementedError
FAILED tests/test_ingest_live.py::test_loop_polls_every_30s_in_active_window
FAILED tests/test_ingest_live.py::test_loop_polls_hourly_when_idle - NotImplementedError
12 failed in 0.03s
```

All 12 fail with `NotImplementedError("brutus contract nba-rmn: implementer
must complete")`. This is the *right* red shape — behavior is provably
missing, not a setup/import error. See `.brutus/nba-rmn/transcript.md` for
the full captured run.

## Out of scope

- **Do not** touch `nba/ingest/espn.py`, `nba/ingest/season.py`,
  `nba/ingest/parse.py`. The cache guard lives in `live.ingest_if_final`,
  not in `espn._write_cache` — the existing `_write_cache` stays
  status-unaware and is correct for `fetch_boxscore`'s contract.
- **Do not** modify the four fixture JSONs.
- **Do not** change the signatures in the `live.py` skeleton. Fill bodies
  only. If you believe a signature is wrong, route back to athena with
  one line; do not unilaterally change it.
- **Do not** add a 7th TickResult key. cli-lane's log-writer contract
  asserts set-equality on these five keys.
- **Do not** ingest to the DB from `live.py`. The current contract is
  cache-population only — `ingest_if_final` populates the summary cache;
  the existing `ingest_season` path handles DB writes. (DB persistence
  hook can be added in a follow-up bead.)
- **Do not** invent retry/backoff logic. `espn._get` already retries
  `{429, 500, 502, 503, 504}` with exponential backoff; trust it. The
  10-consecutive-5xx hard-fail surface is `cli-lane`'s scope, not yours.

## Hand-off

```
bash ~/.claude/skills/crew/crew.sh clear-and-talk espn-lane "brutus contract at .brutus/nba-rmn/CONTRACT.md. Fixtures at .brutus/nba-rmn/fixtures/. Stub already exists at nba/ingest/live.py — fill the bodies, do not change signatures. Green these 12 tests: python3 -m pytest tests/test_ingest_live.py -v. Nothing else in scope."
```

## Implementer

`espn-lane` (crew member). Route via athena.

## Transcript

`.brutus/nba-rmn/transcript.md` — showboat capture of the red run.
