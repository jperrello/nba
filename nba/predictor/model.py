# pyright: reportPrivateImportUsage=false
from __future__ import annotations

import torch
from torch import nn

from nba.embeddings.version import EMBEDDINGS_DIM
from nba.predictor.version import HIDDEN_1, HIDDEN_2, HIDDEN_3, INPUT_DIM


def features(
    home: torch.Tensor,
    away: torch.Tensor,
    era: torch.Tensor,
    home_flag: torch.Tensor,
) -> torch.Tensor:
    # home/away: (B, 5, D). era/home_flag: (B,).
    assert home.shape[-1] == EMBEDDINGS_DIM
    h = torch.cat([home.sum(dim=-2), home.mean(dim=-2)], dim=-1)
    a = torch.cat([away.sum(dim=-2), away.mean(dim=-2)], dim=-1)
    extras = torch.stack([era, home_flag], dim=-1)
    return torch.cat([h, a, extras], dim=-1)


class Predictor(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(INPUT_DIM, HIDDEN_1),
            nn.ReLU(),
            nn.Linear(HIDDEN_1, HIDDEN_2),
            nn.ReLU(),
            nn.Linear(HIDDEN_2, HIDDEN_3),
            nn.ReLU(),
            nn.Linear(HIDDEN_3, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, INPUT_DIM). Output: (B,) — predicted margin per second.
        return self.net(x).squeeze(-1)
