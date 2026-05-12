from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
EMB_VERSION_FILE = REPO_ROOT / "nba" / "embeddings" / "version.py"
PRED_VERSION_FILE = REPO_ROOT / "nba" / "predictor" / "version.py"
PRED_LATEST_JSON = REPO_ROOT / "data" / "models" / "predictor_latest.json"

EMBEDDINGS_ENVELOPE_KEYS = {"version", "n_players", "train_loss", "artifact_path"}
PREDICTOR_ENVELOPE_KEYS = {"version", "n_players", "train_loss", "val_mse", "artifact_path"}


@pytest.fixture(autouse=True)
def _restore_tracked_files():
    # ml-lane's run() rewrites these tracked files in-place. Save and
    # restore so tests don't pollute the working tree.
    targets = [EMB_VERSION_FILE, PRED_VERSION_FILE, PRED_LATEST_JSON]
    snapshots: dict[Path, bytes | None] = {
        p: (p.read_bytes() if p.exists() else None) for p in targets
    }
    yield
    for p, content in snapshots.items():
        if content is None:
            p.unlink(missing_ok=True)
        else:
            p.write_bytes(content)


@pytest.fixture
def stub_embeddings_main(monkeypatch):
    # Replace heavy main() with a controlled stub so run() can be tested
    # without DB / torch. ml-lane's run() must call main() (or an
    # equivalent inner trainer) and shape the envelope around its return.
    import nba.train.embeddings as emb

    calls = []

    def fake_main(season, team=None, epochs=1, seed=0):
        calls.append({"season": season, "team": team})
        return {
            "model_version": "stub-ignored-by-run",
            "season": season,
            "n_player_seasons": 463,
            "n_persisted": 463,
            "train_loss": 0.0421,
        }

    monkeypatch.setattr(emb, "main", fake_main)
    return calls


@pytest.fixture
def stub_predictor_main(monkeypatch):
    import nba.train.predictor as pred

    calls = []

    def fake_main(season, epochs=50, batch=64, lr=1e-3, seed=0, weight_decay=1e-1):
        calls.append({"season": season})
        return {
            "model_version": "stub-ignored-by-run",
            "run_id": "stub-run-id",
            "season": season,
            "weights_path": str(REPO_ROOT / "data" / "models" / "predictor_v17.pt"),
            "final_train_loss": 0.183,
            "final_val_mse": 0.241,
        }

    monkeypatch.setattr(pred, "main", fake_main)
    return calls


# ---------------------------------------------------------------------------
# (1) Envelope key-set: per-trainer set equality (Q3 resolution from
# overseer — embeddings has NO val_mse; predictor includes val_mse).
# ---------------------------------------------------------------------------

def test_embeddings_run_envelope_keys(stub_embeddings_main):
    from nba.train.embeddings import run

    out = run()
    assert isinstance(out, dict)
    assert set(out.keys()) == EMBEDDINGS_ENVELOPE_KEYS, (
        f"embeddings envelope must be EXACTLY {EMBEDDINGS_ENVELOPE_KEYS}; "
        f"got {set(out.keys())}"
    )


def test_predictor_run_envelope_keys(stub_predictor_main):
    from nba.train.predictor import run

    out = run()
    assert isinstance(out, dict)
    assert set(out.keys()) == PREDICTOR_ENVELOPE_KEYS, (
        f"predictor envelope must be EXACTLY {PREDICTOR_ENVELOPE_KEYS}; "
        f"got {set(out.keys())}"
    )


def test_embeddings_envelope_excludes_val_mse(stub_embeddings_main):
    # Q3 resolution (overseer-locked): embeddings has no labeled validation
    # signal, so val_mse must NOT appear. Tested explicitly so a future
    # implementer doesn't accidentally add it for "consistency".
    from nba.train.embeddings import run

    out = run()
    assert "val_mse" not in out, (
        "embeddings envelope must omit val_mse entirely — no labeled "
        "validation signal exists for embeddings"
    )


def test_predictor_envelope_includes_val_mse(stub_predictor_main):
    from nba.train.predictor import run

    out = run()
    assert "val_mse" in out
    assert isinstance(out["val_mse"], float)


# ---------------------------------------------------------------------------
# (2) No idempotency: every successful run() MUST produce a new version
# string (Q2 resolution from overseer). Calling run() twice on identical
# inputs returns two distinct version strings — explicit user intent that
# `nba train <x>` always retrains.
# ---------------------------------------------------------------------------

def test_embeddings_run_returns_new_version_each_call(stub_embeddings_main):
    from nba.train.embeddings import run

    v1 = run()["version"]
    v2 = run()["version"]
    assert v1 != v2, (
        f"embeddings.run() must mint a new version string every call "
        f"(no no-op idempotency); got v1={v1!r} == v2={v2!r}"
    )
    assert isinstance(v1, str) and v1, "version must be a non-empty string"


def test_predictor_run_returns_new_version_each_call(stub_predictor_main):
    from nba.train.predictor import run

    v1 = run()["version"]
    v2 = run()["version"]
    assert v1 != v2
    assert isinstance(v1, str) and v1


# ---------------------------------------------------------------------------
# (3) Version persistence: after run(), the version file on disk reflects
# the new version string. Module file is atomically rewritten.
# ---------------------------------------------------------------------------

def test_embeddings_run_persists_new_version_to_module_file(stub_embeddings_main):
    from nba.train.embeddings import run

    out = run()
    new_version = out["version"]
    text = EMB_VERSION_FILE.read_text()
    # Locked literal: EMBEDDINGS_VERSION = "<new_version>"
    assert f'EMBEDDINGS_VERSION = "{new_version}"' in text, (
        f"nba/embeddings/version.py must be rewritten with the new "
        f"EMBEDDINGS_VERSION assignment after run(); searched for "
        f"`EMBEDDINGS_VERSION = \"{new_version}\"` in:\n{text}"
    )


def test_predictor_run_persists_new_model_version_to_latest_json(stub_predictor_main):
    from nba.train.predictor import run

    out = run()
    new_version = out["version"]
    assert PRED_LATEST_JSON.exists(), (
        "predictor.run() must write data/models/predictor_latest.json"
    )
    manifest = json.loads(PRED_LATEST_JSON.read_text())
    assert manifest.get("model_version") == new_version, (
        f"predictor_latest.json model_version must match returned envelope "
        f"version; manifest={manifest.get('model_version')!r}, "
        f"envelope={new_version!r}"
    )


# ---------------------------------------------------------------------------
# (4) Inner trainer is invoked. Asserts run() actually shells into main(),
# not a no-op that fabricates an envelope.
# ---------------------------------------------------------------------------

def test_embeddings_run_invokes_inner_trainer(stub_embeddings_main):
    from nba.train.embeddings import run

    run()
    assert len(stub_embeddings_main) >= 1, (
        "embeddings.run() must invoke nba.train.embeddings.main() — "
        "do not synthesize the envelope without training"
    )


def test_predictor_run_invokes_inner_trainer(stub_predictor_main):
    from nba.train.predictor import run

    run()
    assert len(stub_predictor_main) >= 1
