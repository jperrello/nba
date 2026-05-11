import { useState } from "react"
import * as Tooltip from "@radix-ui/react-tooltip"
import type { Warning } from "@/lib/api"

export function WarningPill({ warning, compact }: { warning: Warning; compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const label = compact ? warning.code : labelFor(warning)
  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root open={open} onOpenChange={setOpen}>
        <Tooltip.Trigger asChild>
          <button
            type="button"
            className="pill pill-warn"
            onClick={() => setOpen((v) => !v)}
            style={{ cursor: "help" }}
          >
            {label}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="card"
            sideOffset={6}
            style={{
              padding: "8px 12px",
              maxWidth: 320,
              fontSize: 12,
              boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
              zIndex: 50,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 2 }}>{warning.code}</div>
            <div style={{ color: "var(--color-muted)" }}>{warning.message}</div>
            {warning.context && Object.keys(warning.context).length > 0 && (
              <pre
                className="num"
                style={{
                  margin: "6px 0 0",
                  fontSize: 11,
                  color: "var(--color-muted)",
                  whiteSpace: "pre-wrap",
                }}
              >
                {JSON.stringify(warning.context, null, 2)}
              </pre>
            )}
            <Tooltip.Arrow style={{ fill: "var(--color-bg)" }} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}

function labelFor(w: Warning): string {
  if (w.code === "season_fallback") {
    const c = w.context as { requested?: number | string; used?: number | string } | undefined
    if (c?.requested != null && c?.used != null) return `using ${c.used} (req ${c.requested})`
  }
  if (w.code === "sparse_data") {
    const c = w.context as { n_effective?: number } | undefined
    if (typeof c?.n_effective === "number") return `sparse (n=${c.n_effective})`
  }
  return w.code
}

export function WarningStrip({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) return null
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {warnings.map((w, i) => (
        <WarningPill key={i} warning={w} />
      ))}
    </div>
  )
}
