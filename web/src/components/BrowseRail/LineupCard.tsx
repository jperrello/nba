import type { NameCache, RecentLineup } from "./BrowseRail"

function lastWord(s: string): string {
  const parts = s.trim().split(/\s+/)
  return parts[parts.length - 1] ?? s
}

export function LineupCard({
  lineup,
  namecache,
  onClick,
}: {
  lineup: RecentLineup
  namecache: NameCache
  onClick: () => void
}) {
  const labels = lineup.players.map((id) => {
    const n = namecache[id]?.name
    return n ? lastWord(n) : id
  })
  const positive = lineup.net_rating != null && lineup.net_rating >= 0
  return (
    <button
      type="button"
      onClick={onClick}
      className="card card-hover"
      style={{
        flex: "0 0 240px",
        scrollSnapAlign: "start",
        textAlign: "left",
        padding: "10px 12px",
        background: "transparent",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--color-muted)", letterSpacing: 0.08 }}>
          Lineup
        </div>
        <div className="num" style={{ fontSize: 11, color: "var(--color-muted)" }}>
          S{lineup.season}
        </div>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.3 }}>{labels.join(" · ")}</div>
      {lineup.net_rating != null && (
        <div
          className="num"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: positive ? "var(--color-positive)" : "var(--color-negative)",
          }}
        >
          {positive ? "+" : ""}
          {lineup.net_rating.toFixed(1)} net
        </div>
      )}
    </button>
  )
}
