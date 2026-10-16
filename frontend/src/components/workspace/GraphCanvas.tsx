import cytoscape from "cytoscape"
import fcose from "cytoscape-fcose"
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react"
import type { GraphPayload } from "../../api/types"
import { RISK_LABEL } from "../../lib/format"
import { ConnectionGlobe } from "./ConnectionGlobe"

cytoscape.use(fcose)

const COLORS: Record<string, string> = {
  risk: "#e11d48",
  contextual: "#0f766e",
  uncertain: "#d97706",
}

const LABEL = "#e7ebf2"
const HALO = "#000000"
const EXPORT_BG = "#000000"
const LABEL_PX = 10
const GLOBE_PX = 200

function labelFontSize(zoom: number): number {
  return LABEL_PX / Math.max(zoom, 0.12)
}

function applyLabelSize(cy: cytoscape.Core) {
  cy.style().selector("node").style("font-size", labelFontSize(cy.zoom())).update()
}

function sizeFor(degree: number): number {
  return Math.max(5, Math.min(16, 4.5 + Math.sqrt(Math.max(degree, 1)) * 1.35))
}

function nodeSize(node: cytoscape.NodeSingular, extra = 0): number {
  if (node.hasClass("hub")) return GLOBE_PX / Math.max(node.cy().zoom(), 0.12)
  return sizeFor(Number(node.data("degree") || 1)) + extra
}

function nodeCaption(value: string, type: string): string {
  const text = value.length > 36 ? `${value.slice(0, 35)}…` : value
  return `${text}\n${type}`
}

function ringPosition(index: number, count: number): { x: number; y: number } {
  const angle = (index / Math.max(count, 1)) * Math.PI * 2 - Math.PI / 2
  const radius = 260 + (index % 5) * 42
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }
}

function hubNodeId(graph: GraphPayload, rootId: string | null): string | null {
  if (rootId && graph.nodes.some((node) => node.id === rootId)) return rootId
  const domain = graph.nodes.find((node) => node.entity_type === "domain")
  return domain?.id || graph.nodes[0]?.id || null
}

function rayEdges(graph: GraphPayload, hubId: string | null): GraphPayload["edges"] {
  if (!hubId) return []
  const linked = new Set<string>()
  const rays = graph.edges.filter((edge) => {
    const touches = edge.source === hubId || edge.target === hubId
    if (!touches) return false
    linked.add(edge.source === hubId ? edge.target : edge.source)
    return true
  })
  graph.nodes.forEach((node) => {
    if (node.id === hubId || linked.has(node.id)) return
    rays.push({
      id: `ray-${node.id}`,
      source: hubId,
      target: node.id,
      source_label: "",
      target_label: node.display_value,
      rel_type: "connected",
      reason: "",
      provenance: "",
      risk_state: "contextual",
      observation_ids: [],
      observed_at: null,
      retrieved_at: null,
      is_conflicting: false,
      is_stale: false,
      weak_reason: null,
    })
  })
  return rays
}

export type GraphHandle = {
  focus: (id: string) => void
  fit: () => void
  zoom: (factor: number) => void
  resetLayout: () => void
  png: () => void
  svg: () => void
}

type Props = {
  graph: GraphPayload | undefined
  rootId: string | null
  selectedId: string | null
  pathIds: string[]
  onSelectNode: (id: string) => void
  onSelectEdge: (id: string) => void
  onExpand: (id: string) => void
  onPathPick: (id: string) => void
}

export const GraphCanvas = forwardRef<GraphHandle, Props>(function GraphCanvas(
  { graph, rootId, selectedId, pathIds, onSelectNode, onSelectEdge, onExpand, onPathPick },
  ref,
) {
  const container = useRef<HTMLDivElement>(null)
  const globeAnchor = useRef<HTMLDivElement>(null)
  const rootIdRef = useRef(rootId)
  rootIdRef.current = rootId
  const hubIdRef = useRef<string | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const handlers = useRef({ onSelectNode, onSelectEdge, onExpand, onPathPick })
  handlers.current = { onSelectNode, onSelectEdge, onExpand, onPathPick }

  useImperativeHandle(ref, () => ({
    focus: (id: string) => {
      const cy = cyRef.current
      if (!cy) return
      const node = cy.getElementById(id)
      if (!node.nonempty()) return
      node.style("display", "element")
      cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.1) }, { duration: 180 })
      node.select()
    },
    fit: () => cyRef.current?.fit(undefined, 28),
    zoom: (factor: number) => {
      const cy = cyRef.current
      if (!cy) return
      cy.zoom({ level: Math.min(3, Math.max(0.15, cy.zoom() * factor)), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })
    },
    resetLayout: () => {
      const cy = cyRef.current
      if (!cy || !graph) return
      const hubId = hubNodeId(graph, rootId)
      const others = graph.nodes.filter((node) => node.id !== hubId)
      cy.batch(() => {
        if (hubId) cy.getElementById(hubId).position({ x: 0, y: 0 })
        others.forEach((node, index) => cy.getElementById(node.id).position(ringPosition(index, others.length)))
      })
      cy.fit(undefined, 72)
      applyLabelSize(cy)
    },
    png: () => {
      const cy = cyRef.current
      if (!cy) return
      const uri = cy.png({ bg: EXPORT_BG, full: true, scale: 2 })
      const link = document.createElement("a")
      link.href = uri
      link.download = "piae-graph.png"
      link.click()
    },
    svg: () => {
      const cy = cyRef.current
      if (!cy) return
      const link = document.createElement("a")
      link.href = URL.createObjectURL(new Blob([graphSvg(cy)], { type: "image/svg+xml" }))
      link.download = "piae-graph.svg"
      link.click()
    },
  }))

  useEffect(() => {
    if (!container.current) return
    const cy = cytoscape({
      container: container.current,
      elements: [],
      wheelSensitivity: 0.18,
      minZoom: 0.12,
      maxZoom: 3,
      boxSelectionEnabled: false,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (node: cytoscape.NodeSingular) => COLORS[node.data("riskState")] || COLORS.contextual,
            width: (node: cytoscape.NodeSingular) => nodeSize(node),
            height: (node: cytoscape.NodeSingular) => nodeSize(node),
            label: "data(caption)",
            "font-size": LABEL_PX,
            color: LABEL,
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 4,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "min-zoomed-font-size": 1,
            "text-outline-width": 2,
            "text-outline-color": HALO,
            "border-width": 1.5,
            "border-color": "#ffffff",
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 2.5,
            "border-color": "#0f172a",
            width: (node: cytoscape.NodeSingular) => nodeSize(node, 4),
            height: (node: cytoscape.NodeSingular) => nodeSize(node, 4),
          },
        },
        {
          selector: "node.path",
          style: { "border-width": 2.5, "border-color": "#0f766e" },
        },
        {
          selector: "node.hub",
          style: {
            width: (node: cytoscape.NodeSingular) => nodeSize(node),
            height: (node: cytoscape.NodeSingular) => nodeSize(node),
            "background-opacity": 0,
            "border-width": 0,
            label: "",
            "text-opacity": 0,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "curve-style": "straight",
            "line-color": (edge: cytoscape.EdgeSingular) => COLORS[edge.data("riskState")] || "#94a3b8",
            "line-style": "dashed",
            "line-dash-pattern": [8, 6],
            "line-cap": "round",
            opacity: 0.9,
            "target-arrow-shape": "none",
          },
        },
        {
          selector: "edge:selected, edge.path",
          style: { width: 2, opacity: 1, "line-color": "#0f766e" },
        },
      ],
    })
    cy.on("tap", "node", (event) => {
      const id = event.target.id()
      if (event.originalEvent && "shiftKey" in event.originalEvent && (event.originalEvent as MouseEvent).shiftKey) {
        handlers.current.onPathPick(id)
      }
      handlers.current.onSelectNode(id)
    })
    cy.on("tap", "edge", (event) => handlers.current.onSelectEdge(event.target.id()))
    cy.on("dbltap", "node", (event) => handlers.current.onExpand(event.target.id()))
    cy.on("mouseover", "node", (event) => {
      const node = event.target
      const original = event.originalEvent as MouseEvent | undefined
      if (!original) return
      const risk = RISK_LABEL[node.data("riskState")] || node.data("riskState")
      setTip({ x: original.clientX + 12, y: original.clientY + 12, text: `${node.data("label")} · ${node.data("type")} · ${risk}` })
    })
    cy.on("mouseout", "node", () => setTip(null))
    cy.on("zoom", () => applyLabelSize(cy))
    let offset = 0
    let frame = 0
    const flow = () => {
      offset = (offset + 0.45) % 14
      cy.edges().style("line-dash-offset", -offset)
      frame = requestAnimationFrame(flow)
    }
    frame = requestAnimationFrame(flow)
    cyRef.current = cy
    return () => {
      cancelAnimationFrame(frame)
      cy.destroy()
      cyRef.current = null
    }
  }, [])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !graph) return
    const hubId = hubNodeId(graph, rootIdRef.current)
    hubIdRef.current = hubId
    const others = graph.nodes.filter((node) => node.id !== hubId)
    const elements: cytoscape.ElementDefinition[] = [
      ...graph.nodes.map((node) => {
        const index = others.findIndex((item) => item.id === node.id)
        const position = node.id === hubId ? { x: 0, y: 0 } : ringPosition(index, others.length)
        return {
          data: {
            id: node.id,
            label: node.display_value,
            caption: nodeCaption(node.display_value, node.entity_type),
            type: node.entity_type,
            riskState: node.risk_state,
            degree: node.degree,
          },
          classes: node.id === hubId ? "hub" : undefined,
          position,
        }
      }),
      ...rayEdges(graph, hubId).map((edge) => ({
        data: { id: edge.id, source: edge.source, target: edge.target, relType: edge.rel_type, riskState: edge.risk_state, reason: edge.reason },
      })),
    ]
    cy.batch(() => {
      cy.elements().remove()
      cy.add(elements)
    })
    cy.resize()
    cy.layout({ name: "preset", fit: true, padding: 72 } as cytoscape.LayoutOptions).run()
    applyLabelSize(cy)
    container.current?.setAttribute("data-graph-ready", String(graph.nodes.length))
  }, [graph, rootId])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().unselect()
    cy.elements().removeClass("path")
    if (selectedId) cy.getElementById(selectedId).select()
    pathIds.forEach((id) => cy.getElementById(id).addClass("path"))
  }, [selectedId, pathIds, graph])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    const sync = () => {
      const anchor = globeAnchor.current
      if (!anchor) return
      const id = hubIdRef.current || rootIdRef.current
      const node = id ? cy.getElementById(id) : cy.collection()
      cy.nodes().removeClass("hub")
      if (node.nonempty()) {
        node.addClass("hub")
        const model = GLOBE_PX / Math.max(cy.zoom(), 0.12)
        node.style({ width: model, height: model })
      }
      const placed = node.nonempty() ? node.renderedPosition() : null
      const point = placed || { x: cy.width() / 2, y: cy.height() / 2 }
      const box = container.current?.getBoundingClientRect()
      anchor.style.display = "block"
      anchor.style.position = "fixed"
      anchor.style.zIndex = "40"
      anchor.style.transform = "none"
      if (!box || !cy.width()) return
      anchor.style.left = `${box.left + point.x - GLOBE_PX / 2}px`
      anchor.style.top = `${box.top + point.y - GLOBE_PX / 2}px`
    }
    cy.on("pan zoom resize", sync)
    sync()
    return () => {
      cy.off("pan zoom resize", sync)
    }
  }, [graph, rootId])

  return (
    <>
      <div ref={container} className="absolute inset-0 z-0" />
      <div ref={globeAnchor} className="pointer-events-none fixed left-0 top-0 z-40 overflow-hidden rounded-full" style={{ width: GLOBE_PX, height: GLOBE_PX, background: "radial-gradient(circle at 35% 35%, #99f6e4, #0f766e 46%, #042f2e 72%)" }}>
        <ConnectionGlobe hub nodes={graph?.nodes || []} edges={graph?.edges || []} rootId={rootId} onFocus={onSelectNode} />
      </div>
      {tip && (
        <div className="pointer-events-none fixed z-50 max-w-xs rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-800 shadow-md" style={{ left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      )}
    </>
  )
})

function rimPoint(node: cytoscape.NodeSingular, toward: { x: number; y: number }): { x: number; y: number } {
  const from = node.position()
  const dx = toward.x - from.x
  const dy = toward.y - from.y
  const length = Math.hypot(dx, dy) || 1
  const radius = node.hasClass("hub") ? node.width() / 2 : sizeFor(Number(node.data("degree") || 1)) / 2
  return { x: from.x + (dx / length) * radius, y: from.y + (dy / length) * radius }
}

function graphSvg(cy: cytoscape.Core): string {
  const nodes = cy.nodes().map((node) => {
    const position = node.position()
    const color = COLORS[node.data("riskState")] || "#37B99A"
    const radius = sizeFor(Number(node.data("degree") || 1)) / 2
    const caption = String(node.data("caption") || "")
      .split("\n")
      .map((line, index) => {
        const escaped = line.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
        return `<tspan x="${position.x}" dy="${index === 0 ? radius + 11 : 10}">${escaped}</tspan>`
      })
      .join("")
    const fontSize = labelFontSize(cy.zoom())
    return `<circle cx="${position.x}" cy="${position.y}" r="${radius}" fill="${color}" stroke="#ffffff" stroke-width="1.5" /><text x="${position.x}" y="${position.y}" text-anchor="middle" fill="#e7ebf2" font-size="${fontSize}" font-family="sans-serif">${caption}</text>`
  })
  const edges = cy.edges().map((edge) => {
    const sourceNode = edge.source()
    const targetNode = edge.target()
    const source = rimPoint(sourceNode, targetNode.position())
    const target = rimPoint(targetNode, sourceNode.position())
    const color = COLORS[edge.data("riskState")] || "#94a3b8"
    return `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" stroke="${color}" stroke-width="1.4" stroke-linecap="round" />`
  })
  const box = cy.elements().boundingBox()
  const pad = 20
  return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="${box.x1 - pad} ${box.y1 - pad} ${box.w + pad * 2} ${box.h + pad * 2}"><rect width="100%" height="100%" fill="${EXPORT_BG}"/>${edges.join("")}${nodes.join("")}</svg>`
}
