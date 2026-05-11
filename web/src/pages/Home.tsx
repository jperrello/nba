import { useCallback, useMemo } from "react"
import { MatchupCard, type MatchupSpec } from "@/components/MatchupCard"
import { MatchupsRail } from "@/components/MatchupsRail"
import { BrowseRail } from "@/components/BrowseRail"
import { useLocalStorage } from "@/hooks/useLocalStorage"
import { DEFAULT_PRESET_ID, presetById } from "@/data/presets"
import type { LineupPrefill } from "@/App"
import type { Tab } from "@/components/nav/Nav"

type Props = {
  setTab: (t: Tab) => void
  setOpenPlayerId: (id: string | null) => void
  setLineupPrefill: (p: LineupPrefill | null) => void
}

export default function Home({ setTab, setOpenPlayerId, setLineupPrefill }: Props) {
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

  const onOpenPlayer = useCallback((id: string) => {
    setOpenPlayerId(id)
    setTab("players")
  }, [setOpenPlayerId, setTab])

  const onOpenLineup = useCallback((prefill: { players: string[]; season: number }) => {
    setLineupPrefill(prefill)
    setTab("lineups")
  }, [setLineupPrefill, setTab])

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      <MatchupCard initial={initial} />
      <MatchupsRail onPick={onPick} />
      <BrowseRail onOpenPlayer={onOpenPlayer} onOpenLineup={onOpenLineup} />
    </section>
  )
}
