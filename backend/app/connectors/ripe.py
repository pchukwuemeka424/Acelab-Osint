from urllib.parse import quote

from app.connectors.base import CollectionResult, EntityIn, ProviderError, RelIn
from app.security.ssrf import UnsafeURL, guarded_request


def _overview(payload: dict) -> tuple[str, str, str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return "", "", ""
    prefix = str(data.get("resource") or "")
    asns = data.get("asns") or []
    asn = ""
    holder = ""
    if isinstance(asns, list) and asns:
        first = asns[0]
        if isinstance(first, dict):
            number = first.get("asn")
            asn = f"AS{number}" if number else ""
            holder = str(first.get("holder") or "")
    return prefix, asn, holder


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _place(payload: dict) -> dict[str, object]:
    data = payload.get("data") if isinstance(payload, dict) else None
    locations: list = []
    if isinstance(data, dict):
        direct = data.get("locations") or []
        if isinstance(direct, list):
            locations.extend(item for item in direct if isinstance(item, dict))
        for item in data.get("located_resources") or []:
            if not isinstance(item, dict):
                continue
            for place in item.get("locations") or []:
                if isinstance(place, dict):
                    locations.append(place)
    found: dict[str, object] = {}
    for place in locations:
        country = place.get("country")
        if country and "country" not in found:
            found["country"] = str(country)
        city = place.get("city")
        if city and "city" not in found:
            found["city"] = str(city)
        latitude = _number(place.get("latitude"))
        longitude = _number(place.get("longitude"))
        if latitude is not None and longitude is not None and "latitude" not in found:
            found["latitude"] = latitude
            found["longitude"] = longitude
    return found


def collect_ripe(domain: str, addresses: list[str], fetcher=guarded_request) -> CollectionResult:
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=domain,
            display_value=domain,
            source_name="ripe",
            verification_status="observed",
        )
    )
    seen_asn: list[str] = []
    for address in addresses[:8]:
        try:
            overview = fetcher("GET", f"https://stat.ripe.net/data/prefix-overview/data.json?resource={quote(address)}", "ripe", timeout=8)
            geo = fetcher("GET", f"https://stat.ripe.net/data/geoloc/data.json?resource={quote(address)}", "ripe", timeout=8)
        except UnsafeURL as exc:
            raise ProviderError("ripe", exc.public_message) from exc
        except Exception as exc:
            raise ProviderError("ripe", "request failed") from exc
        if overview.status_code >= 400:
            continue
        try:
            prefix, asn, holder = _overview(overview.json())
            place = _place(geo.json()) if geo.status_code < 400 else {}
            country = str(place.get("country") or "")
        except Exception as exc:
            raise ProviderError("ripe", "invalid json") from exc
        if not asn and not prefix:
            continue
        result.entities.append(
            EntityIn(
                entity_type="ip",
                normalized_value=address,
                display_value=address,
                source_name="ripe",
                verification_status="observed",
                metadata={"prefix": prefix, "asn": asn, "holder": holder, "country": country, "geoloc": country, "network": prefix, "hosting": holder, **place},
            )
        )
        if asn and asn not in seen_asn:
            seen_asn.append(asn)
            result.entities.append(
                EntityIn(
                    entity_type="hosting",
                    normalized_value=asn,
                    display_value=f"{asn} {holder}".strip(),
                    source_name="ripe",
                    verification_status="observed",
                    metadata={"asn": asn, "holder": holder, "prefix": prefix, "country": country, **place},
                )
            )
        if asn:
            result.relationships.append(
                RelIn(
                    source_type="ip",
                    source_value=address,
                    target_type="hosting",
                    target_value=asn,
                    rel_type="announced_by",
                    reason="RIPEstat prefix overview records the network that announces this address.",
                    provenance="ripe",
                )
            )
    if seen_asn:
        result.entities[0].metadata["asn"] = seen_asn[0]
    result.limitations.append("RIPEstat describes the current announcing network. It is not a history of past DNS resolutions.")
    return result
