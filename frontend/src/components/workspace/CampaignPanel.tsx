import type { CampaignSummary, ExpandSuggestion } from "../../api/types"

type Props = {
  campaign: CampaignSummary
  suggestions: ExpandSuggestion[]
  saved: boolean
  onFocus: (entityId: string) => void
}

export function CampaignPanel({ campaign, suggestions, saved, onFocus }: Props) {
  const timeline = campaign.timeline.slice(0, 8)
  const matchLabel =
    campaign.domain_count > 0
      ? `Shares a rare artifact with ${campaign.domain_count} ${campaign.domain_count === 1 ? "domain" : "domains"} in ${campaign.case_count} saved ${campaign.case_count === 1 ? "case" : "cases"}.`
      : "No saved case shares a rare artifact."

  return (
    <div className="pointer-events-auto max-h-72 overflow-auto rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-400">Saved cases</div>
      <p className="mt-1 text-[12px] text-slate-900">{matchLabel}</p>
      {campaign.withheld_common > 0 && (
        <p className="mt-1 text-[11px] text-slate-500">Common artifacts were left off the graph.</p>
      )}
      {campaign.artifact_count > 0 && !saved && (
        <p className="mt-1 text-[11px] text-slate-500">Save this case to compare it with later searches.</p>
      )}
      {campaign.matches.length > 0 && (
        <ul className="mt-2 space-y-1">
          {campaign.matches.slice(0, 6).map((match) => (
            <li key={`${match.saved_investigation_id}-${match.artifact_label}`}>
              <button
                type="button"
                className="text-left text-[11px] text-teal-800 hover:underline"
                onClick={() => match.entity_id && onFocus(match.entity_id)}
              >
                {match.artifact_label} · {match.saved_indicator}
              </button>
            </li>
          ))}
        </ul>
      )}
      {timeline.length > 0 && (
        <ol className="mt-2 space-y-1 border-t border-slate-100 pt-2">
          {timeline.map((event) => (
            <li key={`${event.kind}-${event.at}-${event.subject}`} className="text-[11px] text-slate-700">
              <span className="text-slate-400">{event.at}</span> {event.label}
              {event.subject ? ` · ${event.subject}` : ""}
            </li>
          ))}
        </ol>
      )}
      {suggestions.length > 0 && (
        <div className="mt-2 border-t border-slate-100 pt-2">
          <div className="text-[10px] font-medium uppercase tracking-wide text-slate-400">Next expand</div>
          <ul className="mt-1 space-y-1">
            {suggestions.slice(0, 5).map((item) => (
              <li key={item.entity_id}>
                <button type="button" className="text-left text-[11px] text-slate-800 hover:underline" onClick={() => onFocus(item.entity_id)}>
                  <span className={item.weak ? "text-slate-400" : "font-medium"}>{item.label}</span>
                  <span className="block text-[10px] text-slate-500">{item.reason}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-2 text-[10px] leading-snug text-slate-500">{campaign.note}</p>
    </div>
  )
}
