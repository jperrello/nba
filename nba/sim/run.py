# pyright: reportPrivateImportUsage=false
from __future__ import annotations

import math
from dataclasses import dataclass

import torch

from nba.predictor.model import features
from nba.sim import constants as K
from nba.sim.edges import team_edges
from nba.sim.loader import TeamView, load_predictor, view
from nba.sim.matchup import assign


@dataclass
class SimResult:
    score_home: int
    score_away: int
    win_prob: float
    win_prob_ci: float
    matchups: list[dict]
    team_edges: list[dict]
    season_used_home: int
    season_used_away: int
    season_requested_home: int
    season_requested_away: int
    home_team_full: str
    away_team_full: str
    used_predictor: bool


def _scores_from_margin(total_margin: float) -> tuple[int, int]:
    base = K.LEAGUE_AVG_GAME_TOTAL / 2.0
    home = base + K.HOME_COURT_PTS + total_margin / 2.0
    away = base - K.HOME_COURT_PTS - total_margin / 2.0
    home = max(K.SCORE_FLOOR, min(K.SCORE_CEIL, home))
    away = max(K.SCORE_FLOOR, min(K.SCORE_CEIL, away))
    return int(round(home)), int(round(away))


def _matchups(h: TeamView, a: TeamView) -> list[dict]:
    pairs = assign(h.embeddings, a.embeddings)
    out: list[dict] = []
    for i, j, cos in pairs:
        note = "cross-matchup flag: low embedding similarity" if cos < 0.1 else None
        out.append({
            "home_player": h.starter_names[i],
            "away_player": a.starter_names[j],
            "edge": float(cos),
            "note": note,
        })
    return out


def run(
    team1: str,
    season1: int,
    team2: str,
    season2: int,
    starters_home: list[int] | None = None,
    starters_away: list[int] | None = None,
) -> tuple[SimResult, list[dict]]:
    warnings: list[dict] = []
    h = view(team1, season1, starters=starters_home)
    a = view(team2, season2, starters=starters_away)
    if h.season_used != h.season_requested:
        warnings.append({
            "code": "season_fallback",
            "message": f"requested {team1} season {h.season_requested}; using nearest available {h.season_used}",
            "context": {"team": h.team_abbr, "requested": h.season_requested, "used": h.season_used},
        })
    if a.season_used != a.season_requested:
        warnings.append({
            "code": "season_fallback",
            "message": f"requested {team2} season {a.season_requested}; using nearest available {a.season_used}",
            "context": {"team": a.team_abbr, "requested": a.season_requested, "used": a.season_used},
        })

    model, manifest = load_predictor()
    if model is None:
        warnings.append({
            "code": "model_unavailable",
            "message": "predictor weights not found; falling back to neutral margin",
            "context": {},
        })
        total_margin = 0.0
        used_predictor = False
    else:
        era = float((max(h.season_used, a.season_used) - 2003) / 20.0)
        x = features(
            torch.from_numpy(h.embeddings).unsqueeze(0),
            torch.from_numpy(a.embeddings).unsqueeze(0),
            torch.tensor([era], dtype=torch.float32),
            torch.tensor([1.0], dtype=torch.float32),
        )
        with torch.no_grad():
            margin_per_sec = float(model(x).squeeze())
        total_margin = margin_per_sec * K.GAME_SECONDS
        used_predictor = True

    score_home, score_away = _scores_from_margin(total_margin)
    spread = score_home - score_away
    win_prob = 1.0 / (1.0 + math.exp(-spread / 5.0))
    win_prob = max(0.001, min(0.999, win_prob))

    return SimResult(
        score_home=score_home,
        score_away=score_away,
        win_prob=win_prob,
        win_prob_ci=0.10,
        matchups=_matchups(h, a),
        team_edges=team_edges(h.embeddings, a.embeddings),
        season_used_home=h.season_used,
        season_used_away=a.season_used,
        season_requested_home=h.season_requested,
        season_requested_away=a.season_requested,
        home_team_full=h.full_name,
        away_team_full=a.full_name,
        used_predictor=used_predictor,
    ), warnings


def model_versions() -> dict[str, str]:
    from nba.embeddings.version import EMBEDDINGS_VERSION

    _, manifest = load_predictor()
    if manifest is None:
        return {"predictor": "unavailable", "embeddings": EMBEDDINGS_VERSION, "lm": "placeholder-no-lora-v0"}
    return {
        "predictor": manifest["model_version"],
        "embeddings": EMBEDDINGS_VERSION,
        "lm": "placeholder-no-lora-v0",
    }
