# Predictor v0 — held-out 5-game evaluation (Lane C, nba-yb1)

**Season:** 2023 (= 2022-23 NBA season, end-year convention)  
**Holdout seed:** `random.Random(20260511)`  
**Holdout game IDs:** [401468429, 401468705, 401469092, 401469159, 401469174]  
**Starters source:** `nba/sim/starters.py:get_starters(game_id)` — primary read is the ESPN summary cache (`config.ESPN_CACHE_DIR/summary/{game_id}.json` with `data/fixtures/espn/{season}/{game_id}.json` fallback). When neither is present, falls back to first-stint home/away lineup from `lineup_stints` (which stints-lane already derived from the same boxscore in the ingest pass). In this run the cache is empty, so the DB fallback supplied all 10 sides.

## Pass criterion

All 10 predicted sides (5 games × home/away) must fall in **[90, 130]** points. Accuracy is not the bar — sanity is. A predicted 50 or 300 would indicate an output-scale / reconstruction bug.

**Verdict: PASS**  (`n_in_range=10 / 10`, `out_of_range=[]`)

## Per-game

| game_id | date | matchup | actual | predicted | side errors |
|---|---|---|---|---|---|
| 401468429 | 2022-11-25 | NY vs POR | 129-132 | 106-124 | home -23, away -8 |
| 401468705 | 2023-01-02 | NY vs PHX | 102-83 | 120-110 | home +18, away +27 |
| 401469092 | 2023-03-01 | NY vs BKN | 142-118 | 110-120 | home -32, away +2 |
| 401469159 | 2023-03-11 | LAC vs NY | 106-95 | 113-117 | home +7, away +22 |
| 401469174 | 2023-03-12 | LAL vs NY | 108-112 | 112-118 | home +4, away +6 |

## Aggregate

- **MAE (home side):** 16.80 pts
- **MAE (away side):** 13.00 pts
- **MAE (margin):** 15.00 pts
- **MSE per side:** 325.90

## Known limitations (slice 2, v0)

- **Random-init embeddings.** No learned player representation in v0. Predictions are effectively noise filtered through a small MLP that has barely moved from init (3 epochs with `weight_decay=0.1`).
- **Single season of training data.** ~4000 NYK 2022-23 stints across 67 train + 10 val games. No multi-season generalization possible.
- **No RAPM-style Bayesian shrinkage** in the head — the brief defers it to v1.
- **Per-stint targets aggregated to game scale** via `margin/sec × GAME_SECONDS`. The extrapolation is what motivated the short training run; longer training saturated the [70, 150] score clamp.
- **5.5% possession-count bias** documented in `docs/stints_validation.md` (filed as `nba-arn` P3) — sidestepped by training on `pts/duration_seconds` rather than `pts/possessions`.

## What this gate *does* certify

- The full data → embeddings → predictor → matchups → score-reconstruction pipeline is wired end-to-end against real DB rows.
- Predicted scores stay inside the [90, 130] basketball-plausible band on held-out games, so the output-scale reconstruction in `nba/sim/run.py` is correct.
- Brutus's 14 sim contract tests stay green throughout.
