import { useQuery } from "@tanstack/react-query"
import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../../api/client"
import type { Investigation } from "../../api/types"

type Props = {
  investigation: Investigation | null
  onSaved: () => void
}

export function UserMenu({ investigation, onSaved }: Props) {
  const [open, setOpen] = useState(false)
  const me = useQuery({ queryKey: ["me"], queryFn: api.me })
  const name = me.data?.display_name || "analyst"
  const role = me.data?.role || ""
  const showRole = role.length > 0 && role.toLowerCase() !== name.toLowerCase()

  async function save() {
    if (!investigation) return
    await api.patchInvestigation(investigation.id, { is_saved: !investigation.is_saved })
    onSaved()
    setOpen(false)
  }

  return (
    <div className="relative">
      <button type="button" aria-label="Account menu" aria-expanded={open} className="flex items-center gap-2 rounded-full py-0.5 pl-0.5 pr-2 text-slate-800 hover:bg-white" onClick={() => setOpen((value) => !value)}>
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0A1628] text-[11px] font-semibold uppercase text-white">{name.slice(0, 1)}</span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-[13px] font-medium text-slate-900">{name}</span>
          {showRole && <span className="block text-[10px] uppercase tracking-[0.12em] text-slate-400">{role}</span>}
        </span>
        <ChevronDown size={14} className={`text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-[12px] text-slate-800 shadow-[0_16px_40px_-24px_rgba(15,23,42,0.45)]">
          <div className="border-b border-slate-100 px-3 py-2">
            <div className="text-[13px] font-medium text-slate-900">{name}</div>
            <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">{showRole ? role : "AceLab"}</div>
          </div>
          <MenuLink to="/" label="Workspace" onClick={() => setOpen(false)} />
          <MenuLink to="/history" label="Investigation history" onClick={() => setOpen(false)} />
          <MenuLink to="/cases" label="Saved cases" onClick={() => setOpen(false)} />
          {investigation && <MenuLink to={`/investigations/${investigation.id}/report`} label="Report" onClick={() => setOpen(false)} />}
          <button type="button" className="block w-full px-3 py-1.5 text-left hover:bg-slate-50" onClick={save}>
            {investigation?.is_saved ? "Unsave case" : "Save case"}
          </button>
          <MenuLink to="/sources" label="Data sources" onClick={() => setOpen(false)} />
          <MenuLink to="/settings" label="Settings" onClick={() => setOpen(false)} />
          <MenuLink to="/health" label="System health" onClick={() => setOpen(false)} />
        </div>
      )}
    </div>
  )
}

function MenuLink({ to, label, onClick }: { to: string; label: string; onClick: () => void }) {
  return (
    <Link to={to} className="block px-3 py-1.5 text-slate-800 hover:bg-slate-50" onClick={onClick}>
      {label}
    </Link>
  )
}
