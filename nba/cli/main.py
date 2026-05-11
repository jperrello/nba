from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Annotated, Any

import typer

from nba.cli import human as human_view
from nba.cli import warnings as warn
from nba.cli._schema_stub import TABLES
from nba.cli.teamspec import TeamSpecError
from nba.cli.teamspec import parse as parse_teamspec
from nba.contracts import EXIT_CODES, ErrorPayload

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    add_completion=False,
)
lineup_app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
players_app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
ingest_app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
app.add_typer(lineup_app, name="lineup")
app.add_typer(players_app, name="players")
app.add_typer(ingest_app, name="ingest")


class InvalidPlayerError(Exception):
    exit_code = 3

    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


class InsufficientDataError(Exception):
    exit_code = 5


class EraOutOfRangeError(Exception):
    exit_code = 4

    def __init__(self, season: int):
        super().__init__(str(season))
        self.season = season


class MultiStatementError(Exception):
    exit_code = 2

    def __init__(self, query: str):
        super().__init__(query)
        self.query = query


def _emit_error(code: str, message: str, context: dict[str, Any], exit_code: int) -> None:
    payload = ErrorPayload(error=code, message=message, context=context)  # type: ignore[arg-type]
    sys.stderr.write(payload.model_dump_json() + "\n")
    sys.stderr.flush()
    raise typer.Exit(code=exit_code)


def _emit_json(payload: Any) -> None:
    if hasattr(payload, "model_dump_json"):
        text: str = payload.model_dump_json()
    else:
        text = json.dumps(payload, separators=(",", ":"))
    sys.stdout.write(text)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _meta(**extra: Any) -> dict:
    base = {
        "model_versions": {"predictor": "stub-0.0", "embeddings": "stub-0.0", "lm": "stub-0.0"},
        "data_versions": {"espn": "stub-0.0"},
        "cache_hit": False,
        "cached": False,
        "generated_at": _now(),
        "stub": True,
    }
    base.update(extra)
    return base


KNOWN_PLAYERS = {
    "brunson", "towns", "randle", "divincenzo", "bridges", "anunoby",
    "kat", "haliburton", "siakam", "mathurin", "turner", "nesmith",
}


def _resolve_player(name: str) -> str | None:
    lc = name.lower()
    for key in KNOWN_PLAYERS:
        if key in lc:
            return key
    return None


def _parse_team(field: str, spec: str) -> Any:
    try:
        return parse_teamspec(spec)
    except TeamSpecError as e:
        context = {**e.context, "field": field}
        _emit_error(e.code, e.message, context, EXIT_CODES[e.code])
        raise  # unreachable; _emit_error raises typer.Exit


def _validate_swap_players(field: str, spec: Any) -> None:
    for clause in spec.get("swaps", []):
        for player in clause.get("in", []):
            if _resolve_player(player) is None:
                _emit_error(
                    "InvalidPlayerError",
                    f"unknown player {player!r} in swap clause for {field}.",
                    {
                        "field": field,
                        "player": player,
                        "swap": clause,
                        "team": spec.get("team"),
                        "season": spec.get("season"),
                    },
                    EXIT_CODES["InvalidPlayerError"],
                )


def generate_scouting_take(team1: Any, team2: Any, sim_data: Any) -> str:
    return (
        "Stub scouting take: the model gives the edge to the home side on cleaner "
        "halfcourt fit, but flags the cross-matchup at the 4 as the swing factor. "
        "Treat the win-probability band as wider than it looks; the supporting "
        "stints under this exact configuration are thin."
    )


@app.command()
def schema(
    table: str | None = typer.Option(None, "--table", help="Filter to a single table by name."),
    format: str = typer.Option("json", "--format", help="Output format: json | human."),
) -> None:
    tables = TABLES
    if table is not None:
        tables = [t for t in TABLES if t["name"] == table]
    payload = {
        "data": {"tables": tables, "pgvector_dims": 128},
        "warnings": [],
        "meta": _meta(schema_version="v1"),
    }
    _emit_json(payload)


@app.command()
def sql(query: str = typer.Argument(..., help="SQL query (single statement only).")) -> None:
    parts = [p.strip() for p in query.split(";") if p.strip()]
    if len(parts) > 1:
        _emit_error(
            "MultiStatementError",
            "nba sql accepts a single statement; got multiple separated by ';'.",
            {"query": query, "statement_count": len(parts)},
            EXIT_CODES["MultiStatementError"],
        )
    payload = {
        "data": {
            "rows": [[1]],
            "columns": ["?column?"],
            "row_count": 1,
        },
        "warnings": [],
        "meta": _meta(cached=False, elapsed_ms=0.0),
    }
    _emit_json(payload)


@lineup_app.command("stats")
def lineup_stats(
    players: Annotated[list[str], typer.Option("--players", help="5 player names/ids.")],
    season: int = typer.Option(..., "--season", help="Season-start year."),
    context: str | None = typer.Option(None, "--context", help="Optional context bundle."),
) -> None:
    if season < 2003:
        _emit_error(
            "EraOutOfRangeError",
            f"season {season} is before the data window (>= 2003).",
            {"season": season, "earliest_available": 2003},
            EXIT_CODES["EraOutOfRangeError"],
        )
    warnings = []
    resolved = [_resolve_player(p) for p in players]
    n_known = sum(1 for r in resolved if r is not None)
    n_effective = 50 + 80 * n_known
    warnings.append(warn.sparse(n_effective))
    payload = {
        "data": {
            "stint_count": 12,
            "possessions": 340,
            "net_rating": 3.1,
            "off_rating": 114.2,
            "def_rating": 111.1,
            "players": players,
            "season": season,
        },
        "warnings": warnings,
        "meta": _meta(),
    }
    _emit_json(payload)


@app.command()
def sim(
    team1: str = typer.Option(..., "--team1"),
    team2: str = typer.Option(..., "--team2"),
    no_scouting: bool = typer.Option(False, "--no-scouting"),
    human: bool = typer.Option(False, "--human"),
) -> None:
    t1 = _parse_team("team1", team1)
    t2 = _parse_team("team2", team2)
    _validate_swap_players("team1", t1)
    _validate_swap_players("team2", t2)
    if t1["season"] < 2003:
        _emit_error(
            "EraOutOfRangeError",
            f"team1 season {t1['season']} is before the data window (>= 2003).",
            {"team": t1["team"], "season": t1["season"], "earliest_available": 2003},
            EXIT_CODES["EraOutOfRangeError"],
        )
    if t2["season"] < 2003:
        _emit_error(
            "EraOutOfRangeError",
            f"team2 season {t2['season']} is before the data window (>= 2003).",
            {"team": t2["team"], "season": t2["season"], "earliest_available": 2003},
            EXIT_CODES["EraOutOfRangeError"],
        )
    sim_data = {
        "score": {"home": 114, "away": 109},
        "win_prob": {"value": 0.61, "ci": 0.08},
        "matchups": [
            {"home_player": "Brunson", "away_player": "Haliburton", "edge": 0.7, "note": None},
            {"home_player": "DiVincenzo", "away_player": "Nesmith", "edge": 0.3, "note": None},
            {"home_player": "Bridges", "away_player": "Mathurin", "edge": 0.9, "note": None},
            {
                "home_player": "Anunoby",
                "away_player": "Siakam",
                "edge": -0.4,
                "note": "cross-matchup flag: switch risk on primary scorer",
            },
            {"home_player": "Randle", "away_player": "Turner", "edge": 0.5, "note": None},
        ],
        "team_edges": [
            {"tag": "rebounding", "sign": "+", "magnitude": 1.4, "label": "rebound rate vs Indiana frontcourt"},
            {"tag": "halfcourt_fit", "sign": "+", "magnitude": 0.8, "label": "cleaner fit at the 4 spot"},
            {"tag": "spacing", "sign": "-", "magnitude": 1.2, "label": "lost spacing relative to actual roster"},
            {"tag": "defensive_switchability", "sign": "-", "magnitude": 0.6, "label": "worse on Haliburton actions"},
        ],
    }
    take = None if no_scouting else generate_scouting_take(t1, t2, sim_data)
    sim_data["scouting_take"] = take
    warnings_list = [warn.sparse(340)]
    payload = {
        "data": sim_data,
        "warnings": warnings_list,
        "meta": _meta(cached=False),
    }
    _emit_json(payload)
    if human:
        sys.stdout.write("\n")
        sys.stdout.write(human_view.render_sim(t1, t2, sim_data, warnings_list))
        sys.stdout.flush()


@players_app.command("show")
def players_show(
    name: str | None = typer.Option(None, "--name"),
    player_id: str | None = typer.Option(None, "--id"),
) -> None:
    if name is None and player_id is None:
        _emit_error(
            "InvalidPlayerError",
            "must provide --name or --id",
            {"name": None, "id": None},
            EXIT_CODES["InvalidPlayerError"],
        )
    query = name or player_id or ""
    if name is not None:
        resolved = _resolve_player(name)
        if resolved is None:
            _emit_error(
                "InvalidPlayerError",
                f"unknown player {query!r}: not in the stub roster.",
                {"name": name, "query": query},
                EXIT_CODES["InvalidPlayerError"],
            )
        canonical = name.title()
    else:
        canonical = f"Player {player_id}"
        resolved = "stub"
    payload = {
        "data": {
            "player_id": f"stub-{resolved}",
            "name": canonical,
            "seasons": [
                {"season": 2022, "team_id": "NYK"},
                {"season": 2023, "team_id": "NYK"},
                {"season": 2024, "team_id": "NYK"},
            ],
        },
        "warnings": [],
        "meta": _meta(),
    }
    _emit_json(payload)


@ingest_app.command("season")
def ingest_season_cmd(
    team: str = typer.Option(..., "--team", help="Team abbreviation (e.g. NYK)."),
    season: int = typer.Option(..., "--season", help="Season-end year (ESPN convention; 2023 = 2022-23)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview counts without DB writes."),
) -> None:
    from nba.contracts import EXIT_CODES
    from nba.ingest.season import (
        EraOutOfRangeError as _Era,
    )
    from nba.ingest.season import (
        InvalidTeamError as _InvTeam,
    )
    from nba.ingest.season import (
        ingest_season,
    )
    try:
        out = ingest_season(team, season, dry_run=dry_run)
    except _InvTeam as e:
        _emit_error(
            "InvalidTeamError",
            f"unknown team abbreviation {e.team!r}",
            {"team": e.team},
            EXIT_CODES["InvalidTeamError"],
        )
        return
    except _Era as e:
        _emit_error(
            "EraOutOfRangeError",
            f"season {e.season} is before the data window (>= 2003).",
            {"season": e.season, "earliest_available": 2003},
            EXIT_CODES["EraOutOfRangeError"],
        )
        return
    _emit_json(out)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
