export type RecentLineup = { players: string[]; season: number; net_rating?: number }
export type NameCache = Record<string, { name: string; last_season?: number | string }>

export function RecentList({
  items,
  namecache,
  onPick,
}: {
  items: RecentLineup[]
  namecache: NameCache
  onPick: (item: RecentLineup) => void
}) {
  return (
    <section>
      <Label>Recent</Label>
      {items.length === 0 && (
        <Hint>recent lookups will appear here</Hint>
      )}
      {items.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0", display: "flex", flexDirection: "column", gap: 4 }}>
          {items.map((item, i) => (
            <li key={`${item.season}-${item.players.join(",")}-${i}`}>
              <button
                type="button"
                onClick={() => onPick(item)}
                className="card card-hover"
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "8px 10px",
                  fontSize: 12,
                  cursor: "pointer",
                  background: "transparent",
                }}
              >
                <div className="num" style={{ color: "var(--color-muted)", marginBottom: 2 }}>
                  S{item.season}
                </div>
                <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                    {item.players.map((id) => namecache[id]?.name ?? id).join(" · ")}
                  </span>
                  {item.net_rating != null && (
                    <span
                      className="num"
                      style={{
                        color: item.net_rating >= 0 ? "var(--color-positive)" : "var(--color-negative)",
                        fontWeight: 600,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.net_rating >= 0 ? "+" : ""}{item.net_rating.toFixed(1)}
                    </span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.08, color: "var(--color-muted)", fontWeight: 500 }}>
      {children}
    </div>
  )
}

function Hint({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 12, color: "var(--color-muted)", padding: "8px 0" }}>
      {children}
    </div>
  )
}
