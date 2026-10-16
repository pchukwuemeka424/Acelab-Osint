from urllib.parse import quote

from app.connectors.base import CollectionResult, EntityIn, ProviderError, RelIn
from app.security.ssrf import UnsafeURL, guarded_request
from app.services.normalize import is_domain


def normalize_ct(domain: str, payload: object) -> CollectionResult:
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=domain,
            display_value=domain,
            source_name="certificate_transparency",
            verification_status="observed",
        )
    )
    if not isinstance(payload, list):
        result.limitations.append("Certificate transparency returned no certificate list.")
        return result
    seen: set[str] = set()
    for row in payload[:25]:
        if not isinstance(row, dict):
            continue
        fingerprint = str(row.get("id") or row.get("serial_number") or "")
        names = str(row.get("name_value") or domain)
        issuer = row.get("issuer_name")
        key = fingerprint or names
        if key in seen:
            continue
        seen.add(key)
        cert_id = fingerprint.lower() or f"ct-{len(seen)}-{domain}"
        result.entities.append(
            EntityIn(
                entity_type="certificate",
                normalized_value=cert_id[:64] if len(cert_id) >= 32 else f"{cert_id}:{domain}",
                display_value=names.split("\n")[0][:80],
                source_name="certificate_transparency",
                verification_status="observed",
                metadata={
                    "fingerprint": fingerprint,
                    "issuer": issuer,
                    "not_before": row.get("not_before"),
                    "not_after": row.get("not_after"),
                    "subject_names": names.split("\n"),
                    "demonstration": False,
                },
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="certificate",
                target_value=result.entities[-1].normalized_value,
                rel_type="appears_in_certificate",
                reason="Name appeared in a certificate-transparency entry.",
                provenance="certificate_transparency",
                weak_reason="common_ca" if issuer and "let's encrypt" in str(issuer).lower() else None,
            )
        )
    return result


def collect_ct(domain: str, fetcher=guarded_request) -> CollectionResult:
    if not is_domain(domain):
        raise ProviderError("ct", "invalid domain")
    url = f"https://crt.sh/?q={quote(domain)}&output=json"
    try:
        response = fetcher("GET", url, "ct", timeout=20)
    except UnsafeURL as exc:
        raise ProviderError("ct", exc.public_message) from exc
    except Exception as exc:
        raise ProviderError("ct", "request failed") from exc
    if response.status_code >= 400:
        raise ProviderError("ct", f"status {response.status_code}")
    try:
        payload = response.json()
    except Exception as exc:
        raise ProviderError("ct", "invalid json") from exc
    return normalize_ct(domain, payload)
