"""Tenant registry: load, verify, and decrypt tenant credentials."""

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TenantConfig:
    slug: str
    name: str
    api_key: str
    base_url: str | None


class TenantRegistry:
    """Registry of tenants loaded from an encrypted JSON config file.

    When no registry file is present the system operates in single-tenant mode.
    """

    def __init__(self, encryption_key: str | None = None):
        self._fernet: Fernet | None = None
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())
        self._tenants: dict[str, TenantConfig] = {}
        self._secret_hashes: dict[str, str] = {}

    def load(self, path: str) -> None:
        """Load tenants from a JSON file, decrypting API keys.

        Raises ValueError if the file exists but encryption is not configured.
        """
        if not os.path.isfile(path):
            logger.info("No tenant registry at %s — single-tenant mode", path)
            self._tenants.clear()
            self._secret_hashes.clear()
            return

        if self._fernet is None:
            raise ValueError(
                "TENANT_ENCRYPTION_KEY must be set when a tenant registry file is present"
            )

        with open(path) as f:
            data = json.load(f)

        tenants: dict[str, TenantConfig] = {}
        secret_hashes: dict[str, str] = {}

        for slug, entry in data.get("tenants", {}).items():
            try:
                api_key = self._fernet.decrypt(entry["api_key_encrypted"].encode()).decode()
            except (InvalidToken, KeyError) as exc:
                logger.error("Failed to decrypt API key for tenant %r: %s", slug, exc)
                continue

            tenants[slug] = TenantConfig(
                slug=slug,
                name=entry.get("name", slug),
                api_key=api_key,
                base_url=entry.get("base_url"),
            )
            raw_hash = entry.get("api_secret_hash", "")
            secret_hashes[slug] = raw_hash.removeprefix("sha256:")

        self._tenants = tenants
        self._secret_hashes = secret_hashes
        logger.info("Loaded %d tenant(s) from %s", len(tenants), path)

    def verify_secret(self, secret: str) -> str | None:
        """Return the tenant slug if *secret* matches a registered tenant, else None."""
        incoming_hash = hashlib.sha256(secret.encode()).hexdigest()
        for slug, stored_hash in self._secret_hashes.items():
            if hmac.compare_digest(incoming_hash, stored_hash):
                return slug
        return None

    def get_tenant(self, slug: str) -> TenantConfig | None:
        return self._tenants.get(slug)

    @property
    def slugs(self) -> list[str]:
        return list(self._tenants)

    def __len__(self) -> int:
        return len(self._tenants)


def resolve_org(
    api_secret: str,
    tenant_registry: TenantRegistry | None = None,
) -> str | None:
    """Resolve an API secret to an org identifier.

    Checks the tenant registry first, then falls back to the global API_SECRET.
    Returns the tenant slug, ``"api"`` for the global secret, or ``None`` on mismatch.
    """
    if tenant_registry:
        slug = tenant_registry.verify_secret(api_secret)
        if slug:
            return slug
    expected = os.getenv("API_SECRET", "")
    if expected and hmac.compare_digest(api_secret, expected):
        return "api"
    return None
