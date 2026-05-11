import { useEffect, useState } from "react"
import {
  simulate,
  isStubMeta,
  type ApiResult,
  type SimData,
} from "@/lib/api"
import { PRESETS, type Preset } from "@/data/presets"

// Module-memo so revisiting Home doesn't re-fire 6 sims.
const CACHE = new Map<string, Promise<ApiResult<SimData>>>()

function fetchPreset(p: Preset): Promise<ApiResult<SimData>> {
  const hit = CACHE.get(p.id)
  if (hit) return hit
  const promise = simulate(p.home, p.away)
  CACHE.set(p.id, promise)
  return promise
}

export type MatchupsRailProps = {
  onPick?: (m: { home: Preset["home"]; away: Preset["away"] }) => void
}

export function MatchupsRail({ onPick }: MatchupsRailProps) {
  return (
    <section>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--color-muted)", textTransform: "uppercase", letterSpacing: 0.08 }}>
        More matchups
      </h3>
      <div
        style={{
          display: "flex",
          gap: 12,
          overflowX: "auto",
          scrollSnapType: "x mandatory",
          paddingBottom: 8,
        }}
      >
        {PRESETS.map((p) => (
          <PresetCard
            key={p.id}
            preset={p}
            onClick={() => onPick?.({ home: p.home, away: p.away })}
          />
        ))}
      </div>
    </section>
  )
}

function PresetCard({ preset, onClick }: { preset: Preset; onClick: () => void }) {
  const [res, setRes] = useState<ApiResult<SimData> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPreset(preset).then((r) => {
      if (cancelled) return
      setLoading(false)
      setRes(r)
    })
    return () => {
      cancelled = true
    }
  }, [preset])

  return (
    <button
      type="button"
      onClick={onClick}
      className="card card-hover"
      style={{
        flex: "0 0 240px",
        scrollSnapAlign: "start",
        padding: 12,
        textAlign: "left",
        background: "transparent",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 500 }}>{preset.label}</div>
      {loading && <Shimmer />}
      {!loading && res?.ok && <Mini data={res.data} stub={isStubMeta(res.meta)} />}
      {!loading && res && !res.ok && (
        <div className="num" style={{ fontSize: 11, color: "var(--color-negative)" }}>
          sim failed
        </div>
      )}
    </button>
  )
}

function Mini({ data, stub }: { data: SimData; stub: boolean }) {
  const homeWp = data.win_prob.value
  const homeFavored = homeWp >= 0.5
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
      <span className="num" style={{ fontSize: 18, fontWeight: 600 }}>
        {data.score.home}
        <span style={{ color: "var(--color-muted)", margin: "0 4px" }}>–</span>
        {data.score.away}
      </span>
      <span
        className="num"
        style={{
          fontSize: 12,
          fontWeight: 500,
          color: homeFavored ? "var(--color-positive)" : "var(--color-negative)",
        }}
      >
        {(homeWp * 100).toFixed(0)}%
      </span>
      {stub && <span className="pill pill-stub" style={{ marginLeft: 6 }}>stub</span>}
    </div>
  )
}

function Shimmer() {
  return (
    <div
      style={{
        height: 22,
        background: "var(--color-surface-hover)",
        borderRadius: 4,
      }}
    />
  )
}
