import { useMemo, useState } from "react"
import type { EntityRecord } from "../../api/types"
import { metaString } from "../../lib/format"
import { ConnectionGlobe } from "./ConnectionGlobe"

type Props = {
  address: string
  hits: EntityRecord[]
  loading: boolean
  notice?: string
}

const DETAIL_KEYS = ["name", "fullname", "display_name", "bio", "followers", "follower_count", "following", "following_count", "posts", "public_repos", "created_at"]

export function EmailScreen({ address, hits, loading, notice = "" }: Props) {
  const [category, setCategory] = useState("all")
  const categories = useMemo(() => categoryCounts(hits), [hits])
  const visible = category === "all" ? hits : hits.filter((item) => metaString(item.metadata, "category") === category)
  const title = "Name"
  const subtitle = "Public pages that contain this name. A match is a lead to verify, not proof it is one person."

  return (
    <main className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
      <section className="graph-surface relative h-[280px] shrink-0 lg:h-auto lg:min-w-0 lg:flex-1" aria-label="Registration globe">
        <div className="absolute inset-0 flex items-center justify-center p-8">
          <div className="aspect-square h-full max-h-[460px] w-full max-w-[460px]">
            <ConnectionGlobe hub nodes={[]} edges={[]} rootId={null} onFocus={() => undefined} />
          </div>
        </div>
        <div className="pointer-events-none absolute left-4 top-4 max-w-[min(340px,calc(100%-2rem))] rounded-lg border border-white/10 bg-black/70 px-3 py-2 text-white shadow-lg backdrop-blur">
          <p className="text-[10px] font-medium uppercase tracking-wide text-teal">{title}</p>
          <p className="mt-0.5 truncate text-[13px] font-semibold">{address}</p>
        </div>
      </section>
      <aside className="flex min-h-0 min-w-0 flex-1 flex-col border-slate-200 bg-slate-50 lg:w-[42%] lg:max-w-[640px] lg:flex-none lg:border-l" aria-label="Registration log">
        <header className="border-b border-slate-200 bg-white px-4 py-3">
          <h1 className="text-[15px] font-semibold tracking-tight text-slate-900">Registration log</h1>
          <p className="mt-1 text-[12px] text-slate-600">{subtitle}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Stat label="Shown" value={String(hits.length)} />
          </div>
          {categories.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <FilterChip active={category === "all"} label="All" count={hits.length} onClick={() => setCategory("all")} />
              {categories.map((item) => (
                <FilterChip key={item.id} active={category === item.id} label={item.id} count={item.count} onClick={() => setCategory(item.id)} />
              ))}
            </div>
          )}
        </header>
        <div className="light-scroll min-h-0 flex-1 overflow-y-auto px-3 py-3">
          {notice && <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-[13px] text-amber-900">{notice}</p>}
          {loading ? (
            <p className="px-1 py-3 text-[13px] text-slate-500">Loading results.</p>
          ) : visible.length === 0 && !notice ? (
            <p className="rounded-lg border border-slate-200 bg-white px-3 py-4 text-[13px] text-slate-500">
              No public page contained this name.
            </p>
          ) : (
            <ul className="grid gap-3">
              {visible.map((item) => (
                <ResultCard key={item.id} item={item} />
              ))}
            </ul>
          )}
        </div>
      </aside>
    </main>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-[16px] font-semibold text-slate-900">{value}</div>
    </div>
  )
}

function FilterChip({ active, label, count, onClick }: { active: boolean; label: string; count: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-[12px] capitalize ${active ? "border-teal bg-teal text-white" : "border-slate-200 bg-white text-slate-700"}`}
    >
      {label}
      <span className={`ml-1 ${active ? "text-white/80" : "text-slate-400"}`}>{count}</span>
    </button>
  )
}

function categoryCounts(hits: EntityRecord[]): { id: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const item of hits) {
    const category = metaString(item.metadata, "category") || "other"
    counts.set(category, (counts.get(category) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([id, count]) => ({ id, count }))
    .sort((left, right) => right.count - left.count || left.id.localeCompare(right.id))
}

function ResultCard({ item }: { item: EntityRecord }) {
  const meta = item.metadata || {}
  const url = metaString(meta, "url")
  const safeUrl = url.startsWith("https://") ? url : ""
  const avatar = metaString(meta, "avatar")
  const safeAvatar = avatar.startsWith("https://") ? avatar : ""
  const category = metaString(meta, "category")
  const status = metaString(meta, "status")
  const platform = metaString(meta, "platform") || item.display_value
  const details = detailLines(meta.extra)
  const lead = metaString(meta, "lead")
  return (
    <li className="rounded-lg border border-slate-200 bg-white px-3 py-3">
      <div className="flex items-start gap-3">
        {safeAvatar ? (
          <img src={safeAvatar} alt="" className="h-10 w-10 shrink-0 rounded-full border border-slate-200 object-cover" />
        ) : (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[12px] font-semibold uppercase text-slate-500">
            {platform.slice(0, 1)}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-semibold text-slate-900">{platform}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-slate-400">
            {category && <span>{category}</span>}
            {status && (
              <span className={`rounded px-1.5 py-0.5 ${status === "Unreachable" ? "bg-amber-50 text-amber-800" : "bg-teal/10 text-teal"}`}>
                {status}
              </span>
            )}
          </div>
        </div>
      </div>
      {lead === "unreachable" && (
        <p className="mt-2 text-[12px] text-slate-600">This site could not be checked. The connection closed before it answered, so this is not a miss.</p>
      )}
      {lead === "profile_link" && <p className="mt-2 text-[12px] text-slate-600">Linked from a profile page. This does not confirm who operates the site.</p>}
      {details.length > 0 && (
        <dl className="mt-2 space-y-1">
          {details.map((detail) => (
            <div key={detail.label} className="text-[12px] text-slate-600">
              <dt className="inline capitalize text-slate-400">{detail.label.replaceAll("_", " ")} </dt>
              <dd className="inline">{detail.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {safeUrl && (
        <a href={safeUrl} target="_blank" rel="noreferrer" className="mt-2 block truncate text-[12px] text-teal hover:underline">
          {safeUrl}
        </a>
      )}
    </li>
  )
}

function detailLines(extra: unknown): { label: string; value: string }[] {
  if (!extra || typeof extra !== "object") return []
  const record = extra as Record<string, unknown>
  const keys = [...DETAIL_KEYS.filter((key) => key in record), ...Object.keys(record).filter((key) => !DETAIL_KEYS.includes(key))]
  return keys
    .map((key) => ({ label: key, value: typeof record[key] === "string" ? record[key] : "" }))
    .filter((item) => item.value)
    .slice(0, 4)
}
