import { useCallback, useEffect, useMemo, useState } from "react"
import {
  simulate,
  type ApiResult,
  type SimData,
  type Swap,
  type TeamSpec,
  type Warning,
  type Meta,
} from "@/lib/api"
import { PlayerPicker, type PickerPick } from "@/components/PlayerPicker"
import { SimRenderer, SimSkeleton } from "@/components/SimRenderer"
import { ErrorBanner } from "@/components/ErrorBanner"
import { CachedBadge, StubPill } from "@/components/StubPill"
import { WarningPill } from "@/components/WarningPill"

export type Side = "home" | "away"

export type MatchupSpec = {
  home: TeamSpec
  away: TeamSpec
}

type Roster = string[]
type RosterPair = { home: Roster; away: Roster }

export type MatchupCardProps = {
  initial: MatchupSpec
  onChange?: (spec: MatchupSpec) => void
}

const TITLE: Record<Side, string> = { home: "Home", away: "Away" }

export function MatchupCard({ initial, onChange }: MatchupCardProps) {
  const [spec, setSpec] = useState<MatchupSpec>(initial)
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<ApiResult<SimData> | null>(null)
  const [staged, setStaged] = useState<{ home: Swap[]; away: Swap[] }>({ home: [], away: [] })
  const [picker, setPicker] = useState<{ side: Side; index: number; anchor: string } | null>(null)
  const [rosters, setRosters] = useState<RosterPair | null>(null)

  useEffect(() => {
    setSpec(initial)
    setStaged({ home: [], away: [] })
    setResult(null)
    setRosters(null)
  }, [initial])

  useEffect(() => {
    onChange?.(spec)
  }, [spec, onChange])

  const run = useCallback(
    async (s: MatchupSpec, swaps: { home: Swap[]; away: Swap[] }) => {
      setPending(true)
      const res = await simulate(
        { ...s.home, swaps: swaps.home },
        { ...s.away, swaps: swaps.away },
      )
      setPending(false)
      setResult(res)
      if (res.ok && (!rosters || swaps.home.length === 0 && swaps.away.length === 0)) {
        setRosters({
          home: res.data.matchups.map((m) => m.home_player),
          away: res.data.matchups.map((m) => m.away_player),
        })
      } else if (res.ok && rosters) {
        const next = applySwaps(rosters, swaps)
        setRosters(next)
      }
      return res
    },
    [rosters],
  )

  useEffect(() => {
    let cancelled = false
    setPending(true)
    setResult(null)
    simulate(spec.home, spec.away).then((res) => {
      if (cancelled) return
      setPending(false)
      setResult(res)
      if (res.ok) {
        setRosters({
          home: res.data.matchups.map((m) => m.home_player),
          away: res.data.matchups.map((m) => m.away_player),
        })
      }
    })
    return () => {
      cancelled = true
    }
  }, [spec])

  const stagedDisplay = useMemo(() => {
    if (!rosters) return null
    return applySwaps(rosters, staged)
  }, [rosters, staged])

  const hasStaged = staged.home.length + staged.away.length > 0

  const onSimulate = useCallback(() => {
    run(spec, staged)
    setStaged({ home: [], away: [] })
  }, [run, spec, staged])

  const onReset = useCallback(() => setStaged({ home: [], away: [] }), [])

  const onPick = useCallback(
    (pick: PickerPick) => {
      if (!picker) return
      setStaged((prev) => {
        const arr = [...prev[picker.side]]
        const ix = arr.findIndex((s) => s.from === picker.anchor)
        const next: Swap = { from: picker.anchor, to: pick.name }
        if (ix >= 0) arr[ix] = next
        else arr.push(next)
        return { ...prev, [picker.side]: arr }
      })
      setPicker(null)
    },
    [picker],
  )

  const warnings: Warning[] = result?.ok ? result.warnings : []
  const meta: Meta = result?.ok ? result.meta : {}

  return (
    <article className="card" style={{ padding: 18 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>Matchup</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {result?.ok && <CachedBadge meta={meta} />}
          {result?.ok && <StubPill meta={meta} />}
          {hasStaged && (
            <button type="button" className="chip" onClick={onReset} style={{ fontSize: 12 }}>
              Reset swaps
            </button>
          )}
          <button
            type="button"
            className="chip chip-active"
            onClick={onSimulate}
            disabled={pending}
            style={{ fontSize: 13, opacity: pending ? 0.6 : 1 }}
          >
            {pending ? "Simulating…" : "Simulate"}
          </button>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <RosterColumn
          side="home"
          spec={spec.home}
          roster={stagedDisplay?.home ?? rosters?.home ?? []}
          stagedFor={staged.home}
          warnings={warnings.filter((w) => warningMatchesTeam(w, spec.home))}
          loading={pending && !rosters}
          onCellClick={(i, name) => setPicker({ side: "home", index: i, anchor: name })}
        />
        <RosterColumn
          side="away"
          spec={spec.away}
          roster={stagedDisplay?.away ?? rosters?.away ?? []}
          stagedFor={staged.away}
          warnings={warnings.filter((w) => warningMatchesTeam(w, spec.away))}
          loading={pending && !rosters}
          onCellClick={(i, name) => setPicker({ side: "away", index: i, anchor: name })}
        />
      </div>

      <div style={{ marginTop: 18 }}>
        {pending && <SimSkeleton />}
        {!pending && result?.ok === false && (
          <ErrorBanner err={result} onRetry={onSimulate} />
        )}
        {!pending && result?.ok && (
          <SimRenderer data={result.data} warnings={result.warnings} />
        )}
      </div>

      {picker && (
        <PlayerPicker
          open
          onOpenChange={(o) => !o && setPicker(null)}
          mode="swap"
          anchorId={picker.anchor}
          anchorName={picker.anchor}
          onPick={onPick}
        />
      )}
    </article>
  )
}

function RosterColumn({
  side,
  spec,
  roster,
  stagedFor,
  warnings,
  loading,
  onCellClick,
}: {
  side: Side
  spec: TeamSpec
  roster: Roster
  stagedFor: Swap[]
  warnings: Warning[]
  loading: boolean
  onCellClick: (index: number, name: string) => void
}) {
  return (
    <section>
      <header style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--color-muted)", letterSpacing: 0.08 }}>
          {TITLE[side]}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, textTransform: "capitalize" }}>{spec.team}</h3>
          <span className="num" style={{ fontSize: 14, color: "var(--color-muted)" }}>{spec.season}</span>
        </div>
        {warnings.length > 0 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
            {warnings.map((w, i) => <WarningPill key={i} warning={w} />)}
          </div>
        )}
      </header>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        {loading && Array.from({ length: 5 }).map((_, i) => (
          <li
            key={i}
            className="card"
            style={{ height: 34, background: "var(--color-surface-hover)" }}
          />
        ))}
        {!loading && roster.map((name, i) => {
          const swap = stagedFor.find((s) => s.to === name)
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => onCellClick(i, name)}
                className="card card-hover"
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "8px 12px",
                  fontSize: 13,
                  cursor: "pointer",
                  background: "transparent",
                }}
              >
                {swap ? (
                  <>
                    <span style={{ textDecoration: "line-through", color: "var(--color-muted)" }}>
                      {swap.from}
                    </span>
                    <span style={{ color: "var(--color-positive)", marginLeft: 8, fontWeight: 500 }}>
                      → {swap.to}
                    </span>
                  </>
                ) : (
                  name
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function applySwaps(r: RosterPair, swaps: { home: Swap[]; away: Swap[] }): RosterPair {
  return {
    home: applySide(r.home, swaps.home),
    away: applySide(r.away, swaps.away),
  }
}

function applySide(roster: Roster, swaps: Swap[]): Roster {
  let out = [...roster]
  for (const s of swaps) {
    const ix = out.indexOf(s.from)
    if (ix >= 0) out[ix] = s.to
  }
  return out
}

function warningMatchesTeam(w: Warning, t: TeamSpec): boolean {
  if (w.code !== "season_fallback") return false
  const ctx = w.context as { team?: string } | undefined
  if (!ctx?.team) return false
  const a = ctx.team.toLowerCase()
  const b = t.team.toLowerCase()
  return a.includes(b) || b.includes(a)
}
