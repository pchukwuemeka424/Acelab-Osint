import { describe, expect, it } from "vitest"
import type { EntityRecord, RelationshipRecord } from "../api/types"
import { connectionOrigins, siteSnapshot } from "./geo"

function node(id: string, type: string, value: string, country: string): EntityRecord {
  return {
    id,
    entity_type: type,
    display_value: value,
    normalized_value: value,
    risk_state: "contextual",
    degree: 1,
    pos_x: 0,
    pos_y: 0,
    metadata: { country },
    first_observed: null,
    last_observed: null,
    source_name: "ripe",
    retrieved_at: null,
    observed_at: null,
    verification_status: "observed",
    observation_id: null,
  }
}

describe("connection origins", () => {
  it("places a resolved address ahead of other networks and uses the country centroid", () => {
    const edge = {
      id: "e1",
      source: "domain",
      target: "ip",
      source_label: "example.com",
      target_label: "203.0.113.10",
      rel_type: "resolves_to",
      reason: "",
      provenance: "dns",
      risk_state: "contextual",
      observation_ids: [],
      observed_at: null,
      retrieved_at: null,
      is_conflicting: false,
      is_stale: false,
      weak_reason: null,
    } satisfies RelationshipRecord
    const points = connectionOrigins(
      [node("host", "hosting", "AS64496 Example", "DE"), node("ip", "ip", "203.0.113.10", "US")],
      [edge],
      "domain",
    )
    expect(points.map((point) => point.id)).toEqual(["ip", "host"])
    expect(points[0].countryName).toBe("United States")
    expect(points[0].lat).toBeCloseTo(39.8, 1)
  })

  it("reads the website address and city from the resolved network", () => {
    const domain = node("domain", "domain", "example.com", "")
    domain.metadata = { ip: "203.0.113.10" }
    const address = node("ip", "ip", "203.0.113.10", "US")
    address.metadata = { country: "US", city: "San Francisco" }
    const edge = {
      id: "e1",
      source: "domain",
      target: "ip",
      source_label: "example.com",
      target_label: "203.0.113.10",
      rel_type: "resolves_to",
      reason: "",
      provenance: "dns",
      risk_state: "contextual",
      observation_ids: [],
      observed_at: null,
      retrieved_at: null,
      is_conflicting: false,
      is_stale: false,
      weak_reason: null,
    } satisfies RelationshipRecord
    expect(siteSnapshot([domain, address], [edge], "domain")).toEqual({
      ip: "203.0.113.10",
      location: "San Francisco, United States",
      countryCode: "US",
    })
  })

  it("omits a placeholder country when the network has no published location", () => {
    const domain = node("domain", "domain", "example.com", "")
    domain.metadata = { ip: "104.20.23.154" }
    const address = node("ip", "ip", "104.20.23.154", "?")
    address.metadata = { country: "?", geoloc: "?" }
    expect(siteSnapshot([domain, address], [], "domain")).toEqual({
      ip: "104.20.23.154",
      location: "",
      countryCode: "",
    })
  })

  it("uses stored coordinates when the lookup included them", () => {
    const record = node("ip", "ip", "203.0.113.10", "US")
    record.metadata = { country: "US", latitude: 37.7, longitude: -122.4 }
    const [point] = connectionOrigins([record], [], null)
    expect(point.lat).toBe(37.7)
    expect(point.lon).toBe(-122.4)
  })
})