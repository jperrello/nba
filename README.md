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
