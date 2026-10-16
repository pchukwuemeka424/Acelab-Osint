import { Search } from "lucide-react"
import { FormEvent, useEffect, useState } from "react"
import { z } from "zod"

const indicatorSchema = z.string().trim().min(1, "Enter a domain, URL, IP address, certificate fingerprint, or full name.").max(512)

type Props = {
  value: string
  busy: boolean
  error: string
  onSubmit: (value: string) => void
  size?: "bar" | "hero"
}

export function GraphSearch({ value, busy, error, onSubmit, size = "bar" }: Props) {
  const [draft, setDraft] = useState(value)
  const [localError, setLocalError] = useState("")

  useEffect(() => {
    setDraft(value)
  }, [value])

  function submit(event?: FormEvent) {
    event?.preventDefault()
    const parsed = indicatorSchema.safeParse(draft)
    if (!parsed.success) {
      setLocalError(parsed.error.issues[0]?.message || "That indicator is not valid.")
      return
    }
    setLocalError("")
    onSubmit(parsed.data)
  }

  return (
    <form onSubmit={submit} className={size === "hero" ? "relative w-full" : "relative w-full min-w-[17rem] max-w-lg"}>
      <Search size={size === "hero" ? 16 : 14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        aria-label="Investigate indicator"
        value={draft}
        disabled={busy}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault()
            submit()
          }
        }}
        className={
          size === "hero"
            ? "h-12 w-full rounded-lg border border-slate-300 bg-white pl-10 pr-[6.5rem] text-[15px] text-slate-900 shadow-sm outline-none placeholder:text-slate-400 focus:border-[#0A1628] focus:ring-2 focus:ring-[#0A1628]/10 disabled:opacity-60"
            : "h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-[13px] text-slate-900 outline-none placeholder:text-slate-400 focus:border-teal-700 focus:bg-white focus:ring-2 focus:ring-teal-700/15 disabled:opacity-60"
        }
        placeholder={size === "hero" ? "Name or website" : "Name, domain, URL, IP, or fingerprint"}
      />
      {size === "hero" && (
        <button type="submit" disabled={busy} className="absolute right-1.5 top-1/2 h-9 -translate-y-1/2 rounded-md bg-[#0A1628] px-3.5 text-[13px] font-medium text-white disabled:opacity-60">
          {busy ? "Searching" : "Search"}
        </button>
      )}
      {(busy || error || localError) && (
        <p className={`absolute left-1 z-20 rounded-md border bg-white px-2 py-1 text-[11px] shadow-sm ${size === "hero" ? "top-14" : "top-10"} ${error || localError ? "border-rose-200 text-rose-700" : "border-slate-200 text-slate-500"}`}>{busy ? "Scanning public registrations. This can take a few minutes." : error || localError}</p>
      )}
    </form>
  )
}
