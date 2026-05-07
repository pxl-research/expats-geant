"""Tests for m_shared.tenant.registry."""

import hashlib
import json

import pytest
from cryptography.fernet import Fernet

from m_shared.tenant.registry import TenantRegistry, resolve_org

ENCRYPTION_KEY = Fernet.generate_key().decode()
FERNET = Fernet(ENCRYPTION_KEY.encode())

TENANT_SECRET_A = "sk-tenant-faculty-a-secret"
TENANT_SECRET_B = "sk-tenant-faculty-b-secret"
API_KEY_A = "sk-or-v1-real-key-for-faculty-a"
API_KEY_B = "sk-or-v1-real-key-for-faculty-b"


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _encrypt_key(api_key: str) -> str:
    return FERNET.encrypt(api_key.encode()).decode()


def _make_registry_file(tmp_path, tenants: dict | None = None) -> str:
    if tenants is None:
        tenants = {
            "faculty-a": {
                "name": "Faculty of Sciences",
                "api_secret_hash": f"sha256:{_hash_secret(TENANT_SECRET_A)}",
                "api_key_encrypted": _encrypt_key(API_KEY_A),
                "base_url": "https://openrouter.ai/api/v1",
            },
            "faculty-b": {
                "name": "Faculty of Engineering",
                "api_secret_hash": f"sha256:{_hash_secret(TENANT_SECRET_B)}",
                "api_key_encrypted": _encrypt_key(API_KEY_B),
            },
        }
    path = str(tmp_path / "tenants.json")
    with open(path, "w") as f:
        json.dump({"tenants": tenants}, f)
    return path


class TestTenantRegistryLoad:
    def test_load_valid_registry(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)

        assert len(reg) == 2
        assert set(reg.slugs) == {"faculty-a", "faculty-b"}

    def test_load_decrypts_api_keys(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)

        tenant_a = reg.get_tenant("faculty-a")
        assert tenant_a is not None
        assert tenant_a.api_key == API_KEY_A
        assert tenant_a.base_url == "https://openrouter.ai/api/v1"

        tenant_b = reg.get_tenant("faculty-b")
        assert tenant_b is not None
        assert tenant_b.api_key == API_KEY_B
        assert tenant_b.base_url is None

    def test_missing_file_returns_empty(self, tmp_path):
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(str(tmp_path / "nonexistent.json"))

        assert len(reg) == 0
        assert reg.slugs == []

    def test_missing_encryption_key_raises(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=None)

        with pytest.raises(ValueError, match="TENANT_ENCRYPTION_KEY must be set"):
            reg.load(path)

    def test_wrong_encryption_key_skips_tenant(self, tmp_path):
        path = _make_registry_file(tmp_path)
        wrong_key = Fernet.generate_key().decode()
        reg = TenantRegistry(encryption_key=wrong_key)
        reg.load(path)

        assert len(reg) == 0

    def test_reload_replaces_tenants(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)
        assert len(reg) == 2

        path2 = _make_registry_file(
            tmp_path,
            tenants={
                "faculty-c": {
                    "name": "Faculty C",
                    "api_secret_hash": f"sha256:{_hash_secret('secret-c')}",
                    "api_key_encrypted": _encrypt_key("key-c"),
                }
            },
        )
        reg.load(path2)
        assert len(reg) == 1
        assert reg.slugs == ["faculty-c"]

    def test_tenant_config_is_frozen(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)
        tenant = reg.get_tenant("faculty-a")
        with pytest.raises(AttributeError):
            tenant.api_key = "tampered"


class TestSecretVerification:
    @pytest.fixture()
    def registry(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)
        return reg

    def test_correct_secret_returns_slug(self, registry):
        assert registry.verify_secret(TENANT_SECRET_A) == "faculty-a"
        assert registry.verify_secret(TENANT_SECRET_B) == "faculty-b"

    def test_wrong_secret_returns_none(self, registry):
        assert registry.verify_secret("wrong-secret") is None

    def test_empty_secret_returns_none(self, registry):
        assert registry.verify_secret("") is None

    def test_empty_registry_returns_none(self):
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        assert reg.verify_secret(TENANT_SECRET_A) is None


class TestResolveOrg:
    @pytest.fixture()
    def registry(self, tmp_path):
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)
        return reg

    def test_tenant_match(self, registry, monkeypatch):
        monkeypatch.setenv("API_SECRET", "global-secret")
        assert resolve_org(TENANT_SECRET_A, registry) == "faculty-a"

    def test_global_secret_match(self, registry, monkeypatch):
        monkeypatch.setenv("API_SECRET", "global-secret")
        assert resolve_org("global-secret", registry) == "api"

    def test_no_match(self, registry, monkeypatch):
        monkeypatch.setenv("API_SECRET", "global-secret")
        assert resolve_org("bad-secret", registry) is None

    def test_no_registry_global_match(self, monkeypatch):
        monkeypatch.setenv("API_SECRET", "global-secret")
        assert resolve_org("global-secret", None) == "api"

    def test_no_registry_no_match(self, monkeypatch):
        monkeypatch.setenv("API_SECRET", "global-secret")
        assert resolve_org("bad-secret", None) is None

    def test_tenant_takes_priority_over_global(self, tmp_path, monkeypatch):
        monkeypatch.setenv("API_SECRET", TENANT_SECRET_A)
        path = _make_registry_file(tmp_path)
        reg = TenantRegistry(encryption_key=ENCRYPTION_KEY)
        reg.load(path)
        assert resolve_org(TENANT_SECRET_A, reg) == "faculty-a"
