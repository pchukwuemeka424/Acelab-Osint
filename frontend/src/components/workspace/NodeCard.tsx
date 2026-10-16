import { useState } from "react"
import type { EntityRecord } from "../../api/types"
import { formatDate, metaString } from "../../lib/format"

type Props = {
  entity: EntityRecord
  investigationId: string
  selected: boolean
  onFocus: (id: string) => void
}

function published(meta: Record<string, unknown>, key: string): string {
  const value = metaString(meta, key)
  if (value) return value
  return meta.registration_found === true ? "Not published" : "—"
}

function publishedDate(meta: Record<string, unknown>, key: string): string {
  const value = metaString(meta, key)
  if (value) return formatDate(value)
  return meta.registration_found === true ? "Not published" : "—"
}

export function NodeCard({ entity, investigationId, selected, onFocus }: Props) {
  const meta = entity.metadata || {}
  const registered = metaString(meta, "registered_domain")
  const source = `${entity.source_name || "unknown"} · retrieved ${formatDate(entity.retrieved_at)}`
  return (
    <article
      id={`record-${entity.id}`}
      className={`mb-2 rounded-lg border bg-white px-3 py-2.5 text-[11px] leading-snug shadow-sm ${selected ? "border-teal-700 ring-1 ring-teal-700" : "border-slate-200"}`}
    >
      {entity.entity_type === "domain" ? (
        <>
        <div className="grid grid-cols-2 gap-x-2">
          <div className="min-w-0">
            <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Reg date</div>
            <div className="text-slate-900">{publishedDate(meta, "registered_at")}</div>
            <button type="button" className="mt-0.5 block max-w-full truncate text-left text-[13px] font-semibold text-slate-900" onClick={() => onFocus(entity.id)}>
              {entity.display_value}
            </button>
            {registered && registered !== entity.display_value && <div className="text-slate-500">Registered {registered}</div>}
            <div className="mt-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">IP</div>
            <div className="text-slate-900">{metaString(meta, "ip") || "—"}</div>
          </div>
          <div className="min-w-0 text-right">
            <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Exp date</div>
            <div className="text-slate-900">{publishedDate(meta, "expires_at")}</div>
            <div className="mt-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">Registrar</div>
            <div className="break-words text-slate-900">{published(meta, "registrar")}</div>
            <div className="mt-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">Owner</div>
            <div className="break-words text-slate-900">{published(meta, "organization")}</div>
          </div>
        </div>
        <dl className="mt-2 space-y-1 border-t border-slate-100 pt-2">
          <Detail label="ASN" value={metaString(meta, "asn")} />
          <Detail label="Mail" value={metaString(meta, "mx")} />
          <Detail label="SPF" value={metaString(meta, "spf")} />
          <Detail label="DMARC" value={metaString(meta, "dmarc")} />
          <Detail label="Title" value={metaString(meta, "title")} />
          <Detail label="Technology" value={metaString(meta, "technologies")} />
          {captures(meta).length > 0 && (
            <div>
              <dt className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Wayback</dt>
              <dd className="text-slate-900">
                {captures(meta).map((item) => (
                  <div key={`${item.timestamp}-${item.original}`} className="truncate" title={item.original}>
                    {captureDate(item.timestamp)} · {item.status} · {item.original}
                  </div>
                ))}
              </dd>
            </div>
          )}
        </dl>
        </>
      ) : entity.entity_type === "whois" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold text-slate-900 break-words">{metaString(meta, "domain") || entity.display_value}</div>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
            <Detail label="Registrar" value={published(meta, "registrar")} />
            <Detail label="Registry ID" value={metaString(meta, "registry_id")} />
            <Detail label="Registered" value={publishedDate(meta, "registered_at")} />
            <Detail label="Updated" value={publishedDate(meta, "changed_at")} />
            <Detail label="Expires" value={publishedDate(meta, "expires_at")} />
            <Detail label="Status" value={metaString(meta, "status")} />
            <Detail label="DNSSEC" value={metaString(meta, "dnssec")} />
            <Detail label="Registrant" value={published(meta, "registrant")} />
            <Detail label="Abuse phone" value={metaString(meta, "abuse_phone")} />
            <Detail label="Handle" value={metaString(meta, "handle")} />
            <div className="col-span-2">
              <Detail label="Registrar site" value={metaString(meta, "registrar_url")} />
              <Detail label="Nameservers" value={metaString(meta, "nameservers")} />
            </div>
          </dl>
        </button>
      ) : entity.entity_type === "seo" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold text-slate-900 break-words">{metaString(meta, "title") || entity.display_value}</div>
          {metaString(meta, "domain") && <div className="mt-0.5 text-slate-500">{metaString(meta, "domain")}</div>}
          <dl className="mt-2 space-y-1">
            <Detail label="Description" value={metaString(meta, "description")} />
            <Detail label="Keywords" value={metaString(meta, "keywords")} />
            <Detail label="Heading" value={metaString(meta, "h1")} />
            <Detail label="Canonical" value={metaString(meta, "canonical")} />
            <Detail label="Robots" value={metaString(meta, "robots")} />
            <Detail label="Open Graph title" value={metaString(meta, "og_title")} />
            <Detail label="Site name" value={metaString(meta, "og_site_name")} />
            <Detail label="Page" value={metaString(meta, "page")} />
            <Detail label="Language" value={metaString(meta, "language")} />
          </dl>
        </button>
      ) : entity.entity_type === "logo" ? (
        <div>
          <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
            <div className="text-[13px] font-semibold capitalize text-slate-900">{entity.display_value}</div>
          </button>
          {investigationId && <LogoImage investigationId={investigationId} entityId={entity.id} alt={metaString(meta, "alt") || entity.display_value} />}
          <dl className="mt-2 space-y-1">
            <Detail label="URL" value={metaString(meta, "url")} />
            <Detail label="Host" value={metaString(meta, "host")} />
            <Detail label="On investigation host" value={meta.same_host === true ? "Yes" : meta.same_host === false ? "No" : ""} />
            <Detail label="Alt" value={metaString(meta, "alt")} />
          </dl>
        </div>
      ) : entity.entity_type === "url" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold break-all text-slate-900">{entity.display_value}</div>
          <dl className="mt-2 space-y-1">
            <Detail label="Title" value={metaString(meta, "title")} />
            <Detail label="URL" value={metaString(meta, "url")} />
          </dl>
        </button>
      ) : entity.entity_type === "account" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold break-all text-slate-900">{entity.display_value}</div>
          <dl className="mt-2 space-y-1">
            <Detail label="Platform" value={metaString(meta, "platform")} />
            <Detail label="Category" value={metaString(meta, "category")} />
            <Detail label="Profile" value={metaString(meta, "url")} />
            <Detail label="Handle" value={metaString(meta, "handle")} />
          </dl>
        </button>
      ) : entity.entity_type === "contact" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold break-all text-slate-900">{entity.display_value}</div>
          <dl className="mt-2 space-y-1">
            <Detail label="Role" value={metaString(meta, "role")} />
            <Detail label="Name" value={metaString(meta, "name")} />
            <Detail label="Phone" value={metaString(meta, "phone")} />
            <Detail label="Organization" value={metaString(meta, "organization")} />
          </dl>
        </button>
      ) : entity.entity_type === "file" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold break-all text-slate-900">{entity.display_value}</div>
          <dl className="mt-2 space-y-1">
            <Detail label="Kind" value={metaString(meta, "kind")} />
            <Detail label="URL" value={metaString(meta, "url")} />
            <Detail label="Host" value={metaString(meta, "host")} />
          </dl>
        </button>
      ) : entity.entity_type === "hypothesis" ? (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold break-words text-slate-900">{entity.display_value}</div>
          <dl className="mt-2 space-y-1">
            <Detail label="Kind" value={metaString(meta, "kind").replaceAll("_", " ")} />
            <Detail label="Basis" value={metaString(meta, "basis")} />
          </dl>
        </button>
      ) : (
        <button type="button" className="block w-full text-left" onClick={() => onFocus(entity.id)}>
          <div className="text-[13px] font-semibold text-slate-900 break-all">{entity.display_value}</div>
          <div className="mt-1 grid grid-cols-2 gap-2 text-slate-900">
            <Field label="Type" value={entity.entity_type} />
            <Field label="State" value={entity.risk_state} />
            {metaString(meta, "asn") && <Field label="ASN" value={metaString(meta, "asn")} />}
            {metaString(meta, "prefix") && <Field label="Prefix" value={metaString(meta, "prefix")} />}
            {metaString(meta, "holder") && <Field label="Holder" value={metaString(meta, "holder")} />}
            {metaString(meta, "country") && <Field label="Country" value={metaString(meta, "country")} />}
            {metaString(meta, "network") && <Field label="Network" value={metaString(meta, "network")} />}
            {metaString(meta, "hosting") && <Field label="Hosting" value={metaString(meta, "hosting")} />}
            {metaString(meta, "fingerprint") && <Field label="Fingerprint" value={metaString(meta, "fingerprint")} />}
            {metaString(meta, "issuer") && <Field label="Issuer" value={metaString(meta, "issuer")} />}
            {metaString(meta, "statement") && <Field label="Statement" value={metaString(meta, "statement")} />}
            {metaString(meta, "note") && <Field label="Note" value={metaString(meta, "note")} />}
          </div>
        </button>
      )}
      <div className="mt-2 text-[10px] text-slate-400">
        {source}
        {entity.observed_at ? ` · observed ${formatDate(entity.observed_at)}` : ""}
        {entity.verification_status ? ` · ${entity.verification_status}` : ""}
      </div>
    </article>
  )
}

function captures(meta: Record<string, unknown>): Array<{ timestamp: string; original: string; status: string }> {
  const value = meta.wayback
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return []
    const row = item as Record<string, unknown>
    const timestamp = typeof row.timestamp === "string" ? row.timestamp : ""
    const original = typeof row.original === "string" ? row.original : ""
    const status = typeof row.status === "string" ? row.status : ""
    return timestamp ? [{ timestamp, original, status }] : []
  })
}

function captureDate(timestamp: string): string {
  if (timestamp.length < 8) return timestamp
  return `${timestamp.slice(0, 4)}.${timestamp.slice(4, 6)}.${timestamp.slice(6, 8)}`
}

function LogoImage({ investigationId, entityId, alt }: { investigationId: string; entityId: string; alt: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <p className="mt-2 text-slate-500">Image unavailable</p>
  return (
    <img
      src={`/api/investigations/${investigationId}/entities/${entityId}/image`}
      alt={alt}
      className="mt-2 max-h-28 max-w-full rounded border border-slate-200 bg-slate-50 object-contain p-1"
      onError={() => setFailed(true)}
    />
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="break-words text-slate-900">{value}</dd>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="break-words text-slate-900">{value}</div>
    </div>
  )
}
