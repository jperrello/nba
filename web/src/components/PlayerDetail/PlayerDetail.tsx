import { useEffect, useState } from "react"
import {
  playerCareer,
  playerSimilar,
  type PlayerCareer,
  type PlayerSimilarHit,
  type Warning,
  type Meta,
  type ApiErr,
} from "@/lib/api"
import { CachedBadge, StubPill } from "@/components/StubPill"
import { WarningPill } from "@/components/WarningPill"
import { ErrorBanner } from "@/components/ErrorBanner"
import { Career } from "./Career"
import { Similar } from "./Similar"

type Props = {
  id: string
  onPickNeighbor: (id: string, name: string) => void
  onSwapTarget: (id: string, name: string) => void
}

type CareerState = {
  data: PlayerCareer | null
  warnings: Warning[]
  meta: Meta
  err: ApiErr | null
}

type SimilarState = {
  neighbors: PlayerSimilarHit[]
  randomInit: boolean
  err: ApiErr | null
}

export function PlayerDetail({ id, onPickNeighbor, onSwapTarget }: Props) {
  const [career, setCareer] = useState<CareerState>({ data: null, warnings: [], meta: {}, err: null })
  const [similar, setSimilar] = useState<SimilarState>({ neighbors: [], randomInit: false, err: null })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setCareer({ data: null, warnings: [], meta: {}, err: null })
    setSimilar({ neighbors: [], randomInit: false, err: null })
    Promise.all([playerCareer(id), playerSimilar(id, 8)]).then(([c, s]) => {
      if (cancelled) return
      setLoading(false)
      if (c.ok) setCareer({ data: c.data, warnings: c.warnings, meta: c.meta, err: null })
      if (!c.ok) setCareer({ data: null, warnings: [], meta: {}, err: c })
      if (s.ok) {
        setSimilar({
          neighbors: s.data.neighbors ?? [],
          randomInit: (s.warnings ?? []).some((w) => w.code === "random_init_embeddings"),
          err: null,
        })
      }
      if (!s.ok) setSimilar({ neighbors: [], randomInit: false, err: s })
    })
    return () => {
      cancelled = true
    }
  }, [id])

  if (loading) return <Skeleton />
  if (career.err) return <ErrorBanner err={career.err} />

  const name = career.data?.name ?? id
  return (
    <article className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 600 }}>{name}</h2>
          <div className="num" style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2 }}>{id}</div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <CachedBadge meta={career.meta} />
          <StubPill meta={career.meta} />
          <button
            type="button"
            className="chip chip-active"
            onClick={() => onSwapTarget(id, name)}
            style={{ fontSize: 13 }}
          >
            Use as swap target
          </button>
        </div>
      </header>
      {career.warnings.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {career.warnings.map((w, i) => <WarningPill key={i} warning={w} />)}
        </div>
      )}
      <Career data={career.data} warnings={career.warnings} />
      <Similar
        neighbors={similar.neighbors}
        randomInit={similar.randomInit}
        err={similar.err}
        onPick={onPickNeighbor}
      />
    </article>
  )
}

function Skeleton() {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ height: 26, width: 220, background: "var(--color-surface-hover)", borderRadius: 4, marginBottom: 12 }} />
      <div style={{ height: 12, width: 140, background: "var(--color-surface-hover)", borderRadius: 4, marginBottom: 20 }} />
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} style={{ height: 30, background: "var(--color-surface-hover)", borderRadius: 4, marginBottom: 6 }} />
      ))}
    </div>
  )
}
