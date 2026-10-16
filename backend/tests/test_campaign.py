from types import SimpleNamespace

from app.connectors.base import CollectionResult, EntityIn, RelIn
from app.connectors.page import collect_page
from app.models import Investigation
from app.services.campaign import artifacts_from, infrastructure_timeline, is_public_nameserver, rank_expansion
from app.services.persist import persist_collection

from tests.conftest import login


def _entity(**kwargs):
    payload = {"id": "e1", "metadata_json": {}, "display_value": "", "normalized_value": ""}
    payload.update(kwargs)
    return SimpleNamespace(**payload)


def test_generic_infrastructure_is_not_a_fingerprint():
    assert is_public_nameserver("ns1.cloudflare.com")
    assert not is_public_nameserver("ns1.rare-kit.test")
    found = artifacts_from(
        [
            _entity(entity_type="nameserver", normalized_value="ns1.cloudflare.com", display_value="ns1.cloudflare.com"),
            _entity(
                id="c1",
                entity_type="contact",
                normalized_value="email:withheld@privacy.test",
                display_value="withheld",
                metadata_json={"redacted": True},
            ),
            _entity(
                entity_type="domain",
                normalized_value="login.example",
                display_value="login.example",
                metadata_json={"kit_fields": ["email", "password"], "kit_scripts": ["jquery.min.js"]},
            ),
        ]
    )
    assert found == []


def test_kit_fingerprint_ignores_host_and_field_order():
    first = artifacts_from(
        [
            _entity(
                entity_type="domain",
                normalized_value="one.example",
                display_value="one.example",
                metadata_json={"kit_fields": ["cvv", "cardnumber"], "kit_scripts": ["checkout-kit.js"]},
            )
        ]
    )
    second = artifacts_from(
        [
            _entity(
                entity_type="domain",
                normalized_value="two.example",
                display_value="two.example",
                metadata_json={"kit_fields": ["cardnumber", "cvv"], "kit_scripts": ["checkout-kit.js"]},
            )
        ]
    )
    assert first[0].kind == "kit"
    assert first[0].key == second[0].key


def test_timeline_uses_source_dates():
    events = infrastructure_timeline(
        [
            _entity(
                id="d1",
                entity_type="domain",
                normalized_value="one.example",
                metadata_json={"registered_at": "2024-03-01T00:00:00Z", "wayback": [{"timestamp": "20240302000000"}, {"timestamp": "20240401000000"}]},
            ),
            _entity(id="c1", entity_type="certificate", normalized_value="cert", metadata_json={"not_before": "2024-03-02"}),
        ],
        "one.example",
    )
    kinds = [event["kind"] for event in events]
    assert kinds == ["registration", "certificate", "wayback", "wayback"]
    assert events[0]["at"] == "2024-03-01"
    assert events[2]["at"] == "2024-03-02"
    assert events[3]["label"] == "Latest stored Wayback capture"


def test_expansion_ranks_a_rare_artifact_ahead_of_public_dns():
    root = _entity(id="root", entity_type="domain", display_value="one.example", normalized_value="one.example", degree=2)
    fingerprint = _entity(id="fp", entity_type="fingerprint", display_value="Kit structure", normalized_value="kit:abc", degree=1)
    nameserver = _entity(id="ns", entity_type="nameserver", display_value="ns1.cloudflare.com", normalized_value="ns1.cloudflare.com", degree=1)
    rare = SimpleNamespace(source_entity_id="root", target_entity_id="fp", rel_type="matches_kit", weak_reason=None)
    public = SimpleNamespace(source_entity_id="root", target_entity_id="ns", rel_type="uses_nameserver", weak_reason=None)
    ranked = rank_expansion("root", [public, rare], {"root": root, "fp": fingerprint, "ns": nameserver})
    assert ranked[0]["entity_id"] == "fp"
    assert ranked[0]["weak"] is False
    assert ranked[-1]["entity_id"] == "ns"
    assert ranked[-1]["weak"] is True


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200
        self.headers = {}


def test_page_records_distinctive_kit_parts():
    document = """
        <form>
          <input name="cardNumber">
          <input name="cvv">
          <input name="email">
        </form>
        <script src="https://cdn.example/jquery.min.js"></script>
        <script src="/assets/checkout-kit.js"></script>
    """
    page = collect_page("kit.example", "https://kit.example/", fetcher=lambda url, host: _Page(document))
    assert page.entities[0].metadata["kit_fields"] == ["cardnumber", "cvv"]
    assert page.entities[0].metadata["kit_scripts"] == ["checkout-kit.js"]


def _collection(domain: str) -> CollectionResult:
    return CollectionResult(
        entities=[
            EntityIn(
                entity_type="domain",
                normalized_value=domain,
                display_value=domain,
                source_name="page",
                metadata={
                    "kit_fields": ["cardnumber", "cvv"],
                    "kit_scripts": ["checkout-kit.js"],
                    "registered_at": "2024-03-01T00:00:00Z",
                    "wayback": [{"timestamp": "20240302000000"}],
                },
            ),
            EntityIn(
                entity_type="nameserver",
                normalized_value="ns1.cloudflare.com",
                display_value="ns1.cloudflare.com",
                source_name="dns",
            ),
            EntityIn(
                entity_type="certificate",
                normalized_value=f"cert-{domain}",
                display_value=domain,
                source_name="certificate_transparency",
                metadata={"not_before": "2024-03-02T00:00:00Z"},
            ),
        ],
        relationships=[
            RelIn(
                source_type="domain",
                source_value=domain,
                target_type="nameserver",
                target_value="ns1.cloudflare.com",
                rel_type="uses_nameserver",
                reason="DNS NS record.",
                provenance="dns",
            )
        ],
    )


def test_saved_case_match_timeline_and_handoff(client):
    from app import db as dbmod

    headers = login(client)
    first = client.post("/api/investigations", json={"indicator": "kit-one.example"}, headers=headers)
    assert first.status_code == 202, first.text
    first_id = first.json()["id"]
    db = dbmod.SessionLocal()
    investigation = db.get(Investigation, first_id)
    investigation.is_demonstration = False
    persist_collection(db, investigation, _collection("kit-one.example"))
    investigation.is_saved = True
    db.commit()
    db.close()

    second = client.post("/api/investigations", json={"indicator": "kit-two.example"}, headers=headers)
    assert second.status_code == 202, second.text
    second_id = second.json()["id"]
    db = dbmod.SessionLocal()
    investigation = db.get(Investigation, second_id)
    investigation.is_demonstration = False
    persist_collection(db, investigation, _collection("kit-two.example"))
    root_id = investigation.root_entity_id
    db.commit()
    db.close()

    graph = client.get(f"/api/investigations/{second_id}/graph")
    assert graph.status_code == 200
    campaign = graph.json()["campaign"]
    assert campaign["active"] is True
    assert campaign["domain_count"] == 1
    assert campaign["matches"][0]["artifact_kind"] == "kit"
    assert campaign["matches"][0]["saved_indicator"] == "kit-one.example"
    assert any(event["kind"] == "registration" and event["subject"] == "kit-one.example" for event in campaign["timeline"])
    assert not any(node["normalized_value"] == "ns:ns1.cloudflare.com" for node in graph.json()["nodes"])

    expanded = client.post(f"/api/investigations/{second_id}/graph/expand?entity_id={root_id}", headers=headers)
    assert expanded.status_code == 200
    suggestions = expanded.json()["suggestions"]
    assert suggestions[0]["weak"] is False
    assert suggestions[-1]["label"] == "ns1.cloudflare.com"
    assert suggestions[-1]["weak"] is True

    handoff = client.get(f"/api/investigations/{second_id}/export?format=handoff")
    assert handoff.status_code == 200
    body = handoff.json()
    assert any("does not assert that an asset is malicious" in line for line in body["not_claimed"])
    assert any(claim["observations"] for claim in body["claims"])
    assert "attachment" in handoff.headers["content-disposition"]
