# Lane C — Embeddings + Predictor v0 (ml-lane plan)

> **Status:** `nba-ibw` GREEN. Embeddings landed; brutus's `nba-bbq` smoke (5/5) passes.
> Next up: `nba-dd1` (predictor + real `nba sim`) and `nba-yb1` (validation gate).
> Owns beads: `nba-ibw` (embeddings), `nba-dd1` (predictor + real `nba sim`), `nba-yb1` (validation gate).
> Frozen surfaces: `nba/contracts.py`, the 14 sim contract tests in `tests/test_cli_contract.py`.

### Lane B handoff note (read before nba-dd1)

stints-lane's `docs/stints_validation.md` flagged a systematic **~5.5% possession undercount** (Oliver-weight bias, filed `nba-arn` P3). Net rating is bias-free (symmetric across off/def); raw per-possession ratings are inflated. **For the predictor target, use signed margin (`lineup_stints.pts = home_pts - away_pts`) weighted by `duration_seconds`, NOT divided by `possessions`.** Updates plan §5 — to be applied when starting `nba-dd1`.

### Scope adjustment for nba-ibw (landed)

- Built embeddings for **all 463 rostered players in season 2023** (30 teams), not NYK-only. Predictor (`nba-dd1`) needs opponent vectors too; doing it now avoids re-running training later. Brutus's smoke filters to NYK cohort (19 rows) and passes — superset is contract-compatible.
- **Skipped the SQL view** (`migrations/0003_player_season_stats_view.sql`). With random-init embeddings + no stat features in the predictor input (just embedding sums/means + era + flag), the per-(player, season) stat view has no consumer in v0. Defer to v1.

---

## 0. Scope and non-goals

In scope (this run):
- 128-dim `(player, season)` embedding, random init acceptable for v0.
- ~5M-param MLP predicting `(home_pts − away_pts)` per possession.
- MLflow file-backend tracking.
- Hungarian-assignment matchup in real `nba sim`, replacing the stub numbers.
- Held-out 5-game sanity eval on NYK 2022-23.

Out of scope:
- RAPM-style Bayesian shrinkage (v1).
- Multi-season pretraining — NYK 2022-23 only.
- FSDP / multi-GPU / cloud.
- Real `scouting_take` (LoRA is Lane D, deferred).
- Coach embeddings.

---

## 1. SQL view — per-(player, season) stat aggregates

File: `migrations/0003_player_season_stats_view.sql` (next free number; do not edit 0001 or 0002).

Materialized? **No.** A regular VIEW is enough for v0 — one season, one team, ~15-20 players. If we ever go multi-season, revisit.

### Stat columns (matches the brief)

`pts, ast, reb, stl, blk, tov, fga, fta, three_pa, min` — plus `gp` (games played) as a denominator option.

### Source mapping (using `event_type` enum documented in `docs/schema.md` line 146)

```
pts       SUM(points_scored) WHERE player_id = p
ast       COUNT(*) WHERE assist_player_id = p AND event_type IN ('made_2pt','made_3pt')
reb       COUNT(*) WHERE event_type IN ('rebound_off','rebound_def') AND player_id = p
stl       COUNT(*) WHERE event_type = 'steal' AND player_id = p
blk       COUNT(*) WHERE event_type = 'block' AND player_id = p
tov       COUNT(*) WHERE event_type = 'turnover' AND player_id = p
fga       COUNT(*) WHERE event_type IN ('made_2pt','missed_2pt','made_3pt','missed_3pt') AND player_id = p
fta       COUNT(*) WHERE event_type IN ('ft_made','ft_missed') AND player_id = p
three_pa  COUNT(*) WHERE event_type IN ('made_3pt','missed_3pt') AND player_id = p
min       SUM(duration_seconds) / 60.0 over lineup_stints where p ∈ home_lineup ∪ away_lineup
gp        COUNT(DISTINCT game_id) where p appears in any pbp_events row
```

`min` is the only one that joins through `lineup_stints` — the rest are pure `pbp_events` aggregations grouped by `player_id` joined to `games(season)`. The view returns one row per `(player_id, season)`.

### Shape

```sql
CREATE VIEW player_season_stats AS
SELECT
  pe.player_id,
  g.season,
  SUM(pe.points_scored)                              AS pts,
  -- counts as above
  -- min via subquery against lineup_stints
FROM pbp_events pe
JOIN games g ON g.game_id = pe.game_id
GROUP BY pe.player_id, g.season;
```

Final query is two CTEs joined: one over `pbp_events` for counts, one over `lineup_stints` for minutes. Keep it readable; perf doesn't matter at this size.

### Smoke test

`tests/test_player_season_stats_view.py` — gated by the same DB env var as Lane A's smoke test. Asserts: NYK 2022-23 has 15-20 rows, Brunson's pts is plausibly between 1500-2200, no NULL pts.

---

## 2. PyTorch embedding module

File: `nba/embeddings/model.py`.

### Architecture

```python
class PlayerSeasonEmbedding(nn.Module):
    def __init__(self, n_player_seasons: int, dim: int = 128):
        super().__init__()
        self.table = nn.Embedding(n_player_seasons, dim)
        nn.init.normal_(self.table.weight, std=0.02)
    def forward(self, idx):
        return self.table(idx)
```

128 dims matches `embeddings_player.embedding vector(128)`. Random init is the explicit v0 choice — the goal is to wire pgvector and the predictor end-to-end, not to publish a usable representation.

**Unit-normalize before persist** (per overseer ruling D4 — brutus's post-train smoke asserts `||v|| ≈ 1.0` per row). Done in `nba/embeddings/persist.py` via `v / max(||v||, eps)` immediately before the INSERT. Side benefit: §7's cosine-similarity matchup becomes a plain dot product.

### Index map

A separate file `nba/embeddings/index.py` maintains `(player_id, season) ↔ int idx`. Persisted in-process during training; embeddings written out by `(player_id, season)` so the int idx never escapes the training process.

### Why no MLP-encoder-over-stats for v0?

We *could* feed z-scored stats through a small encoder to produce the 128-d vector. But the brief says **random init is acceptable**, and the predictor MLP gets the embeddings as input *and gradient flows back*, so the embedding table will move toward something useful from the predictor loss alone. Adding an encoder doubles the moving parts without helping the wire-end-to-end goal.

### Input normalization (still relevant — fed to predictor concat, not the embedding)

z-score per-season per-league for each stat. Per-season because raw counts mean different things across eras; per-league because we only have one league.

`nba/embeddings/normalize.py`:
- `fit(stats: DataFrame) -> {mean, std}` per stat per season
- `transform(stats) -> Tensor` returning z-scored stats
- `era_token(season) -> float` scalar per season (for now: `(season - 2003) / 20.0` — a simple monotonic feature in `[~0, ~1.5]`).

---

## 3. Embeddings training loop

File: `nba/embeddings/train.py`.

For v0 with random init, "training" is the no-op case: instantiate, write to DB. But we keep a single optimizer step so the loop is exercised end-to-end and the wire is real.

```
1. Build (player_id, season) index from player_season_stats view.
2. Instantiate PlayerSeasonEmbedding(n, dim=128).
3. (Optional v0 step) one fake reconstruction loss against z-scored stats projected into 128-d
   via a random fixed linear map. Provides a non-zero training-loss artifact for MLflow.
4. mlflow.log_metric("loss", float(loss))  mlflow.log_param("model_version", "embeddings-v0")
5. Persist to embeddings_player via psycopg.
```

### MLflow

File backend at `mlruns/` (gitignore it). Experiment name: `embeddings`. Run name: `v0-randinit-<timestamp>`. Logs: `model_version` (param), `train_loss` (metric), `n_player_seasons` (param), `dim` (param).

### Persistence

`nba/embeddings/persist.py`:

```sql
INSERT INTO embeddings_player (player_id, season, model_version, embedding, minutes_sample)
VALUES (%s, %s, %s, %s::vector, %s)
ON CONFLICT (player_id, season, model_version) DO UPDATE
SET embedding = EXCLUDED.embedding,
    minutes_sample = EXCLUDED.minutes_sample;
```

`model_version` lives in `nba/embeddings/version.py` as `EMBEDDINGS_VERSION = "embeddings-v0-randinit"`. Bumping the string produces a new row family without breaking older rows.

### Entrypoint (overseer ruling D4: NO new CLI subcommand)

Script entrypoint, not a `nba ...` subcommand:

```
python -m nba.train.embeddings --season 2023 --team NYK [--epochs 1]
```

File: `nba/train/embeddings.py` (`__main__` block + a `main(season, team, epochs)` function that the smoke test can import). Same for the predictor: `python -m nba.train.predictor`.

### Post-train smoke contract

Filed: `nba-bbq` (P2, open) — gated by `nba-z3o` (closed) per overseer D4. Brutus writes the failing smoke when I signal ready on `nba-ibw`. Blocks both `nba-ibw` and `nba-dd1` until green.

Smoke runs *after* `python -m nba.train.embeddings` populates the table. Asserts:

- Row count in `embeddings_player WHERE season = 2023 AND model_version = EMBEDDINGS_VERSION` equals the count of distinct `player_id` in `rosters WHERE season = 2023 AND team_id = NYK`.
- `vector_dims(embedding) = 128` for every row.
- `||embedding||_2 ∈ [1 - 1e-4, 1 + 1e-4]` for every row (unit-norm).
- `season` column populated and `embeddings_player` is queryable via the existing `embeddings_player_model_idx`.

Factor the script so the smoke can hit `nba.train.embeddings.main(...)` directly, then re-query the DB to assert.

---

## 4. Predictor MLP

File: `nba/predictor/model.py`.

### Param budget

5 lineup × 128-d × 2 (sum, mean) × 2 (home, away) = 2560-d input + 1 (era) + 1 (home/away flag) = 2562 features.

```
fc1: 2562 → 1024     (2.6M params)
fc2: 1024 → 1024     (1.0M params)
fc3: 1024 → 256      (0.26M)
fc4: 256  → 1        (0.0003M)
total ≈ 3.9M params
```

ReLU between layers. Single scalar output = predicted `home_pts - away_pts` per possession (signed, range typically [-3, 3]).

### Input construction

```python
def features(home_emb, away_emb, era, home_flag):
    # home_emb: (5, 128) tensor
    h = torch.cat([home_emb.sum(0), home_emb.mean(0)])   # (256,)
    a = torch.cat([away_emb.sum(0), away_emb.mean(0)])   # (256,)
    # Wait — that's only 512. The 2560 above is wrong; the per-side concat is (sum, mean) of 128 each = 256.
    # 256 home + 256 away + 1 era + 1 flag = 514 features.
    return torch.cat([h, a, era.unsqueeze(0), home_flag.unsqueeze(0)])
```

**Correction to the budget:** input is **514-d**, not 2562. Revised param budget:

```
fc1: 514 → 2048      (1.05M)
fc2: 2048 → 2048     (4.20M)
fc3: 2048 → 512      (1.05M)
fc4: 512  → 1        (~0.0005M)
total ≈ 6.3M
```

Trim fc2 to 1024 if 6.3M feels heavy — anywhere in the 3–6M range is fine.

### `home_flag`

For per-stint records the home side is always "home"; flag is always 1.0 at training time. But at `nba sim` inference, we evaluate **both** sides as the offensive team — flag toggles. This is the lever that turns a per-possession net-points scalar into per-side scoring.

Concretely: predict `delta_home_off = MLP(home, away, era, flag=1)` (home is on offense) and `delta_away_off = MLP(away, home, era, flag=1)` (away is on offense, with the embeddings swapped). Then game-level reconstruction in §7 sums these over ~100 possessions per side.

---

## 5. Predictor training

File: `nba/predictor/train.py`.

### Dataset

```sql
SELECT season, home_lineup, away_lineup, home_pts, away_pts, possessions
FROM lineup_stints
WHERE season = 2023 AND possessions > 0;
```

Per-row training example:
- `x_home_emb = stack(emb[p] for p in home_lineup)`  (5, 128)
- `x_away_emb = stack(emb[p] for p in away_lineup)`  (5, 128)
- `y = (home_pts - away_pts) / possessions`  (scalar, per-possession net)
- Sample weight: `possessions` (so 60-possession stints dominate over 5-possession ones)

### Train/val/holdout split

**By game**, not by stint, to avoid leakage. NYK plays 82 games × ~2 stints-per-team-quarter × 4 quarters × 2 teams = on order of 1200-2000 stints/season. Plenty.

- **Holdout: 5 games** (the validation-gate set, see §8). Picked once, deterministically — see §8 for the seed and selection rule.
- **Val: 10 games** from the remaining 77. Random with fixed seed `42`.
- **Train: 67 games.** Everything else.

All splits live in `nba/predictor/split.py` as a function returning three `set[int]` of `game_id`. Stored game-id lists also written to `data/splits/predictor_v0.json` so the holdout set is reproducible across crew restarts.

### Loss + optimizer

- Loss: weighted MSE on per-possession net points. `loss = (weight * (pred - y)**2).sum() / weight.sum()`.
- Optimizer: `torch.optim.Adam(lr=1e-3)`. Vanilla. No scheduler in v0.
- Epochs: 50 (CPU OK at this dataset size).
- Batch size: 64 stints.

### Joint training: embeddings + predictor

Two optimizers, single backward pass. Embedding table receives gradient through the lineup index lookup. Both move; the predictor moves faster because random-init embeddings provide little signal at start.

### MLflow

Experiment: `predictor`. Run: `v0-<timestamp>`. Metrics: `train_loss`, `val_mse`, `epoch`. Params: `model_version`, `n_stints_train`, `n_stints_val`, `n_games_holdout=5`, `lr`, `epochs`, `batch_size`. Artifacts: trained weights as `predictor_v0.pt`.

`model_version` = `predictor-v0-<short-hash>` (hash of git HEAD + run-start ISO ts).

---

## 6. CLI wiring — `meta.model_versions`

The current stub in `nba/cli/main.py` (lines 75-85) returns:

```python
"model_versions": {"predictor": "stub-0.0", "embeddings": "stub-0.0", "lm": "stub-0.0"}
```

Replace with a function `nba/cli/model_meta.py:read_latest_versions()` that:

1. Reads `mlruns/` for the latest finished run in `experiment_name in ("predictor", "embeddings")`.
2. Returns `{"predictor": <run.params.model_version>, "embeddings": <run.params.model_version>, "lm": "placeholder-no-lora-v0"}`.
3. Falls back to `"stub-0.0"` + a structured warning if no run found.

`meta.stub` flips to `false` when both predictor and embeddings versions are non-stub.

---

## 7. Real `nba sim` — Hungarian matchups + team edges + score reconstruction

Replace the hardcoded `sim_data` dict in `nba/cli/main.py` lines 206-227 with a real path. **The contract from `nba/contracts.py:SimData` does not change.** All 14 of brutus's sim tests must stay green.

### Loading

`nba/sim/loader.py`:
- Resolve `team1` / `team2` via existing `teamspec.parse` → `{team, season}`.
- For each side: pull the season's most-recent starting lineup from `rosters` (or — once Lane B has it — the canonical "most-played 5-man unit" from `lineup_stints`). Resolves to 5 `player_id`s per side.
- For each `player_id`: load `embedding` vector from `embeddings_player` where `(player_id, season, model_version)` matches the version `meta.model_versions.embeddings`.

### Matchups via Hungarian assignment

`nba/sim/matchup.py`, uses `scipy.optimize.linear_sum_assignment`:

```python
def assign(home: np.ndarray, away: np.ndarray) -> list[tuple[int, int]]:
    # home, away: (5, 128). Cost = 1 - cosine_similarity.
    cost = 1 - (home @ away.T) / (np.linalg.norm(home, axis=1, keepdims=True) *
                                  np.linalg.norm(away, axis=1, keepdims=True).T)
    row, col = linear_sum_assignment(cost)
    return list(zip(row, col))
```

Distance = cosine. Reason: scale-invariant, plays nice with the per-feature variance random init produces. L2 is a fine alternative; document the choice.

Per-pair edge:

```python
edge = float(home[i] @ away[j] / (norm(home[i]) * norm(away[j])))  # in [-1, 1]
```

Maps to `Matchup.edge`. `note` stays null in v0 unless `|edge| < 0.1` (a flag for "cross-matchup ambiguous" — keeps the contract field exercised).

### Team edges

Synthesized from delta-embedding heuristics, since the v0 embedding has no semantic axes. v0 strategy: a fixed bank of 4 "fake-named" edges produced by projections of `(home.sum - away.sum)` onto 4 fixed random unit vectors generated once and stashed in `nba/sim/edge_basis.npy`. Each projection maps to a (tag, label) pair:

```
basis[0] → ("rebounding",            "rebound rate vs opponent frontcourt")
basis[1] → ("halfcourt_fit",         "halfcourt fit at the wings")
basis[2] → ("spacing",               "spacing vs opponent")
basis[3] → ("defensive_switchability", "switch coverage vs opponent ballhandlers")
```

`sign = '+'` if projection > 0, else `'-'`. `magnitude = abs(projection)`, scaled to roughly [0, 2] via a `tanh` to keep them comparable in the human-readable formatter.

This is **deliberately not "good."** It's a meaning-free transform that hits the contract shape. Lane D / a later slice replaces the basis with learned heads on top of trained embeddings.

### Score reconstruction

The MLP predicts `delta_per_possession`. Game-level score has to come back:

```python
delta_home_off = MLP(home_emb, away_emb, era, flag=1)   # home on offense
delta_away_off = MLP(away_emb, home_emb, era, flag=1)   # away on offense (swap inputs)
# League-average possessions/team/game ≈ 100. Use a fixed 100.
home_score = round(LEAGUE_AVG_PPP * 100 + delta_home_off * 100)
away_score = round(LEAGUE_AVG_PPP * 100 - delta_away_off * 100)
```

`LEAGUE_AVG_PPP = 1.13` for 2022-23 (hardcoded constant in `nba/sim/constants.py`; cite the source in a comment).

Note: `delta_home_off + delta_away_off` is the net per-possession score difference summed over both sides. The signs are arranged so a positive `delta_home_off` adds to home, a positive `delta_away_off` adds to away — symmetric. Tested in §8.

If predicted score lands outside [70, 150] per side at inference, log a warning and clamp to that range — defensive guardrail against a head-output-scale bug breaking the contract's `Score(home: int, away: int)`.

### Win probability

For v0: `win_prob.value = sigmoid((home_score - away_score) / 5.0)`. `ci = 0.10` constant. Standard 5-point spread → 0.5 win prob convention. Adequate for the contract; replaced with bootstrap intervals once we have multi-season data.

### `scouting_take`

Stays a placeholder string per the brief:
```
"scouting LM not yet trained — placeholder narrative"
```
Set in `generate_scouting_take()` (replacing the current stub at `nba/cli/main.py:102`). LoRA is deferred.

### `meta.stub`

Flips to `false` when both embeddings and predictor load successfully. Falls back to `true` with a `Warning(code="model_unavailable", ...)` when either is missing — old behavior preserved as fallback.

---

## 8. Validation gate (nba-yb1)

### Holdout selection

Deterministic. The 5 holdout games are chosen by:

```python
random.Random(20260511).sample(sorted(all_nyk_2023_game_ids), 5)
```

Stored in `data/splits/predictor_v0.json` under key `"holdout_game_ids"`. Documented in the eval doc with the seed for reproducibility.

### Procedure

For each of the 5 holdout games:

1. Pull **actual** starters via `get_starters(game_id)` (overseer ruling D5). Helper lives at `nba/sim/starters.py`:

   ```python
   def get_starters(game_id: int) -> tuple[list[int], list[int]]:
       """Return (home_starter_ids, away_starter_ids) from the cached ESPN summary.

       Reads boxscore.players[].statistics[0].athletes[] where the per-athlete
       'starter' flag is true (or the first 5 athletes per side if ESPN's
       per-game flag is missing — fall back, log a warning).
       """
   ```
   Read order (first hit wins): `config.ESPN_CACHE_DIR / "summary" / f"{game_id}.json"` (live cache, confirmed by espn-lane in `nba-kve` close), then `data/fixtures/espn/{game_id}.json` (committed fixtures for deterministic tests). `nba/config.py:ESPN_CACHE_DIR` resolves to `data/cache/espn/` and honors `NBA_ESPN_CACHE_DIR`.

2. Run `nba sim` with these starters. Mechanism: `nba/sim/loader.py` accepts an optional `starters` override; the held-out eval driver (a script, not a new CLI flag — keeps the contract frozen) calls into the same `sim_data(...)` core function with the override.

3. Capture predicted `score.home`, `score.away`.

4. Compare to actual `home_score`, `away_score` from `games`.

### Pass criteria (the actual gate)

**Predicted scores must land in [90, 130] per side for all 5 games.** Accuracy is not the bar; sanity is. A predicted 50 or 300 indicates an output-scale or reconstruction bug — fix before closing the bead.

Compute and log: per-side MSE, mean signed error, MAE. Qualitative note per game (e.g., "predicted 112-108, actual 119-103 — directionally right, magnitude off").

### Deliverable

`docs/predictor_v0_eval.md`, structured as:

```
## Holdout games (seed 20260511)
  game_id | date | opponent | actual | predicted | per-side error
  ...

## Aggregate
  mean abs error: X
  mean signed error: Y
  all-sides-in-[90,130]: PASS / FAIL

## Per-game notes
  ...

## Known limitations
  - Random-init embeddings
  - Single season
  - No RAPM shrinkage
  - Fixed 100 possessions / side assumption
```

If FAIL, the bead does not close. Iterate.

---

## 9. Test gating — keep brutus's 14 sim tests green

The contract tests in `tests/test_cli_contract.py` assert **shape**, not values. Sources of regression risk:

- `nba sim` must still return JSON validating against `SimData`. Score, win_prob, matchups (length 5), team_edges (length 4), scouting_take present.
- All 5 matchups must have valid `home_player` / `away_player` names — these come from `players.full_name` joined on the lineup `player_id`s.
- Team edges must have valid `tag`, `sign in {'+', '-'}`, `magnitude: float`, `label: str`. The 4-tag bank in §7 covers this.
- `meta.model_versions` must be `dict[str, str]`. The version-reader in §6 returns strings.
- `meta.cached: bool` — keep `False` for v0 (no cache yet).

I do **not** touch `tests/test_cli_contract.py`. I run it locally before closing each bead.

---

## 10. File inventory (what gets written)

```
migrations/0003_player_season_stats_view.sql       NEW (Lane C scaffold)
nba/embeddings/__init__.py                         NEW
nba/embeddings/model.py                            NEW — PlayerSeasonEmbedding
nba/embeddings/normalize.py                        NEW — z-score, era_token
nba/embeddings/index.py                            NEW — (player_id, season) ↔ idx
nba/embeddings/persist.py                          NEW — psycopg ON CONFLICT upsert; unit-norm before INSERT
nba/embeddings/version.py                          NEW — EMBEDDINGS_VERSION constant
nba/predictor/__init__.py                          NEW
nba/predictor/model.py                             NEW — MLP
nba/predictor/split.py                             NEW — deterministic train/val/holdout
nba/predictor/version.py                           NEW — version-string helper
nba/train/__init__.py                              NEW
nba/train/embeddings.py                            NEW — `python -m nba.train.embeddings` entrypoint (D4)
nba/train/predictor.py                             NEW — `python -m nba.train.predictor` entrypoint
nba/sim/__init__.py                                NEW
nba/sim/loader.py                                  NEW — load embeddings + lineups (accepts starters override)
nba/sim/starters.py                                NEW — get_starters(game_id) from ESPN summary cache (D5)
nba/sim/matchup.py                                 NEW — Hungarian assignment over unit-norm vectors
nba/sim/edges.py                                   NEW — team-edge basis projections
nba/sim/edge_basis.npy                             NEW — fixed random 4-d basis
nba/sim/constants.py                               NEW — LEAGUE_AVG_PPP etc.
nba/cli/model_meta.py                              NEW — MLflow → meta.model_versions
nba/cli/main.py                                    EDIT — sim path + meta
scripts/eval_predictor_v0.py                       NEW — drives 5-game holdout eval (not a CLI flag)
data/splits/predictor_v0.json                      NEW — holdout game IDs
mlruns/                                            NEW (gitignored)
docs/predictor_v0_eval.md                          NEW — validation-gate output
docs/ml_plan.md                                    THIS FILE
tests/test_player_season_stats_view.py             NEW — env-gated SQL view smoke
# tests/test_embeddings_persist_smoke.py           DEFERRED — brutus files when implementation begins (D4 ruling)
```

Notes:
- No edits to `migrations/0001_init.sql` or `migrations/0002_pbp_status.sql`.
- No edits to `nba/contracts.py`, `tests/test_cli_contract.py`, or the existing stints/ingest modules.

---

## 11. Order of operations

When Lane B closes (one season of stints persisted):

1. Land `migrations/0003_player_season_stats_view.sql` + its smoke test.
2. Land embeddings module + persist (with unit-norm) + `python -m nba.train.embeddings` script. Run end-to-end on NYK 2022-23. Verify `embeddings_player` row count = distinct NYK 2022-23 players from `rosters`. Wait for brutus's smoke contract bead → turn it green. **Close `nba-ibw`.**
3. Land predictor module + split + `python -m nba.train.predictor`. Verify MLflow run exists. **Do not close `nba-dd1` yet.**
4. Wire real `nba sim`: loader, `get_starters`, matchup, edges, reconstruction, model-meta reader. Run the 14 contract tests — all green.
5. Run validation gate via `scripts/eval_predictor_v0.py`: 5 holdout games with `get_starters(game_id)`-driven starters. Write `docs/predictor_v0_eval.md`. If all-sides-in-[90, 130], **close `nba-dd1` and `nba-yb1`.** If not, debug (likely the output-scale reconstruction in §7) and re-run.
6. `ruff check .` + `pyright .` clean. Commit + push. Route to athena.

---

## 12. Risk register

| Risk | Mitigation |
|---|---|
| Random-init embeddings drift to garbage during joint training, hurting predictor | Lower embedding LR (`1e-4`) vs MLP LR (`1e-3`); or freeze for first 10 epochs. Decide empirically. |
| Per-possession output scale wrong → game scores out of [90, 130] | Validation gate catches it. Likely fix: re-check sign convention in §7 and the `LEAGUE_AVG_PPP * 100` baseline. |
| `lineup_stints.possessions` is 0 for many rows (low-event stints) | Filter `WHERE possessions > 0` in the training query; document the row count drop. |
| MLflow file backend gets noisy across many runs | Single `mlruns/` directory, gitignored. Cleanup outside this slice. |
| `players.full_name` is missing for some player IDs the embedding has → matchup names break the contract | Defensive lookup in `nba/sim/loader.py` with fallback to `"Player {player_id}"` and a warning. |
| Lane B's stint deriver outputs `home_pts`/`away_pts` that don't reconcile to `pbp_events` boxscore | Cross-check at training-set load: assert `sum(stint.home_pts) ≈ game.home_score ± 4` per game. Warn-not-crash. |
| `embeddings_player.minutes_sample` — what do we put? | Per-(player, season) sum of `lineup_stints.duration_seconds / 60` from the stat view. Cap at INT range. |

---

## 13. Open coordination items

Resolved by overseer:

- ~~`nba embeddings train` CLI contract.~~ **D4: no CLI subcommand.** Script entrypoint `python -m nba.train.embeddings` per §3; brutus files a post-train DB smoke when implementation begins.
- ~~`--lineups-from-game` flag.~~ **D5: actual boxscore starters.** `get_starters(game_id)` helper at `nba/sim/starters.py` reads ESPN summary cache. Validation driver is a script (`scripts/eval_predictor_v0.py`), not a new CLI flag.

Still open:

- ~~ESPN summary cache path.~~ **Confirmed in `nba-kve` close: `nba/config.py:ESPN_CACHE_DIR` (resolves to `data/cache/espn/`).** `get_starters` reads from there with a fallback to `data/fixtures/espn/`.
- **`minutes_sample` source.** Per-(player, season) sum of `lineup_stints.duration_seconds / 60` from the stat view, cast to INT. Already noted in row 7 of the risk register.

---

## 14. What I'm NOT doing during the wait

- Not touching Lane A/B/D code.
- Not modifying `nba/contracts.py`.
- Not modifying `tests/test_cli_contract.py`.
- Not training on multi-season data.
- Not adding RAPM in v0.
- Not adding a real `scouting_take`.

When Lane B signals done in athena, I move from scaffold to implementation in order §11.
