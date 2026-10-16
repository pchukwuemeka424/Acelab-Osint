import { useEffect, useRef } from "react"
import type { EntityRecord, RelationshipRecord } from "../../api/types"
import { connectionOrigins, type ConnectionPoint } from "../../lib/geo"

type Props = {
  nodes: EntityRecord[]
  edges: RelationshipRecord[]
  rootId: string | null
  onFocus: (id: string) => void
  hub?: boolean
}

const LAND: Array<[number, number][]> = [
  [[72, -165], [70, -140], [68, -90], [60, -65], [47, -53], [30, -81], [25, -80], [18, -88], [15, -92], [22, -106], [32, -117], [48, -125], [60, -140], [71, -156]],
  [[12, -72], [8, -60], [5, -51], [-5, -35], [-15, -39], [-23, -43], [-35, -58], [-55, -68], [-52, -72], [-40, -73], [-18, -70], [-5, -80], [8, -77]],
  [[36, -10], [43, -8], [48, -5], [51, 2], [54, 8], [58, 12], [60, 25], [55, 28], [48, 23], [42, 28], [36, 28], [36, 10], [38, -1]],
  [[32, -6], [30, 10], [32, 25], [22, 37], [12, 43], [0, 42], [-15, 40], [-26, 32], [-34, 25], [-34, 18], [-20, 14], [-5, 8], [5, -5], [15, -17], [28, -13]],
  [[40, 28], [42, 45], [45, 50], [50, 60], [55, 80], [60, 100], [65, 130], [70, 160], [66, 170], [60, 163], [50, 142], [38, 140], [32, 130], [22, 114], [10, 106], [1, 104], [8, 98], [22, 88], [25, 68], [22, 60], [12, 44], [15, 42], [28, 34], [32, 35]],
  [[-12, 130], [-18, 122], [-32, 116], [-35, 137], [-28, 153], [-16, 146], [-12, 142]],
]

function inside(lat: number, lon: number, ring: Array<[number, number]>): boolean {
  let hit = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [yi, xi] = ring[i]
    const [yj, xj] = ring[j]
    const crosses = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi || 1e-9) + xi
    if (crosses) hit = !hit
  }
  return hit
}

function land(lat: number, lon: number): boolean {
  return LAND.some((ring) => inside(lat, lon, ring))
}

function vector(lat: number, lon: number, turn: number): [number, number, number] {
  const phi = (lat * Math.PI) / 180
  const lambda = ((lon + turn) * Math.PI) / 180
  return [Math.cos(phi) * Math.sin(lambda), Math.sin(phi), Math.cos(phi) * Math.cos(lambda)]
}

function slerp(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  const dot = Math.min(1, Math.max(-1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
  const omega = Math.acos(dot)
  if (omega < 0.001) return a
  const scaleA = Math.sin((1 - t) * omega) / Math.sin(omega)
  const scaleB = Math.sin(t * omega) / Math.sin(omega)
  return [a[0] * scaleA + b[0] * scaleB, a[1] * scaleA + b[1] * scaleB, a[2] * scaleA + b[2] * scaleB]
}

export function ConnectionGlobe({ nodes, edges, rootId, onFocus, hub = false }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const hovering = useRef(false)
  const points = connectionOrigins(nodes, edges, rootId)
  const pointsRef = useRef<ConnectionPoint[]>(points)
  pointsRef.current = points
  const hubRef = useRef(hub)
  hubRef.current = hub

  useEffect(() => {
    let frame = 0
    let turn = 20
    const draw = () => {
      const surface = canvas.current
      const context = surface?.getContext("2d")
      if (!surface || !context) {
        frame = requestAnimationFrame(draw)
        return
      }
      if (!hovering.current) turn = (turn + 0.9) % 360
      const ratio = window.devicePixelRatio || 1
      const width = surface.clientWidth
      const height = surface.clientHeight
      const pixelWidth = Math.floor(width * ratio)
      const pixelHeight = Math.floor(height * ratio)
      if (surface.width !== pixelWidth || surface.height !== pixelHeight) {
        surface.width = pixelWidth
        surface.height = pixelHeight
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.clearRect(0, 0, width, height)
      const cx = width / 2
      const cy = height / 2 + (hubRef.current ? 0 : 4)
      const radius = hubRef.current ? Math.min(width, height) / 2 - 1 : Math.min(width, height) * 0.38
      const shade = context.createRadialGradient(cx - radius * 0.35, cy - radius * 0.35, radius * 0.2, cx, cy, radius)
      shade.addColorStop(0, "#5eead4")
      shade.addColorStop(0.42, "#0f766e")
      shade.addColorStop(1, "#042f2e")
      context.beginPath()
      context.arc(cx, cy, radius, 0, Math.PI * 2)
      context.fillStyle = shade
      context.fill()
      context.save()
      context.beginPath()
      context.arc(cx, cy, radius, 0, Math.PI * 2)
      context.clip()
      context.strokeStyle = "rgba(45, 212, 191, 0.18)"
      context.lineWidth = 1
      for (let lat = -60; lat <= 60; lat += 30) {
        context.beginPath()
        let started = false
        for (let lon = -180; lon <= 180; lon += 6) {
          const [x, y, z] = vector(lat, lon, turn)
          if (z < 0.02) {
            started = false
            continue
          }
          const px = cx + x * radius
          const py = cy - y * radius
          if (!started) context.moveTo(px, py)
          else context.lineTo(px, py)
          started = true
        }
        context.stroke()
      }
      for (let lon = -180; lon < 180; lon += 30) {
        context.beginPath()
        let started = false
        for (let lat = -80; lat <= 80; lat += 6) {
          const [x, y, z] = vector(lat, lon, turn)
          if (z < 0.02) {
            started = false
            continue
          }
          const px = cx + x * radius
          const py = cy - y * radius
          if (!started) context.moveTo(px, py)
          else context.lineTo(px, py)
          started = true
        }
        context.stroke()
      }
      for (let lat = -70; lat <= 70; lat += 5) {
        for (let lon = -180; lon < 180; lon += 5) {
          if (!land(lat, lon)) continue
          const [x, y, z] = vector(lat, lon, turn)
          if (z < 0.05) continue
          context.fillStyle = `rgba(236, 253, 245, ${0.5 + z * 0.45})`
          context.fillRect(cx + x * radius, cy - y * radius, 2.2, 2.2)
        }
      }
      const origins = pointsRef.current
      const primary = origins[0]
      if (primary && origins.length > 1) {
        const site = vector(primary.lat, primary.lon, turn)
        origins.slice(1, 6).forEach((origin, index) => {
          const from = vector(origin.lat, origin.lon, turn)
          const to = site
          context.beginPath()
          let started = false
          for (let step = 0; step <= 28; step += 1) {
            const [x, y, z] = slerp(from, to, step / 28)
            const lifted: [number, number, number] = [x * 1.08, y * 1.08, z * 1.08]
            if (lifted[2] < 0) {
              started = false
              continue
            }
            const px = cx + lifted[0] * radius
            const py = cy - lifted[1] * radius
            if (!started) context.moveTo(px, py)
            else context.lineTo(px, py)
            started = true
          }
          context.strokeStyle = "rgba(45, 212, 191, 0.55)"
          context.stroke()
          const travel = ((turn / 40) + index * 0.18) % 1
          const [px, py, pz] = slerp(from, to, travel)
          if (pz > 0) {
            context.fillStyle = "#f8fafc"
            context.beginPath()
            context.arc(cx + px * 1.08 * radius, cy - py * 1.08 * radius, 2.2, 0, Math.PI * 2)
            context.fill()
          }
        })
      }
      origins.slice(0, 6).forEach((origin, index) => {
        const [x, y, z] = vector(origin.lat, origin.lon, turn)
        if (z < 0.05) return
        const px = cx + x * radius
        const py = cy - y * radius
        const pulse = 4 + Math.sin(turn / 12 + index) * 1.5
        context.strokeStyle = "rgba(248, 250, 252, 0.7)"
        context.beginPath()
        context.arc(px, py, pulse, 0, Math.PI * 2)
        context.stroke()
        context.fillStyle = index === 0 ? "#f8fafc" : "#2dd4bf"
        context.beginPath()
        context.arc(px, py, 2.4, 0, Math.PI * 2)
        context.fill()
      })
      context.restore()
      context.strokeStyle = "#ccfbf1"
      context.lineWidth = 2
      context.beginPath()
      context.arc(cx, cy, radius, 0, Math.PI * 2)
      context.stroke()
      frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [])

  if (hub) {
    return (
      <div className="h-full w-full" aria-label="Connection origins">
        <canvas ref={canvas} className="h-full w-full" />
      </div>
    )
  }

  return (
    <section
      className="pointer-events-auto absolute left-4 top-4 z-20 w-[250px] rounded-xl border border-white/10 bg-black/75 p-3 text-white shadow-lg backdrop-blur"
      aria-label="Connection origins"
      onMouseEnter={() => {
        hovering.current = true
      }}
      onMouseLeave={() => {
        hovering.current = false
      }}
    >
      <div className="flex items-baseline justify-between">
        <h2 className="text-[12px] font-semibold">Connection origins</h2>
        <span className="text-[10px] text-slate-400">{points.length}</span>
      </div>
      <canvas ref={canvas} className="mt-1 h-[168px] w-full" />
      {points.length === 0 ? (
        <p className="text-[10px] text-slate-400">No located addresses in this investigation.</p>
      ) : (
        <ul className="max-h-24 space-y-1 overflow-y-auto">
          {points.slice(0, 6).map((point) => (
            <li key={point.id}>
              <button type="button" className="block w-full truncate text-left text-[10px] text-slate-200 hover:text-white" onClick={() => onFocus(point.id)}>
                <span className="text-teal-300">{point.countryName}</span>
                <span className="text-slate-500"> · </span>
                {point.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
