import { useCallback, useMemo } from "react"
import { MatchupCard, type MatchupSpec } from "@/components/MatchupCard"
import { MatchupsRail } from "@/components/MatchupsRail"
import { BrowseRail } from "@/components/BrowseRail"
import { useLocalStorage } from "@/hooks/useLocalStorage"
import { DEFAULT_PRESET_ID, presetById } from "@/data/presets"

export default function Home() {
  const [storedId, setStoredId] = useLocalStorage<string>("nba.hero.matchup", DEFAULT_PRESET_ID)

  const initial: MatchupSpec = useMemo(() => {
    const p = presetById(storedId) ?? presetById(DEFAULT_PRESET_ID)!
    return { home: p.home, away: p.away }
  }, [storedId])

  const onPick = useCallback(
    (m: { home: MatchupSpec["home"]; away: MatchupSpec["away"] }) => {
      const id = `${m.home.team}-${m.home.season}_vs_${m.away.team}-${m.away.season}`
      setStoredId(id)
    },
    [setStoredId],
  )

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      <MatchupCard initial={initial} />
      <MatchupsRail onPick={onPick} />
      <BrowseRail />
    </section>
  )
}
