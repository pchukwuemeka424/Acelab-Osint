export type User = {
  id: string
  email: string
  display_name: string
  role: string
}

export type Investigation = {
  id: string
  root_indicator: string
  indicator_type: string
  title: string
  status: string
  is_saved: boolean
  is_demonstration: boolean
  entity_count: number
  relationship_count: number
  root_entity_id: string | null
  created_at: string | null
  updated_at: string | null
  existing?: boolean
  job_id?: string | null
}

export type EntityRecord = {
  id: string
  entity_type: string
  display_value: string
  normalized_value: string
  risk_state: string
  degree: number
  pos_x: number | null
  pos_y: number | null
  metadata: Record<string, unknown>
  first_observed: string | null
  last_observed: string | null
  source_name: string | null
  retrieved_at: string | null
  observed_at: string | null
  verification_status: string | null
  observation_id: string | null
  relationships?: RelationshipRecord[]
}

export type RelationshipRecord = {
  id: string
  source: string
  target: string
  source_label: string
  target_label: string
  rel_type: string
  reason: string
  provenance: string
  risk_state: string
  observation_ids: string[]
  observed_at: string | null
  retrieved_at: string | null
  is_conflicting: boolean
  is_stale: boolean
  weak_reason: string | null
}

export type GraphPayload = {
  nodes: EntityRecord[]
  edges: RelationshipRecord[]
  root_entity_id: string | null
  truncated: boolean
  campaign?: CampaignSummary
  suggestions?: ExpandSuggestion[]
}

export type CampaignMatch = {
  artifact_kind: string
  artifact_label: string
  saved_investigation_id: string
  saved_title: string
  saved_indicator: string
  entity_id: string | null
  observation_ids: string[]
}

export type TimelineEvent = {
  kind: string
  at: string
  label: string
  subject: string
  entity_id?: string | null
}

export type CampaignSummary = {
  active?: boolean
  matches: CampaignMatch[]
  case_count: number
  domain_count: number
  artifact_count: number
  withheld_common: number
  timeline: TimelineEvent[]
  note: string
}

export type ExpandSuggestion = {
  entity_id: string
  label: string
  rel_type: string
  reason: string
  weak: boolean
}

export type EntityPage = {
  items: EntityRecord[]
  total: number
  counts: Record<string, number>
  page: number
  page_size: number
}

export type Report = {
  summary: string
  root_indicator: string
  status: string
  is_demonstration: boolean
  counts: Record<string, number>
  associations: Array<{
    id: string
    source: string | null
    target: string | null
    heuristic_score: number
    score_kind: string
    label: string
    summary: string
    factors: Array<{ name: string; contribution: number; note: string }>
  }>
  timeline: Array<{ observation_id: string; observed_at: string | null; retrieved_at: string | null; source: string | null; value: string }>
  sources: Array<{ name: string; kind: string; reliability: number; is_demonstration: boolean; description: string }>
  limitations: string[]
  conflicts: Array<{ id: string; reason: string }>
  notes: Array<{ id: string; note: string; created_at: string | null }>
  narrative: string | null
  narrative_status: string
  analysis?: { campaign?: CampaignSummary }
}

export type SourceSetting = {
  name: string
  enabled: boolean
  description: string
  requires_key: boolean
  key_configured: boolean
}

export type Health = {
  status: string
  database: boolean
  redis: boolean
  neo4j_configured: boolean
  demo_mode: boolean
  openrouter_configured: boolean
  debug: boolean
}

export type GraphFilters = {
  types: string[]
  relTypes: string[]
  risk: string[]
  observedAfter: string
  observedBefore: string
}

export const DEFAULT_FILTERS: GraphFilters = {
  types: ["domain", "ip", "certificate", "nameserver", "url", "hosting", "indicator", "fingerprint", "account"],
  relTypes: [],
  risk: [],
  observedAfter: "",
  observedBefore: "",
}
