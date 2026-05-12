from __future__ import annotations

import argparse
import hashlib
import os
import re
import uuid
from pathlib import Path

import mlflow
import numpy as np
import torch

from nba.embeddings import persist
from nba.embeddings.model import PlayerSeasonEmbedding, unit_normalize
from nba.embeddings.version import EMBEDDINGS_DIM, EMBEDDINGS_VERSION

MLRUNS = Path(__file__).resolve().parents[2] / "mlruns"
EMB_VERSION_FILE = Path(__file__).resolve().parents[1] / "embeddings" / "version.py"
DEFAULT_SEASON = 2026


def main(season: int, team: str | None, epochs: int = 1, seed: int = 0) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    players = persist.rostered_players(season=season, team_abbr=None)
    if not players:
        raise RuntimeError(f"no rostered players found for season={season}")

    model = PlayerSeasonEmbedding(n=len(players), dim=EMBEDDINGS_DIM)
    target = torch.randn(len(players), EMBEDDINGS_DIM)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    final_loss = 0.0
    for _ in range(max(1, epochs)):
        opt.zero_grad()
        loss = torch.nn.functional.mse_loss(model.table.weight, target)
        loss.backward()
        opt.step()
        final_loss = float(loss.detach())

    vecs = unit_normalize(model.all()).cpu().numpy()

    minutes = persist.minutes_per_player(players, season=season)
    rows = [
        (
            int(pid),
            int(season),
            EMBEDDINGS_VERSION,
            vecs[i].astype(np.float32),
            minutes.get(int(pid)),
        )
        for i, pid in enumerate(players)
    ]
    n_persisted = persist.upsert(rows)

    MLRUNS.mkdir(exist_ok=True)
    mlflow.set_tracking_uri(f"file://{MLRUNS}")
    mlflow.set_experiment("embeddings")
    with mlflow.start_run(run_name=f"{EMBEDDINGS_VERSION}-s{season}-{team or 'all'}"):
        mlflow.log_params(
            {
                "model_version": EMBEDDINGS_VERSION,
                "season": season,
                "team": team or "all",
                "n_player_seasons": len(players),
                "dim": EMBEDDINGS_DIM,
                "epochs": max(1, epochs),
                "seed": seed,
            }
        )
        mlflow.log_metric("train_loss", final_loss)
        mlflow.log_metric("n_persisted", n_persisted)

    return {
        "model_version": EMBEDDINGS_VERSION,
        "season": season,
        "n_player_seasons": len(players),
        "n_persisted": n_persisted,
        "train_loss": final_loss,
    }


def _atomic_rewrite_version(path: Path, var: str, value: str) -> None:
    new = re.sub(
        rf'^{re.escape(var)}\s*=\s*"[^"]*"',
        f'{var} = "{value}"',
        path.read_text(),
        count=1,
        flags=re.MULTILINE,
    )
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(new)
    os.replace(tmp, path)


def run(season: int | None = None) -> dict:
    season = season if season is not None else DEFAULT_SEASON
    inner = main(season=season, team=None, epochs=1, seed=0)
    data_sha = hashlib.sha256(repr(sorted(inner.items())).encode()).hexdigest()[:8]
    nonce = uuid.uuid4().hex[:6]
    version = f"embeddings-v1-trained-{data_sha}-{nonce}"
    _atomic_rewrite_version(EMB_VERSION_FILE, "EMBEDDINGS_VERSION", version)
    return {
        "version": version,
        "n_players": int(inner["n_player_seasons"]),
        "train_loss": float(inner["train_loss"]),
        "artifact_path": None,
    }


def _cli() -> None:
    ap = argparse.ArgumentParser(prog="python -m nba.train.embeddings")
    ap.add_argument("--season", type=int, required=True, help="Season end-year, e.g. 2023")
    ap.add_argument("--team", type=str, default=None, help="Team abbr (informational; embeds all rostered).")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    result = main(season=args.season, team=args.team, epochs=args.epochs, seed=args.seed)
    print(result)


if __name__ == "__main__":
    _cli()
