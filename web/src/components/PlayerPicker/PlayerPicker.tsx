import { useEffect, useMemo, useRef, useState } from "react"
import * as Dialog from "@radix-ui/react-dialog"
import {
  playerSearch,
  playerSimilar,
  type PlayerSearchHit,
  type PlayerSimilarHit,
} from "@/lib/api"

export type PickerMode = "swap" | "slot"

export type PickerPick = {
  player_id?: string
  name: string
  season?: number | string
}

export type PlayerPickerProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode?: PickerMode
  // Anchor for "Similar" tab; required when mode === "swap"
  anchorId?: string
  anchorName?: string
  onPick: (pick: PickerPick) => void
  title?: string
}

type Tab = "similar" | "search"

export function PlayerPicker(props: PlayerPickerProps) {
  const mode: PickerMode = props.mode ?? "swap"
  const initialTab: Tab = mode === "slot" ? "search" : "similar"
  const [tab, setTab] = useState<Tab>(initialTab)
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (props.open) {
      setTab(initialTab)
      setQuery("")
      setTimeout(() => inputRef.current?.focus(), 20)
    }
  }, [props.open, initialTab])

  return (
    <Dialog.Root open={props.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.25)",
            zIndex: 40,
          }}
        />
        <Dialog.Content
          className="card"
          style={{
            position: "fixed",
            top: "10%",
            left: "50%",
            transform: "translateX(-50%)",
            width: "min(520px, 92vw)",
            maxHeight: "75vh",
            display: "flex",
            flexDirection: "column",
            zIndex: 50,
            padding: 0,
            boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
          }}
        >
          <header
            style={{
              padding: "14px 16px",
              borderBottom: "1px solid var(--color-border)",
            }}
          >
            <Dialog.Title
              style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}
            >
              {props.title ?? (mode === "slot" ? "Pick a player" : `Replace ${props.anchorName ?? ""}`)}
            </Dialog.Title>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                if (e.target.value.length > 0 && tab !== "search") setTab("search")
              }}
              placeholder="Search players…"
              className="card"
              style={{
                width: "100%",
                padding: "8px 10px",
                fontSize: 13,
                borderRadius: 6,
              }}
            />
            {mode === "swap" && (
              <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                <button
                  type="button"
                  className={"chip" + (tab === "similar" ? " chip-active" : "")}
                  onClick={() => setTab("similar")}
                  style={{ fontSize: 12 }}
                >
                  Similar
                </button>
                <button
                  type="button"
                  className={"chip" + (tab === "search" ? " chip-active" : "")}
                  onClick={() => setTab("search")}
                  style={{ fontSize: 12 }}
                >
                  Search
                </button>
              </div>
            )}
          </header>

          <div style={{ flex: 1, overflowY: "auto", padding: 4 }}>
            {tab === "similar" && mode === "swap" ? (
              <SimilarList
                anchorId={props.anchorId}
                onPick={(p) => {
                  props.onPick(p)
                  props.onOpenChange(false)
                }}
              />
            ) : (
              <SearchList
                query={query}
                onPick={(p) => {
                  props.onPick(p)
                  props.onOpenChange(false)
                }}
              />
            )}
          </div>

          <footer
            style={{
              padding: "8px 12px",
              borderTop: "1px solid var(--color-border)",
              display: "flex",
              justifyContent: "flex-end",
            }}
          >
            <Dialog.Close asChild>
              <button type="button" className="chip" style={{ fontSize: 12 }}>
                Cancel
              </button>
            </Dialog.Close>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function SimilarList({
  anchorId,
  onPick,
}: {
  anchorId: string | undefined
  onPick: (p: PickerPick) => void
}) {
  const [items, setItems] = useState<PlayerSimilarHit[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [randomInit, setRandomInit] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!anchorId) {
      setErr("no anchor player")
      return
    }
    let cancelled = false
    setLoading(true)
    setErr(null)
    setRandomInit(false)
    playerSimilar(anchorId, 12).then((res) => {
      if (cancelled) return
      setLoading(false)
      if (!res.ok) {
        setErr(res.message || res.error)
        return
      }
      setRandomInit(res.warnings.some((w) => w.code === "random_init_embeddings"))
      setItems(res.data.neighbors ?? [])
    })
    return () => {
      cancelled = true
    }
  }, [anchorId])

  if (loading) return <Loading>loading similar players…</Loading>
  if (err) return <Empty>could not load similar: {err}</Empty>
  if (randomInit || !items || items.length === 0)
    return (
      <Empty>
        {randomInit
          ? "random-init embeddings; pick from search instead"
          : "no similar players"}
      </Empty>
    )

  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {items.map((p) => (
        <Row
          key={`${p.player_id}-${p.season ?? ""}`}
          onClick={() => onPick(p)}
          right={<span className="num" style={{ color: "var(--color-muted)" }}>{p.distance.toFixed(3)}</span>}
        >
          {p.name}
          {p.season != null && (
            <span className="num" style={{ marginLeft: 6, color: "var(--color-muted)" }}>
              {p.season}
            </span>
          )}
        </Row>
      ))}
    </ul>
  )
}

function SearchList({
  query,
  onPick,
}: {
  query: string
  onPick: (p: PickerPick) => void
}) {
  const [items, setItems] = useState<PlayerSearchHit[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const trimmed = useMemo(() => query.trim(), [query])

  useEffect(() => {
    if (trimmed.length === 0) {
      setItems(null)
      setErr(null)
      setLoading(false)
      return
    }
    let cancelled = false
    const t = setTimeout(() => {
      setLoading(true)
      setErr(null)
      playerSearch(trimmed).then((res) => {
        if (cancelled) return
        setLoading(false)
        if (!res.ok) {
          setErr(res.message || res.error)
          return
        }
        setItems(res.data.results ?? [])
      })
    }, 180)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [trimmed])

  if (trimmed.length === 0) return <Empty>start typing to search</Empty>
  if (loading) return <Loading>searching…</Loading>
  if (err) return <Empty>search failed: {err}</Empty>
  if (!items || items.length === 0) return <Empty>no players matching “{trimmed}”</Empty>

  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {items.map((p) => (
        <Row
          key={`${p.player_id}-${p.season ?? ""}`}
          onClick={() => onPick(p)}
        >
          {p.name}
          {p.season != null && (
            <span className="num" style={{ marginLeft: 6, color: "var(--color-muted)" }}>
              {p.season}
            </span>
          )}
        </Row>
      ))}
    </ul>
  )
}

function Row({
  children,
  right,
  onClick,
}: {
  children: React.ReactNode
  right?: React.ReactNode
  onClick: () => void
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="card-hover"
        style={{
          display: "flex",
          width: "100%",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          border: "none",
          background: "transparent",
          fontSize: 13,
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span>{children}</span>
        {right}
      </button>
    </li>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: "20px 16px", fontSize: 12, color: "var(--color-muted)" }}>
      {children}
    </div>
  )
}

function Loading({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: "20px 16px", fontSize: 12, color: "var(--color-muted)" }}>
      {children}
    </div>
  )
}
