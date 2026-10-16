import { Crosshair, Download, Minus, Plus, RotateCcw, SlidersHorizontal } from "lucide-react"
import type { ReactNode } from "react"
import { useState } from "react"
import type { GraphFilters } from "../../api/types"

const NODE_TYPES = ["domain", "ip", "certificate", "nameserver", "url", "hosting", "indicator", "fingerprint", "ssh", "file", "hypothesis", "contact", "account", "seo", "logo", "whois"]
const REL_TYPES = ["resolves_to", "uses_nameserver", "appears_in_certificate", "announced_by", "redirects_to", "observed_in_threat_intel", "shares_infrastructure", "potentially_associated", "observed_on_page", "has_contact", "has_account", "matches_kit"]
const RISKS = ["risk", "contextual", "uncertain"]

type Props = {
  filters: GraphFilters
  onChange: (filters: GraphFilters) => void
  onFit: () => void
  onZoom: (factor: number) => void
  onReset: () => void
  onPng: () => void
  onSvg: () => void
}

export function GraphControls({ filters, onChange, onFit, onZoom, onReset, onPng, onSvg }: Props) {
  const [open, setOpen] = useState(false)

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
  }

  return (
    <div className="absolute bottom-4 right-3 z-20 flex flex-col items-end gap-2">
      {open && (
        <div className="mb-1 w-72 rounded-xl border border-slate-200 bg-white p-3 text-[11px] text-slate-700 shadow-lg">
          <FilterGroup title="Node types" options={NODE_TYPES} selected={filters.types} onToggle={(value) => onChange({ ...filters, types: toggle(filters.types, value) })} />
          <FilterGroup title="Relationships" options={REL_TYPES} selected={filters.relTypes} onToggle={(value) => onChange({ ...filters, relTypes: toggle(filters.relTypes, value) })} />
          <FilterGroup title="Risk category" options={RISKS} selected={filters.risk} onToggle={(value) => onChange({ ...filters, risk: toggle(filters.risk, value) })} />
          <div className="mt-2 flex flex-wrap gap-1">
            <TextButton label="Zoom in" onClick={() => onZoom(1.2)} icon={<Plus size={12} />} />
            <TextButton label="Zoom out" onClick={() => onZoom(0.8)} icon={<Minus size={12} />} />
            <TextButton label="Reset layout" onClick={onReset} icon={<RotateCcw size={12} />} />
            <TextButton label="Export graph PNG" onClick={onPng} icon={<Download size={12} />} />
            <TextButton label="Export graph SVG" onClick={onSvg} icon={<Download size={12} />} />
          </div>
          <label className="mt-3 block text-slate-500">
            Observed after
            <input aria-label="Observed after" type="date" value={filters.observedAfter} onChange={(event) => onChange({ ...filters, observedAfter: event.target.value })} className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-slate-900" />
          </label>
          <label className="mt-2 block text-slate-500">
            Observed before
            <input aria-label="Observed before" type="date" value={filters.observedBefore} onChange={(event) => onChange({ ...filters, observedBefore: event.target.value })} className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-slate-900" />
          </label>
        </div>
      )}
      <div className="flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <IconButton label="Fit graph" onClick={onFit}><Crosshair size={14} /></IconButton>
        <IconButton label="Graph filters" onClick={() => setOpen((value) => !value)}><SlidersHorizontal size={14} /></IconButton>
      </div>
    </div>
  )
}

function FilterGroup({ title, options, selected, onToggle }: { title: string; options: string[]; selected: string[]; onToggle: (value: string) => void }) {
  return (
    <div className="mb-2">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">{title}</div>
      <div className="flex flex-wrap gap-1">
        {options.map((option) => {
          const active = selected.includes(option) || (selected.length === 0 && title !== "Node types")
          return (
            <button key={option} type="button" aria-pressed={selected.length === 0 ? true : selected.includes(option)} className={`rounded-md px-1.5 py-0.5 ${active ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`} onClick={() => onToggle(option)}>
              {option.replaceAll("_", " ")}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function TextButton({ label, onClick, icon }: { label: string; onClick: () => void; icon: ReactNode }) {
  return (
    <button type="button" aria-label={label} onClick={onClick} className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-1.5 py-1 text-slate-700 hover:bg-slate-50">
      {icon}
      {label}
    </button>
  )
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className="flex h-8 w-8 items-center justify-center text-slate-600 hover:bg-slate-50">
      {children}
    </button>
  )
}
