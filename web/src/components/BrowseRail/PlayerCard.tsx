import type { NameCacheEntry } from "./BrowseRail"

export function PlayerCard({
  id,
  meta,
  onClick,
}: {
  id: string
  meta: NameCacheEntry | undefined
  onClick: () => void
}) {
  const name = meta?.name ?? id
  return (
    <button
      type="button"
      onClick={onClick}
      className="card card-hover"
      style={{
        flex: "0 0 200px",
        scrollSnapAlign: "start",
        textAlign: "left",
        padding: "10px 12px",
        background: "transparent",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--color-muted)", letterSpacing: 0.08 }}>
        Player
      </div>
      <div style={{ fontSize: 14, fontWeight: 600 }}>{name}</div>
      {meta?.last_season != null && (
        <div className="num" style={{ fontSize: 12, color: "var(--color-muted)" }}>
          S{meta.last_season}
        </div>
      )}
    </button>
  )
}
