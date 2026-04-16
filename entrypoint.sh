#!/bin/sh
set -e

if [ "$(id -u)" = "0" ]; then
  # Running as root: fix volume ownership, then drop to appuser
  chown -R appuser:appuser /app/data /app/logs 2>/dev/null || true
  exec gosu appuser "$@"
else
  # Already non-root (e.g. docker run --user): run directly
  exec "$@"
fi
