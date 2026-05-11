import { useCallback, useEffect, useState } from "react"
import {
  lineupStats,
  type LineupStats,
  type ApiErr,
  type Warning,
  type Meta,
} from "@/lib/api"
import type { LineupPrefill } from "@/App"
import { useLocalStorage } from "@/hooks/useLocalStorage"
import { ErrorBanner } from "@/components/ErrorBanner"
import {
  LineupPicker,
  RecentList,
  Result,
  type RecentLineup,
  type NameCache,
  type SlotPlayer,
} from "@/components/LineupPicker"

type Props = {
  prefill: LineupPrefill | null
  setPrefill: (p: LineupPrefill | null) => void
}

type ResultState = { data: LineupStats; warnings: Warning[]; meta: Meta }

const EMPTY: (SlotPlayer | null)[] = [null, null, null, null, null]

function recentKey(l: RecentLineup): string {
  return `${[...l.players].sort().join("|")}@${l.season}`
}

export default function Lineups({ prefill, setPrefill }: Props) {
  const [slots, setSlots] = useState<(SlotPlayer | null)[]>(EMPTY)
  const [season, setSeason] = useState(2024)
  const [result, setResult] = useState<ResultState | null>(null)
  const [err, setErr] = useState<ApiErr | null>(null)
  const [loading, setLoading] = useState(false)
  const [recent, setRecent] = useLocalStorage<RecentLineup[]>("nba.recent.lineups", [])
  const [namecache, setNamecache] = useLocalStorage<NameCache>("nba.players.namecache", {})

  useEffect(() => {
    if (!prefill) return
    setSlots(prefill.players.map((id) => ({
      player_id: id,
      name: namecache[id]?.name ?? id,
    })))
    setSeason(prefill.season)
    setResult(null)
    setErr(null)
    setPrefill(null)
  }, [prefill, setPrefill, namecache])

  const onLookup = useCallback(async () => {
    const filled: SlotPlayer[] = []
    for (const s of slots) {
      if (s) filled.push(s)
    }
    if (filled.length !== 5) return
    const playerIds = filled.map((s) => s.player_id)
    setLoading(true)
    setErr(null)
    setResult(null)
    const res = await lineupStats(playerIds, season)
    setLoading(false)
    if (!res.ok) {
      setErr(res)
      return
    }
    setResult({ data: res.data, warnings: res.warnings, meta: res.meta })
    setNamecache((prev) => {
      const next = { ...prev }
      for (const s of filled) {
        next[s.player_id] = { name: s.name, last_season: s.season }
      }
      return next
    })
    const entry: RecentLineup = {
      players: playerIds,
      season,
      net_rating: res.data.net_rating,
    }
    setRecent((prev) => {
      const filtered = prev.filter((l) => recentKey(l) !== recentKey(entry))
      return [entry, ...filtered].slice(0, 8)
    })
  }, [slots, season, setRecent, setNamecache])

  const onPickRecent = (item: RecentLineup) => {
    setSlots(item.players.map((id) => ({
      player_id: id,
      name: namecache[id]?.name ?? id,
    })))
    setSeason(item.season)
    setResult(null)
    setErr(null)
  }

  return (
    <section style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 18 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <LineupPicker
          slots={slots}
          season={season}
          onSlotChange={(i, p) => setSlots((prev) => {
            const next = [...prev]
            next[i] = p
            return next
          })}
          onSeasonChange={setSeason}
          onLookup={onLookup}
          loading={loading}
        />
        {err && <ErrorBanner err={err} onRetry={onLookup} />}
        {result && <Result data={result.data} warnings={result.warnings} meta={result.meta} />}
      </div>
      <aside>
        <RecentList items={recent} namecache={namecache} onPick={onPickRecent} />
      </aside>
    </section>
  )
}
