# ml-lane (nba-1ab) red transcript

*2026-05-12T18:21:05Z by Showboat 0.6.1*
<!-- showboat-id: c4e97a01-0e74-48c7-b3ea-11144f27084d -->

Spec (brutus restatement): nba.train.embeddings.run() and nba.train.predictor.run() — thin wrappers around existing main() trainers that (1) compute a new version string per invocation (no idempotency: every successful call mints a different version), (2) atomically rewrite the corresponding version.py module file with the new version constant, (3) for predictor: also rewrite data/models/predictor_latest.json with the new model_version, (4) return per-trainer envelopes. embeddings envelope keys = {version, n_players, train_loss, artifact_path} (NO val_mse — overseer Q3 lock). predictor envelope keys = {version, n_players, train_loss, val_mse, artifact_path}. run() must invoke the inner main() trainer — no synthesizing envelopes without training.

```bash
python3 -m pytest tests/test_train_run.py --no-header --tb=line -q 2>&1 | tail -20
```

```output
E   NotImplementedError: brutus contract nba-1ab: implementer must complete
/Users/jperr/Documents/nba/nba/train/embeddings.py:80: NotImplementedError: brutus contract nba-1ab: implementer must complete
E   NotImplementedError: brutus contract nba-1ab: implementer must complete
/Users/jperr/Documents/nba/nba/train/predictor.py:138: NotImplementedError: brutus contract nba-1ab: implementer must complete
E   NotImplementedError: brutus contract nba-1ab: implementer must complete
/Users/jperr/Documents/nba/nba/train/embeddings.py:80: NotImplementedError: brutus contract nba-1ab: implementer must complete
E   NotImplementedError: brutus contract nba-1ab: implementer must complete
/Users/jperr/Documents/nba/nba/train/predictor.py:138: NotImplementedError: brutus contract nba-1ab: implementer must complete
=========================== short test summary info ============================
FAILED tests/test_train_run.py::test_embeddings_run_envelope_keys - NotImplem...
FAILED tests/test_train_run.py::test_predictor_run_envelope_keys - NotImpleme...
FAILED tests/test_train_run.py::test_embeddings_envelope_excludes_val_mse - N...
FAILED tests/test_train_run.py::test_predictor_envelope_includes_val_mse - No...
FAILED tests/test_train_run.py::test_embeddings_run_returns_new_version_each_call
FAILED tests/test_train_run.py::test_predictor_run_returns_new_version_each_call
FAILED tests/test_train_run.py::test_embeddings_run_persists_new_version_to_module_file
FAILED tests/test_train_run.py::test_predictor_run_persists_new_model_version_to_latest_json
FAILED tests/test_train_run.py::test_embeddings_run_invokes_inner_trainer - N...
FAILED tests/test_train_run.py::test_predictor_run_invokes_inner_trainer - No...
10 failed in 1.40s
```
