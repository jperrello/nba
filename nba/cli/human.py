from __future__ import annotations

import textwrap
from typing import Any

WIDTH = 63
WRAP_WIDTH = 50

TEAM_ABBR = {
    "hawks": "ATL", "celtics": "BOS", "nets": "BKN", "hornets": "CHA",
    "bulls": "CHI", "cavaliers": "CLE", "mavericks": "DAL", "nuggets": "DEN",
    "pistons": "DET", "warriors": "GSW", "rockets": "HOU", "pacers": "IND",
    "clippers": "LAC", "lakers": "LAL", "grizzlies": "MEM", "heat": "MIA",
    "bucks": "MIL", "timberwolves": "MIN", "pelicans": "NOP", "knicks": "NYK",
    "thunder": "OKC", "magic": "ORL", "76ers": "PHI", "sixers": "PHI",
    "suns": "PHX", "trail-blazers": "POR", "blazers": "POR", "kings": "SAC",
    "spurs": "SAS", "raptors": "TOR", "jazz": "UTA", "wizards": "WAS",
}


def _abbr(team: str) -> str:
    return TEAM_ABBR.get(team.lower(), team.upper()[:3])


def _bar() -> str:
    return "═" * WIDTH


def render_sim(t1: Any, t2: Any, data: dict, warnings: list[dict]) -> str:
    lines: list[str] = []
    score = data["score"]
    wp = data["win_prob"]
    a1 = _abbr(t1["team"])
    a2 = _abbr(t2["team"])
    suffix1 = " (alt)" if t1.get("swaps") else ""
    suffix2 = " (alt)" if t2.get("swaps") else ""

    lines.append(_bar())
    lines.append(
        f"  {a1}{suffix1} {score['home']}  —  {a2}{suffix2} {score['away']}"
        f"     win prob: {wp['value']:.2f} ± {wp['ci']:.2f}"
    )
    lines.append(_bar())

    lines.append("")
    lines.append("Key matchups (Hungarian-assigned):")
    home_w = max(len(m["home_player"]) for m in data["matchups"])
    away_w = max(len(m["away_player"]) for m in data["matchups"])
    flagged: list[str] = []
    for m in data["matchups"]:
        edge = m["edge"]
        side = a1 if edge >= 0 else a2
        sign = "+" if edge >= 0 else "-"
        marker = " *" if m.get("note") else ""
        lines.append(
            f"  {m['home_player']:<{home_w}}  vs  {m['away_player']:<{away_w}}"
            f"    edge: {side}  ({sign}{abs(edge):.1f}){marker}"
        )
        if m.get("note"):
            flagged.append(m["note"])
    if flagged:
        lines.append("")
        for note in flagged:
            wrapped = textwrap.fill(
                f"* {note}",
                width=WIDTH - 2,
                initial_indent="  ",
                subsequent_indent="    ",
            )
            lines.append(wrapped)

    lines.append("")
    lines.append("Team edges:")
    for edge in data.get("team_edges", []):
        sign = edge.get("sign", "+")
        lines.append(f"  {sign} {edge['label']}")

    take = data.get("scouting_take")
    if take:
        lines.append("")
        lines.append("Scouting take:")
        for para in str(take).split("\n\n"):
            wrapped = textwrap.fill(
                para.strip(),
                width=WRAP_WIDTH,
                initial_indent="  ",
                subsequent_indent="  ",
            )
            lines.append(wrapped)

    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings:
            msg = w.get("message", "")
            ctx = w.get("context") or {}
            n = ctx.get("n_effective")
            if n is not None and "n_effective" not in msg:
                msg = f"{msg} (n_effective ≈ {n})"
            wrapped = textwrap.fill(
                msg,
                width=WRAP_WIDTH,
                initial_indent="  • ",
                subsequent_indent="    ",
            )
            lines.append(wrapped)

    return "\n".join(lines) + "\n"
