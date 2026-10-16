import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["INVESTIGATION_EAGER"] = "true"
os.environ["AUTO_CREATE"] = "true"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DEBUG"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["DNS_ENABLED"] = "false"
os.environ["RDAP_ENABLED"] = "false"
os.environ["CT_ENABLED"] = "false"
os.environ["RIPE_ENABLED"] = "false"
os.environ["WAYBACK_ENABLED"] = "false"
os.environ["PAGE_ENABLED"] = "false"
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["ANALYST_EMAIL"] = "analyst@piae.test"
os.environ["ANALYST_PASSWORD"] = "test-password-123"
os.environ["ADMIN_EMAIL"] = "admin@piae.test"
os.environ["ADMIN_PASSWORD"] = "admin-password-123"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/piae.db")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    monkeypatch.setenv("AUTO_CREATE", "true")
    monkeypatch.setenv("INVESTIGATION_EAGER", "true")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    from app.security.rate_limit import limiter

    limiter.reset()
    init_db(get_settings())
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def login(client: TestClient, email: str = "analyst@piae.test", password: str = "test-password-123") -> dict:
    from app.seed.run import seed_database

    seed_database()
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    csrf = client.cookies.get("piae_csrf")
    return {"X-CSRF-Token": csrf}
