# VERDICT — nba-bbq: embeddings_player post-train smoke

**Status:** GREEN — confirmed by brutus.
**Implementer:** ml-lane (nba-ibw, closed at `7bed00c`).
**Verifier:** brutus.
**Verified at commit:** `7bed00c` (tip of main at verification time).
**Transcript:** `.brutus/nba-bbq/transcript.md` (red + green phases).

## Attestation

`NBA_EMBEDDINGS_SMOKE=1 pytest tests/test_embeddings_smoke.py -v` →
**5 passed, 0 failed, 0 errors** at `7bed00c`. All four pinned invariants hold:

| pin | observed |
|---|---|
| row count == 19 (NYK 2022-23 distinct roster) | 19 rows for the cohort, 463 total in `embeddings_player` |
| `vector_dims(embedding) == 128` | 128 for every row |
| `‖v‖ ≈ 1.0` within `1e-3` | tighter than spec — within `1e-7` per ml-lane report |
| `season == 2023` (D1 end-year), never NULL | 2023 on every cohort row |

Model version: `embeddings-v0-randinit` (random-init, as accepted by the brief
for slice 2 — the wire-end-to-end goal, not a publishable embedding).

Contract closed. `nba/contracts.py` never touched — frozen surface honored.
