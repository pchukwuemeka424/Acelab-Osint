import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { api, ApiError, waitForJob } from "../api/client"
import { DEFAULT_FILTERS, type ExpandSuggestion, type GraphFilters, type RelationshipRecord } from "../api/types"
import { AceLogo, AceWordmark } from "../components/workspace/AceLogo"
import { DetailsPanel } from "../components/workspace/DetailsPanel"
import { CampaignPanel } from "../components/workspace/CampaignPanel"
import { EmailScreen } from "../components/workspace/EmailScreen"
import { GraphCanvas, type GraphHandle } from "../components/workspace/GraphCanvas"
import { GraphControls } from "../components/workspace/GraphControls"
import { GraphSearch } from "../components/workspace/GraphSearch"
import { HomeSearch } from "../components/workspace/HomeSearch"
import { NotificationBell } from "../components/workspace/NotificationBell"
import { RegistrationLog } from "../components/workspace/RegistrationLog"
import { UserMenu } from "../components/workspace/UserMenu"
import { accountVisible, metaString, resultScreen, tabForType } from "../lib/format"
import { flagEmoji, siteSnapshot } from "../lib/geo"
import { registrationLog } from "../lib/registration"

export function WorkspacePage() {
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const requested = params.get("investigation")
  const [activeId, setActiveId] = useState("")
  const id = requested || activeId
  const investigation = useQuery({ queryKey: ["investigation", id], queryFn: () => api.getInvestigation(id), enabled: Boolean(id) })
  const [tab, setTab] = useState("domain")
  const [sort, setSort] = useState("domain")
  const [recordQuery, setRecordQuery] = useState("")
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= 1024)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [edge, setEdge] = useState<RelationshipRecord | null>(null)
  const [pathIds, setPathIds] = useState<string[]>([])
  const [pathPick, setPathPick] = useState<string[]>([])
  const [filters, setFilters] = useState<GraphFilters>(DEFAULT_FILTERS)
  const [searchError, setSearchError] = useState("")
  const [suggestions, setSuggestions] = useState<ExpandSuggestion[]>([])
  const [narrow, setNarrow] = useState(false)
  const graphRef = useRef<GraphHandle>(null)

  useEffect(() => {
    const media = window.matchMedia("(max-width: 1023px)")
    const apply = () => setNarrow(media.matches)
    apply()
    media.addEventListener("change", apply)
    return () => media.removeEventListener("change", apply)
  }, [])

  useEffect(() => {
    if (narrow) setPanelOpen(false)
  }, [narrow])

  const kind = investigation.data?.indicator_type || ""
  const screen = !id ? "home" : investigation.data ? resultScreen(kind) : "loading"
  const graph = useQuery({ queryKey: ["graph", id, filters], queryFn: () => api.graph(id, filters), enabled: screen === "website" })
  const entities = useQuery({
    queryKey: ["entities", id, tab, sort, recordQuery],
    queryFn: () => api.entities(id, tab, sort, "asc", recordQuery),
    enabled: screen === "website",
  })
  const nameContacts = useQuery({
    queryKey: ["entities", id, "contact", "name-screen"],
    queryFn: () => api.entities(id, "contact", "domain", "asc", ""),
    enabled: screen === "name",
  })
  const investigate = useMutation({
    mutationFn: async (indicator: string) => {
      const created = await api.createInvestigation(indicator)
      if (created.job_id) {
        const job = await waitForJob(created.id, created.job_id)
        if (job.status === "failed") throw new ApiError(500, job.error || "The investigation could not be completed.")
      }
      return created
    },
    onSuccess: (created) => {
      setSearchError("")
      setActiveId(created.id)
      if (created.indicator_type === "name") setTab("contact")
      setSelectedId(null)
      setEdge(null)
      setPathIds([])
      setPathPick([])
      setSuggestions([])
      setParams({}, { replace: true })
      queryClient.invalidateQueries({ queryKey: ["investigation", created.id] })
      queryClient.invalidateQueries({ queryKey: ["graph", created.id] })
      queryClient.invalidateQueries({ queryKey: ["entities", created.id] })
    },
    onError: (error: Error) => setSearchError(error.message),
  })

  useEffect(() => {
    if (!selectedId && investigation.data?.root_entity_id) setSelectedId(investigation.data.root_entity_id)
  }, [investigation.data?.root_entity_id, selectedId])

  useEffect(() => {
    const kind = investigation.data?.indicator_type
    if (!investigation.data?.id || !kind) return
    setTab(kind === "name" ? "contact" : "domain")
  }, [investigation.data?.id, investigation.data?.indicator_type])

  async function focusNode(nodeId: string) {
    setSelectedId(nodeId)
    const node = graph.data?.nodes.find((item) => item.id === nodeId) || entities.data?.items.find((item) => item.id === nodeId)
    if (node) setTab(tabForType(node.entity_type))
    graphRef.current?.focus(nodeId)
  }

  async function pickPath(nodeId: string) {
    const next = [...pathPick, nodeId].slice(-2)
    setPathPick(next)
    if (next.length === 2 && id) {
      const result = await api.path(id, next[0], next[1])
      setPathIds([...result.node_ids, ...result.edge_ids])
    }
  }

  async function expand(nodeId: string) {
    if (!id) return
    const extra = await api.expand(id, nodeId)
    queryClient.setQueryData(["graph", id, filters], (currentGraph: typeof graph.data) => {
      if (!currentGraph) return extra
      const nodes = new Map(currentGraph.nodes.map((node) => [node.id, node]))
      extra.nodes.forEach((node) => nodes.set(node.id, node))
      const edges = new Map(currentGraph.edges.map((item) => [item.id, item]))
      extra.edges.forEach((item) => edges.set(item.id, item))
      return { ...currentGraph, nodes: [...nodes.values()], edges: [...edges.values()] }
    })
    setSuggestions(extra.suggestions || [])
    graphRef.current?.focus(nodeId)
  }

  function selectEdge(edgeId: string) {
    setEdge(graph.data?.edges.find((item) => item.id === edgeId) || null)
  }

  const root = investigation.data?.root_indicator || ""
  const site = siteSnapshot(graph.data?.nodes || [], graph.data?.edges || [], graph.data?.root_entity_id || investigation.data?.root_entity_id || null)
  const registrations = registrationLog(graph.data?.nodes || [])
  const panelClass = narrow
    ? "absolute inset-y-0 right-0 z-40 flex w-[min(100%,420px)] flex-col border-l border-slate-200 bg-white shadow-xl"
    : "flex h-full w-[39%] min-w-[390px] max-w-[640px] flex-col border-l border-slate-200 bg-white"

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-black text-slate-900">
      <header className="z-30 flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-3 sm:px-4">
        <button
          type="button"
          className="flex shrink-0 items-center gap-2.5 text-left"
          aria-label="Home"
          onClick={() => {
            setActiveId("")
            setSelectedId(null)
            setEdge(null)
            setPathIds([])
            setPathPick([])
            setSuggestions([])
            setSearchError("")
            setParams({}, { replace: true })
          }}
        >
          <AceLogo size={28} />
          <div className="leading-tight">
            <AceWordmark className="text-[13px]" />
            {screen !== "home" && <div className="text-[10px] text-slate-500">Investigation</div>}
          </div>
        </button>
        {screen !== "home" && (
          <GraphSearch value="" busy={investigate.isPending} error={searchError} onSubmit={(value) => investigate.mutate(value)} />
        )}
        <div className="ml-auto flex shrink-0 items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 p-1 pl-1.5">
          <NotificationBell />
          <span className="h-5 w-px bg-slate-200" aria-hidden />
          <UserMenu
            investigation={investigation.data || null}
            onSaved={() => {
              queryClient.invalidateQueries({ queryKey: ["investigation", id] })
            }}
          />
        </div>
      </header>
      {screen === "home" && (
        <HomeSearch busy={investigate.isPending} error={searchError} onSubmit={(value) => investigate.mutate(value)} />
      )}
      {screen === "loading" && <div className="min-h-0 flex-1 bg-black" />}
      {screen === "name" && (
        <EmailScreen
          address={investigation.data?.root_indicator || ""}
          loading={nameContacts.isLoading}
          notice={scannerNotice(nameContacts.data?.items || [])}
          hits={(nameContacts.data?.items || []).filter((item) => accountVisible(item.entity_type))}
        />
      )}
      {screen === "website" && (
      <div className="relative flex min-h-0 flex-1 overflow-hidden">
      <div className="graph-surface relative min-w-0 flex-1">
        <GraphCanvas
          ref={graphRef}
          graph={graph.data}
          rootId={graph.data?.root_entity_id || investigation.data?.root_entity_id || null}
          selectedId={selectedId}
          pathIds={pathIds}
          onSelectNode={(nodeId) => {
            setEdge(null)
            void focusNode(nodeId)
          }}
          onSelectEdge={selectEdge}
          onExpand={(nodeId) => void expand(nodeId)}
          onPathPick={(nodeId) => void pickPath(nodeId)}
        />
        <div className="pointer-events-none absolute left-4 top-4 z-20 flex w-[min(340px,calc(100%-2rem))] flex-col gap-2">
          <div className="pointer-events-auto rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <div className="truncate text-[12px] font-medium text-slate-900">{root || "No investigation"}</div>
            {investigation.data && (
              <>
                <p className="mt-1 flex items-center gap-1 text-[11px] text-slate-800">
                  <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">Location</span>
                  {site.countryCode ? (
                    <span className="text-[14px] leading-none" aria-hidden>
                      {flagEmoji(site.countryCode)}
                    </span>
                  ) : null}
                  <span>{site.location || "—"}</span>
                </p>
                <p className="text-[11px] text-slate-800">
                  <span className="mr-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">IP</span>
                  {site.ip || "—"}
                </p>
                <p className="mt-1 text-[10px] text-slate-500">
                  {investigation.data.is_demonstration ? "Live collection off" : "Collected observations"}
                </p>
              </>
            )}
          </div>
          {graph.isError && <p className="rounded-md border border-rose-200 bg-white px-2 py-1 text-[12px] text-rose-700">The graph could not be loaded.</p>}
          {graph.data?.campaign?.active && (
            <CampaignPanel
              campaign={graph.data.campaign}
              suggestions={suggestions}
              saved={Boolean(investigation.data?.is_saved)}
              onFocus={(nodeId) => void focusNode(nodeId)}
            />
          )}
        </div>
        <GraphControls
          filters={filters}
          onChange={setFilters}
          onFit={() => graphRef.current?.fit()}
          onZoom={(factor) => graphRef.current?.zoom(factor)}
          onReset={() => graphRef.current?.resetLayout()}
          onPng={() => graphRef.current?.png()}
          onSvg={() => graphRef.current?.svg()}
        />
      </div>
      {panelOpen && (
        <div className={narrow ? "contents" : "relative flex h-full w-[39%] min-w-[390px] max-w-[640px]"}>
        <button
          type="button"
          aria-label="Collapse details"
          className={`${narrow ? "hidden" : "absolute left-0 top-1/2 z-50 flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 shadow-sm"}`}
          onClick={() => setPanelOpen(false)}
        >
          <ChevronRight size={16} />
        </button>
        <aside className={narrow ? panelClass : "flex h-full w-full flex-col border-l border-slate-200 bg-white"}>
          <DetailsPanel
            investigationId={id}
            counts={entities.data?.counts || {}}
            tab={tab}
            sort={sort}
            items={entities.data?.items || []}
            selectedId={selectedId}
            edge={edge}
            status={entities.isLoading ? "loading" : entities.isError ? "error" : "ready"}
            error={entities.error instanceof Error ? entities.error.message : ""}
            onTab={setTab}
            onSort={(next) => {
              setSort(next)
            }}
            onSearch={setRecordQuery}
            onExport={() => id && void api.export(id, "csv")}
            onClose={() => setPanelOpen(false)}
            onFocus={(nodeId) => void focusNode(nodeId)}
            registrations={registrations}
          />
        </aside>
        </div>
      )}
      {!panelOpen && (
        <div className="pointer-events-auto absolute bottom-4 left-4 z-20 w-[min(340px,calc(100%-5rem))]">
          <RegistrationLog rows={registrations} onFocus={(nodeId) => void focusNode(nodeId)} />
        </div>
      )}
      {!panelOpen && (
        <button
          type="button"
          aria-label="Open details"
          className="absolute right-3 top-1/2 z-50 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 shadow-sm"
          onClick={() => setPanelOpen(true)}
        >
          <ChevronLeft size={16} />
        </button>
      )}
      </div>
      )}
    </div>
  )
}

function scannerNotice(items: { entity_type: string; metadata: Record<string, unknown> }[]): string {
  const root = items.find((item) => item.entity_type === "name")
  return metaString(root?.metadata || {}, "scanner_notice")
}
