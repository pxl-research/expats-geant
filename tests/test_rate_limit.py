"""Tests for m_shared/rate_limit.py — _key_by_user branching."""

from types import SimpleNamespace

from m_shared.rate_limit import _key_by_user


class TestKeyByUser:
    """All four branches of _key_by_user()."""

    def test_returns_user_id_when_claims_present(self):
        request = SimpleNamespace(
            state=SimpleNamespace(claims={"user_id": "alice"}),
            client=SimpleNamespace(host="1.2.3.4"),
        )
        assert _key_by_user(request) == "alice"

    def test_returns_anonymous_when_claims_lack_user_id(self):
        # Non-empty (truthy) claims dict without "user_id" → falls to .get default
        request = SimpleNamespace(
            state=SimpleNamespace(claims={"org": "test"}),
            client=SimpleNamespace(host="1.2.3.4"),
        )
        assert _key_by_user(request) == "anonymous"

    def test_returns_ip_when_no_claims(self):
        request = SimpleNamespace(
            state=SimpleNamespace(claims=None),
            client=SimpleNamespace(host="1.2.3.4"),
        )
        assert _key_by_user(request) == "1.2.3.4"

    def test_returns_anonymous_when_no_client(self):
        request = SimpleNamespace(
            state=SimpleNamespace(claims=None),
            client=None,
        )
        assert _key_by_user(request) == "anonymous"
