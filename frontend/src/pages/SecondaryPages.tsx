import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FormEvent, useState, type ReactNode } from "react"
import { Link, useParams } from "react-router-dom"
import { api } from "../api/client"

function Frame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="h-full overflow-auto bg-ink px-6 py-4 text-[13px]">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-[15px] font-semibold">{title}</h1>
        <Link to="/" className="text-[12px] text-muted">
          Workspace
        </Link>
      </div>
      {children}
    </main>
  )
}

export function HistoryPage() {
  const rows = useQuery({ queryKey: ["investigations"], queryFn: () => api.investigations() })
  return (
    <Frame title="Investigation history">
      <table className="w-full text-left text-[12px]">
        <thead className="text-muted">
          <tr>
            <th className="py-1">ID</th>
            <th>Root indicator</th>
            <th>Created</th>
            <th>Status</th>
            <th>Entities</th>
            <th>Relationships</th>
          </tr>
        </thead>
        <tbody>
          {(rows.data?.items || []).map((item) => (
            <tr key={item.id} className="border-t border-[#1c1c1c]">
              <td className="py-2 pr-2 font-mono text-[11px]">
                <Link to={`/?investigation=${item.id}`}>{item.id.slice(0, 8)}</Link>
              </td>
              <td>{item.root_indicator}</td>
              <td>{item.created_at?.slice(0, 10)}</td>
              <td>{item.status}</td>
              <td>{item.entity_count}</td>
              <td>{item.relationship_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.isError && <p className="text-coral">Could not load history.</p>}
      {rows.data?.items.length === 0 && <p className="text-muted">No investigations yet.</p>}
    </Frame>
  )
}

export function CasesPage() {
  const rows = useQuery({ queryKey: ["cases"], queryFn: () => api.investigations(true) })
  return (
    <Frame title="Saved cases">
      <ul className="space-y-2">
        {(rows.data?.items || []).map((item) => (
          <li key={item.id} className="rounded bg-card px-3 py-2">
            <Link to={`/?investigation=${item.id}`} className="font-semibold">
              {item.root_indicator}
            </Link>
            <div className="text-[11px] text-muted">
              {item.status} · {item.entity_count} entities · {item.relationship_count} relationships
            </div>
          </li>
        ))}
      </ul>
      {rows.data?.items.length === 0 && <p className="text-muted">No saved cases.</p>}
    </Frame>
  )
}

export function ReportPage() {
  const { id = "" } = useParams()
  const report = useQuery({ queryKey: ["report", id], queryFn: () => api.report(id), enabled: Boolean(id) })
  const [note, setNote] = useState("")
  const queryClient = useQueryClient()
  const saveNote = useMutation({
    mutationFn: () => api.addNote(id, note),
    onSuccess: () => {
      setNote("")
      queryClient.invalidateQueries({ queryKey: ["report", id] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (note.trim()) saveNote.mutate()
  }

  const data = report.data
  return (
    <Frame title="Investigation report">
      {report.isLoading && <p className="text-muted">Loading report…</p>}
      {report.isError && <p className="text-coral">Could not load the report.</p>}
      {data && (
        <div className="max-w-3xl space-y-4">
          <p>{data.summary}</p>
          <p className="text-[12px] text-muted">Root indicator {data.root_indicator}</p>
          {data.is_demonstration && <p className="text-[12px] text-gold">Live collection is off. Only the submitted indicator is stored.</p>}
          <section>
            <h2 className="mb-1 text-[13px] font-semibold">Associations</h2>
            <ul className="space-y-2">
              {data.associations.slice(0, 12).map((item) => (
                <li key={item.id} className="rounded bg-card px-3 py-2 text-[12px]">
                  <div>
                    {item.source} → {item.target} · {item.label} · heuristic {item.heuristic_score} ({item.score_kind})
                  </div>
                  <div className="text-muted">{item.summary}</div>
                </li>
              ))}
            </ul>
          </section>
          {data.analysis?.campaign?.active && (
            <section>
              <h2 className="mb-1 text-[13px] font-semibold">Saved-case matches</h2>
              <p className="text-[12px] text-muted">{data.analysis.campaign.note}</p>
              <ul className="mt-2 space-y-1 text-[12px]">
                {data.analysis.campaign.matches.map((match) => (
                  <li key={`${match.saved_investigation_id}-${match.artifact_label}`}>
                    {match.artifact_label} · {match.saved_indicator}
                    {match.observation_ids[0] ? ` · observation ${match.observation_ids[0]}` : ""}
                  </li>
                ))}
                {data.analysis.campaign.matches.length === 0 && <li>No saved case shares a rare artifact.</li>}
              </ul>
              {data.analysis.campaign.timeline.length > 0 && (
                <ul className="mt-2 space-y-1 text-[12px]">
                  {data.analysis.campaign.timeline.slice(0, 8).map((event) => (
                    <li key={`${event.kind}-${event.at}-${event.subject}`}>
                      {event.at} · {event.label} · {event.subject}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          <section>
            <h2 className="mb-1 text-[13px] font-semibold">Timeline</h2>
            <ul className="space-y-1 text-[12px]">
              {data.timeline.slice(0, 12).map((item) => (
                <li key={item.observation_id}>
                  observed {item.observed_at || "unknown"} · retrieved {item.retrieved_at} · {item.source} · {item.value}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2 className="mb-1 text-[13px] font-semibold">Limitations</h2>
            <ul className="list-disc pl-4 text-[12px] text-muted">
              {data.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
          {data.narrative && (
            <section>
              <h2 className="mb-1 text-[13px] font-semibold">Narrative ({data.narrative_status})</h2>
              <pre className="whitespace-pre-wrap rounded bg-card p-3 text-[12px]">{data.narrative}</pre>
            </section>
          )}
          {!data.narrative && <p className="text-[12px] text-muted">Model narrative: {data.narrative_status}.</p>}
          <section>
            <h2 className="mb-1 text-[13px] font-semibold">Analyst notes</h2>
            <ul className="mb-2 space-y-1 text-[12px]">
              {data.notes.map((item) => (
                <li key={item.id}>{item.note}</li>
              ))}
            </ul>
            <form onSubmit={submit} className="flex gap-2">
              <input aria-label="Analyst note" value={note} onChange={(event) => setNote(event.target.value)} className="h-8 flex-1 rounded bg-field px-2" />
              <button type="submit" className="rounded bg-white px-2 text-black">
                Add note
              </button>
            </form>
          </section>
          <div className="flex gap-2">
            <button type="button" className="rounded bg-card px-3 py-1" onClick={() => api.export(id, "json")}>
              Export JSON
            </button>
            <button type="button" className="rounded bg-card px-3 py-1" onClick={() => api.export(id, "csv")}>
              Export CSV
            </button>
            <button type="button" className="rounded bg-card px-3 py-1" onClick={() => api.export(id, "handoff")}>
              Export handoff
            </button>
          </div>
        </div>
      )}
    </Frame>
  )
}

export function SourcesPage() {
  const queryClient = useQueryClient()
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources })
  const me = useQuery({ queryKey: ["me"], queryFn: api.me })
  const update = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) => api.updateSource(name, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
  })
  return (
    <Frame title="Data sources">
      {sources.data?.demo_mode && <p className="mb-3 text-[12px] text-gold">Demonstration mode is on. Live connectors stay idle until DEMO_MODE is turned off.</p>}
      <ul className="max-w-2xl space-y-2">
        {(sources.data?.items || []).map((item) => (
          <li key={item.name} className="rounded bg-card px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{item.name}</span>
              <button
                type="button"
                disabled={me.data?.role !== "admin" || item.name === "demonstration"}
                aria-pressed={item.enabled}
                className="text-[12px] text-white"
                onClick={() => update.mutate({ name: item.name, enabled: !item.enabled })}
              >
                {item.enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
            <p className="text-[12px] text-muted">{item.description}</p>
            {item.requires_key && <p className="text-[11px] text-muted">{item.key_configured ? "Key configured" : "Key not configured"}</p>}
          </li>
        ))}
      </ul>
      {update.isError && <p className="mt-2 text-coral">{update.error instanceof Error ? update.error.message : "Update failed."}</p>}
    </Frame>
  )
}

export function SettingsPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me })
  const [displayName, setDisplayName] = useState("")
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [message, setMessage] = useState("")
  const queryClient = useQueryClient()

  async function submit(event: FormEvent) {
    event.preventDefault()
    setMessage("")
    try {
      await api.updateSettings({
        display_name: displayName || undefined,
        current_password: currentPassword || undefined,
        new_password: newPassword || undefined,
      })
      setMessage("Saved.")
      queryClient.invalidateQueries({ queryKey: ["me"] })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save settings.")
    }
  }

  return (
    <Frame title="Settings">
      <p className="mb-3 text-[12px] text-muted">
        Signed in as {me.data?.email} ({me.data?.role})
      </p>
      <form onSubmit={submit} className="max-w-sm space-y-2">
        <input aria-label="Display name" placeholder={me.data?.display_name || "Display name"} value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="h-8 w-full rounded bg-field px-2" />
        <input aria-label="Current password" type="password" placeholder="Current password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="h-8 w-full rounded bg-field px-2" />
        <input aria-label="New password" type="password" placeholder="New password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="h-8 w-full rounded bg-field px-2" />
        <button type="submit" className="rounded bg-white px-3 py-1 text-black">
          Save
        </button>
        {message && <p className="text-[12px] text-muted">{message}</p>}
      </form>
    </Frame>
  )
}

export function HealthPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health })
  const data = health.data
  return (
    <Frame title="System health">
      {health.isLoading && <p className="text-muted">Checking services…</p>}
      {health.isError && <p className="text-coral">Health check failed.</p>}
      {data && (
        <ul className="max-w-md space-y-2 text-[12px]">
          <li className="rounded bg-card px-3 py-2">Status {data.status}</li>
          <li className="rounded bg-card px-3 py-2">Database {data.database ? "reachable" : "unavailable"}</li>
          <li className="rounded bg-card px-3 py-2">Redis {data.redis ? "reachable" : "not configured or unavailable"}</li>
          <li className="rounded bg-card px-3 py-2">Neo4j {data.neo4j_configured ? "configured" : "not configured; NetworkX is used"}</li>
          <li className="rounded bg-card px-3 py-2">Demonstration mode {data.demo_mode ? "on" : "off"}</li>
          <li className="rounded bg-card px-3 py-2">OpenRouter {data.openrouter_configured ? "key configured" : "not configured"}</li>
        </ul>
      )}
    </Frame>
  )
}
