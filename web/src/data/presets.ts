// Curated preset matchups for the "More matchups" rail.
// Used by MatchupsRail (nba-f0s) and as the first-visit default for Home (nba-ast).

export type Preset = {
  id: string
  label: string
  home: { team: string; season: number | string }
  away: { team: string; season: number | string }
}

export const PRESETS: Preset[] = [
  {
    id: "knicks-2024_vs_pacers-2024",
    label: "Knicks 2024 vs Pacers 2024",
    home: { team: "knicks", season: 2024 },
    away: { team: "pacers", season: 2024 },
  },
  {
    id: "warriors-2016_vs_cavaliers-2016",
    label: "Warriors 2016 vs Cavaliers 2016",
    home: { team: "warriors", season: 2016 },
    away: { team: "cavaliers", season: 2016 },
  },
  {
    id: "lakers-2010_vs_celtics-2010",
    label: "Lakers 2010 vs Celtics 2010",
    home: { team: "lakers", season: 2010 },
    away: { team: "celtics", season: 2010 },
  },
  {
    id: "bulls-1996_vs_sonics-1996",
    label: "Bulls 1996 vs Sonics 1996",
    home: { team: "bulls", season: 1996 },
    away: { team: "sonics", season: 1996 },
  },
  {
    id: "heat-2013_vs_spurs-2013",
    label: "Heat 2013 vs Spurs 2013",
    home: { team: "heat", season: 2013 },
    away: { team: "spurs", season: 2013 },
  },
  {
    id: "knicks-2026_vs_warriors-2016",
    label: "Knicks 2026 vs Warriors 2016 (cross-era)",
    home: { team: "knicks", season: 2026 },
    away: { team: "warriors", season: 2016 },
  },
]

export const DEFAULT_PRESET_ID = "knicks-2024_vs_pacers-2024"

export function presetById(id: string): Preset | undefined {
  return PRESETS.find((p) => p.id === id)
}
