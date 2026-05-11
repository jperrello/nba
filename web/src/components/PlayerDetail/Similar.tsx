import type { ApiErr, PlayerSimilarHit } from "@/lib/api"

type Props = {
  neighbors: PlayerSimilarHit[]
  randomInit: boolean
  err: ApiErr | null
  onPick: (id: string, name: string) => void
}

export function Similar({ neighbors, randomInit, err, onPick }: Props) {
  return (
    <section>
      <Label>Nearest neighbors</Label>
      {err && <Hint>could not load similar: {err.message}</Hint>}
      {!err && randomInit && (
        <Hint>random-init embeddings; pick from search instead</Hint>
      )}
      {!err && !randomInit && neighbors.length === 0 && (
        <Hint>no similar players</Hint>
      )}
      {!err && !randomInit && neighbors.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0", display: "flex", flexDirection: "column", gap: 4 }}>
          {neighbors.map((n) => (
            <li key={`${n.player_id}-${n.season ?? ""}`}>
              <button
                type="button"
                onClick={() => onPick(n.player_id, n.name)}
                className="card card-hover"
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto auto",
                  width: "100%",
                  alignItems: "center",
                  padding: "8px 12px",
                  fontSize: 13,
                  cursor: "pointer",
                  textAlign: "left",
                  background: "transparent",
                  gap: 12,
                }}
              >
                <span>{n.name}</span>
                <span className="num" style={{ color: "var(--color-muted)", fontSize: 12 }}>{n.season ?? ""}</span>
                <Bar distance={n.distance} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Bar({ distance }: { distance: number }) {
  const pct = Math.max(0, Math.min(100, distance * 100))
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 100 }}>
      <div style={{ width: 60, height: 4, background: "var(--color-surface-hover)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: "var(--color-fg)" }} />
      </div>
      <span className="num" style={{ fontSize: 11, color: "var(--color-muted)", minWidth: 36, textAlign: "right" }}>
        {distance.toFixed(3)}
      </span>
    </div>
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
