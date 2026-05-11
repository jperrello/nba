from __future__ import annotations

import torch
from torch import nn

from nba.embeddings.version import EMBEDDINGS_DIM


class PlayerSeasonEmbedding(nn.Module):
    def __init__(self, n: int, dim: int = EMBEDDINGS_DIM):
        super().__init__()
        self.table = nn.Embedding(n, dim)
        nn.init.normal_(self.table.weight, std=0.02)

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        return self.table(idx)

    def all(self) -> torch.Tensor:
        return self.table.weight.detach()


def unit_normalize(v: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    norm = v.norm(p=2, dim=-1, keepdim=True).clamp_min(eps)
    return v / norm
