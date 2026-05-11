import { useState } from "react"
import { PlayerPicker, type PickerPick } from "@/components/PlayerPicker"

export type SlotPlayer = { player_id: string; name: string; season?: number | string }

export function Slot({
  player,
  onPick,
  onClear,
}: {
  player: SlotPlayer | null
  onPick: (p: SlotPlayer) => void
  onClear: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      {player && (
        <div
          className="card"
          style={{
            padding: "8px 10px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 6,
          }}
        >
          <button
            type="button"
            onClick={() => setOpen(true)}
            style={{
              flex: 1,
              textAlign: "left",
              background: "transparent",
              border: "none",
              padding: 0,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {player.name}
          </button>
          <button
            type="button"
            onClick={onClear}
            aria-label="remove"
            style={{
              background: "transparent",
              border: "none",
              padding: 0,
              color: "var(--color-muted)",
              cursor: "pointer",
              fontSize: 14,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}
      {!player && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="card card-hover"
          style={{
            padding: "8px 10px",
            fontSize: 13,
            cursor: "pointer",
            background: "transparent",
            borderStyle: "dashed",
            color: "var(--color-muted)",
            textAlign: "left",
          }}
        >
          + add player
        </button>
      )}
      <PlayerPicker
        open={open}
        onOpenChange={setOpen}
        mode="slot"
        onPick={(p: PickerPick) => {
          onPick({
            player_id: p.player_id ?? p.name,
            name: p.name,
            season: p.season,
          })
        }}
      />
    </>
  )
}
