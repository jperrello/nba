from __future__ import annotations

from nba.cli.human import render_sim

SIM_DATA = {
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
        {"tag": "spacing", "sign": "-", "magnitude": 1.2, "label": "lost spacing relative to actual roster"},
    ],
    "scouting_take": "This is the Knicks team Knicks fans keep dreaming about.",
}

T1 = {"team": "knicks", "season": 2024, "swaps": [{"out": "kat", "in": ["randle"]}]}
T2 = {"team": "pacers", "season": 2024, "swaps": []}

WARNINGS = [
    {
        "code": "sparse_data",
        "message": "lineup support is thin",
        "context": {"n_effective": 340},
    }
]


def test_header_includes_team_abbrev_and_alt_marker():
    out = render_sim(T1, T2, SIM_DATA, WARNINGS)
    first_chunk = out.split("\n", 4)[1]
    assert "NYK" in first_chunk
    assert "IND" in first_chunk
    assert "(alt)" in first_chunk
    assert "114" in first_chunk and "109" in first_chunk
    assert "0.61" in first_chunk and "0.08" in first_chunk


def test_swap_only_on_swapped_side():
    out = render_sim(T1, T2, SIM_DATA, WARNINGS)
    header = out.split("\n", 4)[1]
    assert "NYK (alt)" in header
    assert "IND (alt)" not in header


def test_matchup_edge_attribution_uses_home_team_for_positive():
    out = render_sim(T1, T2, SIM_DATA, WARNINGS)
    assert "edge: NYK  (+0.7)" in out
    assert "edge: IND  (-0.4)" in out


def test_flagged_matchup_gets_asterisk_and_note():
    out = render_sim(T1, T2, SIM_DATA, WARNINGS)
    assert "Anunoby" in out and " *" in out
    assert "cross-matchup flag" in out


def test_team_edges_render_with_sign_prefix():
    out = render_sim(T1, T2, SIM_DATA, WARNINGS)
    assert "+ rebound rate vs Indiana frontcourt" in out
    assert "- lost spacing relative to actual roster" in out


def test_scouting_take_section_present_when_truthy():
    out = render_sim(T1, T2, SIM_DATA, WARNINGS)
    assert "Scouting take:" in out
    assert "Knicks fans" in out


def test_scouting_take_section_omitted_when_null():
    sim = {**SIM_DATA, "scouting_take": None}
    out = render_sim(T1, T2, sim, WARNINGS)
    assert "Scouting take:" not in out


def test_warnings_section_renders_n_effective_only_once():
    msg_with_n = "lineup support is thin (n_effective ≈ 340); priors blended"
    warnings = [
        {"code": "sparse_data", "message": msg_with_n, "context": {"n_effective": 340}}
    ]
    out = render_sim(T1, T2, SIM_DATA, warnings)
    assert out.count("n_effective") == 1


def test_warnings_section_appends_n_effective_when_message_lacks_it():
    warnings = [
        {"code": "sparse_data", "message": "thin lineup", "context": {"n_effective": 340}}
    ]
    out = render_sim(T1, T2, SIM_DATA, warnings)
    assert "n_effective ≈ 340" in out


def test_unknown_team_falls_back_to_uppercase_prefix():
    t1 = {"team": "Furniture", "season": 2024, "swaps": []}
    out = render_sim(t1, T2, SIM_DATA, WARNINGS)
    assert "FUR" in out.splitlines()[1]


def test_empty_warnings_omits_warnings_section():
    out = render_sim(T1, T2, SIM_DATA, [])
    assert "Warnings:" not in out
