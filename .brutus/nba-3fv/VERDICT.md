# VERDICT — nba-3fv: nba CLI JSON output shape

**Status:** GREEN — confirmed by brutus.
**Implementer:** cli-lane (nba-zg0, closed at `7f494e2`).
**Verifier:** brutus.
**Verified at commit:** `7f494e2` (tip of main at verification time).
**Transcript:** `.brutus/nba-3fv/transcript.md` (red phase + green phase appended).

## Attestation

`pytest tests/test_cli_contract.py -v` → **14 passed, 0 failed, 0 errors** at
`7f494e2`. Every subcommand contract (schema, sql, lineup stats, sim, players
show), every typed error (MultiStatementError exit 2, InvalidPlayerError exit 3,
EraOutOfRangeError exit 4), the sparse-data warning shape, and the
`--no-scouting` LM-skip seam at `nba.cli.main.generate_scouting_take` are all
honored. Stubbed responses correctly carry `meta.stub=true`.

Contract closed.
