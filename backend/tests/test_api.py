from datetime import datetime, timedelta, timezone

import app.db as dbmod
from app.config import get_settings
from app.api.router import _missing_public_sources
from app.connectors.base import CollectionResult, EntityIn, ProviderError
from app.models import Entity, Investigation, Observation, SourceSetting
from app.services.neo4j_projection import project_investigation
from app.services.persist import ensure_sources, persist_collection
from tests.conftest import login


def test_login_csrf_and_access_control(client):
    from app.seed.run import seed_database

    seed_database()
    opened = client.get("/api/investigations")
    assert opened.status_code == 200
    assert client.get("/api/auth/me").json()["role"] == "analyst"
    created = client.post("/api/investigations", json={"indicator": "other.example.test"})
    assert created.status_code == 202
    analyst_investigation = created.json()["id"]
    headers = login(client)
    missing = client.post("/api/investigations", json={"indicator": "csrf.example.test"})
    assert missing.status_code == 403
    forbidden = client.put("/api/sources/dns", json={"enabled": True}, headers=headers)
    assert forbidden.status_code == 403
    admin_headers = login(client, "admin@piae.test", "admin-password-123")
    owned = client.post("/api/investigations", json={"indicator": "admin-only.example.test"}, headers=admin_headers)
    admin_investigation = owned.json()["id"]
    updated = client.put("/api/sources/dns", json={"enabled": True}, headers=admin_headers)
    assert updated.status_code == 200
    login(client)
    hidden = client.get(f"/api/investigations/{admin_investigation}")
    assert hidden.status_code == 404
    visible = client.get(f"/api/investigations/{analyst_investigation}")
    assert visible.status_code == 200


def test_demo_investigation_export_sort_and_history(client):
    headers = login(client)
    created = client.post("/api/investigations", json={"indicator": "portal.example.test"}, headers=headers)
    assert created.status_code == 202
    current = client.get("/api/investigations/current")
    assert current.status_code == 200
    body = current.json()
    assert body["is_demonstration"] is True
    assert body["entity_count"] == 1
    assert body["relationship_count"] == 0
    entities = client.get(f"/api/investigations/{body['id']}/entities?entity_type=domain&sort=domain")
    names = [item["display_value"] for item in entities.json()["items"]]
    assert names == sorted(names)
    flipped = client.get(f"/api/investigations/{body['id']}/entities?entity_type=domain&sort=domain&direction=desc")
    assert [item["display_value"] for item in flipped.json()["items"]] == list(reversed(names))
    counts = entities.json()["counts"]
    assert counts["domain"] == 1
    assert counts["contact"] == 0
    graph = client.get(f"/api/investigations/{body['id']}/graph")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) == 1
    assert graph.json()["edges"] == []
    exported = client.get(f"/api/investigations/{body['id']}/export?format=csv", headers=headers)
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert "portal.example.test" in exported.text
    report = client.get(f"/api/investigations/{body['id']}/report")
    assert report.json()["narrative_status"] == "skipped"
    assert any("threat actor" in item.lower() for item in report.json()["limitations"])
    history = client.get("/api/investigations")
    assert history.json()["items"][0]["root_indicator"] == "portal.example.test"


def test_rate_limit(client):
    login(client)
    last = None
    for _ in range(12):
        last = client.post("/api/auth/login", json={"email": "analyst@piae.test", "password": "wrong-password-1"})
    assert last is not None
    assert last.status_code == 429


def test_timestamps_are_not_overwritten(client):
    headers = login(client)
    created = client.post("/api/investigations", json={"indicator": "history.example.test"}, headers=headers)
    investigation_id = created.json()["id"]
    db = dbmod.SessionLocal()
    investigation = db.get(Investigation, investigation_id)
    observed = datetime(2020, 1, 2, tzinfo=timezone.utc)
    first = CollectionResult(
        entities=[
            EntityIn(
                entity_type="domain",
                normalized_value="history.example.test",
                display_value="history.example.test",
                observed_at=observed,
                source_name="demonstration",
            )
        ]
    )
    persist_collection(db, investigation, first)
    db.commit()
    later = CollectionResult(
        entities=[
            EntityIn(
                entity_type="domain",
                normalized_value="history.example.test",
                display_value="history.example.test",
                observed_at=observed + timedelta(days=10),
                source_name="dns",
            )
        ]
    )
    persist_collection(db, investigation, later)
    db.commit()
    rows = db.query(Observation).filter(Observation.entity_id == db.query(Entity).filter(Entity.normalized_value == "history.example.test").one().id).all()
    assert len(rows) >= 2
    assert rows[0].observed_at != rows[0].retrieved_at
    assert {row.source_id for row in rows}
    db.close()


def test_provider_failure_and_neo4j_skip(client, monkeypatch):
    headers = login(client)
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    db = dbmod.SessionLocal()
    source = db.get(SourceSetting, "dns")
    source.enabled = True
    db.commit()
    db.close()

    def boom(domain, timeout=3.0, resolver=None):
        raise ProviderError("dns", "down")

    monkeypatch.setattr("app.services.pipeline.collect_dns", boom)
    created = client.post("/api/investigations", json={"indicator": "live.example.com"}, headers=headers)
    assert created.status_code == 202
    body = created.json()
    fetched = client.get(f"/api/investigations/{body['id']}")
    assert fetched.json()["status"] == "completed"
    report = client.get(f"/api/investigations/{body['id']}/report").json()
    assert any("dns" in item.lower() for item in report["limitations"])
    db = dbmod.SessionLocal()
    assert project_investigation(db, body["id"]) is False
    db.close()


def test_completed_page_without_signals_is_collected_again(client):
    headers = login(client)
    created = client.post("/api/investigations", json={"indicator": "signals.example.test"}, headers=headers)
    investigation_id = created.json()["id"]
    db = dbmod.SessionLocal()
    investigation = db.get(Investigation, investigation_id)
    investigation.status = "completed"
    page = db.get(SourceSetting, "page")
    page.enabled = True
    sources = ensure_sources(db)
    entity = db.query(Entity).filter(Entity.investigation_id == investigation_id).one()
    entity.metadata_json = {"mx": "mail.signals.example.test", "title": "Old title"}
    db.add(
        Observation(
            investigation_id=investigation_id,
            entity_id=entity.id,
            source_id=sources["page"].id,
            original_value=entity.display_value,
            normalized_value=entity.normalized_value,
        )
    )
    db.commit()
    assert _missing_public_sources(db, investigation) is True
    entity.metadata_json = {**entity.metadata_json, "page_signals": True, "panel_records": True, "subpages": True}
    db.commit()
    assert _missing_public_sources(db, investigation) is False
    db.close()


def test_logo_image_uses_the_recorded_bytes(client, monkeypatch):
    headers = login(client)
    created = client.post("/api/investigations", json={"indicator": "logo.example.test"}, headers=headers)
    investigation_id = created.json()["id"]
    db = dbmod.SessionLocal()
    investigation = db.get(Investigation, investigation_id)
    persist_collection(
        db,
        investigation,
        CollectionResult(
            entities=[
                EntityIn(
                    entity_type="logo",
                    normalized_value="favicon:https://logo.example.test/favicon.png",
                    display_value="favicon",
                    source_name="page",
                    metadata={"url": "https://logo.example.test/favicon.png", "kind": "favicon"},
                )
            ]
        ),
    )
    db.commit()
    logo = db.query(Entity).filter(Entity.entity_type == "logo").one()
    logo_id = logo.id
    db.close()
    png = b"\x89PNG\r\n\x1a\nrest"
    monkeypatch.setattr("app.api.router.fetch_recorded_image", lambda url: (png, "image/png"))
    image = client.get(f"/api/investigations/{investigation_id}/entities/{logo_id}/image")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content == png
    missing = client.get(f"/api/investigations/{investigation_id}/entities/{investigation_id}/image")
    assert missing.status_code == 404
