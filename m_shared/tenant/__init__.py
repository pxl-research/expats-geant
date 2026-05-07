"""Tenant registry for multi-tenant credential routing."""

from m_shared.tenant.registry import TenantConfig, TenantRegistry, resolve_org

__all__ = ["TenantConfig", "TenantRegistry", "resolve_org"]
