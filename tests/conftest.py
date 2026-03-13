"""Shared test fixtures."""

import pytest

from m_shared.rate_limit import reset_limiter


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Disable rate limiting in tests to avoid cross-test 429s."""
    reset_limiter()
