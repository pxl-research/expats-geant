#!/usr/bin/env python3
"""CLI utility for managing tenant credentials.

Usage:
    python scripts/manage_tenants.py create \
        --slug faculty-a \
        --name "Faculty of Sciences" \
        --api-key sk-or-v1-abc123... \
        --encryption-key <TENANT_ENCRYPTION_KEY>

    python scripts/manage_tenants.py create \
        --slug faculty-a \
        --name "Faculty of Sciences" \
        --api-key sk-or-v1-abc123... \
        --base-url https://openrouter.ai/api/v1

    The encryption key can also be provided via the TENANT_ENCRYPTION_KEY
    environment variable.
"""

import argparse
import hashlib
import json
import os
import secrets
import sys

from cryptography.fernet import Fernet


def _generate_secret() -> str:
    return f"sk-tenant-{secrets.token_urlsafe(32)}"


def cmd_create(args: argparse.Namespace) -> None:
    encryption_key = args.encryption_key or os.getenv("TENANT_ENCRYPTION_KEY", "")
    if not encryption_key:
        print(
            "Error: --encryption-key or TENANT_ENCRYPTION_KEY env var is required", file=sys.stderr
        )
        sys.exit(1)

    fernet = Fernet(encryption_key.encode())
    api_secret = _generate_secret()
    secret_hash = hashlib.sha256(api_secret.encode()).hexdigest()
    api_key_encrypted = fernet.encrypt(args.api_key.encode()).decode()

    entry = {
        "name": args.name or args.slug,
        "api_secret_hash": f"sha256:{secret_hash}",
        "api_key_encrypted": api_key_encrypted,
    }
    if args.base_url:
        entry["base_url"] = args.base_url

    block = json.dumps({args.slug: entry}, indent=2)
    print(f'\nTenant config block (add to tenants.json under "tenants"):\n{block}')
    print(f"\nTenant API secret (give to tenant, shown once):\n  {api_secret}\n")


def cmd_generate_key(_args: argparse.Namespace) -> None:
    print(Fernet.generate_key().decode())


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage tenant credentials")
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser("create", help="Generate credentials for a new tenant")
    create.add_argument("--slug", required=True, help="Unique tenant identifier")
    create.add_argument("--name", help="Human-readable tenant name (defaults to slug)")
    create.add_argument("--api-key", required=True, help="LLM API key to encrypt")
    create.add_argument("--base-url", help="Optional LLM provider base URL")
    create.add_argument(
        "--encryption-key", help="Fernet encryption key (or set TENANT_ENCRYPTION_KEY)"
    )

    sub.add_parser("generate-key", help="Generate a new Fernet encryption key")

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)
    elif args.command == "generate-key":
        cmd_generate_key(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
