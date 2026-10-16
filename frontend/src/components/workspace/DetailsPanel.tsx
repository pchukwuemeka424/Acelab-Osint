import { Download, Search, X } from "lucide-react"
import { useEffect, useState } from "react"
import type { EntityRecord, RelationshipRecord } from "../../api/types"
import { SORTS, TABS } from "../../lib/format"
import type { RegistrationRow } from "../../lib/registration"
import { NodeCard } from "./NodeCard"
import { RegistrationLog } from "./RegistrationLog"

type Props = {
  investigationId: string
  counts: Record<string, number>
  tab: string
  sort: string
  items: EntityRecord[]
  selectedId: string | null
  edge: RelationshipRecord | null
  status: "loading" | "error" | "ready"
  error: string
  onTab: (tab: string) => void
  onSort: (sort: string) => void
  onSearch: (query: string) => void
  onExport: () => void
  onClose: () => void
  onFocus: (id: string) => void
  registrations?: RegistrationRow[]
}

export function DetailsPanel({ investigationId, counts, tab, sort, items, selectedId, edge, status, error, onTab, onSort, onSearch, onExport, onClose, onFocus, registrations = [] }: Props) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState("")

  useEffect(() => {
    if (!selectedId) return
    document.getElementById(`record-${selectedId}`)?.scrollIntoView({ block: "nearest" })
  }, [selectedId, items])

  return (
    <section className="flex min-h-0 flex-1 flex-col bg-white" aria-label="Nodes details">
      <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div>
          <h1 className="text-[15px] font-semibold tracking-tight text-slate-900">Nodes details</h1>
          <p className="text-[11px] text-slate-500">Records linked to this investigation</p>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" aria-label="Search records" className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900" onClick={() => setSearchOpen((open) => !open)}>
            <Search size={15} />
          </button>
          <button type="button" aria-label="Export records" className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900" onClick={onExport}>
            <Download size={15} />
          </button>
          <button type="button" aria-label="Close details" className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
      </header>
      <div className="grid grid-cols-4 border-b border-slate-200 bg-slate-50" role="tablist">
        {TABS.map((item) => {
          const active = tab === item.id
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`flex min-w-0 flex-col items-center justify-center gap-0.5 border-b-2 px-1 py-1.5 text-center leading-tight ${active ? "border-teal-700 bg-white font-medium text-slate-900" : "border-transparent text-slate-500 hover:bg-white hover:text-slate-800"}`}
              onClick={() => onTab(item.id)}
            >
              <span className="text-[12px] font-semibold" style={{ color: item.color }}>
                {counts[item.id] ?? 0}
              </span>
              <span className="text-[10px]">{item.label}</span>
            </button>
          )
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-slate-100 px-4 py-2 text-[11px]">
        <span className="text-slate-400">Sort by</span>
        {SORTS.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={sort === item.id}
            className={sort === item.id ? "font-medium text-slate-900" : "text-slate-500 hover:text-slate-800"}
            onClick={() => onSort(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {searchOpen && (
        <form
          className="border-b border-slate-100 px-4 py-2"
          onSubmit={(event) => {
            event.preventDefault()
            onSearch(query)
          }}
        >
          <input
            aria-label="Filter records"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              onSearch(event.target.value)
            }}
            className="h-8 w-full rounded-md border border-slate-200 bg-white px-2 text-[12px] text-slate-900 outline-none placeholder:text-slate-400 focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
            placeholder="Filter records"
          />
        </form>
      )}
      <div className="light-scroll min-h-0 flex-1 overflow-y-auto bg-slate-50 px-3 py-3">
        <div className="mb-3">
          <RegistrationLog rows={registrations} onFocus={onFocus} />
        </div>
        {edge && (
          <article className="mb-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] shadow-sm">
            <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Relationship evidence</div>
            <div className="mt-1 font-medium capitalize text-slate-900">{edge.rel_type.replaceAll("_", " ")}</div>
            <p className="mt-1 text-slate-700">{edge.reason}</p>
            <div className="mt-1 text-slate-500">
              {edge.provenance} · retrieved {edge.retrieved_at || "—"}
              {edge.is_conflicting ? " · conflicting" : ""}
              {edge.is_stale ? " · stale" : ""}
              {edge.weak_reason ? ` · ${edge.weak_reason.replaceAll("_", " ")}` : ""}
            </div>
            <div className="mt-1 break-all text-[10px] text-slate-500">Observations {edge.observation_ids.join(", ") || "none"}</div>
          </article>
        )}
        {status === "loading" && <p className="px-1 py-3 text-[12px] text-slate-500">Loading records…</p>}
        {status === "error" && <p className="px-1 py-3 text-[12px] text-rose-700">{error || "Could not load records."}</p>}
        {status === "ready" && items.length === 0 && <p className="px-1 py-3 text-[12px] text-slate-500">No records in this category.</p>}
        {status === "ready" &&
          items.map((entity) => (
            <NodeCard key={entity.id} entity={entity} investigationId={investigationId} selected={entity.id === selectedId} onFocus={onFocus} />
          ))}
      </div>
    </section>
  )
}
