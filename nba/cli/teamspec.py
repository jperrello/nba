from __future__ import annotations

from typing import TypedDict


class Swap(TypedDict):
    out: str
    in_: list[str]


class TeamSpec(TypedDict):
    team: str
    season: int
    swaps: list[dict]


def parse(spec: str) -> TeamSpec:
    spec = spec.strip()
    swap_block: str | None = None
    body = spec
    if "[" in spec:
        if not spec.endswith("]"):
            raise ValueError(f"unterminated swap block in teamspec: {spec!r}")
        body, rest = spec.split("[", 1)
        swap_block = rest[:-1]
    if "-" not in body:
        raise ValueError(f"teamspec must be 'team-season', got {body!r}")
    team, season_str = body.rsplit("-", 1)
    try:
        season = int(season_str)
    except ValueError as e:
        raise ValueError(f"teamspec season must be int, got {season_str!r}") from e
    swaps: list[dict] = []
    if swap_block is not None and swap_block:
        if not swap_block.startswith("swap="):
            raise ValueError(f"swap block must start with 'swap=', got {swap_block!r}")
        payload = swap_block[len("swap="):]
        for clause in payload.split(";"):
            clause = clause.strip()
            if not clause:
                continue
            if "->" not in clause:
                raise ValueError(f"swap clause missing '->': {clause!r}")
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
