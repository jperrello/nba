# VERDICT — nba-6gz: PBP → stint derivation correctness

**Status:** GREEN — confirmed by brutus.
**Implementer:** stints-lane (nba-8gq, closed at `48a83aa`).
**Verifier:** brutus.
**Verified at commit:** `eb41a11` (tip of main at verification time).
**Transcript:** `.brutus/nba-6gz/transcript.md` (red phase + green phase appended).

## Attestation

`pytest tests/test_stints.py -v` → **9 passed, 0 failed, 0 errors** at `eb41a11`.
All 8 contract assertions from `CONTRACT_STINTS.md` plus the lineup-composition
check pass against the fixture. The sub-mid-possession edge case (foul at t=29 →
sub at t=30 → FTs at t=31–32 attributed back to stint 0) is honored.

Contract closed.
