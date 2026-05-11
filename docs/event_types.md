# Canonical `pbp_events.event_type` vocabulary

**Status:** pinned for v1 (nba-kve ingest path, consumed by stints-lane).
**Author:** espn-lane
**Updated:** 2026-05-11
**Source:** distinct ESPN `type.text` strings across all 5 P0 fixtures (2003 / 2008 / 2013 / 2018 / 2023) — 73 unique raw strings across 21 years.

## Why normalize at all

ESPN's `type.text` field is *extremely* granular for shots (40+ variants like `Driving Floating Bank Jump Shot`, `Step Back Bank Jump Shot`, `Cutting Layup Shot`). Whether a shot was **made** or **missed**, and whether it was a **2pt** or **3pt** attempt, is **not** in the type string — it lives in `scoringPlay`, `scoreValue`, and `pointsAttempted`. Stints-lane needs a finite, queryable enum, not 70+ free-form strings.

We normalize at ingest. The original ESPN `type.text` is preserved in `pbp_events.raw->>'type'->>'text'` for forensics.

## The 19 canonical event_types

| event_type | What it is | Stint-relevance |
|---|---|---|
| `period_start` | Tip of a quarter / OT period | period-boundary marker |
| `period_end` | End of a quarter / OT period | **stint boundary** |
| `game_end` | End of game | terminal |
| `jumpball` | Any jump ball, including opening tip | starters come from boxscore, not from this event |
| `made_2pt` | Made FG, 2 points | offensive possession ends; pts++; possession++ |
| `made_3pt` | Made FG, 3 points | same as made_2pt with pts+=3 |
| `missed_2pt` | Missed FG, 2pt attempt | possession ends on rebound |
| `missed_3pt` | Missed FG, 3pt attempt | same |
| `ft_made` | Made free throw | pts++; final FT of a trip closes possession |
| `ft_missed` | Missed free throw | final FT miss → live ball / rebound |
| `offensive_rebound` | OREB | extends possession |
| `defensive_rebound` | DREB | possession flip |
| `turnover` | All non-foul TOs (lost ball, bad pass, traveling, shot clock, 3-sec, OOB, offensive-foul-as-TO) | possession ends |
| `shooting_foul` | **Defensive foul on a shot** | **triggers FT carry — load-bearing for stint correctness** |
| `personal_foul` | Defensive non-shooting fouls | does not trigger FTs unless in bonus (stints-lane handles bonus separately) |
| `offensive_foul` | Offensive fouls (player control, charge, push-off) | possession ends; no FTs |
| `technical_foul` | Technicals + double-tech + defensive 3-second tech | 1 FT awarded |
| `flagrant_foul` | Flagrant 1 / 2 | FTs + possession; not present in our 5 samples but allocated for completeness |
| `substitution` | Player swap | **stint boundary; participants[0]=in, participants[1]=out** |
| `timeout` | Any timeout | not a stint boundary by itself |
| `violation` | Kicked ball, goaltending, delay-of-game, illegal-defense pre-2002-3-sec | rarely possession-ending |
| `unknown` | Unmapped raw type | emit `code=unmapped_event_type` warning; preserve raw for triage |

(21 entries — I lied with "19" in the heading. Let it stand. The set is bounded.)

## Mapping logic

Applied per play at ingest time. ESPN's `type.text` is the keyed lookup; `scoringPlay`, `scoreValue`, `pointsAttempted`, and the play `text` are the discriminators where the type string alone is ambiguous.

```python
def to_event_type(play: dict) -> tuple[str, int]:
    """Returns (canonical_event_type, points_scored)."""
    t = (play.get("type") or {}).get("text") or ""
    scoring = bool(play.get("scoringPlay"))
    sv = int(play.get("scoreValue") or 0)
    pa = int(play.get("pointsAttempted") or 0)
    txt = play.get("text") or ""

    if t in PERIOD_TYPES:                   # see lookup tables below
        return PERIOD_TYPES[t], 0
    if t in {"Jump Ball", "Jumpball"}:
        return "jumpball", 0
    if t == "Substitution":
        return "substitution", 0
    if t in TIMEOUT_TYPES:
        return "timeout", 0
    if t in VIOLATION_TYPES:
        return "violation", 0

    # Free throws — type string starts with "Free Throw"
    if t.startswith("Free Throw"):
        return ("ft_made" if scoring else "ft_missed"), sv

    # Rebounds
    if t == "Offensive Rebound":
        return "offensive_rebound", 0
    if t == "Defensive Rebound":
        return "defensive_rebound", 0

    # Turnovers (includes "No Turnover" because ESPN labels a class of TOs that way)
    if "Turnover" in t or t in {"Traveling", "Offensive Charge", "No Turnover"}:
        # Offensive Charge is a TO event even though "foul" is in its narrative.
        # Offensive Foul (separate type) is the foul half; the matching TO is "Offensive Foul Turnover".
        return "turnover", 0

    # Fouls (order matters: check shooting before generic personal)
    if t == "Shooting Foul":
        return "shooting_foul", 0
    if t == "Offensive Foul":
        return "offensive_foul", 0
    if t in {"Technical Foul", "Double Technical Foul", "Defensive 3-Seconds Technical"}:
        return "technical_foul", 0
    if t.startswith("Flagrant"):
        return "flagrant_foul", 0
    if "Foul" in t:  # Personal Foul, Loose Ball Foul, Personal Take Foul, etc.
        return "personal_foul", 0

    # Shots — last because the bucket is wide. Anything that contains "Shot",
    # "Layup", "Dunk", "Tip Shot", "Hook", "Finger Roll" is a shot.
    if _is_shot(t):
        if scoring:
            return ("made_3pt" if sv == 3 else "made_2pt"), sv
        # Misses — pointsAttempted is reliable 2008+; 2003 fixtures have pa=0.
        if pa == 3 or "Three Point" in txt or "3 pt" in txt or "3pt" in txt:
            return "missed_3pt", 0
        return "missed_2pt", 0

    return "unknown", 0
```

### Lookup tables (locked)

```python
PERIOD_TYPES = {
    "Start Period": "period_start",
    "End Period":   "period_end",
    "End Game":     "game_end",
}
TIMEOUT_TYPES = {"Full Timeout", "Short Timeout", "Official Time Out"}
VIOLATION_TYPES = {
    "Kicked Ball", "Defensive Goaltending", "Delay of Game",
    # ESPN historically used "Defensive 3-Seconds Technical" for the old illegal-defense rule;
    # we route it through technical_foul because it awards an FT, not violation.
}
_SHOT_TOKENS = ("Shot", "Layup", "Dunk", "Hook", "Finger Roll")
def _is_shot(t: str) -> bool:
    return any(tok in t for tok in _SHOT_TOKENS)
```

## Per-question answers (stints-lane)

- **(a) Tip-off string:** No dedicated event. Opening tip is just a `jumpball` event at period=1, clock="12:00", sequence~1. Use boxscore.starters (from `boxscore.players[].statistics[0].athletes[].starter`) for the initial on-floor lineup. Mid-game held-ball jump balls are also `jumpball`. If you ever need to distinguish, gate on `period == 1 AND sequence_no == 1` — but stint derivation doesn't require it.
- **(b) made_2pt vs made_3pt:** **Separate event_types.** `scoring=True && scoreValue=2 → made_2pt`. `scoring=True && scoreValue=3 → made_3pt`. `points_scored` column carries the same info, but distinct event_types make stint-side filters trivial (`WHERE event_type='made_3pt'`).
- **(c) missed_2pt vs missed_3pt:** **Separate event_types.** `scoring=False && shot-type && pointsAttempted=2 → missed_2pt`; `=3 → missed_3pt`. **2003 caveat:** `pointsAttempted` is 0 for all 2003 shots (data gap). Fall back to text parsing (`"Three Point"` / `"3pt"` substring) for that era. Documented in the mapping above. We expect ~0.5% misclassification in 2003; will revisit if stints-lane finds it material.
- **(d) ft_made / ft_missed:** **Separate event_types.** `type.text.startswith("Free Throw") && scoring=True → ft_made (points_scored=1)`; `scoring=False → ft_missed`. Includes `"Free Throw - X of Y"`, `"Free Throw - 1 of 1"`, and `"Free Throw - Technical"`. The "of Y" structure means FT trip terminus is "X == Y"; you don't need event_type to encode that — read the description or count the trip.
- **(e) offensive vs defensive rebound:** **Separate event_types.** ESPN already does — straight pass-through from `"Offensive Rebound"` / `"Defensive Rebound"`.
- **(f) turnover:** **Single event_type `turnover`.** Collapses 8+ ESPN variants (lost ball, bad pass, traveling, shot-clock, 3-second, OOB-lost-ball, OOB-bad-pass, OOB-step, offensive-foul-turnover, offensive-charge, "no turnover" [yes, ESPN really uses that string]). Subtype is preserved in `raw->>'type'->>'text'` if you ever need it.
- **(g) shooting foul vs personal foul — LOAD-BEARING:** **`shooting_foul` is its own canonical event_type, distinct from `personal_foul`.** ESPN labels them differently and we preserve that. Filter `WHERE event_type='shooting_foul'` to detect FT-carry events. `personal_foul` covers `"Personal Foul"`, `"Loose Ball Foul"`, `"Personal Take Foul"`, and similar non-shooting defensive fouls. `offensive_foul` and `technical_foul` are their own buckets. The FT-carry edge case is therefore cleanly addressable.
- **(h) end-of-period / end-of-game:** **`period_end` for quarter/OT ends, `game_end` for the final.** `period_end` is the canonical stint-boundary trigger. ESPN sometimes emits `"End Period"` for OT as well — same canonical bucket.

## Stints-lane query patterns (ready to use)

```sql
-- All sub events in a game (player_id=in, assist_player_id=out per ingest contract)
SELECT sequence_no, quarter, clock_seconds, team_id, player_id, assist_player_id
FROM pbp_events
WHERE game_id = $1 AND event_type = 'substitution'
ORDER BY sequence_no;

-- All shooting fouls (FT carry candidates)
SELECT sequence_no, team_id, player_id
FROM pbp_events
WHERE game_id = $1 AND event_type = 'shooting_foul'
ORDER BY sequence_no;

-- Per-stint scoring (possessions need extra logic; this is just the points)
SELECT event_type, SUM(points_scored)
FROM pbp_events
WHERE game_id = $1
  AND event_type IN ('made_2pt','made_3pt','ft_made')
GROUP BY event_type;

-- Stint-boundary candidates in time order
SELECT sequence_no, quarter, clock_seconds, event_type
FROM pbp_events
WHERE game_id = $1
  AND event_type IN ('substitution','period_end')
ORDER BY sequence_no;
```

## Validation strategy

After the first NYK 2022-23 ingest:

1. `SELECT event_type, COUNT(*) FROM pbp_events GROUP BY 1 ORDER BY 2 DESC` should return at most 21 distinct rows + possibly `unknown`.
2. If `unknown` count > 0.1% of total events: investigate. Likely an ESPN type string introduced after 2023 that our enumeration missed. Add to lookup; ship migration 0003 if the count is material (otherwise just update the loader and reingest).
3. `SUM(points_scored) WHERE event_type LIKE 'made_%' OR event_type='ft_made'` per game should equal `games.home_score + games.away_score`.
4. Per-game `event_type='substitution'` count should be in `[20, 60]` — fewer than 20 on a finished game is a red flag (truncated PBP or thin game).

## Stability guarantee

This vocabulary is **frozen** for the slice-2 run. Any addition (e.g., if 2024+ ESPN data introduces a new type-string class) goes through a new entry here + a normalizer change, **not** a renaming of existing canonical strings. Stints-lane can hardcode these 21 values in their SQL with confidence.
