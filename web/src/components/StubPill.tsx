import type { Meta } from "@/lib/api"
import { isStubMeta } from "@/lib/api"

export function StubPill({ meta }: { meta: Meta }) {
  if (!isStubMeta(meta)) return null
  return <span className="pill pill-stub">stub</span>
}

export function CachedBadge({ meta }: { meta: Meta }) {
  if (!meta.cached) return null
  return <span className="pill pill-cached">cached</span>
}
