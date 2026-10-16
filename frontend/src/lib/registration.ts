import type { EntityRecord } from "../api/types"
import { metaString } from "./format"

export type RegistrationRow = {
  id: string
  website: string
  source: string
}

export function registrationLog(nodes: EntityRecord[]): RegistrationRow[] {
  const rows: RegistrationRow[] = []
  const seen = new Set<string>()
  const add = (row: RegistrationRow) => {
    const key = `${row.website.toLowerCase()}|${row.source}`
    if (!row.website || seen.has(key)) return
    seen.add(key)
    rows.push(row)
  }

  for (const node of nodes) {
    const meta = node.metadata || {}
    if (node.entity_type === "domain") {
      add({ id: node.id, website: node.display_value, source: "Website" })
    }
    if (node.entity_type === "whois") {
      add({ id: node.id, website: metaString(meta, "domain") || node.display_value, source: "Registration" })
    }
    if (node.entity_type === "url") {
      add({ id: node.id, website: node.display_value, source: "Page" })
    }
  }
  return rows
}
