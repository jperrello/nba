# Overseer Brief — nba slice 2 (data → real models)

Authoritative scope for the **current autonomous run**. The prior run's brief landed the foundation: project skeleton, P0 ESPN validation, schema + migrations, CLI contracts with stub data, stint deriver on a fixture, ESPN fetcher module. See `git log` and `docs/p0_espn_coverage.md` for what's already real.

## What this repo is

NBA lineup-analytics backend with two modes (data-app + simulation) exposed via an agent-facing Python CLI. Full vision lives in `SPEC.md` and `DESIGN_FICTION.md` — read both.

## Scope of *this* run

Turn the stubs into real data. By the end of this slice, `nba lineup stats` and `nba sim` should return numbers computed from actual 2022-23 Knicks data, not hardcoded placeholders. The JSON contracts from slice 1 stay frozen — only the values inside change.

Four lanes. A → B → C is a dependency chain; D runs in parallel.

### Lane A — Real ingest into Postgres (gates B and C)

1. Local Postgres 16 + pgvector via Docker. Add `make db-up`, `make db-down`, `make db-reset` targets. Connection details in `nba/config.py` (env-driven, defaults to localhost). No RDS / Terraform / cloud anything this run.
2. Apply `migrations/0001_init.sql` cleanly. If you find a bug in the schema, write a new `migrations/0002_*.sql` rather than editing 0001.
3. New subcommand: `nba ingest season --team NYK --season 2023 [--dry-run]`. Wires the existing `nba/ingest/espn.py` fetcher to the DB. Populates `teams`, `players`, `games`, `rosters`, `pbp_events`, `coach_games`. **Idempotent** (re-running produces no diffs). Respect the 30s rate-limit noted in `docs/p0_espn_coverage.md`. Default cache to `data/cache/espn/`.
4. Bad-PBP handling: when a game returns `len(plays) < 50`, log a structured warning, mark the game `pbp_status='thin'` (add column in 0002 migration), keep boxscore data, skip stints. Do NOT crash the whole ingest.

**Validation gate:** after ingesting NYK 2022-23, row counts must be plausible:
- `games` for NYK 2022-23 regular season: 82.
- `pbp_events` total: ~35-40k.
- `rosters` (NYK 2022-23): 15-20 distinct players.
Hardcode these into a `tests/test_ingest_smoke.py` that runs against the live local DB and is gated by an env var so CI doesn't try to hit ESPN.

### Lane B — Stints at scale + real `nba lineup stats`

1. `nba stints derive --game-id <X>` and `nba stints derive --season 2023 --team NYK` drivers. Wrap the existing `nba/stints/derive.py` (already 9/9 green on the fixture) with DB read/write. Persist to `lineup_stints` with the hashes the schema defines.
2. Replace the stub in `nba lineup stats --players P1 P2 P3 P4 P5 --season 2023` with a real SQL query against `lineup_stints`. Return real stint count, possessions, net rating.
3. Keep the JSON contract from slice 1 (`tests/test_cli_contract.py`) green. Only the numbers change.

**Validation gate (this is the load-bearing one):** pick 2 well-known 2022-23 NYK lineups and compare per-100 numbers to **Cleaning the Glass** (https://cleaningtheglass.com) and **PBPStats** (https://www.pbpstats.com). Accept ±5%; investigate ±5-10%; treat >10% as a deriver bug. Document the comparison in `docs/stints_validation.md`. Without this gate the whole pipeline is "shape-correct, value-meaningless."

### Lane C — Embeddings + Predictor v0 (real `nba sim`)

Starts when Lane B has one full season of stints persisted.

1. **Embeddings.** PyTorch from scratch. One vector per `(player, season)`. Inputs: z-score-normalized per-season stats (use the stats already in `pbp_events` aggregations from Lane B; pts, ast, reb, stl, blk, tov, fga, fta, 3pa, min — derive in a SQL view). Era token is a per-season scalar at this size. 128 dims to match the schema. **Random init is acceptable for this run** — the goal is wiring pgvector end-to-end and unblocking the matchup module, not a publishable embedding. Persist to `embeddings_player`.
2. **Predictor MLP.** Small (~5M params for v0, well under the spec ceiling). Inputs: concat(sum, mean) of home-lineup embeddings + concat(sum, mean) of away-lineup embeddings + era token + home/away flag. Target: home_pts − away_pts per possession from `lineup_stints`. Train with vanilla Adam, no FSDP, single GPU or CPU. **No RAPM shrinkage in v0** — get the wire end-to-end, shrinkage in v1 when residuals demand it.
3. MLflow tracking from day 1, even local-only. Log `model_version`, training loss, val MSE, n_stints. Stub out `meta.model_versions` in the CLI to read from the latest MLflow run.
4. Replace stub numbers in `nba sim`. Same JSON contract — Hungarian-assigned matchups (embedding-distance), team edges (synthesize from delta-embedding heuristics for v0), `scouting_take` stays a placeholder string this run (LoRA is Lane D, deferred). Brutus's 14 sim tests must still pass.

**Validation gate:** held-out 2022-23 game prediction. Pick 5 NYK games not in the training set, run `nba sim` with the actual starting lineups, compare predicted score to actual. Won't be accurate (one season of data, no shrinkage, random-init embeddings) — but predicted scores should be in the 90-130 range per side, not 50 or 300. Document in `docs/predictor_v0_eval.md`.

### Lane D — Polish + SFT corpus (parallel, doesn't block A/B/C)

1. **Typed-error bug.** `nba sim --team1 'wat'` currently throws a raw `ValueError` traceback (caught manually 2026-05-11). Should be `InvalidPlayerError` JSON on stderr with exit code 3. Audit `nba/cli/main.py` and `nba/cli/teamspec.py` for other unwrapped exceptions and route them all through the typed-error formatter. Brutus adds a contract test class for "every parse error produces a typed-error JSON."
2. **`--human` formatter.** Right now `--human` prints the JSON, then a thin header. Build it out to match the DESIGN_FICTION.md output: score header, matchup table, team edges, scouting take, warnings section. Implementer choice on a tiny rendering helper (no `rich` dep unless trivial).
3. **SFT corpus pipeline.** Reddit + yt-dlp + Whisper. Output: `data/corpus/{reddit,transcripts}/*.jsonl` with `{source, url, text, metadata}` per line. Quality filters: min comment karma, dedupe, profanity strip optional. **NO LoRA training this run.** Just get the corpus to disk and run `wc -l` — spec hedge #4 says "verify corpus size early" and we need to know whether the 5-10k LoRA rule of thumb is even reachable before we plan LM training. Document corpus size + filtering rules in `docs/sft_corpus.md`.

## Out of scope for this run

- LoRA training the scouting LM. Corpus only — model training is slice 3.
- vLLM serving, Rust gateway, EKS, Terraform, RDS, MLflow on EKS (local MLflow is fine).
- Reddit + Whisper scraping at scale — get a sample pipeline working, not a full historical pull.
- RAPM-style Bayesian shrinkage in the predictor.
- Facts table population. Schema exists; content waits for the LM.
- Phase 2 web frontend.
- Coach embeddings (still v2 per SPEC).
- Multi-season ingest. NYK 2022-23 only this run. League-wide is slice 3.

## Coordination

- **Canonical ledger:** `bd`. Every lane writes notes to its beads; bd IDs are how we refer to work in dispatches. File the lane-A/B/C/D beads at the start so dispatches have something to reference.
- **Shared docs:** files in this repo. Update `docs/` as you learn things — survives crew death.
- **Router:** athena. Direct worker↔worker only along edges the router publishes.
- **Test gating:** brutus writes contracts first; implementers turn them green. No bypass. The slice-1 contract tests (43 passing) stay green throughout — they're the regression net.
- **Validation gates ≠ contract tests.** Slice 1 verified *shape*. Slice 2 verifies *values*. Each lane has a named validation gate above; do not close the lane bead until the gate is in `docs/`.
- **Frozen surfaces:** `nba/contracts.py` (pydantic models) and the JSON shape of every existing CLI subcommand. New subcommands (`nba ingest`, `nba stints`) need their own contracts before implementation.

## Key external dependencies

- `pseudo-r/Public-ESPN-API` — semi-undocumented endpoints. References in gullivan's `espn-api-refs` bd memory and `docs/p0_espn_coverage.md`. Rate-limit 30s.
- Python 3.12+, PyTorch (CPU acceptable for v0), psycopg or asyncpg, MLflow (local).
- Postgres 16 + pgvector via Docker locally. No cloud DB.
- Cleaning the Glass + PBPStats as Lane B validation references. Read-only via browser; no API.
- Reddit via PRAW or pushshift mirror (whichever survives in 2026; gullivan should re-check at session start).
- yt-dlp + faster-whisper for transcripts.

## Output expectations

CLI contracts unchanged from slice 1. Every command returns `{data, warnings, meta}`. Typed errors on stderr with stable exit codes. `--human` adds pretty output after the JSON. See `CONTRACT.md` and `CONTRACT_STINTS.md`.

New deliverables this run:
- `docs/stints_validation.md` — Lane B validation against CtG / PBPStats.
- `docs/predictor_v0_eval.md` — Lane C held-out eval numbers.
- `docs/sft_corpus.md` — Lane D corpus size + filtering rules.
- `migrations/0002_*.sql` — schema deltas discovered during real ingest.

## Known issues carried from slice 1

- `nba sim --team1 'wat'` raw ValueError — Lane D fixes.
- `derive_stints()` signature requires `starters_home, starters_away` positional args — fine for the fixture-driven unit test, Lane B needs to source these from `boxscore.players[].statistics[0].athletes[]` (the per-game roster, per the P0 doc).
- ESPN game `230126018` returns 1-play PBP. Don't add it back as a test fixture; the bad-PBP handler in Lane A should catch this class of game by row count, not by ID.

## How to handoff

When you complete a piece, update its bead with `bd update <id> --status closed`, leave a comment with the artifact paths (validation doc, migration file, etc.), and route back to athena: `bash ~/.claude/skills/crew/crew.sh send athena "<lane> done: <bd-id> — gate: <doc> — next?"`. The validation-doc reference in the handoff is the signal that the lane actually finished, not just that the tests are green.
