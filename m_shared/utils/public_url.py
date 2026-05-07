"""Derive public URLs from PUBLIC_HOST or explicit env vars."""

import os


def get_public_url(
    env_var: str, port: int, path: str = "", default: str | None = None
) -> str | None:
    """Return a browser-accessible URL, derived from env vars.

    Resolution order:
      1. Explicit env var (e.g. CUE_PUBLIC_URL)
      2. http://{PUBLIC_HOST}:{port}{path}
      3. default
    """
    value = os.getenv(env_var, "").strip()
    if value:
        return value
    host = os.getenv("PUBLIC_HOST", "").strip()
    if host:
        return f"http://{host}:{port}{path}"
    return default
