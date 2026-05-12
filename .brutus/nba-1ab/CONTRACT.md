# CONTRACT — nba-1ab (ml-lane)

**Brutus contract.** Implementer = ml-lane. No bypass.

## Spec restatement (falsifiable)

Expose `nba.train.embeddings.run(season=None) -> dict` and
`nba.train.predictor.run(season=None) -> dict` — thin wrappers around the
existing `main()` trainers that (1) mint a fresh version string on every
invocation, (2) atomically rewrite the corresponding `version.py` module,
(3) for predictor: also rewrite `data/models/predictor_latest.json` with
the new `model_version`, (4) return a per-trainer envelope shaped exactly
per the overseer-locked key sets.

Stubs in place: `nba/train/embeddings.py:run()` and
`nba/train/predictor.py:run()` both raise `NotImplementedError("brutus
contract nba-1ab")`. Fill the bodies; do not change the signatures.

## Locked resolutions (overseer, do not relitigate)

These came down before authoring — repeated here so the test oracle is
explicit. The exact text was stashed in the `nba-1ab` bead notes; this
contract is the canonical version.

### Q1 — Envelope keys (exact)

```python
# nba.train.embeddings.run()  →
{"version", "n_players", "train_loss", "artifact_path"}

# nba.train.predictor.run()  →
{"version", "n_players", "train_loss", "val_mse", "artifact_path"}
```

**Set equality, per trainer.** Tests assert exact key-set match — do not
add extra keys (e.g. `season`, `run_id`, `n_persisted`); they belong in
the inner `main()` return, not the public envelope. cli-lane shells into
`run()` and JSON-dumps the result directly to stdout; downstream consumers
depend on the exact shape.

### Q2 — No idempotency

`nba train <x>` = retrain now, **always**. No "skip retrain if data
unchanged" path. Every successful `run()` must produce a different
`version` string than the previous successful `run()`, even on identical
inputs. Wasting 60s of compute is fine; missing a real version bump is
not. The test asserts `run()["version"] != run()["version"]`.

Suggested implementation (ml-lane's prior plan in `nba-1ab` notes):
new version = `f"embeddings-v1-trained-{short_sha}"` where short_sha is
the first 8 hex of `sha256(sorted_data_tuples)`. To guarantee monotonic
freshness on identical data, append a nonce or timestamp suffix —
implementer's choice; what matters is that the strings differ across
calls.

### Q3 — embeddings has NO val_mse

`val_mse` key is **omitted** from the embeddings envelope (no labeled
validation signal exists). Predictor keeps `val_mse`. Test asserts:
- `"val_mse" not in embeddings.run()`
- `"val_mse" in predictor.run()` and is a `float`

## Oracle definition

Per-function "correct" behavior:

1. **`embeddings.run(season=None)`** — invokes `nba.train.embeddings.main(
   season=season or <current real-world season>, team=None, ...)`, computes
   a new `EMBEDDINGS_VERSION` string, atomically rewrites
   `nba/embeddings/version.py` with `EMBEDDINGS_VERSION = "<new>"`, returns
   `{"version": new, "n_players": int, "train_loss": float,
   "artifact_path": <path or None>}`. Atomic rewrite = write tmp file +
   `os.replace`.

2. **`predictor.run(season=None)`** — invokes `nba.train.predictor.main(
   season=...)`, computes a new `PREDICTOR_VERSION` string, atomically
   rewrites `nba/predictor/version.py` AND
   `data/models/predictor_latest.json` with the new `model_version`.
   Returns `{"version": new, "n_players": int, "train_loss": float,
   "val_mse": float, "artifact_path": str}`.

3. **`n_players` semantics** — for embeddings: rows trained (player-seasons,
   i.e. `n_player_seasons` from inner `main()`). For predictor: stints in
   the training split (`n_train_stints` from inner `main()`). Tests don't
   pin the exact integer (depends on DB state); they assert the field is
   present and is an int.

4. **`artifact_path` semantics** — embeddings: may be `None` (embeddings
   are persisted to DB, not a single file). Predictor: string path to the
   `predictor_v<N>.pt` weights file.

5. **`val_mse` semantics** — predictor only. Final validation MSE from the
   last training epoch.

## Test files

- `tests/test_train_run.py` — 10 tests. All run with `main()` monkeypatched
  via fixtures (`stub_embeddings_main`, `stub_predictor_main`) so no DB /
  torch needed. An autouse fixture snapshots and restores
  `nba/embeddings/version.py`, `nba/predictor/version.py`, and
  `data/models/predictor_latest.json` so test runs don't pollute the
  working tree.

## Run command

```bash
python3 -m pytest tests/test_train_run.py -v
```

Green oracle: 10 passed, 0 failed.

## Captured red output

```
tests/test_train_run.py FFFFFFFFFF                                       [100%]
short test summary info:
FAILED tests/test_train_run.py::test_embeddings_run_envelope_keys
FAILED tests/test_train_run.py::test_predictor_run_envelope_keys
FAILED tests/test_train_run.py::test_embeddings_envelope_excludes_val_mse
FAILED tests/test_train_run.py::test_predictor_envelope_includes_val_mse
FAILED tests/test_train_run.py::test_embeddings_run_returns_new_version_each_call
FAILED tests/test_train_run.py::test_predictor_run_returns_new_version_each_call
FAILED tests/test_train_run.py::test_embeddings_run_persists_new_version_to_module_file
FAILED tests/test_train_run.py::test_predictor_run_persists_new_model_version_to_latest_json
FAILED tests/test_train_run.py::test_embeddings_run_invokes_inner_trainer
FAILED tests/test_train_run.py::test_predictor_run_invokes_inner_trainer
10 failed in 1.40s
```

All 10 fail with `NotImplementedError("brutus contract nba-1ab")`. Pure
"behavior missing" red.

## Out of scope

- **Do not** modify the existing `main()` functions in either module. They
  are the inner trainers and stay as-is. `run()` wraps them.
- **Do not** change the envelope key sets. They are overseer-locked.
- **Do not** add backwards-compat for the old version strings. Just write
  the new value verbatim into `version.py`.
- **Do not** wire DB persistence or new mlflow runs from `run()` — those
  happen inside `main()`. `run()` is a thin orchestration wrapper.
- **Do not** read `data/models/predictor_latest.json` before writing it.
  Each call rewrites it from scratch with the new manifest.
- **Do not** introduce a `season` argument default that hits a network or
  DB call to resolve "current season". Use 2026 as the literal default
  (per `DAEMON_BRIEF.md` — current real-world season is 2026 as of
  2026-05-12). If the implementer needs a configurable default, lift it
  to a module constant `DEFAULT_SEASON = 2026`.

## Hand-off

```
bash ~/.claude/skills/crew/crew.sh clear-and-talk ml-lane "brutus contract at .brutus/nba-1ab/CONTRACT.md. Stubs at nba/train/embeddings.py and nba/train/predictor.py — fill the run() bodies, do not change signatures. Green these 10 tests: python3 -m pytest tests/test_train_run.py -v. Envelope keys are overseer-locked: embeddings={version,n_players,train_loss,artifact_path}, predictor={version,n_players,train_loss,val_mse,artifact_path}. No idempotency: every run() mints a new version string. Atomically rewrite nba/embeddings/version.py + nba/predictor/version.py + data/models/predictor_latest.json."
```

## Implementer

`ml-lane` (crew member). Route via athena.

## Transcript

`.brutus/nba-1ab/transcript.md` — showboat capture of the red run.
