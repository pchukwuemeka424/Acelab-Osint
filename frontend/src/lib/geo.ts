import type { EntityRecord, RelationshipRecord } from "../api/types"

type Centroid = [number, number, string]

const COUNTRY: Record<string, Centroid> = {
  US: [39.8, -98.5, "United States"],
  CA: [56.1, -106.3, "Canada"],
  MX: [23.6, -102.5, "Mexico"],
  BR: [-14.2, -51.9, "Brazil"],
  AR: [-38.4, -63.6, "Argentina"],
  CL: [-35.7, -71.5, "Chile"],
  CO: [4.6, -74.3, "Colombia"],
  PE: [-9.2, -75.0, "Peru"],
  GB: [54.0, -2.0, "United Kingdom"],
  IE: [53.1, -8.0, "Ireland"],
  FR: [46.2, 2.2, "France"],
  DE: [51.2, 10.4, "Germany"],
  NL: [52.1, 5.3, "Netherlands"],
  BE: [50.5, 4.5, "Belgium"],
  LU: [49.8, 6.1, "Luxembourg"],
  CH: [46.8, 8.2, "Switzerland"],
  AT: [47.5, 14.6, "Austria"],
  IT: [41.9, 12.6, "Italy"],
  ES: [40.5, -3.7, "Spain"],
  PT: [39.4, -8.2, "Portugal"],
  SE: [60.1, 18.6, "Sweden"],
  NO: [60.5, 8.5, "Norway"],
  FI: [61.9, 25.7, "Finland"],
  DK: [56.3, 9.5, "Denmark"],
  PL: [51.9, 19.1, "Poland"],
  CZ: [49.8, 15.5, "Czechia"],
  RO: [45.9, 24.9, "Romania"],
  HU: [47.2, 19.5, "Hungary"],
  BG: [42.7, 25.5, "Bulgaria"],
  GR: [39.1, 21.8, "Greece"],
  UA: [48.4, 31.2, "Ukraine"],
  LT: [55.2, 23.9, "Lithuania"],
  LV: [56.9, 24.1, "Latvia"],
  EE: [58.6, 25.0, "Estonia"],
  RU: [61.5, 105.3, "Russia"],
  TR: [38.9, 35.2, "Turkey"],
  IL: [31.0, 34.9, "Israel"],
  AE: [23.4, 53.8, "United Arab Emirates"],
  SA: [23.9, 45.1, "Saudi Arabia"],
  IN: [20.6, 79.0, "India"],
  PK: [30.4, 69.3, "Pakistan"],
  CN: [35.9, 104.2, "China"],
  HK: [22.4, 114.1, "Hong Kong"],
  JP: [36.2, 138.3, "Japan"],
  KR: [35.9, 127.8, "South Korea"],
  SG: [1.4, 103.8, "Singapore"],
  MY: [4.2, 101.9, "Malaysia"],
  ID: [-0.8, 113.9, "Indonesia"],
  TH: [15.9, 100.9, "Thailand"],
  VN: [14.1, 108.3, "Vietnam"],
  PH: [12.9, 121.8, "Philippines"],
  AU: [-25.3, 133.8, "Australia"],
  NZ: [-40.9, 174.9, "New Zealand"],
  ZA: [-30.6, 22.9, "South Africa"],
  EG: [26.8, 30.8, "Egypt"],
  NG: [9.1, 8.7, "Nigeria"],
  KE: [-0.02, 37.9, "Kenya"],
  MA: [31.8, -7.1, "Morocco"],
}

export type ConnectionPoint = {
  id: string
  label: string
  kind: string
  country: string
  countryName: string
  lat: number
  lon: number
}

export type SiteSnapshot = {
  ip: string
  location: string
  countryCode: string
}

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function lookup(country: string): Centroid | null {
  const code = country.trim().toUpperCase()
  if (COUNTRY[code]) return COUNTRY[code]
  const named = Object.values(COUNTRY).find((item) => item[2].toUpperCase() === code)
  return named || null
}

function text(meta: Record<string, unknown>, key: string): string {
  const value = meta[key]
  return typeof value === "string" ? value.trim() : ""
}

function countryInfo(raw: string): { code: string; name: string } | null {
  const cleaned = raw.trim()
  if (!cleaned || cleaned === "?") return null
  const code = cleaned.toUpperCase()
  if (COUNTRY[code]) return { code, name: COUNTRY[code][2] }
  const named = Object.entries(COUNTRY).find(([, item]) => item[2].toUpperCase() === code)
  if (named) return { code: named[0], name: named[1][2] }
  if (/^[A-Z]{2}$/.test(code)) return { code, name: code }
  return null
}

export function flagEmoji(code: string): string {
  if (!/^[A-Z]{2}$/.test(code)) return ""
  return String.fromCodePoint(...[...code].map((char) => 127397 + char.charCodeAt(0)))
}

function hasPlace(node: EntityRecord): boolean {
  const meta = node.metadata || {}
  return Boolean(text(meta, "city") || text(meta, "country") || text(meta, "geoloc"))
}

export function siteSnapshot(nodes: EntityRecord[], edges: RelationshipRecord[], rootId: string | null): SiteSnapshot {
  const root = (rootId && nodes.find((node) => node.id === rootId)) || nodes.find((node) => node.entity_type === "domain") || null
  const linked = new Set<string>()
  if (root) {
    edges.forEach((edge) => {
      if (edge.rel_type !== "resolves_to") return
      if (edge.source === root.id) linked.add(edge.target)
      if (edge.target === root.id) linked.add(edge.source)
    })
  }
  const addresses = nodes.filter((node) => node.entity_type === "ip")
  const recorded = text(root?.metadata || {}, "ip")
  const address =
    addresses.find((node) => recorded && (node.display_value === recorded || node.normalized_value === recorded)) ||
      addresses.find((node) => linked.has(node.id) && hasPlace(node)) ||
      addresses.find((node) => linked.has(node.id)) ||
      addresses.find(hasPlace) ||
      addresses[0] ||
      null
  const place = address?.metadata || {}
  const city = text(place, "city")
  const country = countryInfo(text(place, "country") || text(place, "geoloc"))
  return {
    ip: recorded || address?.display_value || "",
    location: [city, country?.name || ""].filter(Boolean).join(", "),
    countryCode: country?.code || "",
  }
}

export function connectionOrigins(nodes: EntityRecord[], edges: RelationshipRecord[], rootId: string | null): ConnectionPoint[] {
  const preferred = new Set<string>()
  if (rootId) {
    edges.forEach((edge) => {
      if (edge.rel_type !== "resolves_to") return
      if (edge.source === rootId) preferred.add(edge.target)
      if (edge.target === rootId) preferred.add(edge.source)
    })
  }
  const ranked = [...nodes].sort((left, right) => Number(preferred.has(right.id)) - Number(preferred.has(left.id)))
  const points: ConnectionPoint[] = []
  const seen = new Set<string>()
  ranked.forEach((node) => {
    if (node.entity_type !== "ip" && node.entity_type !== "hosting") return
    const meta = node.metadata || {}
    const country = typeof meta.country === "string" ? meta.country : typeof meta.geoloc === "string" ? meta.geoloc : ""
    const storedLat = numeric(meta.latitude)
    const storedLon = numeric(meta.longitude)
    const centroid = lookup(country)
    const lat = storedLat ?? centroid?.[0]
    const lon = storedLon ?? centroid?.[1]
    if (lat == null || lon == null) return
    const key = `${node.entity_type}:${lat.toFixed(2)}:${lon.toFixed(2)}:${node.display_value}`
    if (seen.has(key)) return
    seen.add(key)
    points.push({
      id: node.id,
      label: node.display_value,
      kind: node.entity_type,
      country: country.toUpperCase(),
      countryName: centroid?.[2] || country || "Unknown",
      lat,
      lon,
    })
  })
  return points
}
