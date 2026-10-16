import type { EntityPage, ExpandSuggestion, GraphFilters, GraphPayload, Health, Investigation, Report, SourceSetting, User } from "./types"

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function csrfHeader(): Record<string, string> {
  const match = document.cookie.match(/(?:^|; )piae_csrf=([^;]+)/)
  return match ? { "X-CSRF-Token": decodeURIComponent(match[1]) } : {}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  const method = (options.method || "GET").toUpperCase()
  if (method !== "GET" && method !== "HEAD") {
    Object.entries(csrfHeader()).forEach(([key, value]) => headers.set(key, value))
  }
  const response = await fetch(path, { ...options, headers, credentials: "include" })
  if (!response.ok) {
    let message = "The request could not be completed."
    try {
      const payload = await response.json()
      if (typeof payload.detail === "string") message = payload.detail
      else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) message = String(payload.detail[0].msg)
    } catch {
      message = response.statusText || message
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  const contentType = response.headers.get("content-type") || ""
  if (contentType.includes("application/json")) return response.json() as Promise<T>
  return response.text() as Promise<T>
}

function graphQuery(filters: GraphFilters): string {
  const params = new URLSearchParams()
  if (filters.types.length) params.set("types", filters.types.join(","))
  if (filters.relTypes.length) params.set("rel_types", filters.relTypes.join(","))
  if (filters.risk.length) params.set("risk", filters.risk.join(","))
  if (filters.observedAfter) params.set("observed_after", filters.observedAfter)
  if (filters.observedBefore) params.set("observed_before", filters.observedBefore)
  const query = params.toString()
  return query ? `?${query}` : ""
}

export const api = {
  me: () => request<User>("/api/auth/me"),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  updateSettings: (body: { display_name?: string; current_password?: string; new_password?: string }) =>
    request<User>("/api/settings", { method: "PATCH", body: JSON.stringify(body) }),
  current: () => request<Investigation>("/api/investigations/current"),
  investigations: (saved?: boolean) => request<{ items: Investigation[] }>(`/api/investigations${saved ? "?saved=true" : ""}`),
  getInvestigation: (id: string) => request<Investigation>(`/api/investigations/${id}`),
  createInvestigation: (indicator: string) =>
    request<Investigation>("/api/investigations", { method: "POST", body: JSON.stringify({ indicator }) }),
  patchInvestigation: (id: string, body: { is_saved?: boolean; title?: string }) =>
    request<Investigation>(`/api/investigations/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  job: (investigationId: string, jobId: string) =>
    request<{ id: string; status: string; progress: number; stage: string; error: string | null }>(
      `/api/investigations/${investigationId}/jobs/${jobId}`,
    ),
  entities: (id: string, entityType: string, sort: string, direction: string, q: string) => {
    const params = new URLSearchParams({ entity_type: entityType, sort, direction })
    if (q) params.set("q", q)
    return request<EntityPage>(`/api/investigations/${id}/entities?${params.toString()}`)
  },
  graph: (id: string, filters: GraphFilters) => request<GraphPayload>(`/api/investigations/${id}/graph${graphQuery(filters)}`),
  expand: (id: string, entityId: string) =>
    request<GraphPayload & { suggestions: ExpandSuggestion[] }>(`/api/investigations/${id}/graph/expand?entity_id=${encodeURIComponent(entityId)}`, { method: "POST" }),
  path: (id: string, sourceId: string, targetId: string) =>
    request<{ node_ids: string[]; edge_ids: string[] }>(`/api/investigations/${id}/graph/path`, {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId, target_id: targetId }),
    }),
  report: (id: string) => request<Report>(`/api/investigations/${id}/report`),
  addNote: (id: string, note: string) =>
    request<{ id: string }>(`/api/investigations/${id}/notes`, { method: "POST", body: JSON.stringify({ note }) }),
  export: async (id: string, format: "json" | "csv" | "handoff") => {
    const response = await fetch(`/api/investigations/${id}/export?format=${format}`, {
      credentials: "include",
      headers: csrfHeader(),
    })
    if (!response.ok) throw new ApiError(response.status, "Export failed.")
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = format === "handoff" ? `piae-${id}.handoff.json` : `piae-${id}.${format}`
    link.click()
    URL.revokeObjectURL(url)
  },
  notifications: () => request<{ items: Array<{ id: string; action: string; target: string; created_at: string | null; unread: boolean }>; unread: boolean }>("/api/notifications"),
  readNotifications: () => request<{ ok: boolean }>("/api/notifications/read", { method: "POST" }),
  sources: () => request<{ demo_mode: boolean; items: SourceSetting[] }>("/api/sources"),
  updateSource: (name: string, enabled: boolean) =>
    request<SourceSetting>(`/api/sources/${name}`, { method: "PUT", body: JSON.stringify({ enabled }) }),
  health: () => request<Health>("/api/health"),
}

export async function waitForJob(investigationId: string, jobId: string) {
  for (let attempt = 0; attempt < 360; attempt += 1) {
    const job = await api.job(investigationId, jobId)
    if (job.status === "completed" || job.status === "failed") return job
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new ApiError(504, "The investigation is still running.")
}
