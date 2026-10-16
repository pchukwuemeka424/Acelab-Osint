import { describe, expect, it } from "vitest"
import type { EntityRecord } from "../api/types"
import { registrationLog } from "./registration"

function node(id: string, type: string, value: string, metadata: Record<string, unknown> = {}): EntityRecord {
  return {
    id,
    entity_type: type,
    display_value: value,
    normalized_value: value,
    risk_state: "contextual",
    degree: 1,
    pos_x: 0,
    pos_y: 0,
    metadata,
    first_observed: null,
    last_observed: null,
    source_name: "test",
    retrieved_at: null,
    observed_at: null,
    verification_status: "observed",
    observation_id: null,
  }
}

describe("registration log", () => {
  it("lists websites without email or username records", () => {
    const rows = registrationLog([
      node("domain-1", "domain", "portal.example.test", { email: "ops@example.test" }),
      node("whois-1", "whois", "Whois", { domain: "portal.example.test", registrant_email: "ops@example.test" }),
      node("mail-1", "email", "abuse@example.test", { domain: "portal.example.test" }),
      node("user-1", "username", "kit_author"),
      node("page-1", "url", "https://portal.example.test/about"),
      node("ip-1", "ip", "198.51.100.8"),
    ])
    expect(rows).toEqual([
      { id: "domain-1", website: "portal.example.test", source: "Website" },
      { id: "whois-1", website: "portal.example.test", source: "Registration" },
      { id: "page-1", website: "https://portal.example.test/about", source: "Page" },
    ])
  })
})
