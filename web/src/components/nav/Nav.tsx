export type Tab = "home" | "players" | "lineups"

const LABEL: Record<Tab, string> = {
  home: "Simulate",
  players: "Players",
  lineups: "Lineups",
}

const ORDER: Tab[] = ["home", "players", "lineups"]

export function Nav({
  active,
  onChange,
}: {
  active: Tab
  onChange: (t: Tab) => void
}) {
  return (
    <nav className="flex items-center gap-2 px-6 py-4 border-b" style={{ borderColor: "var(--color-border)" }}>
      <div className="text-sm font-semibold tracking-tight mr-4">nba sim</div>
      <div className="flex items-center gap-2">
        {ORDER.map((t) => (
          <button
            key={t}
            type="button"
            className={"chip" + (active === t ? " chip-active" : "")}
            onClick={() => onChange(t)}
          >
            {LABEL[t]}
          </button>
        ))}
      </div>
    </nav>
  )
}
