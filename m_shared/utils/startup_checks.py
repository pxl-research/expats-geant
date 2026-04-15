"""Startup validation for security-sensitive configuration."""

import logging
import os
import sys

logger = logging.getLogger(__name__)

_KNOWN_PLACEHOLDERS = frozenset(
    {
        "change-me",
        "change-me-in-production",
        "admin",
        "change-this-to-a-secure-random-secret-in-production",
    }
)


def check_secrets() -> None:
    """Validate that placeholder secrets are not used in production.

    In production (ENVIRONMENT=production): logs critical and exits.
    In development: logs a warning.
    """
    is_production = os.getenv("ENVIRONMENT") == "production"

    problems: list[str] = []
    for var_name in ("JWT_SECRET", "OIDC_CLIENT_SECRET"):
        value = os.getenv(var_name, "")
        if value.lower() in _KNOWN_PLACEHOLDERS:
            problems.append(var_name)

    if not problems:
        return

    msg = (
        f"Placeholder value detected for: {', '.join(problems)}. "
        "Set real secrets before deploying."
    )

    if is_production:
        logger.critical(msg)
        sys.exit(1)
    else:
        logger.warning(msg)
