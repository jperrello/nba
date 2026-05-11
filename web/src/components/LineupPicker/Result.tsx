import type { LineupStats, Warning, Meta } from "@/lib/api"
import { CachedBadge, StubPill } from "@/components/StubPill"
import { WarningPill } from "@/components/WarningPill"

export function Result({
  data,
  warnings,
  meta,
}: {
  data: LineupStats
  warnings: Warning[]
  meta: Meta
}) {
  return (
    <section className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <h3 style={{ fontSize: 16, fontWeight: 600 }}>Lineup stats</h3>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <CachedBadge meta={meta} />
          <StubPill meta={meta} />
          {warnings.map((w, i) => <WarningPill key={i} warning={w} />)}
        </div>
      </header>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
        <Stat label="Stints" value={data.stint_count} />
        <Stat label="Poss" value={data.possessions} />
        <Stat label="Net" value={data.net_rating} signed />
        <Stat label="Off" value={data.off_rating} />
        <Stat label="Def" value={data.def_rating} />
      </div>
    </section>
  )
}

function Stat({ label, value, signed }: { label: string; value: number | null | undefined; signed?: boolean }) {
  if (value == null) {
    return (
      <div>
        <Cap>{label}</Cap>
        <div className="num" style={{ fontSize: 20, color: "var(--color-muted)" }}>—</div>
      </div>
    )
  }
  const positive = signed ? value >= 0 : null
  const color = positive == null ? undefined : positive ? "var(--color-positive)" : "var(--color-negative)"
  return (
    <div>
      <Cap>{label}</Cap>
      <div className="num" style={{ fontSize: 20, fontWeight: 600, color }}>
        {signed && positive ? "+" : ""}
        {value.toFixed(1)}
      </div>
    </div>
  )
}

function Cap({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.08, color: "var(--color-muted)", fontWeight: 500 }}>
      {children}
    </div>
  )
}
