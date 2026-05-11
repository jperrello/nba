from __future__ import annotations

import argparse
import json
from pathlib import Path

# pyright: reportPrivateImportUsage=false
import mlflow
import numpy as np
import torch

from nba.predictor.data import Stints, load_embeddings, load_stints
from nba.predictor.model import Predictor, features
from nba.predictor.split import persist as persist_splits
from nba.predictor.version import PREDICTOR_VERSION

ROOT = Path(__file__).resolve().parents[2]
MLRUNS = ROOT / "mlruns"
ARTIFACTS = ROOT / "data" / "models"
MANIFEST = ARTIFACTS / "predictor_latest.json"


def _gather(stints: Stints, idx_of: dict[int, int], table: np.ndarray) -> tuple[torch.Tensor, torch.Tensor, np.ndarray]:
    home_idx = np.vectorize(lambda p: idx_of.get(int(p), -1))(stints.home_lineup)
    away_idx = np.vectorize(lambda p: idx_of.get(int(p), -1))(stints.away_lineup)
    mask = (home_idx >= 0).all(axis=1) & (away_idx >= 0).all(axis=1)
    home_idx, away_idx = home_idx[mask], away_idx[mask]
    home = torch.from_numpy(table[home_idx])
    away = torch.from_numpy(table[away_idx])
    return home, away, mask


def _build(stints: Stints, idx_of: dict[int, int], table: np.ndarray, era_value: float) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    home, away, mask = _gather(stints, idx_of, table)
    pts = torch.from_numpy(stints.pts[mask])
    dur = torch.from_numpy(stints.duration[mask])
    n = home.shape[0]
    era = torch.full((n,), era_value, dtype=torch.float32)
    flag = torch.ones((n,), dtype=torch.float32)
    x = features(home, away, era, flag)
    y = pts / dur  # margin per second
    w = dur
    return x, y, w


def _epoch(model: Predictor, opt: torch.optim.Optimizer, x: torch.Tensor, y: torch.Tensor, w: torch.Tensor, batch: int) -> float:
    n = x.shape[0]
    order = torch.randperm(n)
    total_loss = 0.0
    total_w = 0.0
    model.train()
    for start in range(0, n, batch):
        sel = order[start:start + batch]
        opt.zero_grad()
        pred = model(x[sel])
        diff = pred - y[sel]
        ws = w[sel]
        loss = (ws * diff * diff).sum() / ws.sum().clamp_min(1e-8)
        loss.backward()
        opt.step()
        total_loss += float(loss.detach()) * float(ws.sum())
        total_w += float(ws.sum())
    return total_loss / max(total_w, 1e-8)


def _eval(model: Predictor, x: torch.Tensor, y: torch.Tensor, w: torch.Tensor) -> float:
    model.eval()
    with torch.no_grad():
        pred = model(x)
        diff = pred - y
        return float((w * diff * diff).sum() / w.sum().clamp_min(1e-8))


def main(season: int, epochs: int = 50, batch: int = 64, lr: float = 1e-3, seed: int = 0, weight_decay: float = 1e-1) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    split = persist_splits(season=season)
    train_ids = set(split["train_game_ids"])
    val_ids = set(split["val_game_ids"])

    idx_of, table = load_embeddings(season=season)
    era_value = (season - 2003) / 20.0

    train_stints = load_stints(season=season, game_ids=train_ids)
    val_stints = load_stints(season=season, game_ids=val_ids)
    x_tr, y_tr, w_tr = _build(train_stints, idx_of, table, era_value)
    x_va, y_va, w_va = _build(val_stints, idx_of, table, era_value)

    model = Predictor()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    history: list[dict] = []
    for ep in range(epochs):
        tr = _epoch(model, opt, x_tr, y_tr, w_tr, batch)
        va = _eval(model, x_va, y_va, w_va)
        history.append({"epoch": ep, "train_loss": tr, "val_mse": va})

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    weights_path = ARTIFACTS / "predictor_v0.pt"
    torch.save(model.state_dict(), weights_path)

    MLRUNS.mkdir(exist_ok=True)
    mlflow.set_tracking_uri(f"file://{MLRUNS}")
    mlflow.set_experiment("predictor")
    with mlflow.start_run(run_name=f"{PREDICTOR_VERSION}-s{season}") as run:
        mlflow.log_params({
            "model_version": PREDICTOR_VERSION,
            "season": season,
            "epochs": epochs,
            "batch": batch,
            "lr": lr,
            "weight_decay": weight_decay,
            "seed": seed,
            "n_train_stints": int(x_tr.shape[0]),
            "n_val_stints": int(x_va.shape[0]),
            "n_holdout_games": len(split["holdout_game_ids"]),
        })
        for h in history:
            mlflow.log_metric("train_loss", h["train_loss"], step=h["epoch"])
            mlflow.log_metric("val_mse", h["val_mse"], step=h["epoch"])
        mlflow.log_artifact(str(weights_path))
        run_id = run.info.run_id

    manifest = {
        "model_version": PREDICTOR_VERSION,
        "run_id": run_id,
        "season": season,
        "weights_path": str(weights_path),
        "final_train_loss": history[-1]["train_loss"],
        "final_val_mse": history[-1]["val_mse"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    return manifest


def _cli() -> None:
    ap = argparse.ArgumentParser(prog="python -m nba.train.predictor")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print(main(season=args.season, epochs=args.epochs, batch=args.batch, lr=args.lr, seed=args.seed))


if __name__ == "__main__":
    _cli()
