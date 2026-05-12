# VERDICT — nba-1ab (ml-lane)

**GREEN. Confirmed at 6fe56fb on main.**

- Run: `python3 -m pytest tests/test_train_run.py -v` → 10/10 passed.

## Attestation

Implementer (`ml-lane`) filled `nba.train.embeddings.run()` and
`nba.train.predictor.run()` per the overseer-locked envelope shapes
(embeddings={version, n_players, train_loss, artifact_path};
predictor=+val_mse). Sharp interpretation of Q2 "no idempotency":
version string is `{prefix}-trained-{sha8}-{uuid6}` so back-to-back
identical-input calls still differ — sha8 captures the data fingerprint,
uuid6 nonce guarantees freshness even on byte-identical inputs. Atomic
`os.replace` for both version.py rewrites and `predictor_latest.json`.

Downstream effect: `cli-lane`'s `nba train embeddings` and `nba train
predictor` commands now light up on main — the lazy import resolves to
real `run()` callables. The two cli-lane train tests that previously
relied on monkeypatched seams continue to pass; the un-monkeypatched
guard tests now have a real path to exercise but still exit non-zero
because actual training requires DB+torch and tests don't supply them.

— brutus
