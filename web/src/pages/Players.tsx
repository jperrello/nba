import { useEffect, useMemo, useState } from "react"
import {
  playerSearch,
  type PlayerSearchHit,
  type Warning,
} from "@/lib/api"
import type { Tab } from "@/components/nav/Nav"
import { useLocalStorage } from "@/hooks/useLocalStorage"
import { PlayerDetail } from "@/components/PlayerDetail"

export type NameCacheEntry = { name: string; last_season?: number | string }
export type NameCache = Record<string, NameCacheEntry>
export type SwapTarget = { player_id: string; name: string }

type Props = {
  setTab: (t: Tab) => void
  openPlayerId: string | null
  setOpenPlayerId: (id: string | null) => void
}

export default function Players({ setTab, openPlayerId, setOpenPlayerId }: Props) {
  const [q, setQ] = useState("")
  const [hits, setHits] = useState<PlayerSearchHit[] | null>(null)
  const [warnings, setWarnings] = useState<Warning[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [, setRecent] = useLocalStorage<string[]>("nba.recent.players", [])
  const [, setNamecache] = useLocalStorage<NameCache>("nba.players.namecache", {})
  const [, setSwapTarget] = useLocalStorage<SwapTarget | null>("nba.recent.swap-target", null)

  const trimmed = useMemo(() => q.trim(), [q])

  useEffect(() => {
    if (!trimmed) {
      setHits(null)
      setWarnings([])
      setErr(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setErr(null)
    const t = setTimeout(() => {
      playerSearch(trimmed).then((res) => {
        if (cancelled) return
        setLoading(false)
        if (!res.ok) {
          setErr(res.message || res.error)
          setHits([])
          setWarnings([])
          return
        }
        setHits(res.data.results ?? [])
        setWarnings(res.warnings ?? [])
      })
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [trimmed])

  const pushRecent = (id: string, name: string, season?: number | string) => {
    setNamecache((prev) => ({ ...prev, [id]: { name, last_season: season } }))
    setRecent((prev) => {
      const next = [id, ...prev.filter((x) => x !== id)]
      return next.slice(0, 12)
    })
  }

  const onSelect = (h: PlayerSearchHit) => {
    setOpenPlayerId(h.player_id)
    pushRecent(h.player_id, h.name, h.season)
  }

  const onSwapTarget = (id: string, name: string) => {
    setSwapTarget({ player_id: id, name })
    setTab("home")
  }

  return (
    <section style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 18 }}>
      <aside style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search players…"
          className="card"
          style={{ padding: "8px 10px", fontSize: 13, borderRadius: 6 }}
        />
        <Results
          hits={hits}
          query={trimmed}
          loading={loading}
          err={err}
          warnings={warnings}
          selectedId={openPlayerId}
          onSelect={onSelect}
        />
      </aside>
      <main>
        {openPlayerId ? (
          <PlayerDetail
            id={openPlayerId}
            onPickNeighbor={(id, name) => {
              setOpenPlayerId(id)
              pushRecent(id, name)
            }}
            onSwapTarget={onSwapTarget}
          />
        ) : (
          <Empty>search for a player to see career and neighbors</Empty>
        )}
      </main>
    </section>
  )
}

function Results({
  hits,
  query,
  loading,
  err,
  warnings,
  selectedId,
  onSelect,
}: {
  hits: PlayerSearchHit[] | null
  query: string
  loading: boolean
  err: string | null
  warnings: Warning[]
  selectedId: string | null
  onSelect: (h: PlayerSearchHit) => void
}) {
  if (!query) return <Empty>type a name above</Empty>
  if (loading) return <Empty>searching…</Empty>
  if (err) return <Empty>search failed: {err}</Empty>
  if (!hits || hits.length === 0) {
    const w = warnings.find((x) => x.code === "no_matches")
    return <Empty>{w ? w.message : `no matches for "${query}"`}</Empty>
  }
  const byId = new Map<string, PlayerSearchHit>()
  for (const h of hits) {
    if (!byId.has(h.player_id)) byId.set(h.player_id, h)
  }
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
      {[...byId.values()].map((h) => {
        const active = selectedId === h.player_id
        return (
          <li key={h.player_id}>
            <button
              type="button"
              onClick={() => onSelect(h)}
              className="card card-hover"
              style={{
                display: "flex",
                width: "100%",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                fontSize: 13,
                cursor: "pointer",
                textAlign: "left",
                background: active ? "var(--color-surface-hover)" : "transparent",
                borderColor: active ? "var(--color-fg)" : "var(--color-border)",
              }}
            >
              <span>{h.name}</span>
              <span className="num" style={{ color: "var(--color-muted)", fontSize: 12 }}>
                {h.season ?? ""}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 16, fontSize: 12, color: "var(--color-muted)" }}>
      {children}
    </div>
  )
}
