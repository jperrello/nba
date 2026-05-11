# brutus contract nba-6gz: PBP -> stint derivation (red phase)

*2026-05-11T18:44:48Z by Showboat 0.6.1*
<!-- showboat-id: e9abaf2f-99ad-4b8a-a230-b5a92e6d0cc8 -->

Contract: nba.stints.derive.derive_stints(events, starters_home, starters_away) must derive lineup stints from a PBP event list and reconcile to the box score. Hand-crafted fixture at tests/fixtures/pbp_minigame.json: 2 periods, 2 subs, 1 quarter boundary, 1 shooting foul straddling a sub. Eight correctness assertions + a lineup-composition check. Red phase below: derive_stints is a stub that raises NotImplementedError — every behavior test ERRORs with that message. Stints-lane (nba-8gq) owns the body.

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest tests/test_stints.py -v --tb=short --no-header
```

```output
============================= test session starts ==============================
collecting ... collected 9 items

tests/test_stints.py::test_stint_count_matches_subs_plus_quarter_boundaries ERROR [ 11%]
tests/test_stints.py::test_each_stint_has_five_on_five ERROR             [ 22%]
tests/test_stints.py::test_boundaries_align_with_subs_and_period_ends ERROR [ 33%]
tests/test_stints.py::test_scoring_attributed_to_active_stint ERROR      [ 44%]
tests/test_stints.py::test_possessions_match_oliver_formula ERROR        [ 55%]
tests/test_stints.py::test_stint_points_sum_to_box_score ERROR           [ 66%]
tests/test_stints.py::test_no_stint_crosses_period_boundary ERROR        [ 77%]
tests/test_stints.py::test_sub_mid_possession_attributes_to_stint_at_possession_start ERROR [ 88%]
tests/test_stints.py::test_lineups_match_expected ERROR                  [100%]

==================================== ERRORS ====================================
___ ERROR at setup of test_stint_count_matches_subs_plus_quarter_boundaries ____
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
______________ ERROR at setup of test_each_stint_has_five_on_five ______________
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
______ ERROR at setup of test_boundaries_align_with_subs_and_period_ends _______
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
__________ ERROR at setup of test_scoring_attributed_to_active_stint ___________
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
___________ ERROR at setup of test_possessions_match_oliver_formula ____________
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
_____________ ERROR at setup of test_stint_points_sum_to_box_score _____________
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
___________ ERROR at setup of test_no_stint_crosses_period_boundary ____________
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
_ ERROR at setup of test_sub_mid_possession_attributes_to_stint_at_possession_start _
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
________________ ERROR at setup of test_lineups_match_expected _________________
tests/test_stints.py:26: in derived
    return derive_stints(
nba/stints/derive.py:14: in derive_stints
    raise NotImplementedError(
E   NotImplementedError: derive_stints is not implemented yet. See CONTRACT_STINTS.md (brutus contract nba-6gz). stints-lane (nba-8gq) owns the body.
=========================== short test summary info ============================
ERROR tests/test_stints.py::test_stint_count_matches_subs_plus_quarter_boundaries
ERROR tests/test_stints.py::test_each_stint_has_five_on_five - NotImplemented...
ERROR tests/test_stints.py::test_boundaries_align_with_subs_and_period_ends
ERROR tests/test_stints.py::test_scoring_attributed_to_active_stint - NotImpl...
ERROR tests/test_stints.py::test_possessions_match_oliver_formula - NotImplem...
ERROR tests/test_stints.py::test_stint_points_sum_to_box_score - NotImplement...
ERROR tests/test_stints.py::test_no_stint_crosses_period_boundary - NotImplem...
ERROR tests/test_stints.py::test_sub_mid_possession_attributes_to_stint_at_possession_start
ERROR tests/test_stints.py::test_lineups_match_expected - NotImplementedError...
============================== 9 errors in 0.04s ===============================
```

GREEN PHASE — stints-lane (nba-8gq) closed at 48a83aa. Re-running tests/test_stints.py against the implementation.

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest tests/test_stints.py -v --tb=short --no-header
```

```output
============================= test session starts ==============================
collecting ... collected 9 items

tests/test_stints.py::test_stint_count_matches_subs_plus_quarter_boundaries PASSED [ 11%]
tests/test_stints.py::test_each_stint_has_five_on_five PASSED            [ 22%]
tests/test_stints.py::test_boundaries_align_with_subs_and_period_ends PASSED [ 33%]
tests/test_stints.py::test_scoring_attributed_to_active_stint PASSED     [ 44%]
tests/test_stints.py::test_possessions_match_oliver_formula PASSED       [ 55%]
tests/test_stints.py::test_stint_points_sum_to_box_score PASSED          [ 66%]
tests/test_stints.py::test_no_stint_crosses_period_boundary PASSED       [ 77%]
tests/test_stints.py::test_sub_mid_possession_attributes_to_stint_at_possession_start PASSED [ 88%]
tests/test_stints.py::test_lineups_match_expected PASSED                 [100%]

============================== 9 passed in 0.01s ===============================
```
