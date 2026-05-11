import { Slot, type SlotPlayer } from "./Slot"

type Props = {
  slots: (SlotPlayer | null)[]
  season: number
  onSlotChange: (i: number, p: SlotPlayer | null) => void
  onSeasonChange: (n: number) => void
  onLookup: () => void
  loading: boolean
}

export function LineupPicker({ slots, season, onSlotChange, onSeasonChange, onLookup, loading }: Props) {
  const full = slots.every((s) => s !== null)
  const valid = season >= 2003
  const disabled = !full || !valid || loading
  return (
    <section className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Label>Lineup</Label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
        {slots.map((p, i) => (
          <Slot
            key={i}
            player={p}
            onPick={(np) => onSlotChange(i, np)}
            onClear={() => onSlotChange(i, null)}
          />
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4 }}>
        <label style={{ fontSize: 12, color: "var(--color-muted)", display: "flex", alignItems: "center", gap: 8 }}>
          Season
          <input
            type="number"
            min={2003}
            max={2030}
            value={season}
            onChange={(e) => onSeasonChange(Number(e.target.value))}
            className="card num"
            style={{ width: 84, padding: "4px 8px", fontSize: 13, borderRadius: 4 }}
          />
        </label>
        <button
          type="button"
          className="chip chip-active"
          onClick={onLookup}
          disabled={disabled}
          style={{ fontSize: 13, opacity: disabled ? 0.5 : 1 }}
        >
          {loading ? "Looking up…" : "Look up"}
        </button>
        {!full && (
          <span style={{ fontSize: 12, color: "var(--color-muted)" }}>fill all 5 slots</span>
        )}
        {full && !valid && (
          <span style={{ fontSize: 12, color: "var(--color-negative)" }}>season must be 2003 or later</span>
        )}
      </div>
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
