// Single boundary to the nba CLI via scripts/web/serve.py.
// Every call POSTs {argv:[...]} to /api/run, parses stdout as the
// {data, warnings, meta} envelope, and returns a discriminated union.

export type Warning = {
  code: string
  message: string
  context?: Record<string, unknown>
}

export type ModelVersions = {
  predictor?: string
  embeddings?: string
  lm?: string
  [k: string]: string | undefined
}

export type Meta = {
  model_versions?: ModelVersions
  cached?: boolean
  generated_at?: string
  stub?: boolean
  [k: string]: unknown
}

export type Envelope<T> = {
  data: T
  warnings: Warning[]
  meta: Meta
}

export type TypedError =
  | "InvalidPlayerError"
  | "InsufficientDataError"
  | "EraOutOfRangeError"

export type ApiOk<T> = { ok: true } & Envelope<T>
export type ApiErr = {
  ok: false
  error: TypedError | "untyped"
  message: string
  context?: Record<string, unknown>
  stderr: string
  rc: number
}
export type ApiResult<T> = ApiOk<T> | ApiErr

const TYPED: ReadonlySet<TypedError> = new Set([
  "InvalidPlayerError",
  "InsufficientDataError",
  "EraOutOfRangeError",
])

function isTyped(s: string): s is TypedError {
  return TYPED.has(s as TypedError)
}

function parseStderr(stderr: string): {
  error: TypedError | "untyped"
  message: string
  context?: Record<string, unknown>
} {
  const line = stderr
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .pop()
  if (!line) return { error: "untyped", message: stderr || "no stderr" }
  try {
    const obj = JSON.parse(line)
    const code = typeof obj.error === "string" && isTyped(obj.error) ? obj.error : "untyped"
    return {
      error: code,
      message: typeof obj.message === "string" ? obj.message : line,
      context: obj.context,
    }
  } catch {
    return { error: "untyped", message: line }
  }
}

async function run<T>(argv: string[]): Promise<ApiResult<T>> {
  let res: Response
  try {
    res = await fetch("/api/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ argv }),
    })
  } catch (e) {
    return {
      ok: false,
      error: "untyped",
      message: `network: ${(e as Error).message}`,
      stderr: "",
      rc: -1,
    }
  }
  if (!res.ok) {
    const text = await res.text()
    return {
      ok: false,
      error: "untyped",
      message: `gateway ${res.status}: ${text.slice(0, 200)}`,
      stderr: text,
      rc: res.status,
    }
  }
  const payload = (await res.json()) as {
    stdout: string
    stderr: string
    rc: number
  }
  if (payload.rc !== 0) {
    const parsed = parseStderr(payload.stderr)
    return { ok: false, ...parsed, stderr: payload.stderr, rc: payload.rc }
  }
  let env: Envelope<T>
  try {
    env = JSON.parse(payload.stdout)
  } catch {
    return {
      ok: false,
      error: "untyped",
      message: "non-JSON stdout from nba CLI",
      stderr: payload.stdout.slice(0, 500),
      rc: 0,
    }
  }
  return {
    ok: true,
    data: env.data,
    warnings: env.warnings ?? [],
    meta: env.meta ?? {},
  }
}

// ---------- Domain types ----------

export type Score = { home: number; away: number }
export type WinProb = { value: number; ci?: number }

export type MatchupRow = {
  home_player: string
  away_player: string
  edge: number
  note: string | null
}

export type TeamEdge = {
  tag: string
  sign: "+" | "-"
  magnitude: number
  label: string
}

export type SimData = {
  score: Score
  win_prob: WinProb
  matchups: MatchupRow[]
  team_edges: TeamEdge[]
  scouting_take?: string | null
}

export type PlayerSearchHit = {
  player_id: string
  name: string
  season?: number | string
}

export type PlayerSimilarHit = {
  player_id: string
  name: string
  season?: number | string
  distance: number
}

export type CareerSeason = {
  season: number | string
  team?: string | null
  games?: number | null
  mpg?: number | null
  ppg?: number | null
  rpg?: number | null
  apg?: number | null
}

export type PlayerCareer = {
  player_id: string
  name: string
  seasons: CareerSeason[]
}

export type LineupStats = {
  players: string[]
  season: number | string
  ortg?: number | null
  drtg?: number | null
  netrtg?: number | null
  minutes?: number | null
  pace?: number | null
}

// ---------- Helpers ----------

export type SimOpts = {
  swaps?: Array<{ from: string; to: string; side: "home" | "away" }>
}

export function simulate(
  homeTeam: string,
  homeSeason: number | string,
  awayTeam: string,
  awaySeason: number | string,
  opts: SimOpts = {},
): Promise<ApiResult<SimData>> {
  const argv = [
    "sim",
    "--home", `${homeTeam}-${homeSeason}`,
    "--away", `${awayTeam}-${awaySeason}`,
  ]
  for (const s of opts.swaps ?? []) {
    argv.push("--swap", `${s.side}:${s.from}->${s.to}`)
  }
  return run<SimData>(argv)
}

export function playerSearch(q: string): Promise<ApiResult<{ results: PlayerSearchHit[] }>> {
  return run<{ results: PlayerSearchHit[] }>(["players", "search", "--q", q])
}

export function playerSimilar(
  id: string,
  k = 10,
): Promise<ApiResult<{ neighbors: PlayerSimilarHit[] }>> {
  return run<{ neighbors: PlayerSimilarHit[] }>([
    "players",
    "similar",
    "--id", id,
    "--k", String(k),
  ])
}

export function playerCareer(id: string): Promise<ApiResult<PlayerCareer>> {
  return run<PlayerCareer>(["players", "career", "--id", id])
}

export function lineupStats(
  players: string[],
  season: number | string,
): Promise<ApiResult<LineupStats>> {
  const argv = ["lineup", "--season", String(season)]
  for (const p of players) argv.push("--player", p)
  return run<LineupStats>(argv)
}

// `meta.model_versions` containing stub markers → render the "stub" pill.
const STUB_MARKERS = ["stub", "v0", "placeholder"]
export function isStubMeta(meta: Meta): boolean {
  if (meta.stub === true) return true
  const versions = meta.model_versions
  if (!versions) return false
  return Object.values(versions).some(
    (v) => typeof v === "string" && STUB_MARKERS.some((m) => v.toLowerCase().includes(m)),
  )
}
