"""Tests for POST /admin/reload-tenants endpoint (task 6.2)."""

import hashlib
import json

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from m_shared.routes.admin import router as admin_router
from m_shared.tenant import TenantRegistry

ENCRYPTION_KEY = Fernet.generate_key().decode()
FERNET = Fernet(ENCRYPTION_KEY.encode())
API_SECRET = "test-global-secret"


def _make_tenant_file(tmp_path, slugs=("faculty-a",)):
    tenants = {}
    for slug in slugs:
        secret = f"secret-{slug}"
        tenants[slug] = {
            "name": slug.title(),
            "api_secret_hash": f"sha256:{hashlib.sha256(secret.encode()).hexdigest()}",
            "api_key_encrypted": FERNET.encrypt(f"key-{slug}".encode()).decode(),
        }
    path = str(tmp_path / "tenants.json")
    with open(path, "w") as f:
        json.dump({"tenants": tenants}, f)
    return path


@pytest.fixture()
def _env(monkeypatch):
    monkeypatch.setenv("API_SECRET", API_SECRET)


@pytest.fixture()
def app_no_registry(_env):
    app = FastAPI()
    app.include_router(admin_router)
    return app


@pytest.fixture()
def app_with_registry(_env, tmp_path, monkeypatch):
    path = _make_tenant_file(tmp_path, slugs=("faculty-a",))
    monkeypatch.setenv("TENANT_REGISTRY_PATH", path)

    reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
    reg.load(path)

    app = FastAPI()
    app.include_router(admin_router)
    app.state.tenant_registry = reg
    app.state.llm_client_pool = {"default": None}
    return app


class TestReloadEndpoint:
    def test_valid_secret_returns_tenant_count(self, app_with_registry):
        client = TestClient(app_with_registry)
        resp = client.post(
            "/admin/reload-tenants",
            headers={"Authorization": f"Bearer {API_SECRET}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["tenants_loaded"] == 1

    def test_invalid_secret_returns_401(self, app_with_registry):
        client = TestClient(app_with_registry)
        resp = client.post(
            "/admin/reload-tenants",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 401

    def test_missing_secret_returns_401(self, app_with_registry):
        client = TestClient(app_with_registry)
        resp = client.post("/admin/reload-tenants")
        assert resp.status_code == 401

    def test_no_registry_returns_zero(self, app_no_registry):
        client = TestClient(app_no_registry)
        resp = client.post(
            "/admin/reload-tenants",
            headers={"Authorization": f"Bearer {API_SECRET}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenants_loaded"] == 0

    def test_reload_picks_up_new_tenant(self, app_with_registry, tmp_path, monkeypatch):
        path = _make_tenant_file(tmp_path, slugs=("faculty-a", "faculty-b"))
        monkeypatch.setenv("TENANT_REGISTRY_PATH", path)

        client = TestClient(app_with_registry)
        resp = client.post(
            "/admin/reload-tenants",
            headers={"Authorization": f"Bearer {API_SECRET}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenants_loaded"] == 2
