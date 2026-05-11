import { useLocalStorage } from "@/hooks/useLocalStorage"
import { PlayerCard } from "./PlayerCard"
import { LineupCard } from "./LineupCard"

export type NameCacheEntry = { name: string; last_season?: number | string }
export type NameCache = Record<string, NameCacheEntry>
export type RecentLineup = { players: string[]; season: number; net_rating?: number }

type Card =
  | { kind: "player"; id: string }
  | { kind: "lineup"; lineup: RecentLineup }

type Props = {
  onOpenPlayer?: (id: string) => void
  onOpenLineup?: (prefill: { players: string[]; season: number }) => void
}

function interleave(players: string[], lineups: RecentLineup[]): Card[] {
  const out: Card[] = []
  const max = Math.max(players.length, lineups.length)
  for (let i = 0; i < max; i++) {
    if (i < players.length) out.push({ kind: "player", id: players[i] })
    if (i < lineups.length) out.push({ kind: "lineup", lineup: lineups[i] })
  }
  return out
}

export function BrowseRail({ onOpenPlayer, onOpenLineup }: Props) {
  const [players] = useLocalStorage<string[]>("nba.recent.players", [])
  const [lineups] = useLocalStorage<RecentLineup[]>("nba.recent.lineups", [])
  const [namecache] = useLocalStorage<NameCache>("nba.players.namecache", {})
  const cards = interleave(players, lineups)

  return (
    <section>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.08, color: "var(--color-muted)" }}>
          Browse
        </h3>
      </header>
      {cards.length === 0 && (
        <div
          className="card"
          style={{
            padding: "16px 18px",
            fontSize: 12,
            color: "var(--color-muted)",
          }}
        >
          browse from the Players or Lineups tab
        </div>
      )}
      {cards.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 8,
            overflowX: "auto",
            scrollSnapType: "x mandatory",
            paddingBottom: 4,
          }}
        >
          {cards.map((c, i) => {
            if (c.kind === "player") {
              return (
                <PlayerCard
                  key={`p-${c.id}-${i}`}
                  id={c.id}
                  meta={namecache[c.id]}
                  onClick={() => onOpenPlayer?.(c.id)}
                />
              )
            }
            return (
              <LineupCard
                key={`l-${c.lineup.season}-${i}`}
                lineup={c.lineup}
                namecache={namecache}
                onClick={() => onOpenLineup?.({ players: c.lineup.players, season: c.lineup.season })}
              />
            )
          })}
        </div>
      )}
    </section>
  )
}
