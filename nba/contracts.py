from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Shared envelope

class Warning(BaseModel):
    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class Meta(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str | None = None
    cached: bool | None = None
    elapsed_ms: float | None = None
    model_versions: dict[str, str] | None = None
    data_versions: dict[str, str] | None = None
    cache_hit: bool | None = None
    generated_at: str | None = None


# nba schema

class ColumnSpec(BaseModel):
    name: str
    type: str
    nullable: bool
    fk: str | None = None


class TableSpec(BaseModel):
    name: str
    columns: list[ColumnSpec]
    primary_key: list[str]
    indices: list[str] = Field(default_factory=list)


class SchemaData(BaseModel):
    tables: list[TableSpec]
    pgvector_dims: int


class SchemaOutput(BaseModel):
    data: SchemaData
    warnings: list[Warning] = Field(default_factory=list)
    meta: Meta


# nba sql

class SqlData(BaseModel):
    rows: list[list[Any]]
    columns: list[str]
    row_count: int


class SqlMeta(Meta):
    cached: bool
    elapsed_ms: float


class SqlOutput(BaseModel):
    data: SqlData
    warnings: list[Warning] = Field(default_factory=list)
    meta: SqlMeta


# nba lineup stats

class LineupStatsData(BaseModel):
    model_config = ConfigDict(extra="allow")

    stint_count: int
    possessions: int
    net_rating: float


class LineupStatsOutput(BaseModel):
    data: LineupStatsData
    warnings: list[Warning] = Field(default_factory=list)
    meta: Meta


# nba sim

class Score(BaseModel):
    home: int
    away: int


class WinProb(BaseModel):
    value: float
    ci: float


class Matchup(BaseModel):
    home_player: str
    away_player: str
    edge: float
    note: str | None = None


class TeamEdge(BaseModel):
    tag: str
    sign: Literal["+", "-"]
    magnitude: float
    label: str


class SimData(BaseModel):
    score: Score
    win_prob: WinProb
    matchups: list[Matchup]
    team_edges: list[TeamEdge]
    scouting_take: str | None = None


class SimMeta(Meta):
    model_versions: dict[str, str]
    cached: bool


class SimOutput(BaseModel):
    data: SimData
    warnings: list[Warning] = Field(default_factory=list)
    meta: SimMeta


# nba players show

class PlayerSeason(BaseModel):
    model_config = ConfigDict(extra="allow")

    season: int
    team_id: str | None = None


class PlayersShowData(BaseModel):
    player_id: str
    name: str
    seasons: list[PlayerSeason]


class PlayersShowOutput(BaseModel):
    data: PlayersShowData
    warnings: list[Warning] = Field(default_factory=list)
    meta: Meta


# nba ingest season

class IngestData(BaseModel):
    model_config = ConfigDict(extra="allow")

    teams_upserted: int
    players_upserted: int
    games_upserted: int
    rosters_upserted: int
    pbp_events_inserted: int
    coach_games_upserted: int
    games_marked_thin: int


class IngestMeta(Meta):
    dry_run: bool
    cache_path: str
    team: str
    season: int


class IngestOutput(BaseModel):
    data: IngestData
    warnings: list[Warning] = Field(default_factory=list)
    meta: IngestMeta


# nba stints derive

class StintsDeriveData(BaseModel):
    model_config = ConfigDict(extra="allow")

    stints_persisted: int
    games_processed: int
    games_skipped_thin_pbp: int
    mode: Literal["game", "season"]


class StintsDeriveMeta(Meta):
    mode: Literal["game", "season"]
    game_id: str | None = None
    season: int | None = None
    team: str | None = None


class StintsDeriveOutput(BaseModel):
    data: StintsDeriveData
    warnings: list[Warning] = Field(default_factory=list)
    meta: StintsDeriveMeta


# Errors (printed to stderr as a single JSON line, non-zero exit code)

ErrorCode = Literal[
    "MultiStatementError",
    "InvalidPlayerError",
    "EraOutOfRangeError",
    "InsufficientDataError",
    "InvalidTeamError",
    "InvalidSeasonError",
    "InvalidGameError",
    "IngestError",
]


# Stable exit-code table — pinned by brutus contract nba-5ve. Every typed error
# in the CLI must use exactly the code below. Click's default for usage errors
# (missing args, conflicting options, etc.) is 2 and collides with
# MultiStatementError; that overlap is intentional — both are "the input you
# gave is structurally invalid" and downstream agents can distinguish via the
# error discriminator in the JSON payload.
EXIT_CODES: dict[str, int] = {
    "MultiStatementError": 2,
    "InvalidPlayerError": 3,
    "EraOutOfRangeError": 4,
    "InsufficientDataError": 5,
    "InvalidTeamError": 6,
    "InvalidSeasonError": 7,
    "InvalidGameError": 8,
    "IngestError": 9,
}


class ErrorPayload(BaseModel):
    error: ErrorCode
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
