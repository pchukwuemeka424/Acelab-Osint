"""Public website checks for a full name.

A page is kept when it contains that name. A match is a lead, not proof of who
operates the site. Generic pages and mail-provider sites are not stored.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from app.connectors.base import CollectionResult, EntityIn, RelIn
from app.security.ssrf import fetch_profile

_CATALOG = Path(__file__).with_name("blindeye_platforms.json")
_GROUP_LIMIT = 10
_GENERAL_LIMIT = 30
_PAGE_STEP = 10
_SITE_LIMIT = _GENERAL_LIMIT
_SEARCH = "https://html.duckduckgo.com/html/?q={query}"
_READER = "https://r.jina.ai/{url}"
_UDDG = re.compile(r"uddg=([^&\"'\s)]+)")
WEB_SEARCH_UNAVAILABLE = "A public web search for websites containing this name could not be completed."
SITE_GROUPS = (
    (
        "social",
        (
            "x.com",
            "twitter.com",
            "facebook.com",
            "instagram.com",
            "tiktok.com",
            "reddit.com",
            "threads.net",
            "pinterest.com",
            "snapchat.com",
            "youtube.com",
        ),
    ),
    (
        "jobs",
        (
            "linkedin.com",
            "indeed.com",
            "glassdoor.com",
            "monster.com",
            "ziprecruiter.com",
        ),
    ),
    (
        "adult",
        (
            "onlyfans.com",
            "fansly.com",
            "pornhub.com",
            "xvideos.com",
            "xnxx.com",
            "chaturbate.com",
        ),
    ),
)

FREE_MAIL = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "ymail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "aol.com",
        "gmx.com",
        "gmx.net",
        "mail.com",
        "zoho.com",
        "yandex.com",
        "yandex.ru",
        "fastmail.com",
        "tutanota.com",
        "tuta.com",
    }
)
_SKIP_HOSTS = FREE_MAIL | {
    "duckduckgo.com",
    "www.duckduckgo.com",
    "html.duckduckgo.com",
    "google.com",
    "www.google.com",
    "bing.com",
    "www.bing.com",
}


@lru_cache
def load_platforms() -> tuple[dict, ...]:
    payload = json.loads(_CATALOG.read_text())
    platforms = []
    for item in payload["platforms"]:
        url = str(item.get("url") or "")
        name = str(item.get("name") or "").strip()
        if not name or "{}" not in url or not url.startswith("https://"):
            continue
        platforms.append(
            {
                "name": name,
                "url": url,
                "category": str(item.get("category") or "other"),
                "check": str(item.get("check") or "profile"),
            }
        )
    return tuple(platforms)


def profile_url(template: str, handle: str) -> str:
    return template.replace("{}", quote(handle, safe=""))


def page_has_name(body: str, name: str) -> bool:
    compact = re.sub(r"\s+", " ", body.lower())
    return bool(name) and name.lower() in compact



def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _group_for(host: str, fallback: str) -> str:
    for name, hosts in SITE_GROUPS:
        if host in hosts or any(host.endswith(f".{item}") for item in hosts):
            return name
    return fallback


def _search_url(query: str, offset: int = 0) -> str:
    url = _SEARCH.format(query=quote(query, safe=""))
    if offset:
        return f"{url}&s={offset}"
    return url


def search_is_blocked(status_code: int, body: str) -> bool:
    """DuckDuckGo answers automated lookups with a challenge page and no result links."""
    if status_code == 202:
        return True
    lowered = body.lower()
    return "bots use duckduckgo" in lowered or "confirm this search was made by a human" in lowered


def search_hits(text: str, limit: int = _SITE_LIMIT) -> list[tuple[str, str]]:
    """HTTPS result links and the nearby snippet, without search and mail hosts."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _UDDG.finditer(text):
        url = unquote(match.group(1)).split("#", 1)[0]
        host = _host(url)
        if not url.startswith("https://") or not host or host in _SKIP_HOSTS or host.endswith(".google.com"):
            continue
        if url in seen:
            continue
        seen.add(url)
        window = text[match.end() : match.end() + 800]
        window = re.sub(r"<[^>]+>", " ", window)
        window = re.sub(r"\s+", " ", window).strip()
        nxt = window.find("uddg")
        if nxt > 0:
            window = window[:nxt].strip()
        found.append((url, window[:500]))
        if len(found) >= limit:
            break
    return found


def search_result_urls(html: str, limit: int = _SITE_LIMIT) -> list[str]:
    """HTTPS result links from a DuckDuckGo HTML page, without search and mail hosts."""
    return [url for url, _snippet in search_hits(html, limit)]


def _response_text(fetch, url: str) -> tuple[int, str] | None:
    try:
        response = fetch(url)
    except Exception:
        return None
    return getattr(response, "status_code", 0), getattr(response, "text", "") or ""


def _usable_search(status_code: int, body: str) -> bool:
    return status_code == 200 and not search_is_blocked(status_code, body)


def load_search(fetch, query: str, offset: int = 0) -> tuple[str | None, bool]:
    """Return the result page. A challenge retries once through the reader.

    The second value is True when both the direct request and the reader fail.
    """
    direct = _response_text(fetch, _search_url(query, offset))
    if direct is not None and _usable_search(direct[0], direct[1]):
        return direct[1], False
    reader = _response_text(fetch, _READER.format(url=_search_url(query, offset)))
    if reader is not None and _usable_search(reader[0], reader[1]):
        return reader[1], False
    return None, True


def _collect_mentions(
    query: str,
    *,
    match,
    root_type: str,
    root_value: str,
    handle: str,
    empty_message: str,
    fetch,
    blocked_message: str = WEB_SEARCH_UNAVAILABLE,
) -> CollectionResult:
    """Public pages whose text matches the query. Search hosts and mail providers are skipped."""
    result = CollectionResult()
    kept: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()
    seen_hosts: set[str] = set()
    searched = False

    def consider(url: str, snippet: str, group: str) -> None:
        seen_urls.add(url)
        host = _host(url)
        if not host or host in seen_hosts or host in _SKIP_HOSTS or host.endswith(".google.com"):
            return
        seen_hosts.add(host)
        confirmed = match(snippet)
        if not confirmed:
            fetched = _response_text(fetch, url)
            confirmed = fetched is not None and fetched[0] == 200 and match(fetched[1])
        if confirmed:
            kept.append((host, url, _group_for(host, group)))

    for group, hosts in SITE_GROUPS:
        group_hits = 0
        for host in hosts:
            if group_hits >= _GROUP_LIMIT:
                break
            body, blocked = load_search(fetch, f'"{query}" site:{host}')
            if blocked or body is None:
                continue
            searched = True
            for url, snippet in search_hits(body, _GROUP_LIMIT - group_hits):
                group_hits += 1
                consider(url, snippet, group)
                if group_hits >= _GROUP_LIMIT:
                    break

    offset = 0
    candidates = 0
    while candidates < _GENERAL_LIMIT:
        body, blocked = load_search(fetch, f'"{query}"', offset)
        if blocked or body is None:
            break
        searched = True
        added = 0
        for url, snippet in search_hits(body, _GENERAL_LIMIT):
            if url in seen_urls:
                continue
            if candidates >= _GENERAL_LIMIT:
                break
            candidates += 1
            added += 1
            consider(url, snippet, "web")
        if added == 0:
            break
        offset += _PAGE_STEP

    for host, url, group in kept:
        normalized = f"website:{host}"[:512]
        result.entities.append(
            EntityIn(
                entity_type="account",
                normalized_value=normalized,
                display_value=host,
                risk_state="contextual",
                source_name="profiles",
                verification_status="observed",
                confidence="reported",
                metadata={
                    "platform": host,
                    "category": "website",
                    "group": group,
                    "url": url,
                    "handle": handle,
                    "lead": root_type,
                },
            )
        )
        result.relationships.append(
            RelIn(
                source_type=root_type,
                source_value=root_value,
                target_type="account",
                target_value=normalized,
                rel_type="has_account",
                reason=f"A public page on {host} contains {query}.",
                risk_state="contextual",
                weak_reason="public_handle",
                provenance="profiles",
            )
        )
    if not searched:
        result.limitations.append(blocked_message)
    elif not kept:
        result.limitations.append(empty_message)
    return result


def collect_name_websites(name: str, *, fetch=fetch_profile) -> CollectionResult:
    """Public pages that contain this full name. A matching page is a lead to verify."""
    return _collect_mentions(
        name,
        match=lambda body: page_has_name(body, name),
        root_type="name",
        root_value=name,
        handle="",
        empty_message="No public page contained this name.",
        blocked_message="A public web search for websites containing this name could not be completed.",
        fetch=fetch,
    )
