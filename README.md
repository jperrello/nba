# nba

NBA lineup-analytics backend with two modes (data-app + simulation), exposed via an agent-facing Python CLI. JSON-by-default output, typed errors, structured warnings. See `SPEC.md` for the full working definition, `DESIGN_FICTION.md` for the target output shape, and `OVERSEER_BRIEF.md` for the current foundation-slice scope.

## Quickstart

```bash
python3.12 -m venv .venv
source .venv/bin/activate
make install
make test
make lint
make typecheck
nba --help
```

Issue tracking lives in `bd` (beads). Run `bd ready` to see unblocked work.

## Web GUI

A React + TypeScript app that wraps the `nba` CLI for matchup simulation, player exploration, and lineup lookup. Localhost-only.

```bash
make web           # install web deps and build web/dist
make web-serve     # serve web/dist at http://127.0.0.1:8765 (depends on web)
make web-dev       # Vite dev server :5173 + gateway :8765 in parallel
```

Source lives in `web/` (Vite + React + TS + Tailwind v4 + Radix) and `scripts/web/serve.py` (stdlib gateway). The gateway only allows read-only `nba` subcommands (no DDL via `sql`, no ingest without `--dry-run`).
