import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
FINGERPRINT_RE = re.compile(r"^[a-f0-9]{64}$")
INDICATOR_HINT = "Enter a domain, URL, IP address, certificate fingerprint, or full name."
_NAME_WORD = re.compile(r"^[a-z][a-z'.-]{0,40}$")
BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".arpa")
BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.internal"}
DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)


class InvalidIndicator(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message


def _blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if isinstance(ip, ipaddress.IPv4Address) and any(ip in network for network in DOCUMENTATION_NETWORKS):
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def is_domain(value: str) -> bool:
    if value in BLOCKED_HOSTS or value.endswith(BLOCKED_SUFFIXES):
        return False
    return DOMAIN_RE.match(value) is not None


def person_name(value: str) -> str | None:
    words = re.sub(r"\s+", " ", value.strip().lower()).split(" ")
    if len(words) < 2 or len(words) > 4:
        return None
    if any(_NAME_WORD.match(word) is None for word in words):
        return None
    return " ".join(words)


def classify_indicator(raw: str) -> tuple[str, str]:
    value = (raw or "").strip()
    if not value or len(value) > 512 or any(char in value for char in "\x00\r\n"):
        raise InvalidIndicator(INDICATOR_HINT)
    if "@" in value and "://" not in value:
        raise InvalidIndicator("Email addresses are not investigated.")

    if "://" in value:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"}:
            raise InvalidIndicator("Only http and https URLs are supported.")
        if parts.username or parts.password:
            raise InvalidIndicator("URLs with credentials are not supported.")
        host = (parts.hostname or "").lower().rstrip(".")
        if not is_domain(host):
            raise InvalidIndicator("That URL is not valid.")
        port = f":{parts.port}" if parts.port else ""
        path = parts.path or "/"
        query = parts.query
        normalized = urlunsplit((parts.scheme.lower(), host + port, path, query, ""))
        return "url", normalized

    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        ip = None
    if ip is not None:
        if _blocked_ip(ip):
            raise InvalidIndicator("That IP address cannot be investigated.")
        return "ip", str(ip)

    fingerprint = value.lower().replace(":", "")
    if FINGERPRINT_RE.match(fingerprint):
        return "certificate", fingerprint

    domain = value.lower().rstrip(".")
    if is_domain(domain):
        return "domain", domain
    name = person_name(value)
    if name:
        return "name", name
    raise InvalidIndicator("That indicator is not valid.")
