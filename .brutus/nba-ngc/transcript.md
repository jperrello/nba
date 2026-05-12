# web-pages-lane (nba-ngc) red transcript

*2026-05-12T18:24:33Z by Showboat 0.6.1*
<!-- showboat-id: 7148f9d5-60c7-4f9a-85bd-d7634d140a20 -->

Spec: web/src/pages/Lineups.tsx line 36 useState(2024) → useState(2026). Players.tsx has no default-season state (DAEMON_BRIEF was speculative on that one; confirmed via grep — no useState/defaultSeason in Players.tsx).

```bash
python3 -m pytest tests/test_web_pages_default_season.py --no-header --tb=line -q 2>&1 | tail -5
```

```output
    assert 'useState(2026)' in 'import { useCallback, useEffect, useState } from "react"\nimport {\n  lineupStats,\n  type LineupStats,\n  type ApiEr...   <RecentList items={recent} namecache={namecache} onPick={onPickRecent} />\n      </aside>\n    </section>\n  )\n}\n'
/Users/jperr/Documents/nba/tests/test_web_pages_default_season.py:13: AssertionError: Lineups.tsx must initialize season state to 2026 (current real-world season per DAEMON_BRIEF)
=========================== short test summary info ============================
FAILED tests/test_web_pages_default_season.py::test_lineups_default_season_is_2026
1 failed in 0.00s
```
