"""Transparent association scoring.

Weights are a documented baseline for explanation. They are not a validated
probability model and must not be presented as one.
"""

from dataclasses import dataclass, field

# Unvalidated explanation weights. Shared public infrastructure is capped later.
BASE_WEIGHTS = {
    "resolves_to": 22.0,
    "uses_nameserver": 12.0,
    "appears_in_certificate": 18.0,
    "redirects_to": 16.0,
    "observed_in_threat_intel": 28.0,
    "shares_infrastructure": 10.0,
    "potentially_associated": 6.0,
    "observed_on_page": 4.0,
    "has_contact": 8.0,
    "has_account": 6.0,
    "matches_kit": 24.0,
}

WEAK_REASONS = {
    "shared_cdn": "A shared CDN address is common infrastructure and is weak evidence of association.",
    "shared_hosting": "Shared hosting does not establish common ownership.",
    "common_ca": "A common certificate authority is non-discriminating.",
    "public_dns": "A public DNS provider is non-discriminating without further evidence.",
    "page_markup": "Page title, SEO fields, and images describe the response. They do not show who operates the host.",
    "redacted_contact": "A redacted or privacy registration contact does not identify an operator.",
    "unverified_claim": "Text on a page can name a person or company. It does not confirm who operates the host.",
    "public_handle": "A public profile URL that contains this handle is common and is weak evidence of association.",
}

SCORE_KIND = "heuristic_baseline_v1"


@dataclass
class ScoreInput:
    rel_type: str
    weak_reason: str | None = None
    source_reliability: float = 0.5
    rarity: float = 1.0
    temporal_overlap: bool = False
    corroboration: int = 1
    conflicting: bool = False
    stale: bool = False
    threat_match: bool = False


@dataclass
class ScoreResult:
    heuristic_score: float
    label: str
    summary: str
    factors: list[dict] = field(default_factory=list)
    score_kind: str = SCORE_KIND


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 1)))


def score_association(item: ScoreInput) -> ScoreResult:
    factors: list[dict] = []
    base = BASE_WEIGHTS.get(item.rel_type, 5.0)
    factors.append(
        {
            "name": "relationship_type",
            "weight": base,
            "value": item.rel_type,
            "contribution": base,
            "note": "Baseline weight for this relationship type. Not a validated probability.",
        }
    )
    reliability = max(0.0, min(1.0, item.source_reliability))
    reliability_delta = round(base * (reliability - 0.5), 1)
    factors.append(
        {
            "name": "source_reliability",
            "weight": 1.0,
            "value": reliability,
            "contribution": reliability_delta,
            "note": "Shifts the baseline by source reliability around 0.5.",
        }
    )
    rarity = max(0.2, min(1.0, item.rarity))
    rarity_delta = round(base * (rarity - 1.0) * 0.5, 1)
    factors.append(
        {
            "name": "rarity",
            "weight": rarity,
            "value": rarity,
            "contribution": rarity_delta,
            "note": "Shared characteristics that are common contribute less.",
        }
    )
    overlap = 5.0 if item.temporal_overlap else 0.0
    factors.append(
        {
            "name": "temporal_overlap",
            "weight": 5.0,
            "value": item.temporal_overlap,
            "contribution": overlap,
            "note": "Adds a small amount when observation windows overlap.",
        }
    )
    corroboration = 8.0 if item.corroboration >= 2 else 0.0
    factors.append(
        {
            "name": "independent_corroboration",
            "weight": 8.0,
            "value": item.corroboration,
            "contribution": corroboration,
            "note": "Adds weight only when at least two independent sources agree.",
        }
    )
    threat = 12.0 if item.threat_match else 0.0
    factors.append(
        {
            "name": "threat_indicator",
            "weight": 12.0,
            "value": item.threat_match,
            "contribution": threat,
            "note": "Applied only when a stored indicator references this entity.",
        }
    )
    conflict = -10.0 if item.conflicting else 0.0
    factors.append(
        {
            "name": "conflicting_evidence",
            "weight": -10.0,
            "value": item.conflicting,
            "contribution": conflict,
            "note": "Lowers the score when stored observations disagree.",
        }
    )
    stale = -8.0 if item.stale else 0.0
    factors.append(
        {
            "name": "staleness",
            "weight": -8.0,
            "value": item.stale,
            "contribution": stale,
            "note": "Lowers the score when the supporting observation is stale.",
        }
    )
    total = base + reliability_delta + rarity_delta + overlap + corroboration + threat + conflict + stale
    label = "observed" if item.rel_type in {"resolves_to", "redirects_to", "uses_nameserver"} else "inferred"
    if item.threat_match and item.corroboration >= 2:
        label = "corroborated"
    summary = f"Heuristic {label} association from {item.rel_type.replace('_', ' ')}."
    if item.weak_reason:
        total = min(total, 15.0)
        label = "insufficient"
        summary = WEAK_REASONS.get(item.weak_reason, "This shared infrastructure characteristic is weak evidence.")
        factors.append(
            {
                "name": "common_infrastructure_cap",
                "weight": 15.0,
                "value": item.weak_reason,
                "contribution": 0.0,
                "note": summary,
            }
        )
    elif item.conflicting:
        label = "insufficient"
        summary = "Conflicting observations prevent a stronger association."
    score = _clamp(total)
    return ScoreResult(heuristic_score=score, label=label, summary=summary, factors=factors)
