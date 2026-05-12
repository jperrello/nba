# CONTRACT — nba-2fz (cli-lane)

**Brutus contract.** Implementer = cli-lane. No bypass.

## Spec restatement (falsifiable)

Implement the daemon orchestration + train adapters that sit between
`nba.ingest.live` (espn-lane) and `nba.train.{embeddings,predictor}` (ml-lane).

Three deliverables:

1. **`nba.cli.live.run_daemon(*, stop_after_ticks, log_path, human, now_provider)`**
   — wraps the public `tick()` primitive in a `while True:` loop, writes a
   JSONL line per cycle to `log_path` (default `~/.nba/ingest.log`), tracks
   consecutive-failure ticks, and triggers `_notify` + `_bd_create` at
   threshold=10. Cadence: `POLL_INTERVAL_SEC` (30) when scoreboard has active
   events, `IDLE_INTERVAL_SEC` (3600) otherwise. Implementer chooses the
   active-detection heuristic (TickResult signals, scoreboard peek, state
   machine — all acceptable so long as observable cadence is correct).

2. **`nba.cli.live.run_train_embeddings()` / `run_train_predictor()`**
   — thin cli-side adapters that call `nba.train.embeddings.run()` /
   `nba.train.predictor.run()` (from ml-lane) and return the envelope. The
   typer commands `nba train embeddings` and `nba train predictor` shell
   into these adapters and `_emit_json` the result.

3. **Typer surface** registered on `app` (already wired in `nba/cli/main.py`
   by brutus; **do not change signatures**):
   - `nba ingest live [--stop-after-ticks N] [--log-path PATH] [--human]`
   - `nba train embeddings`
   - `nba train predictor`

## Locked decisions (do not relitigate)

### Orchestration: roll-your-own, not `live.loop()`

`live.loop()` exists for non-CLI consumers; cli-lane is **not** required to
call it. Sanctioned approach: `while True:` around public `tick()` with
explicit log/cadence/hard-fail logic per cycle. Cleaner separation: espn-lane
owns the single-poll primitive, cli-lane owns daemon orchestration.

### Public surface only

Consume **public `tick()`** only. **`_tick` (the private 2-tuple variant in
`nba.ingest.live`) is forbidden** — it's internal to espn-lane. If cli-lane
needs the scoreboard for cadence decisions, call `fetch_scoreboard` directly
or derive from TickResult signals — do not import `_tick`.

### TickResult shape (verbatim from espn-lane VERDICT)

```python
{
    "polled": int,
    "finals_detected": list[str],
    "ingested": list[str],
    "errors": list[str],            # pre-stringified, JSON-safe
    "duration_ms": int,
}
```

cli-lane's upstream finding #1 (confirmed): `errors` are already string-
formatted by espn-lane; the full TickResult drops into one `json.dumps()`
call with no serialization shim.

### JSONL envelope (three line types)

Every line is parseable JSON. Three `type` values:

| `type`        | When emitted                                  | Required keys (beyond `type`, `ts`)                         |
| ------------- | --------------------------------------------- | ----------------------------------------------------------- |
| `"tick"`      | every successful cycle                        | 5 TickResult keys verbatim (polled, finals_detected, ingested, errors, duration_ms) |
| `"ingest_fail"` | OR `"hard_fail"`: cycle where `tick()` raised | `traceback` (str), the 5 TickResult keys may be absent |
| `"hard_fail"` | at threshold=10 (additional line if desired)  | `bd_issue_id`, `traceback`                                  |

`ts` field: ISO-8601 UTC string, e.g. `"2026-05-12T23:45:01.123Z"`.

The test only asserts (a) every line parses as JSON, (b) every line has
`type` and `ts`, (c) tick lines superset-contain the 5 TickResult keys,
(d) raised-tick lines have a `traceback` field with the exception name.
cli-lane chooses whether raised-ticks are `ingest_fail` or `hard_fail`
type — both are accepted by the test as long as `traceback` is present.

### Hard-fail counter

- Increments on **errors-non-empty** TickResults AND on **tick() raises**.
- Resets to 0 on any clean tick (`errors == []` and no raise).
- Fires `_notify(message)` + `_bd_create(BD_HARD_FAIL_TITLE, body)` **exactly
  once** when the counter hits `HARD_FAIL_THRESHOLD = 10`.
- After firing, behavior is implementation choice — typically reset counter
  and continue (don't fire repeatedly while still failing).
- `BD_HARD_FAIL_TITLE = "live ingest daemon: hard-fail threshold reached"`
  (locked — issue must be findable across sessions by exact title).

### Seams (module attrs monkeypatched in tests)

`nba/cli/live.py` already declares:

```python
_tick: Callable[[datetime], TickResult] = _default_tick      # → nba.ingest.live.tick
_sleeper: Callable[[float], None] = _default_sleeper          # → time.sleep
_notify: Callable[[str], None] = _default_notify              # implementer wires to osascript
_bd_create: Callable[[str, str], str] = _default_bd_create    # implementer wires to `bd create`
```

Implementer wires the four `_default_*` bodies. Tests overwrite these via
`monkeypatch.setattr(nba.cli.live, "_tick", ...)` etc. — do not change the
seam names or signatures.

`_default_notify` shells out to:
`osascript -e 'display notification "..." with title "nba ingest daemon"'`

`_default_bd_create` shells out to: `bd create --title "..." --description "..." --type bug --priority 1 --json` and parses the returned issue id.

## Test files

- `tests/test_cli_live.py` — 14 test cases.
- No external fixtures (all inline).

## Run command

```bash
python3 -m pytest tests/test_cli_live.py -v
```

Green oracle: 14 passed, 0 failed.

## Captured red output

```
tests/test_cli_live.py .......FFFFFFF                                    [100%]
short test summary info:
FAILED tests/test_cli_live.py::test_daemon_writes_one_jsonl_line_per_tick
FAILED tests/test_cli_live.py::test_daemon_log_line_is_pure_json
FAILED tests/test_cli_live.py::test_hard_fail_fires_notify_and_bd_after_10_consecutive
FAILED tests/test_cli_live.py::test_hard_fail_does_not_fire_below_threshold
FAILED tests/test_cli_live.py::test_hard_fail_counter_resets_on_clean_tick
FAILED tests/test_cli_live.py::test_hard_fail_on_tick_raising
FAILED tests/test_cli_live.py::test_every_log_line_parses_as_json
7 failed, 7 passed in 0.15s
```

**On the 7 passing tests:** these are scaffold-surface tests — `--help`
visibility, train adapter monkeypatch happy-path, train adapter
unmonkeypatched-raises. Brutus authored the typer registration and the
adapter seam declarations in `nba/cli/live.py`; those tests confirm the
contract scaffold is intact. The implementer's work is the 7 red tests
(daemon body + JSONL writer + hard-fail counter). Do not delete the
green tests — they catch regressions in the contract scaffold (e.g. a
command rename or accidental dropping of the train adapter seams).

Failures shape: each red test's chain is
`NotImplementedError("brutus contract nba-2fz") → typer Exit(1) → assertion`.
Pure "behavior missing" red, not import/typo/setup error.

## Out of scope

- **Do not** call `nba.ingest.live._tick`. Forbidden. Use the public `tick()`
  only.
- **Do not** modify `nba.ingest.live`. espn-lane is closed.
- **Do not** change the four seam names (`_tick`, `_sleeper`, `_notify`,
  `_bd_create`) or their callable signatures.
- **Do not** add or remove TickResult keys when wrapping into a tick JSONL
  line. The 5 keys flow through verbatim; envelope adds `type` and `ts` only.
- **Do not** depend on ml-lane's `run()` body being implemented. The train
  adapters use lazy import inside the function body; tests monkeypatch the
  cli-side seam (`nba.cli.live.run_train_{embeddings,predictor}`), so this
  lane is independently completable.
- **Do not** wire DB persistence here. Cache-only ingest via espn-lane's
  `ingest_if_final`; DB writes happen in a follow-up bead through
  `ingest_season`'s path.
- **Do not** invent retry/backoff. `espn._get` retries internally; cli-lane
  trusts the upstream signal — if it sees an error in the TickResult, it
  counts toward hard-fail and otherwise lets the next tick proceed.

## Hand-off

```
bash ~/.claude/skills/crew/crew.sh clear-and-talk cli-lane "brutus contract at .brutus/nba-2fz/CONTRACT.md. Typer wiring + seam stubs are in nba/cli/main.py and nba/cli/live.py — fill the four function bodies (run_daemon, run_train_embeddings, run_train_predictor, _default_notify, _default_bd_create), keep signatures + seam names. Green these 14 tests: python3 -m pytest tests/test_cli_live.py -v. tick() is public surface ONLY; _tick is forbidden. Hard-fail counter resets on clean tick. JSONL envelope = type + ts + (TickResult or traceback)."
```

## Implementer

`cli-lane` (crew member). Route via athena.

## Transcript

`.brutus/nba-2fz/transcript.md` — showboat capture of the red run.
