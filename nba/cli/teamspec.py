from __future__ import annotations

from typing import Any, TypedDict


class TeamSpecError(ValueError):
    code: str = "InvalidTeamError"

    def __init__(self, message: str, context: dict[str, Any]):
        super().__init__(message)
        self.message = message
        self.context = context


class InvalidTeamError(TeamSpecError):
    code = "InvalidTeamError"


class InvalidSeasonError(TeamSpecError):
    code = "InvalidSeasonError"


class Swap(TypedDict):
    out: str
    in_: list[str]


class TeamSpec(TypedDict):
    team: str
    season: int
    swaps: list[dict]


def parse(spec: str) -> TeamSpec:
    raw = spec
    spec = spec.strip()
    swap_block: str | None = None
    body = spec
    if "[" in spec:
        if not spec.endswith("]"):
            raise InvalidTeamError(
                f"unterminated swap block in teamspec: {raw!r}",
                {"teamspec": raw, "issue": "unterminated_swap_block"},
            )
        body, rest = spec.split("[", 1)
        swap_block = rest[:-1]
    if "-" not in body:
        raise InvalidTeamError(
            f"teamspec must be 'team-season', got {body!r}",
            {"teamspec": raw, "issue": "missing_season_separator"},
        )
    team, season_str = body.rsplit("-", 1)
    if not season_str:
        raise InvalidSeasonError(
            f"teamspec season is empty in {raw!r}",
            {"teamspec": raw, "season_value": season_str},
        )
    try:
        season = int(season_str)
    except ValueError as e:
        raise InvalidSeasonError(
            f"teamspec season must be an integer, got {season_str!r}",
            {"teamspec": raw, "season_value": season_str},
        ) from e
    swaps: list[dict] = []
    if swap_block is not None and swap_block:
        if not swap_block.startswith("swap="):
            raise InvalidTeamError(
                f"swap block must start with 'swap=', got {swap_block!r}",
                {"teamspec": raw, "swap_block": swap_block},
            )
        payload = swap_block[len("swap="):]
        for clause in payload.split(";"):
            clause = clause.strip()
            if not clause:
                continue
            if "->" not in clause:
                raise InvalidTeamError(
                    f"swap clause missing '->': {clause!r}",
                    {"teamspec": raw, "clause": clause},
                )
            out, ins = clause.split("->", 1)
            swaps.append(
                {
                    "out": out.strip(),
                    "in": [p.strip() for p in ins.split(",") if p.strip()],
                }
            )
    return {"team": team.strip(), "season": season, "swaps": swaps}


def render(spec: TeamSpec) -> str:
    base = f"{spec['team']}-{spec['season']}"
    if not spec["swaps"]:
        return base
    clauses = []
    for s in spec["swaps"]:
        ins = ",".join(s["in"])
        clauses.append(f"{s['out']}->{ins}")
    return f"{base}[swap={';'.join(clauses)}]"
