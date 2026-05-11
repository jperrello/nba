from __future__ import annotations

import json
import random
from pathlib import Path

import psycopg

from nba.config import db

NYK_TEAM_ID = 18
HOLDOUT_SEED = 20260511
HOLDOUT_N = 5
VAL_SEED = 42
VAL_N = 10
SPLITS_PATH = Path(__file__).resolve().parents[2] / "data" / "splits" / "predictor_v0.json"


def nyk_game_ids(season: int) -> list[int]:
    with psycopg.connect(db().url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT game_id FROM games "
            "WHERE season = %s AND (home_team_id = %s OR away_team_id = %s) "
            "ORDER BY game_id",
            (season, NYK_TEAM_ID, NYK_TEAM_ID),
        )
        return [row[0] for row in cur.fetchall()]


def splits(season: int) -> tuple[set[int], set[int], set[int]]:
    games = nyk_game_ids(season)
    if len(games) < HOLDOUT_N + VAL_N + 1:
        raise RuntimeError(f"only {len(games)} games for season {season}; need >= {HOLDOUT_N + VAL_N + 1}")
    holdout = set(random.Random(HOLDOUT_SEED).sample(sorted(games), HOLDOUT_N))
    remaining = [g for g in games if g not in holdout]
    val = set(random.Random(VAL_SEED).sample(sorted(remaining), VAL_N))
    train = set(remaining) - val
    return train, val, holdout


def persist(season: int) -> dict:
    train, val, holdout = splits(season)
    payload = {
        "season": season,
        "holdout_seed": HOLDOUT_SEED,
        "val_seed": VAL_SEED,
        "train_game_ids": sorted(train),
        "val_game_ids": sorted(val),
        "holdout_game_ids": sorted(holdout),
    }
    SPLITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPLITS_PATH.write_text(json.dumps(payload, indent=2))
    return payload
