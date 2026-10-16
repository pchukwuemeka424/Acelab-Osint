"""DNS collector. Queries a resolver only. It never connects to resolved addresses."""

from datetime import datetime, timezone

import dns.exception
import dns.resolver

from app.connectors.base import CollectionResult, EntityIn, ProviderError, RelIn
from app.connectors.rdap import registration_candidates
from app.security.ssrf import is_blocked_ip
from app.services.normalize import is_domain


def _resolver(timeout: float) -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.lifetime = timeout
    resolver.timeout = timeout
    return resolver


def collect_dns(domain: str, timeout: float = 3.0, resolver: dns.resolver.Resolver | None = None) -> CollectionResult:
    if not is_domain(domain):
        raise ProviderError("dns", "invalid domain")
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=domain,
            display_value=domain,
            risk_state="contextual",
            source_name="dns",
            verification_status="observed",
            observed_at=None,
        )
    )
    lookup = resolver or _resolver(timeout)
    retrieved = datetime.now(timezone.utc)
    for record_type in ("A", "AAAA", "NS", "CNAME"):
        try:
            answers = lookup.resolve(domain, record_type, lifetime=timeout)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
            continue
        except Exception as exc:
            raise ProviderError("dns", str(exc)) from exc
        for answer in answers:
            text = str(answer).rstrip(".").lower()
            if record_type in {"A", "AAAA"}:
                blocked = is_blocked_ip(text)
                result.entities.append(
                    EntityIn(
                        entity_type="ip",
                        normalized_value=text,
                        display_value=text,
                        risk_state="uncertain" if blocked else "contextual",
                        source_name="dns",
                        metadata={"non_public": blocked, "record_type": record_type, "retrieved_at": retrieved.isoformat()},
                        verification_status="observed",
                    )
                )
                result.relationships.append(
                    RelIn(
                        source_type="domain",
                        source_value=domain,
                        target_type="ip",
                        target_value=text,
                        rel_type="resolves_to",
                        reason=f"DNS {record_type} answer recorded from the configured resolver.",
                        risk_state="uncertain" if blocked else "contextual",
                        provenance="dns",
                    )
                )
            elif record_type == "NS":
                if not is_domain(text):
                    continue
                result.entities.append(
                    EntityIn(
                        entity_type="nameserver",
                        normalized_value=text,
                        display_value=text,
                        source_name="dns",
                        verification_status="observed",
                    )
                )
                result.relationships.append(
                    RelIn(
                        source_type="domain",
                        source_value=domain,
                        target_type="nameserver",
                        target_value=text,
                        rel_type="uses_nameserver",
                        reason="DNS NS record.",
                        provenance="dns",
                        weak_reason=None,
                    )
                )
            elif record_type == "CNAME" and is_domain(text):
                result.entities.append(
                    EntityIn(
                        entity_type="domain",
                        normalized_value=text,
                        display_value=text,
                        source_name="dns",
                        verification_status="observed",
                    )
                )
                result.relationships.append(
                    RelIn(
                        source_type="domain",
                        source_value=domain,
                        target_type="domain",
                        target_value=text,
                        rel_type="resolves_to",
                        reason="DNS CNAME answer.",
                        provenance="dns",
                    )
                )
    public_addresses = [
        item.normalized_value
        for item in result.entities
        if item.entity_type == "ip" and item.metadata.get("record_type") == "A" and not item.metadata.get("non_public")
    ]
    if public_addresses and result.entities:
        result.entities[0].metadata["ip"] = public_addresses[0]
    _attach_mail(result.entities[0], domain, lookup, timeout)
    return result


def _answers(lookup: dns.resolver.Resolver, name: str, record_type: str, timeout: float) -> list:
    try:
        return list(lookup.resolve(name, record_type, lifetime=timeout))
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    except Exception as exc:
        raise ProviderError("dns", str(exc)) from exc


def _txt(answer: object) -> str:
    strings = getattr(answer, "strings", None)
    if strings:
        parts = []
        for item in strings:
            parts.append(item.decode() if isinstance(item, bytes) else str(item))
        return "".join(parts)
    return str(answer).strip('"')


def _spf(lookup: dns.resolver.Resolver, name: str, timeout: float) -> str:
    for answer in _answers(lookup, name, "TXT", timeout):
        text = _txt(answer)
        if text.lower().startswith("v=spf1"):
            return text
    return ""


def _mail_hosts(lookup: dns.resolver.Resolver, name: str, timeout: float) -> list[str]:
    hosts = []
    for answer in _answers(lookup, name, "MX", timeout):
        exchange = getattr(answer, "exchange", None)
        host = str(exchange if exchange is not None else answer).rstrip(".").lower()
        if exchange is None and " " in host:
            host = host.split()[-1]
        if is_domain(host) and host not in hosts:
            hosts.append(host)
    return hosts


def _attach_mail(entity: EntityIn, domain: str, lookup: dns.resolver.Resolver, timeout: float) -> None:
    registered = registration_candidates(domain)[-1]
    hosts = _mail_hosts(lookup, domain, timeout)
    if not hosts and registered != domain:
        hosts = _mail_hosts(lookup, registered, timeout)
    spf = _spf(lookup, domain, timeout) or _spf(lookup, registered, timeout)
    dmarc = ""
    for answer in _answers(lookup, f"_dmarc.{registered}", "TXT", timeout):
        text = _txt(answer)
        if text.lower().startswith("v=dmarc1"):
            dmarc = text
            break
    entity.metadata["mx"] = ", ".join(hosts) if hosts else "No record"
    entity.metadata["spf"] = spf or "No record"
    entity.metadata["dmarc"] = dmarc or "No record"
