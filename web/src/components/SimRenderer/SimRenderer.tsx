import type { MatchupRow, SimData, TeamEdge, Warning } from "@/lib/api"
import { WarningPill } from "@/components/WarningPill"

export function SimRenderer({
  data,
  warnings,
}: {
  data: SimData
  warnings: Warning[]
}) {
  const sparse = warnings.filter((w) => w.code === "sparse_data")
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <ScoreBlock data={data} sparse={sparse} />
      <MatchupsList rows={data.matchups} />
      <TeamEdgesBlock edges={data.team_edges} />
      {data.scouting_take && <ScoutingTake text={data.scouting_take} />}
    </div>
  )
}

function ScoreBlock({ data, sparse }: { data: SimData; sparse: Warning[] }) {
  const wp = data.win_prob
  const home = wp.value
  const away = 1 - wp.value
  const ci = wp.ci ?? 0
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
      <div>
        <Label>Score</Label>
        <div className="num" style={{ fontSize: 32, fontWeight: 600, letterSpacing: -0.5 }}>
          {data.score.home}
          <span style={{ color: "var(--color-muted)", margin: "0 8px" }}>–</span>
          {data.score.away}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 240 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <Label>Win prob (home)</Label>
          {sparse.map((w, i) => <WarningPill key={i} warning={w} />)}
        </div>
        <div className="num" style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>
          {(home * 100).toFixed(1)}%
          {ci > 0 && (
            <span style={{ fontSize: 12, color: "var(--color-muted)", marginLeft: 8 }}>
              ±{(ci * 100).toFixed(1)}%
            </span>
          )}
        </div>
        <WinProbBar home={home} away={away} ci={ci} />
      </div>
    </div>
  )
}

function WinProbBar({ home, away, ci }: { home: number; away: number; ci: number }) {
  const homePct = Math.max(0, Math.min(100, home * 100))
  const awayPct = Math.max(0, Math.min(100, away * 100))
  const lo = Math.max(0, (home - ci) * 100)
  const hi = Math.min(100, (home + ci) * 100)
  return (
    <div style={{ marginTop: 6, position: "relative", height: 8 }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          borderRadius: 4,
          overflow: "hidden",
          border: "1px solid var(--color-border)",
        }}
      >
        <div style={{ width: `${homePct}%`, background: "var(--color-positive)" }} />
        <div style={{ width: `${awayPct}%`, background: "var(--color-negative)" }} />
      </div>
      {ci > 0 && (
        <div
          style={{
            position: "absolute",
            top: -2,
            height: 12,
            left: `${lo}%`,
            width: `${hi - lo}%`,
            border: "1px solid var(--color-fg)",
            borderRadius: 2,
            background: "transparent",
            pointerEvents: "none",
            opacity: 0.35,
          }}
        />
      )}
    </div>
  )
}

function MatchupsList({ rows }: { rows: MatchupRow[] }) {
  return (
    <div>
      <Label>Matchups</Label>
      <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0", display: "flex", flexDirection: "column", gap: 4 }}>
        {rows.map((m, i) => <MatchupRowItem key={i} row={m} />)}
      </ul>
    </div>
  )
}

function MatchupRowItem({ row }: { row: MatchupRow }) {
  const neutral = row.edge === 0
  const positive = !neutral && row.edge > 0
  const mag = neutral ? 0 : Math.min(100, Math.abs(row.edge) * 100 * 2)
  return (
    <li
      className="card"
      style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", padding: "8px 12px", gap: 12 }}
    >
      <span style={{ fontSize: 13 }}>{row.home_player}</span>
      <div style={{ minWidth: 140, display: "flex", alignItems: "center", gap: 8 }}>
        <EdgeBar magnitude={mag} positive={positive} />
        <span
          className="num"
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: neutral
              ? "var(--color-muted)"
              : positive
                ? "var(--color-positive)"
                : "var(--color-negative)",
            minWidth: 48,
            textAlign: "right",
          }}
        >
          {neutral ? "—" : `${positive ? "+" : ""}${row.edge.toFixed(3)}`}
        </span>
      </div>
      <span style={{ fontSize: 13, textAlign: "right" }}>
        {row.away_player}
        {row.note && <NoteFlag note={row.note} />}
      </span>
    </li>
  )
}

function EdgeBar({ magnitude, positive }: { magnitude: number; positive: boolean }) {
  return (
    <div
      style={{
        flex: 1,
        height: 6,
        background: "var(--color-surface-hover)",
        borderRadius: 3,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: positive ? "50%" : `calc(50% - ${magnitude / 2}%)`,
          width: `${magnitude / 2}%`,
          top: 0,
          bottom: 0,
          background: positive ? "var(--color-positive)" : "var(--color-negative)",
        }}
      />
    </div>
  )
}

function NoteFlag({ note }: { note: string }) {
  return (
    <span
      title={note}
      className="pill pill-warn"
      style={{ marginLeft: 6, fontSize: 10, padding: "1px 6px", cursor: "help" }}
    >
      flag
    </span>
  )
}

function TeamEdgesBlock({ edges }: { edges: TeamEdge[] }) {
  return (
    <div>
      <Label>Team edges</Label>
      <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0", display: "flex", flexDirection: "column", gap: 4 }}>
        {edges.map((e, i) => <TeamEdgeRow key={i} edge={e} />)}
      </ul>
    </div>
  )
}

function TeamEdgeRow({ edge }: { edge: TeamEdge }) {
  const neutral = edge.sign === "0" || edge.magnitude === 0
  const positive = !neutral && edge.sign === "+"
  const mag = neutral ? 0 : Math.min(100, edge.magnitude * 100 * 4)
  return (
    <li
      className="card"
      style={{ display: "grid", gridTemplateColumns: "180px 1fr 60px", alignItems: "center", padding: "6px 12px", gap: 12 }}
    >
      <div>
        <div className="num" style={{ fontSize: 11, color: "var(--color-muted)" }}>{edge.tag}</div>
        <div style={{ fontSize: 12 }}>{edge.label}</div>
      </div>
      <EdgeBar magnitude={mag} positive={positive} />
      <span
        className="num"
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: neutral
            ? "var(--color-muted)"
            : positive
              ? "var(--color-positive)"
              : "var(--color-negative)",
          textAlign: "right",
        }}
      >
        {neutral ? "—" : `${positive ? "+" : "−"}${edge.magnitude.toFixed(3)}`}
      </span>
    </li>
  )
}

function ScoutingTake({ text }: { text: string }) {
  return (
    <div>
      <Label>Scouting take</Label>
      <p style={{ marginTop: 6, fontSize: 13, lineHeight: 1.55 }}>{text}</p>
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: 0.08,
        color: "var(--color-muted)",
        fontWeight: 500,
      }}
    >
      {children}
    </div>
  )
}

export function SimSkeleton() {
  return (
    <div className="card" style={{ padding: 24 }}>
      <div
        style={{
          height: 40,
          width: 200,
          background: "var(--color-surface-hover)",
          borderRadius: 4,
          marginBottom: 18,
        }}
      />
      <div
        style={{
          height: 12,
          width: 280,
          background: "var(--color-surface-hover)",
          borderRadius: 4,
          marginBottom: 24,
        }}
      />
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          style={{
            height: 36,
            background: "var(--color-surface-hover)",
            borderRadius: 4,
            marginBottom: 6,
          }}
        />
      ))}
    </div>
  )
}
