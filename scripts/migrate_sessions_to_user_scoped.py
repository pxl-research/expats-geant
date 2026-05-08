#!/usr/bin/env python3
"""Migrate sessions from flat layout to user-scoped nested layout.

Before: data/sessions/{session_id}/metadata.json
After:  data/sessions/{user_hash}/{session_id}/metadata.json

This script is idempotent — already-migrated sessions are skipped.
Run it offline (with services stopped) before upgrading to v0.3.0+.

Usage:
    python scripts/migrate_sessions_to_user_scoped.py [sessions_dir]

Defaults to ./data/sessions if no argument is given.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path


def _hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def migrate(sessions_dir: str) -> None:
    base = Path(sessions_dir)
    if not base.exists():
        print(f"Sessions directory {base} does not exist, nothing to migrate.")
        return

    migrated = 0
    skipped = 0

    for session_dir in sorted(base.iterdir()):
        if not session_dir.is_dir():
            continue

        metadata_file = session_dir / "metadata.json"
        if not metadata_file.exists():
            continue

        # Skip if this looks like a user-hash directory (contains subdirs with metadata.json)
        subdirs_with_meta = [
            d for d in session_dir.iterdir() if d.is_dir() and (d / "metadata.json").exists()
        ]
        if subdirs_with_meta:
            skipped += 1
            continue

        try:
            data = json.loads(metadata_file.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            print(f"SKIP {session_dir.name}: cannot read metadata ({exc})")
            skipped += 1
            continue

        user_id = data.get("user_id")
        if not user_id:
            print(f"SKIP {session_dir.name}: no user_id in metadata")
            skipped += 1
            continue

        user_hash = _hash_user_id(user_id)
        dest_parent = base / user_hash
        dest = dest_parent / session_dir.name

        if dest.exists():
            print(f"SKIP {session_dir.name}: already exists at {dest}")
            skipped += 1
            continue

        dest_parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(session_dir), str(dest))
        print(f"MOVED {session_dir.name} -> {user_hash}/{session_dir.name}")
        migrated += 1

    print(f"\nDone: {migrated} migrated, {skipped} skipped.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "./data/sessions"
    migrate(path)
