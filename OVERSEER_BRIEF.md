# Overseer Brief — nba foundation slice

Read this before working. Authoritative scope for the **current autonomous run**.

## What this repo is

NBA lineup-analytics backend with two modes (data-app + simulation) exposed via an agent-facing Python CLI. Full vision lives in `SPEC.md` and `DESIGN_FICTION.md` — read both.

## Scope of *this* run (foundation slice only)

We are NOT training the LM, standing up EKS, or wiring vLLM in this pass. We are landing the *testable-locally* foundation that everything else hangs off:

1. **Project skeleton** — `pyproject.toml`, package layout (`nba/`, `tests/`), ruff + pyright config, `Makefile`/`justfile`, `.python-version`, `README.md` stub.
2. **ESPN P0 validation** — fetch lineup/PBP/boxscore data for **2003, 2008, 2013, 2018, 2023** via `pseudo-r/Public-ESPN-API`. Deliverable: `docs/p0_espn_coverage.md` one-pager noting which seasons have full PBP, boxscore-only, or missing. This gates everything downstream — spec literally says "before any infra work."
3. **Postgres schema design** — `docs/schema.md` + initial `migrations/` (plain SQL files, no Alembic yet) covering: `players`, `player_seasons`, `teams`, `rosters`, `games`, `pbp_events`, `lineup_stints`, `coach_games`, `facts`, `sim_cache`, `embeddings_player` (pgvector).
4. **`nba` CLI skeleton** — Typer-based, JSON-by-default, `--human` flag for pretty output. Subcommands stubbed to return typed-shape JSON: `nba schema`, `nba sql`, `nba sim`, `nba lineup stats`, `nba players show`. Typed errors: `InvalidPlayerError`, `InsufficientDataError`, `EraOutOfRangeError`. Stubs return placeholder data shaped exactly like the real output will be.
5. **PBP → stint reconstruction prototype** — given raw ESPN PBP JSON for one game, derive lineup stints (5-on-5 intervals, per-possession scoring). Pure-Python, table-stakes algorithm, unit-tested against a known fixture.
6. **Tests/contracts** — brutus writes failing JSON-shape contracts for CLI subcommands and correctness contracts for stint derivation *before* implementation. Implementers turn them green.

## Out of scope for this run

- LoRA training, vLLM, EKS, Terraform, MLflow, Rust gateway, OpenTelemetry
- Reddit/yt-dlp/Whisper SFT corpus ingestion
- Player embedding model training (PyTorch from scratch) — schema only
- Predictor MLP training — schema for inputs only
- Curated facts table content — schema + retrieval interface only
- Phase 2 web frontend

## Coordination

- **Canonical ledger:** `bd`. Every lane writes notes to its beads; bd IDs are how we refer to work in dispatches.
- **Shared docs:** files in this repo. Update them as you learn things — they survive crew death.
- **Router:** athena. Direct worker↔worker only along edges the router publishes.
- **Test gating:** brutus writes contracts first; implementers turn them green. No bypass.

## Key external dependencies

- `pseudo-r/Public-ESPN-API` — semi-undocumented ESPN endpoints. gullivan researches; espn-ingest crew uses.
- Python 3.12+. We use `uv` for dep management if available (else pip + venv).
- Postgres 16 + pgvector. No live DB in this run — schema docs + migrations only.

## Output expectations

Every CLI command, when it eventually runs, returns JSON with:
- `data: {...}` — the structured result
- `warnings: [...]` — array of `{code, message, context}`
- `meta: {model_versions, data_versions, cache_hit, generated_at}`

`--human` adds a pretty-printed version after the JSON header. Errors are typed and printed to stderr with non-zero exit codes. See `SPEC.md` "Look and feel" + `DESIGN_FICTION.md` example output.

## How to handoff

When you complete a piece, update its bead with `bd update <id> --status closed`, leave a comment, and route back to athena: `bash ~/.claude/skills/crew/crew.sh send athena "<lane> done: <bd-id> — next?"`.
