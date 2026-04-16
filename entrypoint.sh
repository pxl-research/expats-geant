#!/bin/sh
set -e

# Ensure mounted volumes are owned by appuser (fixes stale root-owned volumes)
chown -R appuser:appuser /app/data /app/logs 2>/dev/null || true

# Drop to non-root and run the CMD
exec gosu appuser "$@"
