# NBA Sim Web GUI — Shared Context

**Status:** active multi-lane build. The user is out-of-loop; the parent overseer makes all judgment calls.
**Date:** 2026-05-11

Every lane reads this top-to-bottom before its first action. Re-read after a clear.

---

## Spec (authoritative; do not re-litigate)

Localhost-only React + TypeScript app that wraps the existing `nba` Python CLI and replaces `docs/visualizer/` + `scripts/visualizer/`. Kalshi-style chrome: white background, green for positives, red for negatives/warnings, sans-serif at moderate density, card grid under category-chip nav.

**Primary surface:** hero matchup card on the home page. Click a player on either roster → opens a picker → pick a replacement (default tab: "Similar" via embedding distance, search input always visible). Stage any number of swaps. Press **Simulate** to call `nba sim` and rerender.

**Secondary surfaces:** Players page (search + detail) and Lineups page (5-slot picker + lookup) reachable from a 3-tab top nav.

**Not:** Phase-2 product surface from `SPEC.md`. Not deployed. Not multi-user. Not a betting/markets app — Kalshi reference is **visual only**, no yes/no contract framing.

### Home composition
- Hero matchup card (full width) at top.
- Two horizontal-scroll rails below: **"More matchups"** (curated presets from `web/src/data/presets.ts`) and **"Browse"** (heterogeneous mix of recently-viewed players + recently-queried lineups from localStorage).
- First visit default: **Knicks 2024 vs Pacers 2024**. Subsequent visits restore from `localStorage['nba.hero.matchup']`.

### Sim trigger
Explicit Simulate button only. Staged swaps render visibly without firing the sim (struck-through original + new player in green). Skeleton/loading state during the call; replaces current result on response.

### Warnings & stub policy
Every CLI response has `warnings[]` and `meta.model_versions`. Warnings render as **red pill chips** on the contextual element with click-to-expand. `meta.model_versions` containing `stub`, `v0`, or `placeholder` substrings → tiny mono **"stub"** pill on the affected card. `meta.cached` true → small **"cached"** badge.

Specific warning placements:
- `season_fallback` → red pill under the team header, label like "using 2023 (req 2024)".
- `sparse_data` → red pill on the matchup card; tooltip shows `n_effective` from warning context.
- `random_init_embeddings` (new, emitted by `players similar`) → renders the "random-init embeddings; pick from search instead" empty-state hint inside the picker's Similar list.

### Typed errors → UI banner
- `InvalidPlayerError` (exit 3)
- `InsufficientDataError`
- `EraOutOfRangeError` (exit 4)

Render error code as banner title, message body underneath. Retry button re-fires the same sim. Untyped → generic "sim failed; check terminal".

### Palette
- Background `#ffffff`, text `#0a0a0a`, border `#e5e5e5`.
- Green `#0a8a3f` (positives, replacement-player rows, "+" team edges).
- Red `#c8281f` (negatives, warnings, errors, "-" team edges).
- Team colors permitted **only** as small accent stripe / logo on roster card headers. No team-color text or backgrounds.

### Typography
- Inter 14px base.
- JetBrains Mono / SF Mono for **numbers only** (sim-card score, roster cells, stat lines, "stub" pills).

### Density / layout
- Centered max-width **1200px** column.
- Cards: `1px #e5e5e5` border, no shadow, 8px radius. Hover: `#f5f5f5` bg tint. Active/selected: 2px black bottom border.
- No dark mode. No gradients. No team-color backgrounds. No animations beyond 150ms swap-stage fade + skeleton shimmer. **No emojis.**

### localStorage keys (canonical)
- `nba.hero.matchup` — last viewed hero matchup id (e.g. `"knicks-2024_vs_pacers-2024"`).
- `nba.recent.players` — last 12 viewed player ids (FIFO).
- `nba.recent.lineups` — last 8 queried lineups `{players[5], season}` (FIFO).
- `nba.recent.swap-target` — transient: player chosen from Players page as a swap target.

---

## Stack — pinned

- **Frontend:** React 18, TypeScript 5, Vite 5, Tailwind v4, `@radix-ui/react-dialog`, `@radix-ui/react-popover`, `@radix-ui/react-tooltip`. No router needed — single page, 3-tab nav via `useState`. No react-query yet — a small wrapper around `fetch` is enough.
- **Backend gateway:** Python stdlib `http.server.ThreadingHTTPServer` at `scripts/web/serve.py`. No new Python deps. Allowlist-based, mirrors `scripts/visualizer/serve.py` pattern.
- **Persistence:** localStorage only. No backend state.
- **Targets:** `127.0.0.1` only. No HTTPS, no auth, no CORS. Single-origin via serve.py.
- **Node:** assume 20+.

---

## CLI envelope (reference — already implemented in `nba/contracts.py`)

Every nba subcommand returns one JSON document on stdout:

```json
{
  "data": { ... subcommand-specific ... },
  "warnings": [{"code": "...", "message": "...", "context": {...}}],
  "meta": {
    "model_versions": {"predictor": "...", "embeddings": "...", "lm": "..."},
    "cached": true,
    "generated_at": "ISO-8601",
    "...": "..."
  }
}
```

Typed errors print one JSON line on stderr (`{error, message, context}`) and exit non-zero with a stable code (see CONTRACT.md exit-code table).

### Sample `nba sim` payload (captured live 2026-05-11)
```json
{
  "data": {
    "score": {"home": 114, "away": 116},
    "win_prob": {"value": 0.401, "ci": 0.1},
    "matchups": [
      {"home_player": "Julius Randle", "away_player": "Aaron Nesmith", "edge": 0.187, "note": null},
      {"home_player": "RJ Barrett", "away_player": "Bennedict Mathurin", "edge": 0.077, "note": "cross-matchup flag: low embedding similarity"}
      // ... 5 total
    ],
    "team_edges": [
      {"tag": "rebounding", "sign": "+", "magnitude": 0.058, "label": "rebound rate vs opponent frontcourt"},
      {"tag": "halfcourt_fit", "sign": "+", "magnitude": 0.020, "label": "halfcourt fit at the wings"},
      {"tag": "spacing", "sign": "-", "magnitude": 0.056, "label": "spacing vs opponent"},
      {"tag": "defensive_switchability", "sign": "-", "magnitude": 0.037, "label": "switch coverage vs opponent ballhandlers"}
    ],
    "scouting_take": "Stub scouting take: the model gives the edge to the home side ..."
  },
  "warnings": [
    {"code": "season_fallback", "message": "requested knicks season 2024; using nearest available 2023",
     "context": {"team": "NY", "requested": 2024, "used": 2023}}
  ],
  "meta": {
    "model_versions": {"predictor": "predictor-v0-marginpersec", "embeddings": "embeddings-v0-randinit", "lm": "placeholder-no-lora-v0"},
    "cached": false,
    "generated_at": "2026-05-11T22:12:15.701640+00:00"
  }
}
```

All three model versions currently trip the "stub" pill — that's expected for this slice.

### New CLI subcommands to add (owned by cli-lane, gated by brutus)

| Subcommand | Args | data shape |
|---|---|---|
| `nba players similar` | `--id ID --k K` | `{neighbors: [{player_id, name, season, distance}]}` length ≤ K, ascending distance |
| `nba players search`  | `--q QUERY`     | `{results: [{player_id, name, season}]}` empty list OK |
| `nba players career`  | `--id ID`       | `{player_id, name, seasons: [{season, team, games, mpg, ppg, rpg, apg}]}` null stats OK with `facts_table_empty` warning |

Errors: unknown id → `InvalidPlayerError` exit 3 (similar, career).

---

## Lane dispatch matrix

| Lane | Beads | Files owned | Notes |
|---|---|---|---|
| **web-core-lane** (new, forge-spawn) | `nba-9h0` (kill old viz), `nba-hwr` (scaffold), `nba-sio` (gateway + make), `nba-ast` (hero+picker+sim renderer+warnings), `nba-f0s` (matchups rail) | `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tailwind.config.js`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/theme/*`, `web/src/hooks/useLocalStorage.ts`, `web/src/lib/api.ts`, `web/src/components/nav/*`, `web/src/pages/Home.tsx`, `web/src/components/MatchupCard/*`, `web/src/components/PlayerPicker/*`, `web/src/components/SimRenderer/*`, `web/src/components/Warning*`, `web/src/components/StubPill*`, `web/src/components/MatchupsRail/*`, `web/src/data/presets.ts`, `scripts/web/serve.py`, `Makefile` (add web/web-serve/web-dev, delete viz/viz-serve), delete `docs/visualizer/`, `scripts/visualizer/` | Foundation; owns the entire home page + chrome. Land scaffold + gateway first so web-pages-lane can start without conflicts. |
| **web-pages-lane** (new, forge-spawn) | `nba-929` (Players page), `nba-xss` (Lineups page), `nba-79d` (Browse rail) | `web/src/pages/Players.tsx`, `web/src/components/PlayerDetail/*`, `web/src/pages/Lineups.tsx`, `web/src/components/LineupPicker/*`, `web/src/components/BrowseRail/*` | Reads shell primitives from web-core-lane. Wait for web-core scaffold (nba-hwr) to land before writing under `web/src/pages/`. Until then: produce a tight implementation plan inside its beads, sketch component shapes in the bead notes. |
| **cli-lane** (revive) | `nba-g0s` (implement players similar/search/career) | `nba/cli/players.py` (or wherever), `nba/contracts.py` (add models), tests passing the brutus contract | Turn brutus's red into green. |
| **brutus** (alive) | `nba-v0n` (contracts for new CLI) | `tests/test_cli_contract.py` (extend), CONTRACT.md addendum | Red-first; hand off to cli-lane via athena once captured. |

### Edges
- brutus → cli-lane: red tests captured → handoff message via athena. cli-lane turns green.
- cli-lane → web-core-lane: new CLI subcommands available → handoff via athena ("similar/search/career landed, gateway allowlist already covers `players`").
- web-core-lane → web-pages-lane: scaffold ready → handoff via athena ("you may now write under web/src/pages/").
- All lanes → athena: every "done" or "blocked" message goes to athena, not directly between workers.

---

## Conventions

- **Bd-first.** Each lane claims its bead with `bd update <id> --claim` before coding, closes on done.
- **Single-origin dev.** Vite's `vite.config.ts` proxies `/api/*` → `127.0.0.1:8765`. Frontend code calls `fetch("/api/run", {method: "POST", body: JSON.stringify({argv: [...]})})`.
- **API wrapper.** `web/src/lib/api.ts` exports typed helpers: `simulate(team1, team2, opts)`, `playerSearch(q)`, `playerSimilar(id, k)`, `playerCareer(id)`, `lineupStats(players, season)`. All return the `{data, warnings, meta}` envelope typed via inferred shape from contracts (hand-typed for now; no codegen).
- **Error handling.** API wrapper returns a discriminated union: `{ok: true, data, warnings, meta} | {ok: false, error: TypedError | "untyped", message, stderr}`. Components branch on `ok`.
- **No comments unless WHY is non-obvious.** Per global rules — single-word names where possible, early returns, no else.
- **Don't lint-bypass.** If pyright/ruff/tsc fails, fix the cause.
- **Run python with `python3`.**

## Kill rules

- Hard cap **3 hours per lane** before a status check to athena. Lane reports incremental progress to athena every 30–45 min via tmux.
- If a CLI subcommand can't be implemented due to missing DB data, **stub it** — return shape-valid empty arrays + a `random_init_embeddings` / `facts_table_empty` warning. Don't block frontend on data backfill.
- If Vite/Tailwind config wedges, fall back to plain CSS modules — don't burn an hour on a build config.
- **Never** kill the old visualizer until the new scaffold imports/builds cleanly. Sequence: scaffold → gateway → kill old viz.

## Escalation

The user is out-of-loop. **Do not escalate to the user mid-run.** Route blockers to athena; athena routes to overseer. Overseer makes the call.
