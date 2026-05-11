# P0: ESPN API Coverage Validation

**Status:** complete (nba-b4o)
**Date:** 2026-05-11
**Author:** espn-lane
**Spec gate:** `SPEC.md` "Decisions to double-check #1 — ESPN API coverage"

## TL;DR

ESPN's public API gives us **everything we need to reconstruct lineup stints from 2003 onward**: full PBP with substitutions, athlete IDs on every sub, quarter+clock timestamps on every play, and per-game rosters from the boxscore. Coach attribution is fetchable as a separate season-level endpoint. One bad-data game was found in 2003 (1-play stub); the fetcher must treat thin PBP as a coverage gap, not a season-wide signal.

**Training-window recommendation: start at 2003 (the 2002-03 season).** The spec hedge "if pre-2010 is thin, start at 2010" does not bind — 2003 is workable.

## Sources

- Endpoints: per gullivan's `espn-api-refs` bd memory.
- Schedule: `site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/18/schedule?season=YYYY&seasontype=2`
- Game summary (boxscore + PBP embedded as `plays[]`): `site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=<gameId>`
- Coach roster: `sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/YYYY/teams/18/coaches` → follow `$ref` to coach detail.
- Rate-limit courtesy: 30s between calls (gullivan ref #9).
- All calls made with `User-Agent: Mozilla/5.0`; no auth, no key.

## Per-season findings

Knicks team ID = `18`. ESPN `season=YYYY` → season ending in `YYYY` (e.g., `season=2003` = 2002-03 season).

| Year (season) | Game | game_id | Boxscore | PBP | #Plays | Subs in PBP | #Subs | Sub has athlete IDs | clock+quarter on every play | Roster (boxscore.players) | Coach (separate endpoint) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2003 (2002-03) | Celtics @ NYK 2002-12-14 | `221214018` | Y | Y | 430 | Y | 44 | Y | Y | Y (12 + 12) | Y — Don Chaney |
| 2008 (2007-08) | Sixers @ NYK 2008-01-25 | `280125018` | Y | Y | 428 | Y | 44 | Y | Y | Y (15 + 15) | Y |
| 2013 (2012-13) | NYK @ Sixers 2013-01-26 | `400278363` | Y | Y | 438 | Y | 44 | Y | Y | Y (13 + 13) | Y |
| 2018 (2017-18) | NYK @ Wolves 2018-01-12 | `400975369` | Y | Y | 414 | Y | 43 | Y | Y | Y (13 + 13) | Y |
| 2023 (2022-23) | Pacers @ NYK 2023-01-11 | `401468777` | Y | Y | 469 | Y | 46 | Y | Y | Y (13 + 13) | Y — Tom Thibodeau |

All raw fixtures saved under `data/fixtures/espn/<year>/`.

### Field-by-field notes

**Boxscore.** Returned under `boxscore.players[].statistics[0].athletes[]`. Per-player fields used: `active`, `starter`, `didNotPlay`, `ejected`, `athlete.id`, `athlete.displayName`, `stats` (positional array — min/pts/FG/3P/FT/OREB/DREB/AST/STL/BLK/TO/PF/+/-).

**PBP.** Returned under top-level `plays[]`. Each play carries:
- `id`, `sequenceNumber`
- `type.{id,text}` — full inventory ranges 33–54 distinct types across our samples (Jump Shot, Defensive Rebound, Substitution, Free Throw, Personal Foul, Jump Ball, Start/End Period, etc.)
- `period.{number, displayValue}` — present on **every** play, all 5 samples
- `clock.displayValue` — present on **every** play, all 5 samples (`"7:52"`, `"5:26"`, etc.)
- `team.id` — present on most non-meta plays
- `participants[].athlete.id` — present on substitutions in all 5 years, present on most action plays from 2008+

**Substitutions.** Type `"Substitution"`. Two participants: `[{athlete.id: in-player}, {athlete.id: out-player}]`. Text format `"<X> enters the game for <Y>"`. Confirmed across all five seasons including 2003. This is the load-bearing signal for stint reconstruction.

**Roster (per game).** The `boxscore.players[].statistics[0].athletes[]` listing IS the game-day roster (players who suited up, with `didNotPlay` flag). No separate per-game roster endpoint is needed for v1.

**Coach.** Not in the `summary` endpoint. Available at `seasons/{YYYY}/teams/{teamId}/coaches` as `$ref` items → follow each to coach detail (`firstName`, `lastName`, `id`). This is **season-level**, not per-game: mid-season coaching changes return >1 item; per-game attribution requires disambiguating by date if the list has multiple coaches. Acceptable for v1 (spec says coach is a categorical feature, not load-bearing for the predictor).

## Coverage gaps observed

- **One bad PBP for game `230126018` (Suns @ NYK, 2003-01-25).** Summary returned exactly 1 play (`Start Period`) where the rest of the boxscore was intact. Sampling a different 2003 game (`221214018`) returned full 430-play PBP. **Implication:** treat thin PBP as a per-game data hole, not a season-wide signal. Fetcher should log a structured warning when `len(plays) < ~50` and fall back to boxscore-only for that game. The original broken fixture is intentionally NOT saved.
- **Coach is not per-game.** Mid-season coaching changes (e.g., NYK 2003-04 went Don Chaney → Herb Williams → Lenny Wilkens) require date-range disambiguation against the season-level coaches list.
- **No player tracking / shot locations beyond `coordinate.{x,y}`** — already out of scope per SPEC.

## Stint-reconstruction viability

For all five sample seasons, the minimum information required for stint derivation is present:

1. Substitution events with both in-player and out-player IDs **and** team ID
2. Quarter (`period.number`) + clock (`clock.displayValue`) on every play
3. Starters identifiable via `boxscore.players[].statistics[0].athletes[].starter`

This is sufficient for nba-3bh's fetcher and brutus's stint-derivation contracts.

## Training-window recommendation

**Start the training window at the 2002-03 season** (ESPN `season=2003`).

Rationale:
- PBP coverage is full and structurally identical from 2003 forward (sample size: 1 game per season ×5 seasons; types/fields converge).
- ESPN's stated "all box scores back to 1946-47" plus our 2003 PBP confirmation suggests the 2002-03 cutoff is the practical PBP floor — this matches the consensus floor across NBA stats sources (gullivan ref #13).
- The spec's downside hedge ("if pre-2010 is thin, start at 2010") is not necessary. We can train on ~22 seasons (2003-2024) instead of ~14.

Caveats before lighting up nightly ingest:
- We sampled ONE game per season. Before ingesting at scale, run a spot-check pass across ≥20 randomly-sampled games per season to estimate the `len(plays) < 50` data-hole rate. A rate >2% should trigger a backfill strategy (e.g., retry on different game-day or accept boxscore-only).
- Confirm pre-2003 (1996-2002) is genuinely empty before deciding to extend backward — out of scope for this gate.

## Fixtures committed

```
data/fixtures/espn/2003/schedule.json
data/fixtures/espn/2003/221214018.json            # full game summary (boxscore + PBP)
data/fixtures/espn/2003/coaches_list.json
data/fixtures/espn/2003/coach_4689.json           # Don Chaney
data/fixtures/espn/2008/schedule.json
data/fixtures/espn/2008/280125018.json
data/fixtures/espn/2013/schedule.json
data/fixtures/espn/2013/400278363.json
data/fixtures/espn/2018/schedule.json
data/fixtures/espn/2018/400975369.json
data/fixtures/espn/2023/schedule.json
data/fixtures/espn/2023/401468777.json
data/fixtures/espn/2023/coaches_list.json
data/fixtures/espn/2023/coach_6717.json           # Tom Thibodeau
```

These are the canonical inputs for brutus's stint-derivation contracts and the test corpus for nba-3bh (`respx`-mocked fetcher).
