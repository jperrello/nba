from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


ESPN_CACHE_DIR = Path(os.getenv("NBA_ESPN_CACHE_DIR", "data/cache/espn"))


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def psycopg_url(self) -> str:
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


def db() -> DbConfig:
    return DbConfig(
        host=os.getenv("NBA_DB_HOST", "localhost"),
        port=int(os.getenv("NBA_DB_PORT", "5432")),
        name=os.getenv("NBA_DB_NAME", "nba"),
        user=os.getenv("NBA_DB_USER", "nba"),
        password=os.getenv("NBA_DB_PASSWORD", "nba"),
    )
