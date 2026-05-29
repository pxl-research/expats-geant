#!/usr/bin/env python3
"""
End-to-end spot-check for multi-tenant credential routing.

Covers:
  8.2  Tenant-scoped auth — obtain JWT with tenant secret, verify org claim
  8.3  Keycloak groups    — create user in group, verify groups claim in ID token
  8.4  Hot reload         — add tenant to registry, reload, verify immediate availability

Prerequisites:
  - Docker Compose stack running (Cue API on 8801, Shape API on 8802, Keycloak on 8080)
  - .env loaded (API_SECRET, KEYCLOAK_ADMIN_PASSWORD must be set)
  - TENANT_ENCRYPTION_KEY set in .env (generate with: python scripts/manage_tenants.py generate-key)
  - TENANT_REGISTRY_PATH=.secrets/tenants.json in .env
  - docker-compose.yml mounts .secrets/ into the API containers

Usage:
    python tests/scripts/e2e_tenant_routing_spot_check.py [--base-url http://localhost:8801]
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx
import jwt as pyjwt
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_BASE_URL = "http://localhost:8801"
KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_REALM = "expats"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = PROJECT_ROOT / ".secrets"
REGISTRY_FILE = SECRETS_DIR / "tenants.json"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SECTION_FMT = "\033[1;34m"
RESET = "\033[0m"

results: list[tuple[str, bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    line = f"  [{tag}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append((label, condition, detail))
    return condition


def section(title: str) -> None:
    print(f"\n{SECTION_FMT}{'=' * 60}{RESET}")
    print(f"{SECTION_FMT}{title}{RESET}")
    print(f"{SECTION_FMT}{'=' * 60}{RESET}")


def decode_jwt_claims(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False})


def _build_tenant_entry(slug: str, secret: str, encryption_key: str) -> dict:
    fernet = Fernet(encryption_key.encode())
    return {
        "name": f"Test {slug}",
        "api_secret_hash": f"sha256:{hashlib.sha256(secret.encode()).hexdigest()}",
        "api_key_encrypted": fernet.encrypt(f"fake-key-{slug}".encode()).decode(),
        "base_url": "https://openrouter.ai/api/v1",
    }


def _write_registry(tenants: dict) -> None:
    SECRETS_DIR.mkdir(exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump({"tenants": tenants}, f)


def _cleanup_registry() -> None:
    if REGISTRY_FILE.exists():
        REGISTRY_FILE.unlink()


def _reload_tenants(client: httpx.Client, api_secret: str) -> httpx.Response:
    r = client.post(
        "/admin/reload-tenants",
        headers={"Authorization": f"Bearer {api_secret}"},
    )
    if r.status_code != 200:
        check("Reload → 200", False, f"HTTP {r.status_code}: {r.text[:120]}")
    return r


# ────────────────────────────────────────────────────────────
# Preflight
# ────────────────────────────────────────────────────────────


def preflight(api_secret: str, encryption_key: str) -> list[str]:
    """Check prerequisites, return list of issues."""
    issues = []
    if not api_secret:
        issues.append("API_SECRET not set in .env")
    if not encryption_key:
        issues.append(
            "TENANT_ENCRYPTION_KEY not set in .env (generate with: python scripts/manage_tenants.py generate-key)"
        )
    registry_path = os.getenv("TENANT_REGISTRY_PATH", "")
    if not registry_path:
        issues.append("TENANT_REGISTRY_PATH not set in .env (set to .secrets/tenants.json)")
    return issues


# ────────────────────────────────────────────────────────────
# 8.2  Tenant-scoped auth
# ────────────────────────────────────────────────────────────


def test_tenant_auth(client: httpx.Client, api_secret: str, encryption_key: str) -> None:
    section("8.2  Tenant-scoped auth (JWT org claim)")

    tenant_secret = "sk-tenant-e2e-faculty-alpha"
    _write_registry(
        {"faculty-alpha": _build_tenant_entry("faculty-alpha", tenant_secret, encryption_key)}
    )

    r = _reload_tenants(client, api_secret)
    if not check("Reload tenants → 200", r.status_code == 200, r.text[:120]):
        return
    check("Loaded 1 tenant", r.json().get("tenants_loaded") == 1)

    r = client.post("/auth/token", json={"user_id": "tenant-user", "api_secret": tenant_secret})
    if not check("Tenant secret → 200", r.status_code == 200):
        return
    claims = decode_jwt_claims(r.json()["token"])
    check(
        "JWT org = faculty-alpha", claims.get("org") == "faculty-alpha", f"org={claims.get('org')}"
    )

    r = client.post("/auth/token", json={"user_id": "global-user", "api_secret": api_secret})
    check("Global secret still works → 200", r.status_code == 200)
    if r.status_code == 200:
        claims = decode_jwt_claims(r.json()["token"])
        check("Global JWT org = api", claims.get("org") == "api", f"org={claims.get('org')}")

    r = client.post("/auth/token", json={"user_id": "bad-user", "api_secret": "wrong"})
    check("Wrong secret → 401", r.status_code == 401)


# ────────────────────────────────────────────────────────────
# 8.3  Keycloak groups → tenant resolution
# ────────────────────────────────────────────────────────────


def _keycloak_admin_token() -> str | None:
    password = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "")
    if not password:
        return None
    try:
        r = httpx.post(
            f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": password,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except httpx.ConnectError:
        pass
    return None


def test_keycloak_groups() -> None:
    section("8.3  Keycloak groups → tenant resolution")

    admin_token = _keycloak_admin_token()
    if not admin_token:
        check(
            "Keycloak admin token",
            False,
            "KEYCLOAK_ADMIN_PASSWORD not set or Keycloak unreachable",
        )
        return
    check("Keycloak admin token obtained", True)

    headers = {"Authorization": f"Bearer {admin_token}"}
    realm_api = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"

    r = httpx.get(f"{realm_api}/groups", headers=headers, timeout=10)
    if not check("List groups → 200", r.status_code == 200):
        return
    groups = r.json()
    faculty_a = next((g for g in groups if g["name"] == "faculty-a"), None)
    check("Group 'faculty-a' exists", faculty_a is not None)
    if faculty_a is None:
        return

    r = httpx.get(
        f"{realm_api}/clients",
        headers=headers,
        params={"clientId": "cue-api"},
        timeout=10,
    )
    kc_client = None
    if r.status_code == 200 and r.json():
        kc_client = r.json()[0]
        r2 = httpx.get(
            f"{realm_api}/clients/{kc_client['id']}/protocol-mappers/models",
            headers=headers,
            timeout=10,
        )
        has_mapper = False
        if r2.status_code == 200:
            has_mapper = any(m.get("name") == "group-membership" for m in r2.json())
        check("Group-membership mapper on cue-api", has_mapper)

    test_email = "e2e-tenant-test@example.com"
    test_password = "E2eTenantTest123!"

    r = httpx.get(
        f"{realm_api}/users", headers=headers, params={"username": test_email}, timeout=10
    )
    user_id = None
    if r.status_code == 200 and r.json():
        user_id = r.json()[0]["id"]
        check("Test user exists", True, user_id[:12])
    else:
        r = httpx.post(
            f"{realm_api}/users",
            headers=headers,
            json={
                "username": test_email,
                "email": test_email,
                "enabled": True,
                "emailVerified": True,
                "credentials": [{"type": "password", "value": test_password, "temporary": False}],
            },
            timeout=10,
        )
        if check("Create test user → 201", r.status_code == 201):
            r2 = httpx.get(
                f"{realm_api}/users",
                headers=headers,
                params={"username": test_email},
                timeout=10,
            )
            if r2.status_code == 200 and r2.json():
                user_id = r2.json()[0]["id"]

    if not user_id:
        check("Test user ID obtained", False)
        return

    r = httpx.put(
        f"{realm_api}/users/{user_id}/groups/{faculty_a['id']}",
        headers=headers,
        timeout=10,
    )
    check("Assign user to faculty-a → 204", r.status_code == 204)

    r = httpx.get(f"{realm_api}/users/{user_id}/groups", headers=headers, timeout=10)
    if r.status_code == 200:
        user_groups = [g["name"] for g in r.json()]
        check("User is in faculty-a", "faculty-a" in user_groups, str(user_groups))

    if kc_client:
        r = httpx.get(
            f"{realm_api}/clients/{kc_client['id']}/evaluate-scopes/generate-example-id-token",
            headers=headers,
            params={"scope": "openid", "userId": user_id},
            timeout=10,
        )
        if r.status_code == 200:
            example_claims = r.json()
            groups_claim = example_claims.get("groups", [])
            check(
                "Example ID token has groups with faculty-a",
                any("faculty-a" in g for g in groups_claim),
                f"groups={groups_claim}",
            )
        else:
            check(
                "Example ID token endpoint",
                False,
                f"HTTP {r.status_code} — verify groups claim manually via browser login",
            )


# ────────────────────────────────────────────────────────────
# 8.4  Hot reload
# ────────────────────────────────────────────────────────────


def test_hot_reload(client: httpx.Client, api_secret: str, encryption_key: str) -> None:
    section("8.4  Hot reload — add tenant without restart")

    secret_alpha = "sk-tenant-alpha-reload"
    secret_beta = "sk-tenant-beta-reload"

    _write_registry({"alpha": _build_tenant_entry("alpha", secret_alpha, encryption_key)})
    r = _reload_tenants(client, api_secret)
    check("Initial reload → 1 tenant", r.json().get("tenants_loaded") == 1)

    r = client.post("/auth/token", json={"user_id": "a-user", "api_secret": secret_alpha})
    check("Alpha token → 200", r.status_code == 200)

    r = client.post("/auth/token", json={"user_id": "b-user", "api_secret": secret_beta})
    check("Beta before reload → 401", r.status_code == 401)

    _write_registry(
        {
            "alpha": _build_tenant_entry("alpha", secret_alpha, encryption_key),
            "beta": _build_tenant_entry("beta", secret_beta, encryption_key),
        }
    )

    r = _reload_tenants(client, api_secret)
    if r.status_code == 200:
        check("Reload after adding beta → 2 tenants", r.json().get("tenants_loaded") == 2)
    else:
        check("Reload after adding beta → 2 tenants", False, f"HTTP {r.status_code}")

    r = client.post("/auth/token", json={"user_id": "b-user", "api_secret": secret_beta})
    if check("Beta after reload → 200", r.status_code == 200):
        claims = decode_jwt_claims(r.json()["token"])
        check("Beta JWT org = beta", claims.get("org") == "beta", f"org={claims.get('org')}")

    r = client.post("/auth/token", json={"user_id": "a-user", "api_secret": secret_alpha})
    check("Alpha still works → 200", r.status_code == 200)


# ────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E tenant routing spot-check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    api_secret = os.getenv("API_SECRET", "")
    encryption_key = os.getenv("TENANT_ENCRYPTION_KEY", "")

    issues = preflight(api_secret, encryption_key)
    if issues:
        print("Preflight checks failed:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nSet these in .env and restart the API containers:")
        print("  docker compose up -d cue-api shape-api")
        sys.exit(1)

    client = httpx.Client(base_url=args.base_url, timeout=15)

    try:
        r = client.get("/health")
        if not check("API health check → 200", r.status_code == 200):
            print("\n  Start the stack:  docker compose up\n")
            sys.exit(1)
    except httpx.ConnectError:
        check("API health check → 200", False, "Connection refused")
        sys.exit(1)

    try:
        test_tenant_auth(client, api_secret, encryption_key)
        test_keycloak_groups()
        test_hot_reload(client, api_secret, encryption_key)
    finally:
        _cleanup_registry()

    section("Summary")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n  {passed} passed, {failed} failed, {passed + failed} total\n")

    if failed:
        print("  Failed checks:")
        for label, ok, detail in results:
            if not ok:
                print(f"    - {label}" + (f"  ({detail})" if detail else ""))
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
