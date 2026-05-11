import { useState } from "react"
import { Nav, type Tab } from "./components/nav/Nav"
import Home from "./pages/Home"
import Players from "./pages/Players"
import Lineups from "./pages/Lineups"

export default function App() {
  const [tab, setTab] = useState<Tab>("home")
  return (
    <div className="min-h-screen">
      <Nav active={tab} onChange={setTab} />
      <main className="mx-auto" style={{ maxWidth: 1200, padding: "24px" }}>
        {tab === "home" && <Home />}
        {tab === "players" && <Players />}
        {tab === "lineups" && <Lineups />}
      </main>
    </div>
  )
}
