# CONTRACT — nba-6gz: PBP → stint derivation correctness

**Author:** brutus
**Implementer:** stints-lane (nba-8gq)
**Status:** red captured. Tests must turn green by implementing `derive_stints`.

## Spec restatement

`nba.stints.derive.derive_stints(events, starters_home, starters_away)` consumes
a list of play-by-play events plus the starting lineups and returns an ordered
list of lineup stints. A *stint* is a maximal interval during which the same ten
players are on the floor AND the period does not change. The function must
correctly attribute scoring AND possessions to each stint, including the
edge case where a substitution interrupts an in-flight possession.

## Files

- `tests/fixtures/pbp_minigame.json` — hand-crafted 3-minute (180s wall-clock)
  fixture: two periods, two substitutions in period 1, one quarter boundary, one
  shooting foul straddling a substitution. `_expected_stints` is the ground
  truth; `final_box` is the box score the stint totals must reconcile to.
- `tests/test_stints.py` — eight assertion families covering the bead's
  correctness requirements plus a lineup-composition check.

## Run command

```bash
pytest tests/test_stints.py -v
```

## API under contract

```python
def derive_stints(
    events: list[dict],
    starters_home: list[str],
    starters_away: list[str],
) -> list[Stint]
```

Each returned `Stint` must expose:
- `period: int`
- `wall_start: float`, `wall_end: float` — seconds since tipoff, half-open `[start, end)`
- `home: Iterable[str]`, `away: Iterable[str]` — 5 player ids each
- `pts_home: int`, `pts_away: int`
- `possessions_home: int`, `possessions_away: int`

A `dataclass`, `pydantic.BaseModel`, or even a `dict` with these keys is
acceptable — the tests use `getattr`-with-`__getitem__`-fallback.

## Event schema

See the `_event_schema` block in the fixture. Key types this contract pins:
`tipoff`, `made_2pt`, `made_3pt`, `missed_2pt`, `missed_3pt`, `ft_made`,
`ft_miss`, `rebound_off`, `rebound_def`, `turnover`, `shooting_foul`, `sub`,
`period_end`, `game_end`.

## Assertion list (all must pass)

1. **Stint count.** `len(stints) == #subs + #period_ends + 1`.
2. **5-on-5.** Every stint has exactly 5 unique home and 5 unique away players.
3. **Boundaries.** Every `wall_end` (except the last stint's) equals the
   timestamp of a `sub` or `period_end` event.
4. **Scoring attribution.** `stint.pts_home / pts_away` matches the
   `_expected_stints` ground truth.
5. **Possessions (Oliver, ±1).** `poss ≈ FGA + 0.44*FTA + TO − ORB` per team per
   stint, within ±1 of the ground truth.
6. **Box-score reconciliation.** `sum(stint.pts_home) == box.pts_home` and
   `sum(stint.pts_away) == box.pts_away`.
7. **No stint crosses a quarter.** If consecutive stints differ in period, the
   boundary must coincide exactly (`wall_end_i == wall_start_{i+1}`).
8. **Sub mid-possession.** Shooting foul at `t=29` (stint 0), substitution at
   `t=30`, free throws at `t=31-32`. The FT points accrue to **stint 0** (the
   stint at possession start), not stint 1. Stint 0's `wall_end` is still `30`;
   the boundary moves regardless of the possession.

## Oracle

The fixture's `_expected_stints` is the ground truth. Tests compare returned
stints positionally to this list. If `derive_stints` produces the wrong number,
wrong lineups, wrong points, wrong possessions, or attributes the FTs to the
wrong stint, the test fails with a specific diagnostic.

## Out of scope

- ESPN PBP normalization. The fixture's event schema is canonical for this
  contract; ingest mappers are a separate concern.
- Per-player on/off stats. Only stint-level totals are pinned.
- Game clock vs. shot clock vs. wall clock distinctions. Wall clock (`t`) is
  authoritative here.
- Overtime, replay reviews, technical free throws. Out of scope for v1.

## Red transcript

Captured at `.brutus/nba-6gz/transcript.md` (see "red sha" in bead notes).
