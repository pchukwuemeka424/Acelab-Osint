from app.connectors.base import RelIn
from app.security.ssrf import is_blocked_ip
from app.services.normalize import is_domain


def extract_resolution(domain: str, record_type: str, value: str) -> RelIn | None:
    record_type = record_type.upper()
    value = value.rstrip(".").lower()
    if record_type in {"A", "AAAA"}:
        blocked = is_blocked_ip(value)
        return RelIn(
            source_type="domain",
            source_value=domain,
            target_type="ip",
            target_value=value,
            rel_type="resolves_to",
            reason=f"DNS {record_type} answer.",
            risk_state="uncertain" if blocked else "contextual",
            provenance="dns",
        )
    if record_type == "NS" and is_domain(value):
        return RelIn(
            source_type="domain",
            source_value=domain,
            target_type="nameserver",
            target_value=value,
            rel_type="uses_nameserver",
            reason="DNS NS record.",
            provenance="dns",
        )
    if record_type == "CNAME" and is_domain(value):
        return RelIn(
            source_type="domain",
            source_value=domain,
            target_type="domain",
            target_value=value,
            rel_type="resolves_to",
            reason="DNS CNAME answer.",
            provenance="dns",
        )
    return None


def extract_certificate_appearance(domain: str, fingerprint: str, issuer: str | None) -> RelIn:
    weak = None
    if issuer and "let's encrypt" in issuer.lower():
        weak = "common_ca"
    return RelIn(
        source_type="domain",
        source_value=domain,
        target_type="certificate",
        target_value=fingerprint,
        rel_type="appears_in_certificate",
        reason="Subject name listed on the certificate.",
        provenance="certificate_transparency",
        weak_reason=weak,
    )
