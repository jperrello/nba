from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Stint:
    period: int
    wall_start: float
    wall_end: float
    home: tuple[str, ...]
    away: tuple[str, ...]
    pts_home: int = 0
    pts_away: int = 0
    possessions_home: int = 0
    possessions_away: int = 0
    _fga_home: int = 0
    _fga_away: int = 0
    _fta_home: int = 0
    _fta_away: int = 0
    _to_home: int = 0
    _to_away: int = 0
    _orb_home: int = 0
    _orb_away: int = 0
    _raw_event_ids: list[int] = field(default_factory=list)


def derive_stints(
    events: list[dict[str, Any]],
    starters_home: list[str],
    starters_away: list[str],
) -> list[Stint]:
    stints: list[Stint] = []
    home = tuple(starters_home)
    away = tuple(starters_away)
    current = Stint(period=1, wall_start=0.0, wall_end=0.0, home=home, away=away)
    pending_ft: Stint | None = None

    def attribute_fga(team: str, target: Stint, made: bool, pts: int) -> None:
        if team == "home":
            target._fga_home += 1
            if made:
                target.pts_home += pts
        else:
            target._fga_away += 1
            if made:
                target.pts_away += pts

    for idx, e in enumerate(events):
        t = e["t"]
        et: str = e["type"]
        team: str = e.get("team") or ""
        period: int = e.get("period") or 0

        if et == "tipoff":
            continue

        if et == "sub":
            current.wall_end = t
            stints.append(current)
            p_out = e["player_out"]
            p_in = e["player_in"]
            if team == "home":
                home = tuple(p_in if p == p_out else p for p in home)
            else:
                away = tuple(p_in if p == p_out else p for p in away)
            current = Stint(period=period, wall_start=t, wall_end=t, home=home, away=away)
            continue

        if et == "period_end":
            current.wall_end = t
            stints.append(current)
            current = Stint(period=period + 1, wall_start=t, wall_end=t, home=home, away=away)
            pending_ft = None
            continue

        if et == "game_end":
            current.wall_end = t
            stints.append(current)
            break

        if et == "shooting_foul":
            pending_ft = current
            current._raw_event_ids.append(idx)
            continue

        if et in ("ft_made", "ft_miss"):
            target = pending_ft if pending_ft is not None else current
            if team == "home":
                target._fta_home += 1
                if et == "ft_made":
                    target.pts_home += 1
            else:
                target._fta_away += 1
                if et == "ft_made":
                    target.pts_away += 1
            target._raw_event_ids.append(idx)
            continue

        # any other event resets the FT carry
        pending_ft = None

        if et in ("made_2pt", "made_3pt", "missed_2pt", "missed_3pt"):
            pts = 2 if "2pt" in et else 3
            attribute_fga(team, current, et.startswith("made"), pts)
        elif et == "turnover":
            if team == "home":
                current._to_home += 1
            else:
                current._to_away += 1
        elif et == "rebound_off":
            if team == "home":
                current._orb_home += 1
            else:
                current._orb_away += 1
        # rebound_def is tracked but does not factor into Oliver poss for either team
        current._raw_event_ids.append(idx)

    else:
        last_t = events[-1]["t"] if events else current.wall_start
        current.wall_end = last_t
        stints.append(current)

    for s in stints:
        s.possessions_home = round(
            s._fga_home + 0.44 * s._fta_home + s._to_home - s._orb_home
        )
        s.possessions_away = round(
            s._fga_away + 0.44 * s._fta_away + s._to_away - s._orb_away
        )

    return stints
