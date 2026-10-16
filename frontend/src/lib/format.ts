export function formatDate(value?: string | null): string {
  if (!value) return "—"
  const day = value.slice(0, 10)
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) return day.replaceAll("-", ".")
  return value
}

export function resultScreen(indicatorType: string): "name" | "website" {
  return indicatorType === "name" ? "name" : "website"
}

export function tabForType(entityType: string): string {
  if (["nameserver", "hosting", "indicator"].includes(entityType)) return "more"
  if (["name", "account"].includes(entityType)) return "contact"
  if (entityType === "hypothesis") return "hypothesis"
  return entityType
}

export function metaString(metadata: Record<string, unknown>, key: string): string {
  const value = metadata[key]
  return typeof value === "string" && value ? value : ""
}

export function accountVisible(entityType: string): boolean {
  return entityType === "account"
}

export const TABS = [
  { id: "domain", label: "Domains", color: "#334155" },
  { id: "whois", label: "Whois", color: "#334155" },
  { id: "ip", label: "IP", color: "#1d4ed8" },
  { id: "certificate", label: "SSL", color: "#0f766e" },
  { id: "ssh", label: "SSH", color: "#0f766e" },
  { id: "contact", label: "Contacts", color: "#64748b" },
  { id: "file", label: "Files", color: "#b45309" },
  { id: "hypothesis", label: "Attribution", color: "#be123c" },
  { id: "seo", label: "SEO", color: "#334155" },
  { id: "logo", label: "Logo", color: "#b45309" },
  { id: "url", label: "Pages", color: "#334155" },
  { id: "more", label: "More", color: "#b45309" },
] as const

export const SORTS = [
  { id: "domain", label: "Domain" },
  { id: "registrar", label: "Registrar" },
  { id: "reg_date", label: "Reg date" },
  { id: "exp_date", label: "Exp date" },
  { id: "ip", label: "IP" },
] as const

export const RISK_LABEL: Record<string, string> = {
  risk: "Risk-associated observation",
  contextual: "Contextual observation",
  uncertain: "Uncertain observation",
}
