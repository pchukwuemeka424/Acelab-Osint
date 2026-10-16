"""Outbound request guards.

Collectors may call only allowlisted HTTPS hosts. Destination addresses are
resolved before the request and again immediately before connect. Loopback,
private, link-local, multicast, reserved, and non-global addresses are refused.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import httpx

ALLOWED_HOSTS = {
    "openrouter.ai": {"openrouter"},
    "rdap.org": {"rdap"},
    "crt.sh": {"ct"},
    "urlhaus-api.abuse.ch": {"urlhaus"},
    "stat.ripe.net": {"ripe"},
    "web.archive.org": {"wayback"},
}

Resolver = Callable[[str, int], list]


class UnsafeURL(Exception):
    def __init__(self, message: str = "That outbound request is not allowed.") -> None:
        super().__init__(message)
        self.public_message = message


def is_blocked_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (
        ip.is_multicast
        or ip.is_unspecified
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_reserved
        or not ip.is_global
    ):
        return True
    return False


def _resolve(host: str, resolver: Resolver) -> list[str]:
    try:
        records = resolver(host, 443)
    except socket.gaierror as exc:
        raise UnsafeURL("The destination could not be resolved.") from exc
    addresses = []
    for record in records:
        sockaddr = record[4]
        addresses.append(sockaddr[0])
    if not addresses:
        raise UnsafeURL("The destination could not be resolved.")
    return addresses


def assert_public_https(url: str, resolver: Resolver = socket.getaddrinfo) -> list[str]:
    """Check a one-hop RDAP bootstrap target. The host is not on the provider allowlist."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeURL("Only HTTPS destinations are allowed.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Destinations with credentials are not allowed.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host in {"localhost", "metadata.google.internal", "metadata.internal"}:
        raise UnsafeURL("The destination resolved to a blocked address.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if is_blocked_ip(host):
            raise UnsafeURL("The destination resolved to a blocked address.")
    first = _resolve(host, resolver)
    second = _resolve(host, resolver)
    for address in [*first, *second]:
        if is_blocked_ip(address):
            raise UnsafeURL("The destination resolved to a blocked address.")
    return second


def rdap_redirect_url(current_url: str, location: str) -> str:
    current = urlsplit(current_url)
    if (current.hostname or "").lower() != "rdap.org":
        raise UnsafeURL("Redirects are not followed.")
    target = urljoin(current_url, location)
    parsed = urlsplit(target)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        raise UnsafeURL("Redirects are not followed.")
    return target


def assert_safe_url(url: str, purpose: str, resolver: Resolver = socket.getaddrinfo) -> list[str]:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeURL("Only HTTPS destinations are allowed.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Destinations with credentials are not allowed.")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS or purpose not in ALLOWED_HOSTS[host]:
        raise UnsafeURL("That destination is not an approved provider.")
    first = _resolve(host, resolver)
    second = _resolve(host, resolver)
    for address in [*first, *second]:
        if is_blocked_ip(address):
            raise UnsafeURL("The destination resolved to a blocked address.")
    return second


def assert_subject_url(url: str, expected_host: str, resolver: Resolver = socket.getaddrinfo) -> str:
    """Allow one request to the investigation host. Private and metadata addresses are refused."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("Only http and https destinations are allowed.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Destinations with credentials are not allowed.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if host != expected_host.lower().rstrip("."):
        raise UnsafeURL("That destination is not the investigation host.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if is_blocked_ip(host):
            raise UnsafeURL("The destination resolved to a blocked address.")
    first = _resolve(host, resolver)
    second = _resolve(host, resolver)
    for address in [*first, *second]:
        if is_blocked_ip(address):
            raise UnsafeURL("The destination resolved to a blocked address.")
    return host


def same_host_redirect(current_url: str, location: str, expected_host: str) -> str:
    target = urljoin(current_url, location)
    parsed = urlsplit(target)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or host != expected_host.lower().rstrip("."):
        raise UnsafeURL("Redirects are not followed.")
    return target


def assert_public_destination(url: str, resolver: Resolver = socket.getaddrinfo) -> str:
    """Allow one image fetch to a public host. Private and metadata addresses are refused."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("Only http and https destinations are allowed.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Destinations with credentials are not allowed.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host in {"localhost", "metadata.google.internal", "metadata.internal"}:
        raise UnsafeURL("The destination resolved to a blocked address.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if is_blocked_ip(host):
            raise UnsafeURL("The destination resolved to a blocked address.")
    first = _resolve(host, resolver)
    second = _resolve(host, resolver)
    for address in [*first, *second]:
        if is_blocked_ip(address):
            raise UnsafeURL("The destination resolved to a blocked address.")
    return host


def _image_media_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    return None


def fetch_recorded_image(
    url: str,
    *,
    timeout: float = 8.0,
    resolver: Resolver = socket.getaddrinfo,
    limit: int = 524288,
) -> tuple[bytes, str]:
    assert_public_destination(url, resolver=resolver)
    headers = {"User-Agent": "PIAE", "Accept": "image/*"}
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        response = client.get(url, headers=headers)
        if response.status_code in {301, 302, 303, 307, 308}:
            target = urljoin(url, response.headers.get("location") or "")
            assert_public_destination(target, resolver=resolver)
            response = client.get(target, headers=headers)
    if response.status_code != 200 or not response.content or len(response.content) > limit:
        raise UnsafeURL("The image could not be retrieved.")
    media_type = _image_media_type(response.content)
    if media_type is None:
        raise UnsafeURL("The image could not be retrieved.")
    return response.content, media_type


def fetch_profile(
    url: str,
    *,
    timeout: float = 10.0,
    resolver: Resolver = socket.getaddrinfo,
    limit: int = 1_000_000,
) -> httpx.Response:
    """Fetch one public profile page. One same-host redirect is allowed. Private addresses are refused."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeURL("Only HTTPS destinations are allowed.")
    host = assert_public_destination(url, resolver=resolver)
    reader = host == "r.jina.ai"
    headers = {
        "User-Agent": "Mozilla/5.0" if reader else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/plain" if reader else "text/html,application/xhtml+xml",
    }
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        response = client.get(url, headers=headers)
        if response.status_code in {301, 302, 303, 307, 308}:
            target = same_host_redirect(url, response.headers.get("location") or "", host)
            if urlsplit(target).scheme != "https":
                raise UnsafeURL("Only HTTPS destinations are allowed.")
            assert_public_destination(target, resolver=resolver)
            response = client.get(target, headers=headers)
            url = target
    if response.status_code in {301, 302, 303, 307, 308}:
        raise UnsafeURL("Redirects are not followed.")
    assert_public_destination(url, resolver=resolver)
    if len(response.content) > limit:
        response._content = response.content[:limit]
    return response


def fetch_public_subject(
    url: str,
    expected_host: str,
    *,
    timeout: float = 8.0,
    resolver: Resolver = socket.getaddrinfo,
    limit: int = 262144,
) -> httpx.Response:
    assert_subject_url(url, expected_host, resolver=resolver)
    headers = {"User-Agent": "PIAE"}
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        response = client.get(url, headers=headers)
        if response.status_code in {301, 302, 303, 307, 308}:
            target = same_host_redirect(url, response.headers.get("location") or "", expected_host)
            assert_subject_url(target, expected_host, resolver=resolver)
            response = client.get(target, headers=headers)
            url = target
    if response.status_code in {301, 302, 303, 307, 308}:
        raise UnsafeURL("Redirects are not followed.")
    assert_subject_url(url, expected_host, resolver=resolver)
    if len(response.content) > limit:
        response._content = response.content[:limit]
    return response


def guarded_request(
    method: str,
    url: str,
    purpose: str,
    *,
    headers: dict | None = None,
    json_body: dict | None = None,
    timeout: float = 8.0,
    resolver: Resolver = socket.getaddrinfo,
) -> httpx.Response:
    assert_safe_url(url, purpose, resolver=resolver)
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        response = client.request(method, url, headers=headers, json=json_body)
        if response.status_code in {301, 302, 303, 307, 308} and purpose == "rdap":
            target = rdap_redirect_url(url, response.headers.get("location") or "")
            target_host = (urlsplit(target).hostname or "").lower()
            if target_host in ALLOWED_HOSTS:
                assert_safe_url(target, purpose, resolver=resolver)
            else:
                assert_public_https(target, resolver=resolver)
            response = client.request(method, target, headers=headers, json=json_body)
            url = target
    if response.status_code in {301, 302, 303, 307, 308}:
        raise UnsafeURL("Redirects are not followed.")
    target_host = (urlsplit(url).hostname or "").lower()
    if target_host in ALLOWED_HOSTS:
        assert_safe_url(url, purpose, resolver=resolver)
    else:
        assert_public_https(url, resolver=resolver)
    return response
