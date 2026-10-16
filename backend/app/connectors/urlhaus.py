from urllib.parse import quote

from app.connectors.base import CollectionResult, EntityIn, IndicatorIn, ProviderError, RelIn
from app.security.ssrf import UnsafeURL, guarded_request
from app.services.normalize import is_domain


def normalize_urlhaus(host: str, payload: dict) -> CollectionResult:
    result = CollectionResult()
    status = payload.get("query_status")
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=host,
            display_value=host,
            risk_state="risk" if status == "is_host" else "contextual",
            source_name="urlhaus",
            verification_status="confirmed" if status == "is_host" else "observed",
            metadata={"query_status": status, "demonstration": False},
        )
    )
    if status != "is_host":
        result.limitations.append("URLHaus returned no host match.")
        return result
    for url in (payload.get("urls") or [])[:10]:
        if not isinstance(url, dict):
            continue
        value = url.get("url")
        if not value:
            continue
        result.indicators.append(
            IndicatorIn(
                entity_type="domain",
                entity_value=host,
                indicator_type="url",
                value=str(value)[:512],
                status="confirmed",
                actor_name=None,
                details={"threat": url.get("threat"), "urlhaus_reference": url.get("urlhaus_reference")},
                source_name="urlhaus",
            )
        )
        indicator_value = str(url.get("id") or "urlhaus-host")
        result.entities.append(
            EntityIn(
                entity_type="indicator",
                normalized_value=f"urlhaus:{indicator_value}",
                display_value=f"URLHaus {indicator_value}",
                risk_state="risk",
                source_name="urlhaus",
                verification_status="confirmed",
                metadata={"demonstration": False, "reference": url.get("urlhaus_reference")},
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=host,
                target_type="indicator",
                target_value=f"urlhaus:{indicator_value}",
                rel_type="observed_in_threat_intel",
                reason="URLHaus reported this host. The stored reference is the provider record, not an actor attribution.",
                risk_state="risk",
                provenance="urlhaus",
                threat_match=True,
            )
        )
        break
    return result


def collect_urlhaus(host: str, fetcher=guarded_request) -> CollectionResult:
    if not is_domain(host):
        raise ProviderError("urlhaus", "invalid host")
    url = f"https://urlhaus-api.abuse.ch/v1/host/{quote(host)}"
    try:
        response = fetcher("GET", url, "urlhaus")
    except UnsafeURL as exc:
        raise ProviderError("urlhaus", exc.public_message) from exc
    except Exception as exc:
        raise ProviderError("urlhaus", "request failed") from exc
    if response.status_code >= 400:
        raise ProviderError("urlhaus", f"status {response.status_code}")
    try:
        payload = response.json()
    except Exception as exc:
        raise ProviderError("urlhaus", "invalid json") from exc
    if not isinstance(payload, dict):
        raise ProviderError("urlhaus", "unexpected payload")
    return normalize_urlhaus(host, payload)
