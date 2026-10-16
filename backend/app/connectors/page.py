import html
import re
from urllib.parse import urljoin, urlsplit

from app.connectors.base import CollectionResult, EntityIn, ProviderError, RelIn
from app.security.ssrf import UnsafeURL, fetch_public_subject
from app.services.campaign import GENERIC_FIELDS, script_is_generic


def _meta(document: str, name: str) -> str:
    for match in re.finditer(r"<meta\b[^>]*>", document[:200000], re.I):
        tag = match.group(0)
        if re.search(rf"(?:name|property)=[\"']{re.escape(name)}[\"']", tag, re.I) is None:
            continue
        content = re.search(r"content=[\"']([^\"']*)[\"']", tag, re.I)
        if content is None:
            continue
        return html.unescape(re.sub(r"\s+", " ", content.group(1)).strip())[:300]
    return ""


def _title(document: str) -> str:
    match = re.search(r"<title[^>]*>([^<]{0,300})</title>", document[:200000], re.I)
    if match is None:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())[:300]


def _technologies(document: str, headers: dict) -> str:
    found: list[str] = []
    lower = document.lower()
    server = str(headers.get("server") or "")
    powered = str(headers.get("x-powered-by") or "")
    if "cloudflare" in server.lower() or "cf-ray" in {key.lower() for key in headers}:
        found.append("Cloudflare")
    generator = _meta(document, "generator")
    if generator:
        found.append(generator)
    if "wp-content" in lower or "wordpress" in lower:
        found.append("WordPress")
    if "cdn.shopify.com" in lower:
        found.append("Shopify")
    if powered and powered not in found:
        found.append(powered[:80])
    unique = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return ", ".join(unique[:6])


def _attr(tag: str, name: str) -> str:
    match = re.search(rf"{name}=[\"']([^\"']*)[\"']", tag, re.I)
    if match is None:
        return ""
    return html.unescape(match.group(1)).strip()


def _heading(document: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", document[:200000], re.I | re.S)
    if match is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return html.unescape(re.sub(r"\s+", " ", text).strip())[:300]


def _language(document: str) -> str:
    match = re.search(r"<html\b[^>]*\blang=[\"']([^\"']*)[\"']", document[:4000], re.I)
    if match is None:
        return ""
    return html.unescape(match.group(1)).strip()[:32]


def _canonical(document: str) -> str:
    for match in re.finditer(r"<link\b[^>]*>", document[:200000], re.I):
        tag = match.group(0)
        rel = _attr(tag, "rel").lower()
        if "canonical" not in rel.split():
            continue
        return _attr(tag, "href")[:500]
    return ""


def _public_url(raw: str, page_url: str) -> tuple[str, str]:
    value = html.unescape(raw).strip()
    if not value or len(value) > 1000 or value.lower().startswith(("javascript:", "data:", "blob:", "file:")):
        return "", ""
    absolute = urljoin(page_url, value)
    parsed = urlsplit(absolute)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        return "", ""
    return parsed._replace(fragment="").geturl()[:500], host


def _logos(document: str, page_url: str, domain: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, raw: str, alt: str = "") -> None:
        if len(found) >= 6 or not raw:
            return
        url, host = _public_url(raw, page_url)
        key = f"{kind}:{url}"
        if not url or key in seen:
            return
        seen.add(key)
        found.append(
            {
                "kind": kind,
                "url": url,
                "host": host,
                "same_host": host == domain.lower().rstrip("."),
                "alt": alt[:160],
            }
        )

    for match in re.finditer(r"<link\b[^>]*>", document[:200000], re.I):
        tag = match.group(0)
        rel = _attr(tag, "rel").lower()
        href = _attr(tag, "href")
        if "apple-touch-icon" in rel:
            add("apple_touch", href)
        elif "icon" in rel.split() or rel == "shortcut icon":
            add("favicon", href)
    add("open_graph", _meta(document, "og:image"))
    for match in re.finditer(r"<img\b[^>]*>", document[:200000], re.I):
        tag = match.group(0)
        if "logo" not in tag.lower():
            continue
        add("logo", _attr(tag, "src"), _attr(tag, "alt"))
    return found


_PHONE = re.compile(r"\+\d{1,3}(?:[\s\-]+\d{2,6}){2,4}")
_FILE_EXT = (".js", ".mjs", ".css", ".pdf", ".zip", ".csv", ".json", ".xml", ".doc", ".docx", ".xls", ".xlsx", ".txt")
_SKIP_PAGE_EXT = _FILE_EXT + (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2", ".mp4", ".mp3")
_SUBPAGE_LIMIT = 12


def _page_contacts(document: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, value: str) -> None:
        cleaned = re.sub(r"\s+", " ", html.unescape(value)).strip()[:160]
        key = cleaned.lower()
        if not cleaned or key in seen or len(found) >= 8:
            return
        seen.add(key)
        found.append({"kind": kind, "value": cleaned})

    for match in re.finditer(r"<a\b[^>]*>", document[:200000], re.I):
        href = _attr(match.group(0), "href")
        if href.lower().startswith("tel:"):
            add("phone", href.split(":", 1)[1])
    for match in _PHONE.finditer(document[:200000]):
        add("phone", match.group(0))
    return found


def _files(document: str, page_url: str, domain: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, raw: str) -> None:
        if len(found) >= 12 or not raw:
            return
        url, host = _public_url(raw, page_url)
        if not url or url in seen:
            return
        path = urlsplit(url).path.lower()
        if kind == "document" and not path.endswith(_FILE_EXT):
            return
        seen.add(url)
        found.append({"kind": kind, "url": url, "host": host, "same_host": host == domain.lower().rstrip(".")})

    for match in re.finditer(r"<script\b[^>]*>", document[:200000], re.I):
        add("script", _attr(match.group(0), "src"))
    for match in re.finditer(r"<link\b[^>]*>", document[:200000], re.I):
        tag = match.group(0)
        if "stylesheet" in _attr(tag, "rel").lower():
            add("stylesheet", _attr(tag, "href"))
    for match in re.finditer(r"<a\b[^>]*>", document[:200000], re.I):
        add("document", _attr(match.group(0), "href"))
    return found


def _attributions(document: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, statement: str) -> None:
        cleaned = re.sub(r"\s+", " ", html.unescape(statement)).strip(" -|")[:200]
        key = f"{kind}:{cleaned.lower()}"
        if len(cleaned) < 2 or key in seen or len(found) >= 6:
            return
        seen.add(key)
        found.append({"kind": kind, "statement": cleaned})

    author = _meta(document, "author")
    if author:
        add("author", author)
    founded = re.search(r"founded by\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})", document[:200000], re.I)
    if founded:
        add("person", founded.group(1).strip())
    for match in re.finditer(r"(?:©|\bcopyright\b)\s*([^<]{2,80})", document[:200000], re.I):
        add("copyright", match.group(1))
        break
    number = re.search(r"company\s+(?:no\.?|number)\s*:?\s*([A-Z0-9]{5,20})", document[:200000], re.I)
    if number:
        add("company_number", number.group(1))
    return found


def _page_path(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path[:300] or "/"


def _subpages(document: str, page_url: str, domain: str) -> list[str]:
    host = domain.lower().rstrip(".")
    current = _page_path(page_url).rstrip("/") or "/"
    found: list[str] = []
    seen = {current}
    for match in re.finditer(r"<a\b[^>]*>", document[:200000], re.I):
        url, link_host = _public_url(_attr(match.group(0), "href"), page_url)
        if not url or link_host != host:
            continue
        path = urlsplit(url).path.lower()
        if any(path.endswith(ext) for ext in _SKIP_PAGE_EXT):
            continue
        key = _page_path(url).rstrip("/") or "/"
        if key in seen:
            continue
        seen.add(key)
        found.append(parsed_url(url))
        if len(found) >= _SUBPAGE_LIMIT:
            break
    return found


def parsed_url(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return parsed._replace(path=path, fragment="").geturl()[:500]


def _add_subpage(result: CollectionResult, domain: str, url: str, title: str) -> None:
    path = _page_path(url)
    result.entities.append(
        EntityIn(
            entity_type="url",
            normalized_value=url[:512],
            display_value=path[:300],
            source_name="page",
            verification_status="observed",
            metadata={"url": url, "path": path, "host": domain, "title": title},
        )
    )
    result.relationships.append(
        RelIn(
            source_type="domain",
            source_value=domain,
            target_type="url",
            target_value=url[:512],
            rel_type="observed_on_page",
            reason="The public page linked to this same-host page.",
            provenance="page",
            weak_reason="page_markup",
        )
    )


def _attach_page_signals(result: CollectionResult, domain: str, page_url: str, body: str, seo_value: str | None = None) -> None:
    seo = {
        "domain": domain,
        "title": _title(body),
        "description": _meta(body, "description") or _meta(body, "og:description"),
        "keywords": _meta(body, "keywords"),
        "canonical": _canonical(body),
        "robots": _meta(body, "robots"),
        "og_title": _meta(body, "og:title"),
        "og_site_name": _meta(body, "og:site_name"),
        "h1": _heading(body),
        "language": _language(body),
        "page": page_url,
    }
    seo = {key: value for key, value in seo.items() if value}
    if len(seo) > 2 or (seo.get("title") or seo.get("description") or seo.get("h1")):
        result.entities.append(
            EntityIn(
                entity_type="seo",
                normalized_value=(seo_value or domain)[:512],
                display_value=(seo.get("title") or domain)[:300],
                source_name="page",
                verification_status="observed",
                metadata=seo,
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="seo",
                target_value=(seo_value or domain)[:512],
                rel_type="observed_on_page",
                reason="The public page response included these SEO fields.",
                provenance="page",
                weak_reason="page_markup",
            )
        )
    for item in _logos(body, page_url, domain):
        result.entities.append(
            EntityIn(
                entity_type="logo",
                normalized_value=f"{item['kind']}:{item['url']}"[:512],
                display_value=item["kind"].replace("_", " "),
                source_name="page",
                verification_status="observed",
                metadata=item,
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="logo",
                target_value=result.entities[-1].normalized_value,
                rel_type="observed_on_page",
                reason="The public page response referenced this image.",
                provenance="page",
                weak_reason="page_markup",
            )
        )
    for contact in _page_contacts(body):
        result.entities.append(
            EntityIn(
                entity_type="contact",
                normalized_value=f"{contact['kind']}:{contact['value'].lower()}"[:512],
                display_value=contact["value"][:300],
                source_name="page",
                verification_status="observed",
                metadata={"role": contact["kind"], contact["kind"]: contact["value"]},
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="contact",
                target_value=result.entities[-1].normalized_value,
                rel_type="observed_on_page",
                reason="The public page response included this contact.",
                provenance="page",
                weak_reason="page_markup",
            )
        )
    for item in _files(body, page_url, domain):
        name = urlsplit(item["url"]).path.rsplit("/", 1)[-1] or item["kind"]
        result.entities.append(
            EntityIn(
                entity_type="file",
                normalized_value=item["url"][:512],
                display_value=name[:300],
                source_name="page",
                verification_status="observed",
                metadata=item,
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="file",
                target_value=result.entities[-1].normalized_value,
                rel_type="observed_on_page",
                reason="The public page response linked this file.",
                provenance="page",
                weak_reason="page_markup",
            )
        )
    for item in _attributions(body):
        result.entities.append(
            EntityIn(
                entity_type="hypothesis",
                normalized_value=f"{item['kind']}:{item['statement'].lower()}"[:512],
                display_value=item["statement"][:300],
                source_name="page",
                verification_status="observed",
                metadata={
                    **item,
                    "basis": "Observed in the public page response. This does not confirm who operates the host.",
                },
            )
        )
        result.relationships.append(
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="hypothesis",
                target_value=result.entities[-1].normalized_value,
                rel_type="observed_on_page",
                reason="The public page response included this text.",
                provenance="page",
                weak_reason="unverified_claim",
            )
        )


def _kit_parts(document: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    scripts: list[str] = []
    for match in re.finditer(r"<(?:input|select|textarea)\b[^>]*>", document[:200000], re.I):
        name = _attr(match.group(0), "name") or _attr(match.group(0), "id")
        token = re.sub(r"\s+", "", name).lower()[:80]
        if not token or token in GENERIC_FIELDS or token in fields or len(fields) >= 24:
            continue
        fields.append(token)
    for match in re.finditer(r"<script\b[^>]*>", document[:200000], re.I):
        src = _attr(match.group(0), "src")
        if not src:
            continue
        base = urlsplit(urljoin("https://placeholder.invalid/", src)).path.rsplit("/", 1)[-1].lower()
        if script_is_generic(base) or base in scripts or len(scripts) >= 24:
            continue
        scripts.append(base)
    return fields, scripts


def _merge_kit(fields: list[str], scripts: list[str], document: str) -> None:
    more_fields, more_scripts = _kit_parts(document)
    for item in more_fields:
        if item not in fields and len(fields) < 24:
            fields.append(item)
    for item in more_scripts:
        if item not in scripts and len(scripts) < 24:
            scripts.append(item)


def collect_page(domain: str, page_url: str, fetcher=fetch_public_subject) -> CollectionResult:
    try:
        response = fetcher(page_url, domain)
    except UnsafeURL as exc:
        raise ProviderError("page", exc.public_message) from exc
    except Exception as exc:
        raise ProviderError("page", "request failed") from exc
    body = (response.text if response.status_code < 400 else "")[:262144]
    headers = {key: value for key, value in response.headers.items()}
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="domain",
            normalized_value=domain,
            display_value=domain,
            source_name="page",
            verification_status="observed",
            metadata={
                "title": _title(body),
                "description": _meta(body, "description"),
                "server": str(headers.get("server") or ""),
                "technologies": _technologies(body, headers),
                "page_signals": True,
                "panel_records": True,
                "subpages": True,
            },
        )
    )
    _attach_page_signals(result, domain, page_url, body)
    kit_fields: list[str] = []
    kit_scripts: list[str] = []
    _merge_kit(kit_fields, kit_scripts, body)
    if response.status_code < 400:
        for sub_url in _subpages(body, page_url, domain):
            try:
                sub_response = fetcher(sub_url, domain)
            except Exception:
                result.limitations.append("A linked page on the same host could not be retrieved.")
                _add_subpage(result, domain, sub_url, "")
                continue
            sub_body = (sub_response.text if sub_response.status_code < 400 else "")[:262144]
            _add_subpage(result, domain, sub_url, _title(sub_body))
            if sub_body:
                _attach_page_signals(result, domain, sub_url, sub_body, seo_value=sub_url)
                _merge_kit(kit_fields, kit_scripts, sub_body)
    result.entities[0].metadata["kit_fields"] = kit_fields
    result.entities[0].metadata["kit_scripts"] = kit_scripts
    if response.status_code >= 400:
        result.limitations.append("The public page request did not return a readable document.")
    return result
