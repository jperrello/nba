import type { CareerSeason, PlayerCareer, Warning } from "@/lib/api"

type ColKey = keyof CareerSeason
type Col = { key: ColKey; label: string; num: boolean }

const COLS: Col[] = [
  { key: "season", label: "Season", num: true },
  { key: "team", label: "Team", num: false },
  { key: "games", label: "G", num: true },
  { key: "mpg", label: "MPG", num: true },
  { key: "ppg", label: "PPG", num: true },
  { key: "rpg", label: "RPG", num: true },
  { key: "apg", label: "APG", num: true },
]

export function Career({ data, warnings }: { data: PlayerCareer | null; warnings: Warning[] }) {
  const empty = warnings.some((w) => w.code === "facts_table_empty")
  const rows = data?.seasons ?? []
  if (rows.length === 0) {
    return <Hint>{empty ? "no per-season facts available yet" : "no career data"}</Hint>
  }
  const allNull = rows.every((r) => r.games == null && r.mpg == null && r.ppg == null)
  return (
    <section>
      <Label>Career</Label>
      <div style={{ overflowX: "auto", marginTop: 6 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              {COLS.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: c.num ? "right" : "left",
                    padding: "6px 8px",
                    borderBottom: "1px solid var(--color-border)",
                    fontWeight: 600,
                    fontSize: 11,
                    textTransform: "uppercase",
                    letterSpacing: 0.08,
                    color: "var(--color-muted)",
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {COLS.map((c) => {
                  const v = r[c.key] as number | string | null | undefined
                  const display = v == null ? "—" : String(v)
                  return (
                    <td
                      key={c.key}
                      className={c.num ? "num" : undefined}
                      style={{
                        textAlign: c.num ? "right" : "left",
                        padding: "6px 8px",
                        borderBottom: "1px solid var(--color-border)",
                        color: v == null ? "var(--color-muted)" : undefined,
                      }}
                    >
                      {display}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {empty && allNull && (
        <Hint>per-season stat lines null until ingest fills the facts table</Hint>
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
