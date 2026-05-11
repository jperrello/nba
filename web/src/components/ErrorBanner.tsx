import type { ApiErr } from "@/lib/api"

const TITLES: Record<ApiErr["error"], string> = {
  InvalidPlayerError: "InvalidPlayerError",
  InsufficientDataError: "InsufficientDataError",
  EraOutOfRangeError: "EraOutOfRangeError",
  untyped: "Simulation failed",
}

export function ErrorBanner({ err, onRetry }: { err: ApiErr; onRetry?: () => void }) {
  const title = TITLES[err.error]
  const fallback = err.error === "untyped" ? "sim failed; check terminal" : err.message
  return (
    <div
      className="card"
      style={{
        borderColor: "var(--color-negative)",
        background: "var(--color-negative-soft)",
        padding: "12px 14px",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div>
          <div className="num" style={{ fontWeight: 600, color: "var(--color-negative)" }}>
            {title}
          </div>
          <div style={{ marginTop: 4, fontSize: 13 }}>{fallback}</div>
        </div>
        {onRetry && (
          <button type="button" className="chip" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    </div>
  )
}
