from datetime import datetime, timezone

from app.connectors.ct import normalize_ct
from app.connectors.dns_connector import collect_dns
from app.connectors.page import collect_page
from app.connectors.rdap import collect_rdap, normalize_rdap, registration_candidates
from app.connectors.ripe import collect_ripe
from app.connectors.wayback import collect_wayback
from app.connectors.urlhaus import normalize_urlhaus
from app.services.graph_analysis import communities, connected_components, resolve_duplicates, shortest_path
from app.services.relationships import extract_certificate_appearance, extract_resolution


class _Answer:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


class _Resolver:
    def resolve(self, domain, record_type, lifetime=None):
        if record_type == "A":
            return [_Answer("198.51.100.8")]
        if record_type == "NS":
            return [_Answer("ns1.example.test.")]
        raise __import__("dns").resolver.NoAnswer()


def test_relationship_extraction_and_certificate_normalisation():
    resolution = extract_resolution("portal.example.test", "A", "198.51.100.8")
    assert resolution is not None
    assert resolution.rel_type == "resolves_to"
    assert resolution.target_value == "198.51.100.8"
    cert_edge = extract_certificate_appearance("portal.example.test", "ab" * 32, "Let's Encrypt")
    assert cert_edge.weak_reason == "common_ca"
    collected = collect_dns("portal.example.test", resolver=_Resolver())
    assert any(entity.normalized_value == "198.51.100.8" for entity in collected.entities)
    ct = normalize_ct(
        "portal.example.test",
        [{"id": "abc", "name_value": "portal.example.test", "issuer_name": "Example CA", "not_before": "2020-01-01"}],
    )
    assert any(entity.entity_type == "certificate" for entity in ct.entities)


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def test_rdap_uses_the_registered_parent_when_the_host_has_no_record():
    assert registration_candidates("www.youtube.com") == ["www.youtube.com", "youtube.com"]
    assert registration_candidates("www.example.co.uk") == ["www.example.co.uk", "example.co.uk"]

    def fetcher(method, url, purpose, timeout=20):
        if url.endswith("/www.youtube.com"):
            return _Response(404)
        return _Response(
            200,
            {
                "events": [
                    {"eventAction": "registration", "eventDate": "2005-02-15T05:13:12Z"},
                    {"eventAction": "expiration", "eventDate": "2027-02-15T05:13:12Z"},
                ],
                "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "MarkMonitor Inc."]]]}],
            },
        )

    result = collect_rdap("www.youtube.com", fetcher=fetcher)
    meta = result.entities[0].metadata
    assert result.entities[0].normalized_value == "www.youtube.com"
    assert meta["registrar"] == "MarkMonitor Inc."
    assert meta["registered_at"].startswith("2005-02-15")
    assert meta["expires_at"].startswith("2027-02-15")
    assert meta["registered_domain"] == "youtube.com"
    assert meta["whois_record"] is True
    assert "email" not in meta
    whois = next(entity for entity in result.entities if entity.entity_type == "whois")
    assert whois.metadata["registrar"] == "MarkMonitor Inc."
    assert whois.metadata["registered_domain"] == "youtube.com"
    assert whois.metadata["expires_at"].startswith("2027-02-15")


class _MailResolver:
    def resolve(self, domain, record_type, lifetime=None):
        if record_type == "A":
            return [_Answer("203.0.113.10")]
        if record_type == "MX":
            return [_Mail("mx.example.com.")]
        if record_type == "TXT" and domain == "example.com":
            return [_Txt(b"v=spf1 mx -all")]
        if record_type == "TXT" and domain == "_dmarc.example.com":
            return [_Txt(b"v=DMARC1; p=reject")]
        raise __import__("dns").resolver.NoAnswer()


class _Mail:
    def __init__(self, exchange: str) -> None:
        self.exchange = exchange

    def __str__(self) -> str:
        return f"10 {self.exchange}"


class _Txt:
    def __init__(self, value: bytes) -> None:
        self.strings = [value]

    def __str__(self) -> str:
        return self.strings[0].decode()


class _JsonResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"server": "cloudflare"}
        self.text = ""

    def json(self) -> object:
        return self._payload


def test_mail_records_stay_on_the_domain():
    collected = collect_dns("example.com", resolver=_MailResolver())
    meta = collected.entities[0].metadata
    assert meta["mx"] == "mx.example.com"
    assert meta["spf"] == "v=spf1 mx -all"
    assert meta["dmarc"] == "v=DMARC1; p=reject"


def test_ripe_wayback_and_page_snapshots_are_labelled():
    def ripe_fetcher(method, url, purpose, timeout=8):
        if "prefix-overview" in url:
            return _JsonResponse({"data": {"resource": "203.0.113.0/24", "asns": [{"asn": 64496, "holder": "Example Net"}]}})
        return _JsonResponse({"data": {"located_resources": [{"locations": [{"country": "US", "city": "San Francisco", "latitude": 37.7, "longitude": -122.4}]}]}})

    ripe = collect_ripe("example.com", ["203.0.113.10"], fetcher=ripe_fetcher)
    ip = next(entity for entity in ripe.entities if entity.entity_type == "ip")
    assert ip.metadata["asn"] == "AS64496"
    assert ip.metadata["prefix"] == "203.0.113.0/24"
    assert ip.metadata["holder"] == "Example Net"
    assert ip.metadata["country"] == "US"
    assert ip.metadata["latitude"] == 37.7
    assert ip.metadata["longitude"] == -122.4
    assert ripe.entities[0].metadata["asn"] == "AS64496"
    assert any(entity.entity_type == "hosting" for entity in ripe.entities)

    wayback = collect_wayback(
        "example.com",
        fetcher=lambda method, url, purpose, timeout=20: _JsonResponse(
            [["timestamp", "original", "statuscode"], ["20050215051312", "https://example.com/", "200"]]
        ),
    )
    assert wayback.entities[0].metadata["wayback"][0]["timestamp"] == "20050215051312"

    class _Page:
        status_code = 200
        headers = {"server": "cloudflare"}
        text = (
            "<html lang=\"en\"><title>Example</title>"
            "<meta name=\"description\" content=\"A sample page\">"
            "<meta name=\"generator\" content=\"WordPress 6\">"
            "<link rel=\"icon\" href=\"/favicon.ico\">"
            "<meta property=\"og:image\" content=\"https://cdn.example.net/brand.png\">"
            "<img src=\"/assets/logo.svg\" alt=\"Company logo\" class=\"logo\">"
            "<h1>Welcome</h1><p>Founded by Ada Example. Company No: 12345678. © 2024 Example Holdings</p>"
            "<a href=\"/about\">About</a><a href=\"mailto:hostmaster@example.com\">mail</a>"
            "<script src=\"/app.js\"></script><a href=\"/files/report.pdf\">pdf</a>"
            "<div>wp-content</div></html>"
        )

    page = collect_page("example.com", "https://example.com/", fetcher=lambda url, host: _Page())
    assert page.entities[0].metadata["title"] == "Example"
    assert page.entities[0].metadata["page_signals"] is True
    assert page.entities[0].metadata["panel_records"] is True
    assert page.entities[0].metadata["subpages"] is True
    subpage = next(entity for entity in page.entities if entity.entity_type == "url")
    assert subpage.display_value == "/about"
    assert any(entity.entity_type == "seo" and entity.normalized_value.startswith("https://example.com/about") for entity in page.entities)
    assert not any(entity.entity_type == "contact" and "hostmaster@example.com" in entity.display_value for entity in page.entities)
    assert any(entity.entity_type == "file" and entity.display_value == "app.js" for entity in page.entities)
    assert any(entity.entity_type == "file" and entity.display_value == "report.pdf" for entity in page.entities)
    assert any(entity.entity_type == "hypothesis" and "Ada Example" in entity.display_value for entity in page.entities)
    assert any(entity.entity_type == "hypothesis" and entity.metadata["kind"] == "company_number" for entity in page.entities)
    assert "WordPress" in page.entities[0].metadata["technologies"]
    assert "Cloudflare" in page.entities[0].metadata["technologies"]
    seo = next(entity for entity in page.entities if entity.entity_type == "seo")
    assert seo.metadata["description"] == "A sample page"
    assert seo.metadata["h1"] == "Welcome"
    assert seo.metadata["language"] == "en"
    logos = [entity for entity in page.entities if entity.entity_type == "logo"]
    assert {entity.metadata["kind"] for entity in logos} == {"favicon", "open_graph", "logo"}
    favicon = next(entity for entity in logos if entity.metadata["kind"] == "favicon")
    assert favicon.metadata["url"] == "https://example.com/favicon.ico"
    assert favicon.metadata["same_host"] is True
    assert any(rel.rel_type == "observed_on_page" and rel.weak_reason == "page_markup" for rel in page.relationships)


def test_rdap_and_urlhaus_normalisation():
    rdap = normalize_rdap(
        "portal.example.test",
        {
            "ldhName": "portal.example.test",
            "handle": "D123",
            "status": ["active"],
            "secureDNS": {"delegationSigned": False},
            "nameservers": [{"ldhName": "ns1.example.test."}, {"ldhName": "ns2.example.test."}],
            "events": [
                {"eventAction": "registration", "eventDate": "2020-01-02T00:00:00Z"},
                {"eventAction": "expiration", "eventDate": "2026-01-02T00:00:00Z"},
                {"eventAction": "last changed", "eventDate": "2024-03-01T00:00:00Z"},
            ],
            "entities": [
                {
                    "roles": ["registrar"],
                    "publicIds": [{"type": "IANA Registrar ID", "identifier": "1234"}],
                    "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar LLC"], ["url", {}, "uri", "https://registrar.example.test"]]],
                    "entities": [
                        {"roles": ["abuse"], "vcardArray": ["vcard", [["email", {}, "text", "abuse@registrar.example.test"], ["tel", {}, "text", "+1.5550100"]]]},
                    ],
                },
                {"roles": ["registrant"], "vcardArray": ["vcard", [["fn", {}, "text", "Demonstration Holdings"], ["email", {}, "text", "hostmaster@portal.example.test"]]]},
            ],
        },
    )
    meta = rdap.entities[0].metadata
    assert meta["registrar"] == "Example Registrar LLC"
    assert meta["registered_at"] == "2020-01-02T00:00:00Z"
    assert meta["expires_at"] == "2026-01-02T00:00:00Z"
    assert meta["registration_contacts"] is True
    assert meta["whois_record"] is True
    whois = next(entity for entity in rdap.entities if entity.entity_type == "whois")
    assert whois.metadata["registrar"] == "Example Registrar LLC"
    assert whois.metadata["registrar_url"] == "https://registrar.example.test"
    assert whois.metadata["registry_id"] == "1234"
    assert whois.metadata["expires_at"] == "2026-01-02T00:00:00Z"
    assert whois.metadata["changed_at"] == "2024-03-01T00:00:00Z"
    assert whois.metadata["status"] == "active"
    assert whois.metadata["dnssec"] == "unsigned"
    assert whois.metadata["nameservers"] == "ns1.example.test, ns2.example.test"
    assert whois.metadata["registrant"] == "Demonstration Holdings"
    assert "abuse_email" not in whois.metadata
    assert "registrant_email" not in whois.metadata
    contact = next(entity for entity in rdap.entities if entity.entity_type == "contact" and entity.metadata["name"] == "Demonstration Holdings")
    assert contact.metadata["role"] == "registrant"
    assert "email" not in contact.metadata
    urlhaus = normalize_urlhaus("portal.example.test", {"query_status": "no_results"})
    assert urlhaus.limitations
    matched = normalize_urlhaus(
        "portal.example.test",
        {"query_status": "is_host", "urls": [{"id": "1", "url": "https://portal.example.test/a", "threat": "phishing"}]},
    )
    assert matched.indicators[0].actor_name is None
    assert matched.indicators[0].status == "confirmed"


def test_graph_algorithms_are_reproducible():
    nodes = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("b", "c")]
    components = connected_components(nodes, edges)
    assert ["d"] in components
    assert shortest_path(nodes, edges, "a", "c") == ["a", "b", "c"]
    assert shortest_path(nodes, edges, "a", "d") == []
    assert communities(nodes, edges)["a"] == communities(nodes, edges)["b"]
    resolved = resolve_duplicates(
        [
            {"entity_type": "domain", "normalized_value": "a.example.test", "last_observed": datetime(2020, 1, 1, tzinfo=timezone.utc)},
            {"entity_type": "domain", "normalized_value": "a.example.test", "last_observed": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]
    )
    assert len(resolved) == 1
    assert resolved[0]["last_observed"].year == 2024
