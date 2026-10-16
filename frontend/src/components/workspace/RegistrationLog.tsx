import type { RegistrationRow } from "../../lib/registration"

type Props = {
  rows: RegistrationRow[]
  onFocus: (id: string) => void
}

export function RegistrationLog({ rows, onFocus }: Props) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white px-3 py-2" aria-label="Registration log">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[12px] font-semibold text-slate-900">Registration log</h2>
        <span className="text-[10px] text-slate-400">{rows.length}</span>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">Websites collected in this investigation.</p>
      {rows.length === 0 ? (
        <p className="mt-2 text-[11px] text-slate-500">No website has been collected yet.</p>
      ) : (
        <ul className="mt-2 max-h-40 space-y-2 overflow-y-auto">
          {rows.map((row) => (
            <li key={`${row.source}-${row.id}`}>
              <button type="button" className="block w-full rounded-md border border-slate-100 bg-slate-50 px-2 py-1.5 text-left hover:border-teal" onClick={() => onFocus(row.id)}>
                <div className="truncate text-[12px] font-medium text-slate-900">{row.website}</div>
                <div className="text-[10px] uppercase tracking-wide text-slate-400">{row.source}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
