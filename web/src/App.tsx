import { useState } from "react"
import { Nav, type Tab } from "./components/nav/Nav"
import Home from "./pages/Home"
import Players from "./pages/Players"
import Lineups from "./pages/Lineups"

export type LineupPrefill = { players: string[]; season: number }

export default function App() {
  const [tab, setTab] = useState<Tab>("home")
  const [openPlayerId, setOpenPlayerId] = useState<string | null>(null)
  const [lineupPrefill, setLineupPrefill] = useState<LineupPrefill | null>(null)
  return (
    <div className="min-h-screen">
      <Nav active={tab} onChange={setTab} />
      <main className="mx-auto" style={{ maxWidth: 1200, padding: "24px" }}>
        {tab === "home" && (
          <Home
            setTab={setTab}
            setOpenPlayerId={setOpenPlayerId}
            setLineupPrefill={setLineupPrefill}
          />
        )}
        {tab === "players" && (
          <Players
            setTab={setTab}
            openPlayerId={openPlayerId}
            setOpenPlayerId={setOpenPlayerId}
          />
        )}
        {tab === "lineups" && (
          <Lineups
            prefill={lineupPrefill}
            setPrefill={setLineupPrefill}
          />
        )}
      </main>
    </div>
  )
}
