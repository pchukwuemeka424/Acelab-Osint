from urllib.parse import quote

from app.connectors.base import CollectionResult, EntityIn, ProviderError
from app.security.ssrf import UnsafeURL, guarded_request


def _captures(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        return []
    rows = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 3:
            continue
        timestamp, original, status = str(row[0]), str(row[1]), str(row[2])
        if not timestamp.isdigit():
            continue
        rows.append({"timestamp": timestamp, "original": original[:512], "status": status})
        if len(rows) >= 8:
            break
    return rows


def collect_wayback(domain: str, fetcher=guarded_request) -> CollectionResult:
    url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={quote(domain)}&matchType=domain&output=json&fl=timestamp,original,statuscode&limit=8&filter=statuscode:200"
    )
    try:
        response = fetcher("GET", url, "wayback", timeout=20)
    except UnsafeURL as exc:
        raise ProviderError("wayback", exc.public_message) from exc
    except Exception as exc:
        raise ProviderError("wayback", "request failed") from exc
    if response.status_code >= 400:
        raise ProviderError("wayback", f"status {response.status_code}")
    try:
        captures = _captures(response.json())
    except Exception as exc:
        raise ProviderError("wayback", "invalid json") from exc
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=domain,
            display_value=domain,
            source_name="wayback",
            verification_status="observed",
            metadata={"wayback": captures},
        )
    )
    if not captures:
        result.limitations.append("Wayback Machine returned no public captures for this host.")
    return result
