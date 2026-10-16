from urllib.parse import quote

from app.connectors.base import CollectionResult, EntityIn, ProviderError, RelIn
from app.security.ssrf import UnsafeURL, guarded_request
from app.services.normalize import is_domain


def _events(payload: dict) -> dict[str, str]:
    found: dict[str, str] = {}
    for event in payload.get("events") or []:
        action = event.get("eventAction")
        date = event.get("eventDate")
        if action and date:
            found[action] = date
    return found


def _vcard_value(entity: dict, key: str) -> str | None:
    vcard = entity.get("vcardArray")
    if not isinstance(vcard, list) or len(vcard) < 2:
        return None
    for item in vcard[1]:
        if isinstance(item, list) and item and item[0] == key and len(item) > 3:
            value = item[3]
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                return " ".join(str(part) for part in value)
    return None


CONTACT_ROLES = {"registrant", "administrative", "technical", "abuse", "registrar"}


def _redacted(*values: str | None) -> bool:
    text = " ".join(value.lower() for value in values if value)
    return any(word in text for word in ("redact", "privacy", "withheld", "not disclosed", "data protected"))


def _walk_entities(entities: list, inherited: list[str] | None = None):
    for entity in entities or []:
        if not isinstance(entity, dict):
            continue
        roles = [role for role in (entity.get("roles") or inherited or []) if role in CONTACT_ROLES]
        yield entity, roles
        nested = entity.get("entities")
        if isinstance(nested, list):
            yield from _walk_entities(nested, roles)


def _contacts(payload: dict) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for entity, roles in _walk_entities(payload.get("entities") or []):
        if not roles:
            continue
        name = _vcard_value(entity, "fn") or ""
        phone = _vcard_value(entity, "tel") or ""
        organization = _vcard_value(entity, "org") or ""
        if not any((name, phone, organization)):
            continue
        role = roles[0]
        key = (phone or f"{role}:{name or organization}").lower()[:512]
        if key in seen:
            continue
        seen.add(key)
        registry_id = ""
        for item in entity.get("publicIds") or []:
            if isinstance(item, dict) and item.get("identifier"):
                registry_id = str(item["identifier"])[:80]
                break
        found.append(
            {
                "role": role,
                "name": name[:300],
                "phone": phone[:80],
                "organization": organization[:300],
                "url": (_vcard_value(entity, "url") or "")[:300],
                "registry_id": registry_id,
                "key": key,
                "redacted": _redacted(name, phone, organization),
            }
        )
        if len(found) >= 12:
            break
    return found


def _first(contacts: list[dict], role: str) -> dict | None:
    return next((contact for contact in contacts if contact["role"] == role), None)


def _published_party(contact: dict | None) -> str | None:
    if contact is None or contact["redacted"]:
        return None
    return contact["organization"] or contact["name"] or None


def _nameservers(payload: dict) -> str:
    found: list[str] = []
    for row in payload.get("nameservers") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("ldhName") or row.get("unicodeName") or ""
        if not isinstance(name, str):
            continue
        cleaned = name.strip().rstrip(".").lower()
        if cleaned and cleaned not in found:
            found.append(cleaned)
    return ", ".join(found[:12])


def _whois_metadata(domain: str, payload: dict, contacts: list[dict], events: dict[str, str]) -> dict:
    registrar = _first(contacts, "registrar")
    registrant = _first(contacts, "registrant")
    abuse = _first(contacts, "abuse")
    statuses = [item for item in (payload.get("status") or []) if isinstance(item, str) and item.strip()]
    secure = payload.get("secureDNS") if isinstance(payload.get("secureDNS"), dict) else {}
    signed = secure.get("delegationSigned")
    handle = payload.get("handle") if isinstance(payload.get("handle"), str) else ""
    registered_name = payload.get("ldhName") if isinstance(payload.get("ldhName"), str) else domain
    metadata = {
        "domain": registered_name.strip().rstrip(".").lower() or domain,
        "registrar": (registrar["name"] or registrar["organization"]) if registrar else None,
        "registrar_url": registrar["url"] if registrar else None,
        "registry_id": registrar["registry_id"] if registrar else None,
        "registered_at": events.get("registration"),
        "changed_at": events.get("last changed"),
        "expires_at": events.get("expiration"),
        "status": ", ".join(statuses[:8]),
        "nameservers": _nameservers(payload),
        "dnssec": "signed" if signed is True else "unsigned" if signed is False else "",
        "registrant": _published_party(registrant),
        "abuse_phone": abuse["phone"] if abuse else None,
        "handle": handle[:120],
        "registration_found": True,
        "demonstration": False,
    }
    return {key: value for key, value in metadata.items() if value not in (None, "")}


def normalize_rdap(domain: str, payload: dict) -> CollectionResult:
    events = _events(payload)
    contacts = _contacts(payload)
    registrar_contact = _first(contacts, "registrar")
    registrant = _first(contacts, "registrant")
    registrar = (registrar_contact["name"] or registrar_contact["organization"]) if registrar_contact else None
    organization = _published_party(registrant)
    whois = _whois_metadata(domain, payload, contacts, events)
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=domain,
            display_value=domain,
            source_name="rdap",
            verification_status="observed",
            metadata={
                "registrar": registrar,
                "organization": organization,
                "registered_at": events.get("registration"),
                "changed_at": events.get("last changed"),
                "expires_at": events.get("expiration"),
                "registration_contacts": True,
                "whois_record": True,
                "demonstration": False,
            },
        )
    )
    result.entities.append(
        EntityIn(
            entity_type="whois",
            normalized_value=domain,
            display_value=whois.get("domain") or domain,
            source_name="rdap",
            verification_status="observed",
            metadata=whois,
        )
    )
    for contact in contacts:
        label = contact["name"] or contact["phone"] or contact["organization"]
        result.entities.append(
            EntityIn(
                entity_type="contact",
                normalized_value=contact["key"],
                display_value=label[:300],
                source_name="rdap",
                verification_status="observed",
                metadata={
                    "role": contact["role"],
                    "name": contact["name"],
                    "phone": contact["phone"],
                    "organization": contact["organization"],
                    "redacted": contact["redacted"],
                },
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="contact",
                target_value=contact["key"],
                rel_type="has_contact",
                reason="Public registration data listed this contact.",
                provenance="rdap",
                weak_reason="redacted_contact" if contact["redacted"] else None,
            )
        )
    return result


MULTI_SUFFIXES = {
    "co.uk",
    "org.uk",
    "ac.uk",
    "gov.uk",
    "ltd.uk",
    "plc.uk",
    "me.uk",
    "net.uk",
    "com.au",
    "net.au",
    "org.au",
    "co.nz",
    "com.br",
    "co.za",
    "co.jp",
    "com.ng",
    "co.in",
}


def registration_candidates(domain: str) -> list[str]:
    """Host first, then parent names down to the registered domain."""
    labels = domain.split(".")
    names = [domain]
    while len(labels) > 2:
        labels = labels[1:]
        parent = ".".join(labels)
        names.append(parent)
        suffix = ".".join(labels[-2:])
        if suffix in MULTI_SUFFIXES and len(labels) <= 3:
            break
    return names


def collect_rdap(domain: str, fetcher=guarded_request) -> CollectionResult:
    if not is_domain(domain):
        raise ProviderError("rdap", "invalid domain")
    last_status = "404"
    for candidate in registration_candidates(domain):
        url = f"https://rdap.org/domain/{quote(candidate)}"
        try:
            response = fetcher("GET", url, "rdap", timeout=20)
        except UnsafeURL as exc:
            raise ProviderError("rdap", exc.public_message) from exc
        except Exception as exc:
            raise ProviderError("rdap", "request failed") from exc
        if response.status_code == 404:
            last_status = "404"
            continue
        if response.status_code >= 400:
            raise ProviderError("rdap", f"status {response.status_code}")
        try:
            payload = response.json()
        except Exception as exc:
            raise ProviderError("rdap", "invalid json") from exc
        if not isinstance(payload, dict):
            raise ProviderError("rdap", "unexpected payload")
        result = normalize_rdap(domain, payload)
        for entity in result.entities:
            if entity.entity_type in {"domain", "whois"}:
                entity.metadata["registered_domain"] = candidate
                entity.metadata["registration_found"] = True
        return result
    raise ProviderError("rdap", f"status {last_status}")
