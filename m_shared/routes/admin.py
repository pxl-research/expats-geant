"""Shared admin endpoints (included by both Cue and Shape APIs)."""

import hmac
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status

from m_shared.llm.client import LLMClient
from m_shared.tenant import TenantRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])


@router.post("/admin/reload-tenants")
async def reload_tenants(request: Request):
    """Re-read the tenant registry from disk and rebuild the LLM client pool.

    Requires the global API_SECRET as a Bearer token.
    """
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    expected = os.getenv("API_SECRET", "")
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API secret",
        )

    registry_path = os.getenv("TENANT_REGISTRY_PATH", "")
    if not registry_path:
        return {"status": "ok", "tenants_loaded": 0, "message": "TENANT_REGISTRY_PATH not set"}

    registry: TenantRegistry | None = getattr(request.app.state, "tenant_registry", None)
    if registry is None:
        encryption_key = os.getenv("TENANT_ENCRYPTION_KEY", "")
        registry = TenantRegistry(encryption_key=encryption_key or None)
        request.app.state.tenant_registry = registry

    registry.load(registry_path)

    pool: dict[str, LLMClient] = getattr(request.app.state, "llm_client_pool", {}) or {}
    default_client = pool.get("default")

    stale_slugs = [k for k in pool if k not in ("default", "api") and k not in registry.slugs]
    for slug in stale_slugs:
        del pool[slug]

    for slug in registry.slugs:
        if slug not in pool:
            tenant = registry.get_tenant(slug)
            if tenant is None:
                continue
            try:
                pool[slug] = LLMClient(api_key=tenant.api_key, base_url=tenant.base_url)
                logger.info("Created LLM client for tenant '%s'", slug)
            except Exception as e:
                logger.warning("Failed to create LLM client for tenant '%s': %s", slug, e)
                if default_client:
                    pool[slug] = default_client

    request.app.state.llm_client_pool = pool
    logger.info("Tenant registry reloaded: %d tenant(s)", len(registry))
    return {"status": "ok", "tenants_loaded": len(registry)}
